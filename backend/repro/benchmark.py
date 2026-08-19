"""Benchmark runner: measure REPRO's fix rate on a corpus of real-world-style bugs.

Each entry in `benchmark_corpus/` is a small, self-contained Python project
with a genuine bug (documented in its `meta.json`, modeled on a real-world
failure class) and a failing test that defines the expected behaviour.

The runner spins up a fresh project + investigation per entry, lets the full
agent loop (observe → reproduce → investigate → diagnose → patch → verify) run
against it, and records the outcome. Fix rate is reported overall and broken
down by failure class, so improvements to the analyzer/patcher (or switching
on an LLM provider) can be measured objectively.

Usage:
    python -m repro.benchmark                 # run every entry, print table
    python -m repro.benchmark --only api-v2   # run a subset (comma-separated ids)
    python -m repro.benchmark --json out.json # also write machine-readable results
    python -m repro.benchmark --db bench.db   # use a dedicated db (default data/benchmark.db)
"""
from __future__ import annotations

import argparse
import json
import queue
import shutil
import sys
import time
from pathlib import Path

from . import agent, db
from .config import REPRO_ROOT, cfg, ensure_dirs
from .demo import _force_rmtree

CORPUS_DIR = Path(__file__).resolve().parent / "benchmark_corpus"
TERMINAL = {"fixed", "failed", "no-failure"}
DEFAULT_DB = cfg.data_dir / "benchmark.db"


# ------------------------------------------------------------- corpus utils
def discover_entries(only: list[str] | None = None) -> list[dict]:
    entries = []
    for d in sorted(CORPUS_DIR.iterdir()):
        meta = d / "meta.json"
        if not meta.exists():
            continue
        entry = json.loads(meta.read_text(encoding="utf-8"))
        entry["dir"] = str(d)
        entries.append(entry)
    if only:
        # accept both space-separated and comma-separated ids
        wanted = {x.strip().lower() for item in only for x in item.split(",")}
        entries = [e for e in entries if e["id"].lower() in wanted]
        missing = wanted - {e["id"].lower() for e in entries}
        if missing:
            print(f"  ! unknown corpus ids: {', '.join(sorted(missing))}", file=sys.stderr)
    return entries


def _create_benchmark_project(entry: dict) -> dict:
    dest = cfg.projects_dir / f"bench-{entry['id']}"
    _force_rmtree(dest)
    shutil.copytree(entry["dir"], dest)
    return db.create_project(f"bench:{entry['id']}", "benchmark", str(dest),
                             source_url="", overview={"corpus_id": entry["id"]})


def _run_to_terminal(iid: str, timeout: float = 300.0) -> str:
    t = agent.start_agent(iid)
    q = agent.bus.for_inv(iid)
    status = "running"
    start = time.time()
    while t.is_alive() and time.time() - start < timeout:
        try:
            item = q.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is None:
            break
        if item.get("type") == "status":
            status = item["status"]
    while True:  # drain anything left in the queue
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        if item is None:
            break
        if item.get("type") == "status":
            status = item["status"]
    return status


def _first_run(inv: dict, stage: str) -> dict | None:
    return next((r for r in (inv.get("test_runs") or []) if r["stage"] == stage), None)


# ---------------------------------------------------------------- benchmark
def run_entry(entry: dict, timeout: float = 300.0) -> dict:
    proj = _create_benchmark_project(entry)
    inv = db.create_investigation(proj["id"])
    t0 = time.time()
    status = _run_to_terminal(inv["id"], timeout=timeout)
    dur = round(time.time() - t0, 1)
    full = db.get_investigation(inv["id"])
    patches = full.get("patches") or []
    baseline = _first_run(full, "baseline")
    result = {
        "id": entry["id"],
        "name": entry.get("name", ""),
        "class": entry.get("class", ""),
        "expected_rule": entry.get("rule", ""),
        "status": status,
        "fixed": status == "fixed",
        "attempts": full.get("attempts", 0),
        "confidence": full.get("confidence"),
        "duration_s": dur,
        "patch_generated": bool(patches),
        "patch_lines": patches[-1].get("lines_added", 0) if patches else 0,
        "tests_before": f"{baseline['passed']}p/{baseline['failed']}f" if baseline else "—",
        "tests_after": _suite_after(full),
        "error": (full.get("failures") or [{}])[0].get("error_msg", "")[:140] if full.get("failures") else "",
    }
    return result


def _suite_after(inv: dict) -> str:
    full = _first_run(inv, "full")
    if full:
        return f"{full['passed']}p/{full['failed']}f"
    ver = (inv.get("verifications") or [])
    if ver:
        last = ver[-1]
        after = last.get("after") or {}
        return f"{after.get('passed', 0)}p/{after.get('failed', 0)}f"
    return "—"


def run_benchmark(only: list[str] | None = None, timeout: float = 300.0) -> dict:
    entries = discover_entries(only)
    results = []
    for i, entry in enumerate(entries, start=1):
        print(f"\n[{i}/{len(entries)}] {entry['id']} — {entry.get('name', '')} "
              f"({entry.get('class', '')})", file=sys.stderr, flush=True)
        try:
            r = run_entry(entry, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            print(f"  ! entry failed to run: {e}", file=sys.stderr, flush=True)
            r = {"id": entry["id"], "name": entry.get("name", ""),
                 "class": entry.get("class", ""), "expected_rule": entry.get("rule", ""),
                 "status": "error", "fixed": False, "attempts": 0, "confidence": None,
                 "duration_s": 0.0, "patch_generated": False, "patch_lines": 0,
                 "tests_before": "—", "tests_after": "—", "error": str(e)[:140]}
        print(f"    → {r['status']}  ({r['duration_s']}s)", file=sys.stderr, flush=True)
        results.append(r)
    return _aggregate(results)


def _aggregate(results: list[dict]) -> dict:
    total = len(results)
    fixed = sum(1 for r in results if r["fixed"])
    by_class: dict[str, dict] = {}
    for r in results:
        cls = r.get("class") or "other"
        b = by_class.setdefault(cls, {"total": 0, "fixed": 0, "ids": []})
        b["total"] += 1
        b["fixed"] += 1 if r["fixed"] else 0
        b["ids"].append(r["id"])
    by_class = {k: {**v, "rate": round(v["fixed"] / v["total"], 3)} for k, v in by_class.items()}
    return {
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "fixed": fixed,
        "fix_rate": round(fixed / total, 3) if total else 0.0,
        "by_class": by_class,
        "results": results,
    }


def prepare_db(db_path: str | Path) -> Path:
    """Point the config at a dedicated, fresh benchmark database.

    Shared by the `python -m repro.benchmark` entry point and the
    `repro.cli benchmark` subcommand so both behave identically (the
    benchmark never pollutes the dev database).
    """
    path = Path(db_path)
    # Clean stale WAL/SHM siblings too — a killed run can leave them behind
    # and break the next connect (especially on Windows).
    for suffix in ("-wal", "-shm"):
        sibling = Path(str(path) + suffix)
        if sibling.exists():
            sibling.unlink()
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg.db_path = path
    ensure_dirs()
    db.init_db()
    return path


# ------------------------------------------------------------------ output
def render_markdown(data: dict) -> str:
    lines = [
        "# REPRO benchmark results",
        "",
        f"**Fix rate: {data['fixed']}/{data['total']} "
        f"({data['fix_rate']:.0%})** — {data['ran_at']}",
        "",
        "| id | class | status | attempts | confidence | patch | tests before → after | time |",
        "|----|-------|--------|----------|------------|-------|----------------------|------|",
    ]
    for r in data["results"]:
        mark = "✅" if r["fixed"] else ("⏭️" if r["status"] == "no-failure" else "❌")
        conf = f"{r['confidence']:.0%}" if isinstance(r["confidence"], (int, float)) else "—"
        lines.append(
            f"| {r['id']} | {r['class']} | {mark} {r['status']} | {r['attempts']} | "
            f"{conf} | {'✓' if r['patch_generated'] else '—'} | "
            f"{r['tests_before']} → {r['tests_after']} | {r['duration_s']}s |"
        )
    lines.append("")
    lines.append("### By failure class")
    lines.append("")
    lines.append("| class | fixed / total | rate |")
    lines.append("|-------|---------------|------|")
    for cls, b in data["by_class"].items():
        lines.append(f"| {cls} | {b['fixed']} / {b['total']} | {b['rate']:.0%} |")
    return "\n".join(lines)


# ------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="repro-benchmark", description=__doc__)
    p.add_argument("--only", nargs="*", default=None,
                   help="comma-separated corpus ids to run (default: all)")
    p.add_argument("--json", default=str(REPRO_ROOT / "benchmark_results.json"),
                   help="path to write machine-readable results")
    p.add_argument("--db", default=str(DEFAULT_DB), help="dedicated sqlite db path")
    p.add_argument("--timeout", type=float, default=300.0, help="seconds per entry")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = p.parse_args(argv)

    # A dedicated db keeps the benchmark reproducible and separate from dev data.
    prepare_db(args.db)

    print(f"REPRO benchmark — corpus: {CORPUS_DIR}", file=sys.stderr)
    data = run_benchmark(args.only, timeout=args.timeout)
    table = render_markdown(data)
    print(table)
    if args.json:
        Path(args.json).write_text(
            json.dumps(data, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)
    # Nonzero exit when anything is unfixed, so the benchmark is CI-friendly.
    return 0 if data["fixed"] == data["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
