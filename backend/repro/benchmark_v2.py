"""REPRO benchmark v2 — a serious, honest measure of general debugging ability.

The original ``benchmark.py`` measures one number: fix rate on 9 demo repos.
This module measures a richer set of capabilities on a *separate*, larger
corpus (``benchmark_corpus_v2/``) whose entries deliberately cover failure
classes the deterministic rule engine cannot handle, so the results honestly
include failures. It exists to compare REPRO versions against each other,
not to flatter the current one.

Metrics measured per entry:

  * reproduction success        — did REPRO reproduce the failure?
  * diagnosis accuracy          — hypothesis vs. ground-truth root cause
  * root-cause localization     — did REPRO point at the right file/line?
  * patch generation rate       — was a patch produced at all?
  * patch correctness           — did the verified patch actually fix it?
  * regression-free fix rate    — fix with no previously-passing test broken
  * attempts                    — state-machine iterations consumed
  * execution time
  * token / API cost (LLM mode)
  * false diagnosis rate        — confident hypothesis that was wrong

Results are reported separately for the three strategy modes:
``rules`` (deterministic engine only), ``llm`` (LLM only) and
``hybrid`` (rules first, escalate to LLM).

Every run is written as versioned JSON (schema_version, corpus_version,
mode, repro_version) so any future REPRO can be compared against it with
``compare()``. A benchmark that honestly reports 63/100 is more useful than
one tuned to report 100/100 — this module does not cherry-pick.

Usage::

    python -m repro.benchmark_v2 --mode rules                 # one mode
    python -m repro.benchmark_v2 --mode all                   # all three
    python -m repro.benchmark_v2 --mode hybrid --json out.json
    python -m repro.benchmark_v2 --compare prev.json cur.json
"""
from __future__ import annotations

import argparse
import json
import queue
import re
import shutil
import sys
import time
from pathlib import Path

from . import agent, ai as ai_mod, db
from .config import REPRO_ROOT, cfg, ensure_dirs, strategy_ladder
from .demo import _force_rmtree

CORPUS_DIR = Path(__file__).resolve().parent / "benchmark_corpus_v2"
DEFAULT_DB = cfg.data_dir / "benchmark_v2.db"

SCHEMA_VERSION = 2


def _corpus_version() -> str:
    """Read the corpus version from its manifest (single source of truth)."""
    manifest = CORPUS_DIR / "manifest.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("corpus_version", "unknown")
    except Exception:  # noqa: BLE001
        return "unknown"


CORPUS_VERSION = _corpus_version()

try:
    from importlib.metadata import version as _pkg_version
    REPRO_VERSION = _pkg_version("repro")
except Exception:  # noqa: BLE001 — not installed as a package
    REPRO_VERSION = "dev"


# ------------------------------------------------------------- text matching
_WORD = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def text_similarity(a: str, b: str) -> float:
    """Token-overlap similarity in [0, 1] — used to compare the agent's
    root-cause hypothesis with the ground-truth root cause."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return max(inter / len(ta), inter / len(tb))


# ------------------------------------------------------------------ corpus
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
        wanted = {x.strip().lower() for item in only for x in item.split(",")}
        entries = [e for e in entries if e["id"].lower() in wanted]
        missing = wanted - {e["id"].lower() for e in entries}
        if missing:
            print(f"  ! unknown corpus ids: {', '.join(sorted(missing))}", file=sys.stderr)
    return entries


def _create_project(entry: dict) -> dict:
    dest = cfg.projects_dir / f"benchv2-{entry['id']}"
    _force_rmtree(dest)
    shutil.copytree(entry["dir"], dest)
    return db.create_project(f"benchv2:{entry['id']}", "benchmark_v2", str(dest),
                             source_url="", overview={"corpus_id": entry["id"]})


def _run_to_terminal(iid: str, timeout: float) -> str:
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
    while True:  # drain
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        if item is None:
            break
        if item.get("type") == "status":
            status = item["status"]
    return status


# ------------------------------------------------------------ per-entry run
def _first_run(inv: dict, stage: str) -> dict | None:
    return next((r for r in (inv.get("test_runs") or []) if r["stage"] == stage), None)


def _norm_path(p: str | None) -> str:
    return (p or "").replace("\\", "/").lstrip("./")


def run_entry(entry: dict, timeout: float = 300.0) -> dict:
    ai_mod.reset_usage()
    proj = _create_project(entry)
    inv = db.create_investigation(proj["id"])
    t0 = time.time()
    status = _run_to_terminal(inv["id"], timeout=timeout)
    dur = round(time.time() - t0, 2)
    full = db.get_investigation(inv["id"])
    summary = full.get("summary") or {}
    hyp = summary.get("_hypothesis") or {}
    patches = full.get("patches") or []
    failures = full.get("failures") or []
    baseline = _first_run(full, "baseline")
    suite_after = _suite_after(full)
    last_patch = patches[-1] if patches else {}

    # ---- metric 1: reproduction
    reproduced = status != "no-failure" and bool(failures)

    # ---- metric 2: diagnosis accuracy. A "fallback" hypothesis means the
    # agent explicitly said it had NO deterministic rule match — that must
    # not count as a correct diagnosis, so fallback is excluded from
    # rule_match and diagnosis falls back to pure text similarity.
    gt = entry.get("ground_truth") or ""
    hyp_text = f"{hyp.get('root_cause', '')} {hyp.get('explanation', '')}"
    sim = text_similarity(gt, hyp_text) if hyp_text else 0.0
    rule_match = (bool(hyp.get("rule"))
                  and hyp.get("rule") != "fallback"
                  and hyp.get("rule") == entry.get("rule"))
    diagnosis = round(max(sim, 1.0 if rule_match else 0.0), 3)

    # ---- metric 3: root-cause localization. Judged on the hypothesis's OWN
    # claim (patch_hint.file) — the raw traceback file is reproduction, not
    # localization, and would trivially pass for every entry.
    expected_file = _norm_path(entry.get("root_cause_file"))
    hint = hyp.get("patch_hint") or {}
    hint_file = _norm_path(hint.get("file")) if hint else ""
    localized = bool(expected_file) and bool(hint_file) and hint_file == expected_file

    # ---- metrics 4-6: patch generation / correctness / regression-free.
    # regression_free parses the real failed count from the full suite run
    # (the display string "2p/0f" contains the letter 'f', so counting
    # characters would make the metric always false).
    patch_generated = bool(patches)
    patch_correct = status == "fixed"
    full_run = _first_run(full, "full")
    if patch_correct and full_run is not None:
        regression_free = full_run["failed"] == 0
    elif patch_correct and (inv.get("verifications") or []):
        after = (inv["verifications"][-1].get("after") or {})
        regression_free = int(after.get("failed", 1)) == 0
    else:
        regression_free = False

    # ---- metric 10: false diagnosis (confident hypothesis that was wrong)
    false_diagnosis = bool(hyp.get("rule") and hyp.get("rule") != "fallback") and not patch_correct

    usage = ai_mod.usage_stats()
    return {
        "id": entry["id"],
        "name": entry.get("name", ""),
        "category": entry.get("category", "other"),
        "difficulty": entry.get("difficulty", "medium"),
        "status": status,
        "reproduced": reproduced,
        "diagnosis_accuracy": diagnosis,
        "diagnosis_rule": hyp.get("rule", ""),
        "expected_rule": entry.get("rule", ""),
        "localized": localized,
        "patch_generated": patch_generated,
        "patch_correct": patch_correct,
        "regression_free": regression_free,
        "false_diagnosis": false_diagnosis,
        "attempts": full.get("attempts", 0),
        "confidence": full.get("confidence"),
        "duration_s": dur,
        "tests_before": f"{baseline['passed']}p/{baseline['failed']}f" if baseline else "—",
        "tests_after": suite_after,
        "llm_calls": usage["calls"],
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "cost_usd": round(usage["cost_usd"], 6),
        "error": (failures[0].get("error_msg") or "")[:140] if failures else "",
    }


def _suite_after(inv: dict) -> str:
    full = _first_run(inv, "full")
    if full:
        return f"{full['passed']}p/{full['failed']}f"
    ver = inv.get("verifications") or []
    if ver:
        after = (ver[-1].get("after") or {})
        return f"{after.get('passed', 0)}p/{after.get('failed', 0)}f"
    return "—"


# --------------------------------------------------------------- aggregation
def _agg(rows: list[dict]) -> dict:
    n = len(rows) or 1
    fixed = sum(1 for r in rows if r["patch_correct"])
    return {
        "entries": n,
        "reproduction_rate": round(sum(r["reproduced"] for r in rows) / n, 3),
        "diagnosis_accuracy": round(sum(r["diagnosis_accuracy"] for r in rows) / n, 3),
        "localization_rate": round(sum(r["localized"] for r in rows) / n, 3),
        "patch_generation_rate": round(sum(r["patch_generated"] for r in rows) / n, 3),
        "patch_correctness": round(fixed / n, 3),
        "regression_free_fix_rate": round(sum(r["regression_free"] for r in rows) / n, 3),
        "false_diagnosis_rate": round(sum(r["false_diagnosis"] for r in rows) / n, 3),
        "avg_attempts": round(sum(r["attempts"] for r in rows) / n, 2),
        "avg_duration_s": round(sum(r["duration_s"] for r in rows) / n, 2),
        "total_tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows),
        "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
        "fixed_ids": [r["id"] for r in rows if r["patch_correct"]],
        "failed_ids": [r["id"] for r in rows if not r["patch_correct"]],
    }


def run_mode(mode: str, only: list[str] | None = None, timeout: float = 300.0) -> dict:
    entries = discover_entries(only)
    prev_mode = cfg.strategy_mode
    cfg.strategy_mode = mode
    rows = []
    print(f"\n=== mode: {mode} (ladder: {' → '.join(strategy_ladder(mode))}) ===",
          file=sys.stderr, flush=True)
    for i, entry in enumerate(entries, start=1):
        print(f"[{i}/{len(entries)}] {entry['id']} — {entry.get('name', '')} "
              f"[{entry.get('category')}/{entry.get('difficulty')}]",
              file=sys.stderr, flush=True)
        try:
            r = run_entry(entry, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            print(f"  ! entry crashed: {e}", file=sys.stderr, flush=True)
            r = {"id": entry["id"], "name": entry.get("name", ""),
                 "category": entry.get("category", "other"),
                 "difficulty": entry.get("difficulty", "medium"),
                 "status": "error", "reproduced": False, "diagnosis_accuracy": 0.0,
                 "diagnosis_rule": "", "expected_rule": entry.get("rule", ""),
                 "localized": False, "patch_generated": False, "patch_correct": False,
                 "regression_free": False, "false_diagnosis": False, "attempts": 0,
                 "confidence": None, "duration_s": 0.0, "tests_before": "—",
                 "tests_after": "—", "llm_calls": 0, "prompt_tokens": 0,
                 "completion_tokens": 0, "cost_usd": 0.0, "error": str(e)[:140]}
        print(f"    → {r['status']}  diagnosis={r['diagnosis_accuracy']:.2f} "
              f"localized={'Y' if r['localized'] else 'N'}  ({r['duration_s']}s)",
              file=sys.stderr, flush=True)
        rows.append(r)
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    try:
        return {
            "mode": mode,
            "provider": ai_mod.provider_label(),
            "aggregate": _agg(rows),
            "by_category": {c: _agg(v) for c, v in sorted(by_cat.items())},
            "results": rows,
        }
    finally:
        cfg.strategy_mode = prev_mode


# ------------------------------------------------------------------ compare
def compare(prev_path: str | Path, cur_path: str | Path) -> str:
    """Diff two versioned result files so future REPRO versions can be
    compared against this one."""
    prev = json.loads(Path(prev_path).read_text(encoding="utf-8"))
    cur = json.loads(Path(cur_path).read_text(encoding="utf-8"))
    prev_by_mode = {m["mode"]: m for m in prev.get("modes", [prev])}
    cur_by_mode = {m["mode"]: m for m in cur.get("modes", [cur])}
    lines = ["# REPRO benchmark v2 — comparison",
             f"\nprev: {prev_path}  (schema {prev.get('schema_version')}, "
             f"repro {prev.get('repro_version')}, corpus {prev.get('corpus_version')})",
             f"cur:  {cur_path}  (schema {cur.get('schema_version')}, "
             f"repro {cur.get('repro_version')}, corpus {cur.get('corpus_version')})",
             "",
             "| mode | reproduction | diagnosis | localization | patch gen | patch correctness | regression-free | false diagnosis |",
             "|------|--------------|-----------|--------------|-----------|-------------------|-----------------|-----------------|"]
    for mode in sorted(set(prev_by_mode) | set(cur_by_mode)):
        a = (prev_by_mode.get(mode) or {}).get("aggregate") or {}
        b = (cur_by_mode.get(mode) or {}).get("aggregate") or {}
        def cell(k: str, sgn: bool = True) -> str:
            if not a and not b:
                return "—"
            if k not in a and k not in b:
                return "—"
            va, vb = a.get(k), b.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and sgn:
                d = vb - va
                return f"{va:.2f} → {vb:.2f} ({'+' if d >= 0 else ''}{d:.2f})"
            return f"{va} → {vb}"
        lines.append(
            f"| {mode} | {cell('reproduction_rate')} | {cell('diagnosis_accuracy')} | "
            f"{cell('localization_rate')} | {cell('patch_generation_rate')} | "
            f"{cell('patch_correctness')} | {cell('regression_free_fix_rate')} | "
            f"{cell('false_diagnosis_rate')} |")
    return "\n".join(lines)


# ------------------------------------------------------------------ output
def render_markdown(data: dict) -> str:
    modes = data.get("modes") or [data]
    lines = [
        "# REPRO benchmark v2 — general debugging ability",
        "",
        f"schema `{data.get('schema_version')}` · corpus `{data.get('corpus_version')}` · "
        f"repro `{data.get('repro_version')}` · ran {data.get('ran_at')}",
        "",
    ]
    for m in modes:
        agg = m["aggregate"]
        lines += [
            f"## Mode: {m['mode']} (provider: {m.get('provider')})",
            "",
            f"**patch correctness: {agg['patch_correctness']:.0%}** "
            f"({len(agg['fixed_ids'])}/{agg['entries']}) — "
            f"reproduction {agg['reproduction_rate']:.0%} · diagnosis "
            f"{agg['diagnosis_accuracy']:.2f} · localization {agg['localization_rate']:.0%} · "
            f"patch gen {agg['patch_generation_rate']:.0%} · regression-free "
            f"{agg['regression_free_fix_rate']:.0%} · false diagnosis "
            f"{agg['false_diagnosis_rate']:.0%}",
            f"avg attempts {agg['avg_attempts']} · avg {agg['avg_duration_s']}s · "
            f"tokens {agg['total_tokens']} · cost ${agg['total_cost_usd']}",
            "",
            "| id | category | difficulty | status | diag | local | patch | before → after | attempts | time | cost |",
            "|----|----------|-----------|--------|------|-------|-------|----------------|----------|------|------|",
        ]
        for r in m["results"]:
            mark = "✅" if r["patch_correct"] else ("⏭️" if r["status"] == "no-failure" else "❌")
            lines.append(
                f"| {r['id']} | {r['category']} | {r['difficulty']} | {mark} {r['status']} | "
                f"{r['diagnosis_accuracy']:.2f} | {'✓' if r['localized'] else '—'} | "
                f"{'✓' if r['patch_generated'] else '—'} | {r['tests_before']} → "
                f"{r['tests_after']} | {r['attempts']} | {r['duration_s']}s | "
                f"${r['cost_usd']} |")
        lines.append("")
        if agg["failed_ids"]:
            lines += ["### Failures (honest)", ""]
            for r in m["results"]:
                if not r["patch_correct"]:
                    lines.append(f"- `{r['id']}` [{r['category']}] {r['status']} — "
                                 f"diag {r['diagnosis_accuracy']:.2f}, "
                                 f"localized {'✓' if r['localized'] else '—'}, "
                                 f"patch {'✓' if r['patch_generated'] else '—'}")
            lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="repro-benchmark-v2", description=__doc__)
    p.add_argument("--mode", default="rules", choices=["rules", "llm", "hybrid", "all"],
                   help="strategy mode(s) to run (default: rules)")
    p.add_argument("--only", nargs="*", default=None, help="corpus ids to run")
    p.add_argument("--json", default=str(REPRO_ROOT / "benchmark_v2_results.json"),
                   help="path to write versioned JSON results")
    p.add_argument("--db", default=str(DEFAULT_DB), help="dedicated sqlite db path")
    p.add_argument("--timeout", type=float, default=300.0, help="seconds per entry")
    p.add_argument("--compare", nargs=2, metavar=("PREV", "CUR"),
                   help="diff two versioned result files and exit")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = p.parse_args(argv)
    if args.compare:
        print(compare(*args.compare))
        return 0

    prepare_db(args.db)
    modes = ["rules", "llm", "hybrid"] if args.mode == "all" else [args.mode]
    mode_results = []
    for mode in modes:
        mode_results.append(run_mode(mode, only=args.only, timeout=args.timeout))
    data = {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "repro_version": REPRO_VERSION,
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "corpus_dir": str(CORPUS_DIR),
        "modes": mode_results,
    }
    print(render_markdown(data))
    if args.json:
        Path(args.json).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)
    best = max((m["aggregate"]["patch_correctness"] for m in mode_results), default=0.0)
    # Nonzero exit unless every entry was fixed in the best mode — honest CI.
    return 0 if best == 1.0 else 1


def prepare_db(db_path: str | Path) -> Path:
    path = Path(db_path)
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


if __name__ == "__main__":
    sys.exit(main())
