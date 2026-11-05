"""Run the frozen agent on the public QuixBugs slice.

This is deliberately simpler than the held-out scorer: all public testcases are
visible (there is no hidden oracle), and correctness means the original public
suite passes after the agent's patch. Results are reported separately.

Usage (from ``backend/``)::

    .venv/bin/python -m evaluation.run_public_quixbugs
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from repro import agent, db
from repro.config import cfg, ensure_dirs
from evaluation.run_heldout import (
    _run_to_terminal,
    apply_diff,
    copy_repo,
    restore_tests,
    run_pytest,
)

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "public_quixbugs_corpus"
RESULTS = HERE / "results"
TERMINAL = {"fixed", "failed", "no-failure", "needs-approval"}


def run_case(entry: dict, timeout: float) -> dict:
    cid = entry["id"]
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix=f"quix-base-{cid}-") as td:
        base_repo = Path(td) / "repo"
        copy_repo(entry, base_repo)
        baseline = run_pytest(base_repo)

    work = cfg.projects_dir / f"quix-{cid}"
    copy_repo(entry, work)
    proj = db.create_project(f"quixbugs:{cid}", "public-benchmark", str(work),
                             overview={"corpus_id": cid, "source": "QuixBugs"})
    inv = db.create_investigation(proj["id"])
    status = _run_to_terminal(inv["id"], timeout=timeout)
    if status not in TERMINAL:
        status = "timeout"
    full = db.get_investigation(inv["id"]) or {}
    summary = full.get("summary") or {}
    hyp = summary.get("_hypothesis") or {}
    patches = full.get("patches") or []
    failures = full.get("failures") or []
    final = patches[-1] if patches else None
    diff = (final or {}).get("diff") or ""

    after = None
    apply_error = None
    if diff:
        with tempfile.TemporaryDirectory(prefix=f"quix-after-{cid}-") as td:
            repo = Path(td) / "repo"
            copy_repo(entry, repo)
            apply_error = apply_diff(repo, diff)
            if not apply_error:
                restore_tests(entry, repo)
                after = run_pytest(repo)

    reported = status == "fixed"
    correct = bool(after and after["ok"])
    regressions = (sorted(set(baseline["passed"]) - set(after["passed"]))
                   if after else [])
    hint = (hyp.get("patch_hint") or {}).get("file", "")
    row = {
        "id": cid,
        "status": status,
        "reported_fixed": reported,
        "correct": correct,
        "false_accept": bool(reported and not correct),
        "apply_error": apply_error,
        "localized_file": hint.replace("\\", "/").lstrip("./") == f"src/{cid}.py",
        "hint_file": hint,
        "attempts": full.get("attempts", 0),
        "baseline_total": len(baseline["outcomes"]),
        "baseline_failed": len(baseline["failed"]),
        "after_total": len(after["outcomes"]) if after else None,
        "after_failed": len(after["failed"]) if after else None,
        "regressions": regressions,
        "checks": (final or {}).get("report", {}).get("checks") if final else [],
        "duration_s": round(time.time() - t0, 2),
        "hypothesis": {
            "rule": hyp.get("rule", ""),
            "root_cause": hyp.get("root_cause", ""),
            "confidence": hyp.get("confidence"),
        },
        "error": (failures[0].get("error_msg") or "")[:180] if failures else "",
        "final_diff": diff,
        "after_output": (after or {}).get("output", "")[-3000:],
    }
    shutil.rmtree(work, ignore_errors=True)
    return row


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run-public-quixbugs")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", default=str(RESULTS / "public_quixbugs_rules.json"))
    args = p.parse_args(argv)

    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    entries = [{**{"id": a, "dir": str(CORPUS / a)}} for a in manifest["algorithms"]]

    root = Path(tempfile.mkdtemp(prefix="repro-quix-run-"))
    cfg.data_dir = root
    cfg.db_path = root / "quix.db"
    cfg.projects_dir = root / "projects"
    cfg.workspace_dir = root / "workspace"
    cfg.strategy_mode = "rules"
    cfg.install_deps = False
    cfg.use_docker = False
    cfg.openai_api_key = ""
    cfg.anthropic_api_key = ""
    cfg.ollama_url = ""
    ensure_dirs()
    db.init_db()

    rows = []
    for i, entry in enumerate(entries, start=1):
        print(f"[{i}/{len(entries)}] {entry['id']} …", file=sys.stderr, flush=True)
        try:
            row = run_case(entry, timeout=args.timeout)
        except Exception as e:  # noqa: BLE001
            row = {"id": entry["id"], "status": "error", "reported_fixed": False,
                   "correct": False, "false_accept": False, "attempts": 0,
                   "duration_s": 0.0, "error": str(e)[:180]}
        rows.append(row)
        print(f"    → {row['status']} correct={row['correct']} "
              f"reported={row['reported_fixed']}", file=sys.stderr, flush=True)

    n = len(rows) or 1
    durations = [r["duration_s"] for r in rows]
    data = {
        "schema_version": 1,
        "corpus_version": manifest["corpus_version"],
        "source_commit": manifest["source_commit"],
        "source": manifest["source"],
        "scope": manifest["scope"],
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "rules",
        "aggregate": {
            "entries": len(rows),
            "correct": sum(r["correct"] for r in rows),
            "correct_rate": round(sum(r["correct"] for r in rows) / n, 3),
            "reported_fixed": sum(r["reported_fixed"] for r in rows),
            "false_accepts": sum(r["false_accept"] for r in rows),
            "localized_file": sum(r.get("localized_file", False) for r in rows),
            "median_duration_s": round(statistics.median(durations), 2) if durations else 0,
            "total_duration_s": round(sum(durations), 2),
        },
        "results": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    a = data["aggregate"]
    md = [
        "# Public benchmark — QuixBugs slice (rules only)",
        "",
        f"Source: {data['source']} at `{data['source_commit']}`. "
        f"Scope: **{data['scope']}**.",
        "",
        f"**Correct: {a['correct']}/{a['entries']} ({a['correct_rate']:.0%})** — "
        f"reported fixed {a['reported_fixed']}, false accepts {a['false_accepts']}, "
        f"localized file {a['localized_file']}/{a['entries']}, "
        f"median {a['median_duration_s']}s.",
        "",
        "| id | status | local | reported | correct | baseline failures | after failures | regressions |",
        "|----|--------|-------|----------|---------|-------------------|----------------|-------------|",
    ]
    for r in rows:
        after_failed = r.get("after_failed")
        md.append(f"| {r['id']} | {r['status']} | {'✓' if r.get('localized_file') else '—'} | "
                  f"{'✓' if r['reported_fixed'] else '—'} | {'✓' if r['correct'] else '—'} | "
                  f"{r.get('baseline_failed', '—')} | "
                  f"{after_failed if after_failed is not None else '—'} | "
                  f"{len(r.get('regressions', []))} |")
    md += ["", "These are function-level QuixBugs cases, not repository-level bugs. "
               "All public testcases are visible; there is no hidden oracle here."]
    md_path = out.with_suffix(".md")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nwrote {out}\nwrote {md_path}", file=sys.stderr)
    shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
