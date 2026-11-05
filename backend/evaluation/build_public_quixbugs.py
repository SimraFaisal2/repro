"""Convert a small, pre-registered QuixBugs slice into REPRO projects.

QuixBugs is function-level, not repository-level. It is included as an external
check on the same frozen agent, not as a substitute for the held-out corpus.

The script refuses to include an algorithm unless:
  * the buggy program fails at least one public testcase;
  * the project's own correct program passes every public testcase;
  * the test file runs in the same pytest layout REPRO uses.

Usage (from ``backend/``)::

    .venv/bin/python -m evaluation.build_public_quixbugs \
        --source /tmp/quixbugs --out evaluation/public_quixbugs_corpus
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Pre-registered before seeing agent results: self-contained algorithms with
# deterministic JSON testcases and no shared helper objects.
ALGOS = [
    "find_in_sorted",
    "gcd",
    "get_factors",
    "is_valid_parenthesization",
    "kth",
    "max_sublist_sum",
    "powerset",
    "to_base",
]

_TEST_DEF = re.compile(r"def test_\w+\(")


def _run_pytest(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider",
         "--no-header", "--disable-warnings", "--tb=short"],
        cwd=str(repo),
        env={"PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1",
             "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"},
        capture_output=True, text=True, timeout=120,
    )


def _failed(output: str) -> list[str]:
    return sorted(set(re.findall(r"^FAILED (\S+)", output, re.M)))


def build(source: Path, out: Path) -> int:
    if not (source / "python_programs").exists():
        print(f"not a QuixBugs checkout: {source}", file=sys.stderr)
        return 2
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source,
                            capture_output=True, text=True).stdout.strip()
    entries = []
    excluded = []
    for algo in ALGOS:
        buggy = source / "python_programs" / f"{algo}.py"
        correct = source / "correct_python_programs" / f"{algo}.py"
        cases_file = source / "json_testcases" / f"{algo}.json"
        if not (buggy.exists() and correct.exists() and cases_file.exists()):
            excluded.append({"id": algo, "reason": "missing source or testcases"})
            continue
        cases = [json.loads(line) for line in cases_file.read_text().splitlines() if line.strip()]
        with tempfile.TemporaryDirectory(prefix=f"quix-{algo}-") as td:
            repo = Path(td) / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "conftest.py").write_text("# pytest root\n", encoding="utf-8")
            (repo / "src" / f"{algo}.py").write_text(buggy.read_text(), encoding="utf-8")
            test_src = (
                "import pytest\n\n"
                f"from src.{algo} import {algo}\n\n"
                f"CASES = {cases!r}\n\n\n"
                "@pytest.mark.parametrize('args,expected', CASES)\n"
                f"def test_{algo}(args, expected):\n"
                f"    assert {algo}(*args) == expected\n"
            )
            (repo / "tests" / f"test_{algo}.py").write_text(test_src, encoding="utf-8")
            base = _run_pytest(repo)
            if base.returncode == 0:
                excluded.append({"id": algo, "reason": "buggy program passes all public tests"})
                continue
            fixed = Path(td) / "fixed"
            shutil.copytree(repo, fixed)
            (fixed / "src" / f"{algo}.py").write_text(correct.read_text(), encoding="utf-8")
            ok = _run_pytest(fixed)
            if ok.returncode != 0:
                excluded.append({"id": algo, "reason": "correct program does not pass all tests"})
                continue
            entries.append(algo)
            print(f"  ok  {algo} ({len(cases)} cases)")

    return _build_again(source, out, commit, entries, excluded)


def _build_again(source: Path, out: Path, commit: str, keep: list[str],
                 excluded: list[dict]) -> int:
    staging = Path(tempfile.mkdtemp(prefix="quix-corpus-"))
    try:
        for algo in keep:
            cases = [json.loads(line) for line in
                     (source / "json_testcases" / f"{algo}.json").read_text().splitlines()
                     if line.strip()]
            repo = staging / algo / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "conftest.py").write_text("# pytest root\n", encoding="utf-8")
            (repo / "src" / f"{algo}.py").write_text(
                (source / "python_programs" / f"{algo}.py").read_text(), encoding="utf-8")
            (repo / "tests" / f"test_{algo}.py").write_text(
                "import pytest\n\n"
                f"from src.{algo} import {algo}\n\n"
                f"CASES = {cases!r}\n\n\n"
                "@pytest.mark.parametrize('args,expected', CASES)\n"
                f"def test_{algo}(args, expected):\n"
                f"    assert {algo}(*args) == expected\n", encoding="utf-8")
            (staging / algo / "meta.json").write_text(json.dumps({
                "id": algo,
                "name": f"QuixBugs: {algo}",
                "category": "quixbugs",
                "source": "https://github.com/jkoppel/QuixBugs",
                "source_commit": commit,
                "cases": len(cases),
                "scope": "function-level public benchmark",
            }, indent=2) + "\n", encoding="utf-8")
        manifest = {
            "corpus_version": "quixbugs-2026-11-v1",
            "source": "https://github.com/jkoppel/QuixBugs",
            "source_commit": commit,
            "scope": "function-level public benchmark; not repository-level",
            "count": len(keep),
            "algorithms": keep,
            "excluded": excluded,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8")
        (staging / "SOURCE.md").write_text(
            "# QuixBugs slice\n\n"
            f"Source: https://github.com/jkoppel/QuixBugs at `{commit}`.\n\n"
            "QuixBugs is a function-level benchmark. Each converted case contains the "
            "buggy program and the public JSON testcases as a pytest suite. These are "
            "reported separately from the repository-level held-out corpus.\n",
            encoding="utf-8")
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(staging, out)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    print(f"\nwrote {len(keep)} QuixBugs cases to {out}")
    if excluded:
        print("excluded:")
        for e in excluded:
            print(f"  {e['id']}: {e['reason']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="build-public-quixbugs")
    p.add_argument("--source", default="/tmp/quixbugs")
    p.add_argument("--out", default="evaluation/public_quixbugs_corpus")
    args = p.parse_args(argv)
    return build(Path(args.source), Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
