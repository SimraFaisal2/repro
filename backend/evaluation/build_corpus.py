"""Build and sanity-check the held-out REPRO corpus.

The case definitions live in ``evaluation/specs/``. This script writes each
buggy repository, hidden oracle test, ground-truth patch and metadata, and
refuses to publish the corpus unless every case satisfies:

  * the visible suite fails on the buggy repo;
  * the visible suite passes after the ground-truth fix;
  * the visible suite + hidden oracle pass after the ground-truth fix;
  * the generated patch applies cleanly with ``git apply``.

Usage (from ``backend/``)::

    .venv/bin/python -m evaluation.build_corpus
    .venv/bin/python -m evaluation.build_corpus --check   # validate only

The generated corpus is committed so a reviewer can inspect it without running
the builder. Re-running the builder must produce byte-identical files.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from .specs import ALL_CASES

BACKEND = Path(__file__).resolve().parents[1]
CORPUS = BACKEND / "repro" / "benchmark_corpus_heldout"
CORPUS_VERSION = "heldout-2026-11-v1"
RULES_TAG = "rules-v1"

_TEST_DEF = re.compile(r"^def (test_\w+)\(", re.M)


def _python() -> str:
    return sys.executable


def _run_pytest(repo: Path, target: str | None = None) -> subprocess.CompletedProcess:
    args = [_python(), "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider",
            "--no-header", "--disable-warnings", "--tb=short"]
    if target:
        args.append(target)
    env = {
        "PYTHONPATH": str(repo),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    return subprocess.run(args, cwd=str(repo), env=env, capture_output=True,
                          text=True, timeout=120)


def _failed_ids(output: str) -> list[str]:
    return sorted(set(re.findall(r"^FAILED (\S+)", output, re.M)))


def _check_patch_applies(repo: Path, patch: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=REPRO", "-c", "user.email=repro@local",
         "commit", "-q", "-m", "baseline"],
        cwd=repo, check=True,
    )
    p = repo / "_gt.patch"
    p.write_text(patch, encoding="utf-8")
    proc = subprocess.run(["git", "apply", "--check", "--whitespace=nowarn", p.name],
                          cwd=repo, capture_output=True, text=True)
    p.unlink()
    if proc.returncode != 0:
        raise RuntimeError(f"ground-truth patch does not apply: {proc.stderr.strip()[:500]}")


def _make_patch(files: dict[str, str], fixed: dict[str, str]) -> str:
    chunks: list[str] = []
    for path in sorted(fixed):
        old = files[path]
        new = fixed[path]
        if old == new:
            raise ValueError(f"{path}: fixed content is identical to buggy content")
        diff = difflib.unified_diff(
            old.splitlines(True), new.splitlines(True),
            fromfile=f"a/{path}", tofile=f"b/{path}", n=3,
        )
        chunks.append(f"diff --git a/{path} b/{path}\n" + "".join(diff))
    if not chunks:
        raise ValueError("no changed files")
    text = "".join(chunks)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _write_repo(root: Path, files: dict[str, str]) -> None:
    for rel, content in sorted(files.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _validate_case(case: dict) -> dict:
    cid = case["id"]
    files = case["files"]
    fixed = case["fixed"]
    if not files.get("conftest.py"):
        files = {"conftest.py": "# pytest root\n", **files}
    if not any(p.startswith("tests/") and p.endswith(".py") for p in files):
        raise ValueError(f"{cid}: no visible tests")
    if not case.get("oracle", "").strip():
        raise ValueError(f"{cid}: no hidden oracle")
    for path in fixed:
        if path not in files:
            raise ValueError(f"{cid}: fixed file not in repo: {path}")
    if case.get("root_cause_file") not in files:
        raise ValueError(f"{cid}: root_cause_file missing from repo")

    patch = _make_patch(files, fixed)
    with tempfile.TemporaryDirectory(prefix=f"heldout-build-{cid}-") as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        _write_repo(repo, files)

        base = _run_pytest(repo)
        if base.returncode == 0:
            raise ValueError(f"{cid}: visible suite passes on the buggy repo")
        failed = _failed_ids(base.stdout + base.stderr)
        if not failed:
            raise ValueError(f"{cid}: could not parse a failing test id\n{base.stdout[-2000:]}")

        # fixed copy, visible only
        shutil.copytree(repo, Path(td) / "fixed", dirs_exist_ok=True)
        fixed_repo = Path(td) / "fixed"
        for path, content in fixed.items():
            (fixed_repo / path).write_text(content, encoding="utf-8")
        vis = _run_pytest(fixed_repo)
        if vis.returncode != 0:
            raise ValueError(f"{cid}: visible suite fails after ground truth\n"
                             f"{vis.stdout[-3000:]}")

        # same fixed copy, visible + hidden oracle
        oracle = fixed_repo / "tests" / "test_oracle.py"
        oracle.write_text(case["oracle"], encoding="utf-8")
        both = _run_pytest(fixed_repo)
        if both.returncode != 0:
            raise ValueError(f"{cid}: oracle/visible fail after ground truth\n"
                             f"{both.stdout[-3000:]}")
        oracle_count = len(_TEST_DEF.findall(case["oracle"]))
        if oracle_count == 0:
            raise ValueError(f"{cid}: oracle has no test functions")

        _check_patch_applies(repo, patch)

        passing = max(0, len(_TEST_DEF.findall("".join(
            c for p, c in files.items() if p.startswith("tests/")))) - len(failed))

    meta = {
        "id": cid,
        "name": case["name"],
        "category": case["category"],
        "difficulty": case.get("difficulty", "medium"),
        "root_cause_file": case["root_cause_file"],
        "root_cause_line": case.get("root_cause_line"),
        "hidden_bug": case["hidden_bug"],
        "expected_behavior": case["expected_behavior"],
        "ground_truth_summary": case.get("ground_truth_summary", ""),
        "baseline_failed": failed,
        "visible_tests": len(_TEST_DEF.findall("".join(
            c for p, c in files.items() if p.startswith("tests/")))),
        "oracle_tests": oracle_count,
        "tags": case.get("tags", []),
    }
    return {"meta": meta, "files": files, "fixed": fixed,
            "oracle": case["oracle"], "patch": patch}


def build(check_only: bool = False) -> int:
    if not ALL_CASES:
        print("no cases", file=sys.stderr)
        return 1
    ids: set[str] = set()
    built: list[dict] = []
    errors = 0
    for i, case in enumerate(ALL_CASES, start=1):
        cid = case.get("id", f"case-{i}")
        try:
            if cid in ids:
                raise ValueError(f"duplicate id: {cid}")
            ids.add(cid)
            built.append(_validate_case(case))
            print(f"  ok  {cid}")
        except Exception as e:  # noqa: BLE001
            errors += 1
            print(f"  FAIL {cid}: {e}", file=sys.stderr)

    if errors:
        print(f"\n{errors} case(s) failed validation; corpus not written.", file=sys.stderr)
        return 1

    counts = Counter(b["meta"]["category"] for b in built)
    manifest = {
        "corpus_version": CORPUS_VERSION,
        "rules_tag": RULES_TAG,
        "protocol": "evaluation/EVAL_PROTOCOL.md",
        "description": "Held-out bugs authored after the rules freeze; hidden oracle tests "
                       "are not present in the repositories REPRO sees.",
        "count": len(built),
        "by_category": dict(sorted(counts.items())),
        "entries": [b["meta"] for b in built],
    }

    if check_only:
        print(f"\n{len(built)} cases valid; check-only, nothing written.")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="heldout-corpus-"))
    try:
        for b in built:
            cid = b["meta"]["id"]
            d = tmp / cid
            _write_repo(d / "repo", b["files"])
            (d / "oracle").mkdir(parents=True, exist_ok=True)
            (d / "oracle" / "test_oracle.py").write_text(b["oracle"], encoding="utf-8")
            (d / "ground_truth.patch").write_text(b["patch"], encoding="utf-8")
            (d / "meta.json").write_text(json.dumps(b["meta"], indent=2) + "\n",
                                          encoding="utf-8")
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                           encoding="utf-8")
        if CORPUS.exists():
            shutil.rmtree(CORPUS)
        shutil.copytree(tmp, CORPUS)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nwrote {len(built)} cases to {CORPUS}")
    for category, n in sorted(counts.items()):
        print(f"  {category}: {n}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="build-heldout-corpus")
    p.add_argument("--check", action="store_true", help="validate only, do not write")
    args = p.parse_args(argv)
    return build(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
