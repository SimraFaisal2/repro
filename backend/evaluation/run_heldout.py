"""Run the frozen agent on the held-out corpus and score it independently.

The agent's own report is never treated as ground truth. For every case we:

  * run the frozen rules-only agent on a copy of the buggy repo;
  * take the final stored patch (and every candidate patch) and apply it to a
    fresh copy;
  * restore the original visible tests (so a patch cannot weaken them);
  * run the visible suite and the hidden oracle suite separately;
  * score correctness as visible-pass AND oracle-pass, with no regressions.

Usage (from ``backend/``)::

    REPRO_STRATEGY_MODE=rules .venv/bin/python -m evaluation.run_heldout
    .venv/bin/python -m evaluation.run_heldout --only adjacent-pairs --keep
    .venv/bin/python -m evaluation.run_heldout --labels evaluation/results/labels.json

The run uses a disposable data directory; it does not touch ``data/repro.db``
or any project workspace used by the dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from repro import agent, db, validation
from repro.config import cfg, ensure_dirs

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
CORPUS = BACKEND / "repro" / "benchmark_corpus_heldout"
RESULTS = HERE / "results"
TERMINAL = {"fixed", "failed", "no-failure", "needs-approval"}

_OUTCOME_RE = re.compile(r"^(PASSED|FAILED|ERROR)\s+(\S+)", re.M)
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _norm(path: str | None) -> str:
    return (path or "").replace("\\", "/").lstrip("./")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pytest_env(repo: Path) -> dict:
    return {
        "PYTHONPATH": str(repo),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def run_pytest(repo: Path, target: str | None = None, timeout: int = 120) -> dict:
    args = [sys.executable, "-m", "pytest", "-q", "-rfE", "-rA",
            "-p", "no:cacheprovider", "--no-header", "--disable-warnings",
            "--tb=short"]
    if target:
        args.append(target)
    t0 = time.time()
    try:
        proc = subprocess.run(args, cwd=str(repo), env=_pytest_env(repo),
                              capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        code = proc.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\n" + (e.stderr or "")
        code = -9
    out = out[-40_000:]
    outcomes = {test: state for state, test in _OUTCOME_RE.findall(out)}
    return {
        "returncode": code,
        "ok": code == 0,
        "timed_out": code == -9,
        "duration_s": round(time.time() - t0, 2),
        "outcomes": outcomes,
        "passed": sorted(t for t, s in outcomes.items() if s == "PASSED"),
        "failed": sorted(t for t, s in outcomes.items() if s in ("FAILED", "ERROR")),
        "output": out,
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, timeout=60)


def _init_git(repo: Path) -> None:
    if (repo / ".git").exists():
        shutil.rmtree(repo / ".git", ignore_errors=True)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=REPRO", "-c", "user.email=repro@local",
         "commit", "-q", "-m", "baseline")


def apply_diff(repo: Path, diff: str) -> str | None:
    """Apply a unified diff to a clean repo. Return an error string or None."""
    if not diff.strip():
        return "empty patch"
    _init_git(repo)
    p = repo / "_agent.patch"
    p.write_text(diff, encoding="utf-8")
    check = _git(repo, "apply", "--check", "--whitespace=nowarn", p.name)
    if check.returncode != 0:
        p.unlink(missing_ok=True)
        return f"git apply --check failed: {check.stderr.strip()[:500]}"
    apply = _git(repo, "apply", "--whitespace=nowarn", p.name)
    p.unlink(missing_ok=True)
    if apply.returncode != 0:
        return f"git apply failed: {apply.stderr.strip()[:500]}"
    return None


def copy_repo(entry: dict, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(Path(entry["dir"]) / "repo", dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))


def restore_tests(entry: dict, repo: Path) -> None:
    """Put the original visible tests back after applying an agent patch."""
    src = Path(entry["dir"]) / "repo" / "tests"
    dst = repo / "tests"
    if dst.exists():
        shutil.rmtree(dst)
    if src.exists():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def run_candidate(entry: dict, diff: str) -> dict:
    """Independently evaluate one diff on a clean copy of the buggy repo."""
    if not diff.strip():
        return {"applied": False, "apply_error": "empty patch", "correct": False,
                "visible_ok": False, "oracle_ok": False, "regressions": [],
                "touched_tests": [], "missing_tests": [], "visible": None, "oracle": None}
    with tempfile.TemporaryDirectory(prefix=f"heldout-{entry['id']}-") as td:
        repo = Path(td) / "repo"
        copy_repo(entry, repo)
        err = apply_diff(repo, diff)
        if err:
            return {"applied": False, "apply_error": err, "correct": False,
                    "visible_ok": False, "oracle_ok": False, "regressions": [],
                    "touched_tests": validation.diff_files(diff),
                    "missing_tests": [], "visible": None, "oracle": None}
        touched = [f for f in validation.diff_files(diff) if validation.is_test_file(f)]
        restore_tests(entry, repo)
        visible = run_pytest(repo)
        # The oracle file is intentionally copied only after the visible run.
        oracle_path = repo / "tests" / "test_oracle.py"
        oracle_path.write_text((Path(entry["dir"]) / "oracle" / "test_oracle.py")
                               .read_text(encoding="utf-8"), encoding="utf-8")
        oracle = run_pytest(repo, "tests/test_oracle.py")
        return {
            "applied": True,
            "apply_error": None,
            "visible_ok": visible["ok"],
            "oracle_ok": bool(oracle and oracle["ok"]),
            "correct": bool(visible["ok"] and oracle and oracle["ok"]),
            "regressions": [],
            "touched_tests": touched,
            "missing_tests": [],
            "visible": visible,
            "oracle": oracle,
        }


def _baseline(entry: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"heldout-base-{entry['id']}-") as td:
        repo = Path(td) / "repo"
        copy_repo(entry, repo)
        res = run_pytest(repo)
    return res


# ---------------------------------------------------------------- diff overlap
def _new_side_lines(diff: str) -> set[tuple[str, int]]:
    """Set of (file, new-side line) touched by a unified diff."""
    out: set[tuple[str, int]] = set()
    file = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            file = _norm(line[6:].strip())
        m = _HUNK_RE.match(line)
        if m and file:
            start = int(m.group(1))
            length = int(m.group(2) or 1)
            for n in range(start, start + max(length, 1)):
                out.add((file, n))
    return out


def diff_overlap(predicted: str, truth: str) -> dict:
    pf, tf = set(map(_norm, validation.diff_files(predicted))), set(map(_norm, validation.diff_files(truth)))
    pl, tl = _new_side_lines(predicted), _new_side_lines(truth)
    pa, pr = validation.diff_lines(predicted)
    ta, tr = validation.diff_lines(truth)

    def norm(lines: list[str]) -> list[str]:
        return [re.sub(r"\s+", "", x) for x in lines if x.strip()]

    pt, tt = set(norm(pa + pr)), set(norm(ta + tr))
    return {
        "file_match": bool(tf) and pf == tf,
        "file_jaccard": round(len(pf & tf) / len(pf | tf), 3) if (pf | tf) else 0.0,
        "line_iou": round(len(pl & tl) / len(pl | tl), 3) if (pl | tl) else 0.0,
        "token_jaccard": round(len(pt & tt) / len(pt | tt), 3) if (pt | tt) else 0.0,
    }


# ------------------------------------------------------------------ agent run
def _run_to_terminal(iid: str, timeout: float) -> str:
    thread = agent.start_agent(iid)
    q = agent.bus.for_inv(iid)
    status = "running"
    start = time.time()
    while time.time() - start < timeout:
        try:
            item = q.get(timeout=0.5)
        except Exception:
            continue
        if item is None:
            break
        if item.get("type") == "status":
            status = item["status"]
            if status in TERMINAL:
                break
    while True:
        try:
            item = q.get_nowait()
        except Exception:
            break
        if item is None:
            break
        if item.get("type") == "status":
            status = item["status"]
    # The status event is emitted before _finish() writes the final summary.
    # Join the worker so the disposable DB is never removed under it.
    thread.join(timeout=15)
    if status not in TERMINAL:
        inv = db.get_investigation(iid) or {}
        status = inv.get("status", status)
    return status


def run_case(entry: dict, timeout: float, keep: bool = False) -> dict:
    cid = entry["id"]
    t0 = time.time()
    baseline = _baseline(entry)
    baseline_passed = set(baseline["passed"])
    baseline_failed = set(baseline["failed"])

    work = cfg.projects_dir / f"heldout-{cid}"
    copy_repo(entry, work)
    proj = db.create_project(f"heldout:{cid}", "heldout", str(work),
                             overview={"corpus_id": cid, "category": entry.get("category")})
    inv = db.create_investigation(proj["id"])
    status = _run_to_terminal(inv["id"], timeout=timeout)
    duration = round(time.time() - t0, 2)
    full = db.get_investigation(inv["id"]) or {}
    summary = full.get("summary") or {}
    hyp = summary.get("_hypothesis") or {}
    patches = full.get("patches") or []
    failures = full.get("failures") or []

    # Evaluate every stored candidate independently. This is what makes
    # false rejects visible: the agent may have rejected a correct patch.
    candidates = []
    seen = set()
    for p in patches:
        diff = p.get("diff") or ""
        if not diff or diff in seen:
            continue
        seen.add(diff)
        res = run_candidate(entry, diff)
        candidates.append({
            "status": p.get("status", ""),
            "risk": p.get("risk", ""),
            "checks": (p.get("report") or {}).get("checks") or [],
            "correct": res["correct"],
            "visible_ok": res["visible_ok"],
            "oracle_ok": res["oracle_ok"],
            "apply_error": res["apply_error"],
            "touched_tests": res["touched_tests"],
            "visible": res["visible"],
            "oracle": res["oracle"],
            "diff": diff,
        })

    final_patch = patches[-1] if patches else None
    final_diff = (final_patch or {}).get("diff") or ""
    final = next((c for c in candidates if c["diff"] == final_diff), None)
    if final is None and final_diff:
        res = run_candidate(entry, final_diff)
        final = {"status": (final_patch or {}).get("status", ""), "risk": "",
                 "checks": [], "correct": res["correct"],
                 "visible_ok": res["visible_ok"], "oracle_ok": res["oracle_ok"],
                 "apply_error": res["apply_error"], "touched_tests": res["touched_tests"],
                 "visible": res["visible"], "oracle": res["oracle"], "diff": final_diff}
        candidates.append(final)

    reported_fixed = status == "fixed"
    final_correct = bool(final and final["correct"])
    regressions = sorted(baseline_passed - set((final or {}).get("visible", {}).get("passed", []))
                         ) if final and final.get("visible") else []
    missing = sorted(baseline_passed - set((final or {}).get("visible", {}).get("outcomes", {}))
                     ) if final and final.get("visible") else []
    false_accept = bool(reported_fixed and not final_correct)
    false_reject = bool((not reported_fixed) and any(c["correct"] for c in candidates))

    hint = hyp.get("patch_hint") or {}
    hint_file = _norm(hint.get("file"))
    expected_file = _norm(entry.get("root_cause_file"))
    loc_file = bool(expected_file and hint_file == expected_file)
    hint_line = hint.get("line")
    expected_line = entry.get("root_cause_line")
    line_delta = abs(int(hint_line) - int(expected_line)) if (
        isinstance(hint_line, int) and isinstance(expected_line, int)) else None

    checks = (final_patch or {}).get("report", {}).get("checks") if final_patch else []
    if not checks:
        checks = (final or {}).get("checks") or []

    row = {
        "id": cid,
        "name": entry.get("name", ""),
        "category": entry.get("category", ""),
        "difficulty": entry.get("difficulty", ""),
        "status": status,
        "reported_fixed": reported_fixed,
        "reproduced": bool(failures) and status not in ("no-failure", "error"),
        "localized_file": loc_file,
        "localized_line_exact": line_delta == 0,
        "localized_line_within_3": line_delta is not None and line_delta <= 3,
        "localized_line_within_10": line_delta is not None and line_delta <= 10,
        "hint_file": hint_file,
        "expected_file": expected_file,
        "patch_generated": bool(patches),
        "final_patch_status": (final_patch or {}).get("status", ""),
        "final_patch_correct": final_correct,
        "visible_ok": bool(final and final["visible_ok"]),
        "oracle_ok": bool(final and final["oracle_ok"]),
        "false_accept": false_accept,
        "false_reject": false_reject,
        "regressions": regressions,
        "missing_tests": missing,
        "touched_tests": (final or {}).get("touched_tests", []),
        "ground_truth_overlap": diff_overlap(final_diff, (Path(entry["dir"]) / "ground_truth.patch")
                                             .read_text(encoding="utf-8")) if final_diff else None,
        "checks": checks,
        "checks_failed": [c.get("id") for c in checks if c.get("status") == "fail"],
        "attempts": full.get("attempts", 0),
        "confidence": full.get("confidence"),
        "duration_s": duration,
        "agent_error": (failures[0].get("error_msg") or "")[:180] if failures else "",
        "hypothesis": {
            "rule": hyp.get("rule", ""),
            "root_cause": hyp.get("root_cause", ""),
            "confidence": hyp.get("confidence"),
            "patch_hint": hint,
        },
        "candidates": [
            {k: v for k, v in c.items() if k not in ("visible", "oracle", "diff")}
            for c in candidates
        ],
        "final_diff": final_diff,
        "visible_output": (final or {}).get("visible", {}).get("output", "")[-4000:] if final else "",
        "oracle_output": (final or {}).get("oracle", {}).get("output", "")[-4000:] if final else "",
    }
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return row


# ----------------------------------------------------------------- aggregation
def aggregate(rows: list[dict], labels: dict) -> dict:
    n = len(rows) or 1
    durations = sorted(r["duration_s"] for r in rows)
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
        r["diagnosis_label"] = labels.get(r["id"])

    def cat_summary(items: list[dict]) -> dict:
        k = len(items) or 1
        return {
            "entries": len(items),
            "correct": sum(r["final_patch_correct"] for r in items),
            "correct_rate": round(sum(r["final_patch_correct"] for r in items) / k, 3),
            "localized_file": sum(r["localized_file"] for r in items),
            "false_accepts": sum(r["false_accept"] for r in items),
            "false_rejects": sum(r["false_reject"] for r in items),
        }

    labeled = [r for r in rows if r["diagnosis_label"]]
    diag_counts = Counter(r["diagnosis_label"] for r in labeled)
    return {
        "entries": len(rows),
        "reported_fixed": sum(r["reported_fixed"] for r in rows),
        "reproduction_rate": round(sum(r["reproduced"] for r in rows) / n, 3),
        "localization_file_rate": round(sum(r["localized_file"] for r in rows) / n, 3),
        "localization_line_exact": sum(r["localized_line_exact"] for r in rows),
        "localization_line_within_3": sum(r["localized_line_within_3"] for r in rows),
        "patch_generation_rate": round(sum(r["patch_generated"] for r in rows) / n, 3),
        "patch_correctness": round(sum(r["final_patch_correct"] for r in rows) / n, 3),
        "correct": sum(r["final_patch_correct"] for r in rows),
        "regression_free_correct": sum(
            r["final_patch_correct"] and not r["regressions"] for r in rows),
        "false_accepts": sum(r["false_accept"] for r in rows),
        "false_reject_count": sum(r["false_reject"] for r in rows),
        "touched_tests": sum(bool(r["touched_tests"]) for r in rows),
        "diagnosis_labeled": len(labeled),
        "diagnosis_counts": dict(sorted(diag_counts.items())),
        "diagnosis_accuracy": round(diag_counts.get("correct", 0) / len(labeled), 3)
                              if labeled else None,
        "avg_attempts": round(sum(r["attempts"] for r in rows) / n, 2),
        "median_duration_s": round(statistics.median(durations), 2) if durations else 0,
        "total_duration_s": round(sum(durations), 2),
        "by_category": {k: cat_summary(v) for k, v in sorted(by_cat.items())},
    }


def render_markdown(data: dict) -> str:
    a = data["aggregate"]
    lines = [
        "# REPRO held-out evaluation — rules only",
        "",
        f"**Corpus:** `{data['corpus_version']}` · **rules:** `{data['rules_tag']}` "
        f"(`{data['rules_commit']}`) · **run:** {data['ran_at']}",
        "",
        f"**Patch correctness: {a['correct']}/{a['entries']} ({a['patch_correctness']:.0%})** — "
        f"reported fixed {a['reported_fixed']}, false accepts {a['false_accepts']}, "
        f"false rejects {a['false_reject_count']}, regression-free correct "
        f"{a['regression_free_correct']}.",
        "",
        f"Reproduction {a['reproduction_rate']:.0%} · localization (file) "
        f"{a['localization_file_rate']:.0%} · line exact {a['localization_line_exact']}/"
        f"{a['entries']} · patch generation {a['patch_generation_rate']:.0%} · "
        f"median runtime {a['median_duration_s']}s · total {a['total_duration_s']}s.",
        "",
    ]
    if a["diagnosis_accuracy"] is not None:
        lines += [f"Diagnosis (manual rubric, {a['diagnosis_labeled']} labelled): "
                  f"{a['diagnosis_counts']} — accuracy {a['diagnosis_accuracy']:.0%}.", ""]
    else:
        lines += ["Diagnosis: pending manual adjudication (see hypotheses in JSON).", ""]

    lines += [
        "| id | category | status | reported | localized | patch | visible | oracle | correct | regressions | time |",
        "|----|----------|--------|----------|-----------|-------|---------|--------|---------|-------------|------|",
    ]
    for r in data["results"]:
        lines.append(
            f"| {r['id']} | {r['category']} | {r['status']} | "
            f"{'✓' if r['reported_fixed'] else '—'} | {'✓' if r['localized_file'] else '—'} | "
            f"{'✓' if r['patch_generated'] else '—'} | {'✓' if r['visible_ok'] else '—'} | "
            f"{'✓' if r['oracle_ok'] else '—'} | {'✓' if r['final_patch_correct'] else '—'} | "
            f"{len(r['regressions'])} | {r['duration_s']}s |"
        )
    lines.append("")

    lines += ["## Per category", "", "| category | correct | rate | localized file | false accepts | false rejects |",
              "|---|---|---|---|---|---|"]
    for cat, c in a["by_category"].items():
        lines.append(f"| {cat} | {c['correct']}/{c['entries']} | {c['correct_rate']:.0%} | "
                     f"{c['localized_file']}/{c['entries']} | {c['false_accepts']} | {c['false_rejects']} |")
    lines.append("")

    lines += ["## Failures and near misses", ""]
    for r in data["results"]:
        if r["final_patch_correct"]:
            continue
        lines.append(f"### `{r['id']}` — {r['name']}")
        lines.append("")
        lines.append(f"- status **{r['status']}**, reported fixed **{r['reported_fixed']}**, "
                     f"visible **{r['visible_ok']}**, oracle **{r['oracle_ok']}**, "
                     f"final patch **{r['final_patch_status'] or 'none'}**")
        lines.append(f"- localization: hint `{r['hint_file'] or '—'}` vs expected "
                     f"`{r['expected_file']}`")
        lines.append(f"- hypothesis: {r['hypothesis']['root_cause'] or '—'} "
                     f"(rule `{r['hypothesis']['rule'] or '—'}`, confidence "
                     f"{r['hypothesis']['confidence']})")
        if r["checks_failed"]:
            lines.append(f"- failed checks: {', '.join(r['checks_failed'])}")
        if r["agent_error"]:
            lines.append(f"- observed error: `{r['agent_error']}`")
        if r["false_accept"]:
            lines.append("- **FALSE ACCEPT**: agent reported fixed but independent tests failed")
        if r["false_reject"]:
            lines.append("- **FALSE REJECT**: a correct candidate was generated but not reported fixed")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run-heldout")
    p.add_argument("--only", nargs="*", default=None, help="case ids")
    p.add_argument("--timeout", type=float, default=180.0, help="seconds per case")
    p.add_argument("--out", default=str(RESULTS / "heldout_rules.json"))
    p.add_argument("--labels", default=None, help="JSON mapping case id -> diagnosis label")
    p.add_argument("--keep", action="store_true", help="keep project workspaces for debugging")
    args = p.parse_args(argv)

    manifest = _read_json(CORPUS / "manifest.json")
    entries = [{**e, "dir": str(CORPUS / e["id"])} for e in manifest["entries"]]
    if args.only:
        wanted = set(args.only)
        entries = [e for e in entries if e["id"] in wanted]
        missing = wanted - {e["id"] for e in entries}
        if missing:
            print(f"unknown ids: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    labels = _read_json(Path(args.labels)) if args.labels else {}

    # Disposable, isolated run directory.
    root = Path(tempfile.mkdtemp(prefix="repro-heldout-run-"))
    cfg.data_dir = root
    cfg.db_path = root / "heldout.db"
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

    print(f"corpus {manifest['corpus_version']} · {len(entries)} cases · data {root}",
          file=sys.stderr, flush=True)
    rows = []
    for i, entry in enumerate(entries, start=1):
        print(f"[{i}/{len(entries)}] {entry['id']} …", file=sys.stderr, flush=True)
        try:
            row = run_case(entry, timeout=args.timeout, keep=args.keep)
        except Exception as e:  # noqa: BLE001
            print(f"  ! crashed: {e}", file=sys.stderr, flush=True)
            row = {
                "id": entry["id"], "name": entry.get("name", ""),
                "category": entry.get("category", ""), "difficulty": entry.get("difficulty", ""),
                "status": "error", "reported_fixed": False, "reproduced": False,
                "localized_file": False, "localized_line_exact": False,
                "localized_line_within_3": False, "localized_line_within_10": False,
                "hint_file": "", "expected_file": entry.get("root_cause_file", ""),
                "patch_generated": False, "final_patch_status": "", "final_patch_correct": False,
                "visible_ok": False, "oracle_ok": False, "false_accept": False,
                "false_reject": False, "regressions": [], "missing_tests": [],
                "touched_tests": [], "ground_truth_overlap": None, "checks": [],
                "checks_failed": [], "attempts": 0, "confidence": None, "duration_s": 0.0,
                "agent_error": str(e)[:180], "hypothesis": {},
                "candidates": [], "final_diff": "", "visible_output": "", "oracle_output": "",
            }
        rows.append(row)
        print(f"    → {row['status']} correct={row['final_patch_correct']} "
              f"reported={row['reported_fixed']} ({row['duration_s']}s)",
              file=sys.stderr, flush=True)

    agg = aggregate(rows, labels)
    data = {
        "schema_version": 1,
        "corpus_version": manifest["corpus_version"],
        "rules_tag": manifest.get("rules_tag", "rules-v1"),
        "rules_commit": subprocess.run(["git", "rev-parse", "--short", "rules-v1^{commit}"],
                                       cwd=str(BACKEND.parent), capture_output=True,
                                       text=True).stdout.strip(),
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "rules",
        "provider": "none (forced off)",
        "aggregate": agg,
        "results": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = out.with_suffix(".md")
    md.write_text(render_markdown(data), encoding="utf-8")
    print(render_markdown(data))
    print(f"\nwrote {out}\nwrote {md}", file=sys.stderr)
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
