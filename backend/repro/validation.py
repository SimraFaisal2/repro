"""Patch validation: 10 safety checks, regression analysis, risk scoring.

Every candidate patch (rule-based or LLM) passes through a validation gate
before it can be considered a successful fix:

  Dynamic checks (require executing tests):
    1. original failure is fixed
    2. all previously passing tests still pass
    3. no new test failures appear

  Static checks (pure diff/source analysis, run BEFORE applying anything):
    4. patch is minimal
    5. patch modifies only expected files
    6. patch does not introduce obvious syntax errors
    7. patch does not modify tests merely to make them pass
    8. patch does not disable assertions
    9. patch does not remove error handling
   10. patch does not introduce suspicious operations

A patch is never considered successful merely because the original failing
test passes. Each check yields pass/fail/skip with a detail string; the
overall result is a patch risk score LOW / MEDIUM / HIGH. HIGH-risk patches
must be explicitly confirmed by a human before they can be applied.
"""
from __future__ import annotations

import re
from pathlib import Path

from .sandbox import Sandbox

# --------------------------------------------------------------------------
# diff parsing
# --------------------------------------------------------------------------

_MAX_PATCH_LINES = 30          # added + removed lines considered "minimal"
_MAX_PATCH_FILES = 3

_SUSPICIOUS = [
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\b__import__\s*\("),
    re.compile(r"\bcompile\s*\("),
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bos\.(?:system|popen|remove|unlink|rmdir|chmod|kill)\s*\("),
    re.compile(r"\bshutil\.rmtree\s*\("),
    re.compile(r"\bsocket\b"),
    re.compile(r"\brequests?\s*\.\s*(?:get|post|put|delete|request)\s*\("),
    re.compile(r"\burlopen\b"),
    re.compile(r"\b(?:pickle|marshal|shelve)\.loads?\s*\("),
    re.compile(r"\bopen\s*\([^)]*['\"]w"),
    re.compile(r"\bctypes\.\w+"),
    re.compile(r"\b(?:telnetlib|ftplib|imaplib|smtplib)\b"),
]

_ASSERT_RE = re.compile(r"\bassert\b")
_REMOVE_ERR_RE = re.compile(r"^\s*(try|except|finally|raise|with)\b")
_TEST_SEG_RE = re.compile(r"(^|/)(tests?|test_|spec)(/|_|\.|$)")


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def diff_files(diff: str) -> list[str]:
    """File paths touched by a unified diff (normalized to forward slashes)."""
    return [_norm(f) for f in (
        re.findall(r"^diff --git a/(\S+) b/", diff, re.M) or
        re.findall(r"^\+\+\+ b/(\S+)", diff, re.M))]


def diff_lines(diff: str) -> tuple[list[str], list[str]]:
    """Return (added, removed) code lines from a unified diff."""
    added, removed = [], []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def is_test_file(path: str) -> bool:
    p = path.replace("\\", "/")
    return bool(_TEST_SEG_RE.search(p)) or p.endswith("_test.py") or p.startswith("test_")


def is_python_file(path: str) -> bool:
    return path.endswith(".py")


# --------------------------------------------------------------------------
# static checks (pure analysis of the diff — nothing is applied yet)
# --------------------------------------------------------------------------

def check(pid: str, name: str, ok: bool, detail: str, status: str | None = None) -> dict:
    return {"id": pid, "name": name,
            "status": status or ("pass" if ok else "fail"),
            "detail": detail}


def validate_static(diff: str, stats: dict, expected_files: set[str]) -> list[dict]:
    """Run static checks 4-10 against the diff text and stats."""
    files = diff_files(diff)
    added, removed = diff_lines(diff)
    checks: list[dict] = []

    # 4. minimal
    n_lines = stats.get("lines_added", len(added)) + stats.get("lines_removed", len(removed))
    n_files = stats.get("files_changed", len(files))
    checks.append(check(
        "minimal", "Patch is minimal",
        n_lines <= _MAX_PATCH_LINES and n_files <= _MAX_PATCH_FILES,
        f"{n_files} file(s), +{n_lines} line(s)"))

    # 5. only expected files (source files referenced by the failing path)
    unexpected = [f for f in files if not is_test_file(f) and f not in expected_files]
    checks.append(check(
        "only-expected-files", "Modifies only expected files",
        not unexpected,
        f"unexpected: {', '.join(unexpected) or 'none'}"))

    # 7. does not modify tests
    touched_tests = [f for f in files if is_test_file(f)]
    checks.append(check(
        "no-test-changes", "Does not modify tests",
        not touched_tests,
        f"test files: {', '.join(touched_tests) or 'none'}"))

    # 8. does not disable assertions
    dropped = [l.strip()[:80] for l in removed if _ASSERT_RE.search(l)]
    checks.append(check(
        "assertions-intact", "Does not disable assertions",
        not dropped,
        f"removed assert: {', '.join(dropped) or 'none'}"))

    # 9. does not remove error handling
    dropped = [l.strip()[:80] for l in removed if _REMOVE_ERR_RE.search(l)]
    checks.append(check(
        "error-handling-intact", "Does not remove error handling",
        not dropped,
        f"removed: {', '.join(dropped) or 'none'}"))

    # 10. no suspicious operations
    suspicious = [l.strip()[:80] for l in added if any(r.search(l) for r in _SUSPICIOUS)]
    checks.append(check(
        "no-suspicious-ops", "No suspicious operations",
        not suspicious,
        f"suspicious: {', '.join(suspicious) or 'none'}"))

    # 6. syntax — needs real content, provided separately
    return checks


def validate_syntax_edits(sandbox: Sandbox, edits: list[tuple[str, int, list[str]]]) -> list[dict]:
    """Check 6 for planned rule edits: apply them in memory and compile."""
    out: list[dict] = []
    by_file: dict[str, list[tuple[int, list[str]]]] = {}
    for file, lineno, new_lines in edits:
        by_file.setdefault(_norm(file), []).append((lineno, new_lines))
    for file in sorted(by_file):
        p: Path = sandbox.root / file
        if not p.exists():
            out.append(check("syntax", "No obvious syntax errors", False,
                             f"{file}: file not found in sandbox"))
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, new_lines in sorted(by_file[file], key=lambda e: -e[0]):
            lines[lineno - 1:lineno] = new_lines
        try:
            compile("\n".join(lines), file, "exec")
            out.append(check("syntax", "No obvious syntax errors", True, f"{file}: compiles"))
        except SyntaxError as e:
            out.append(check("syntax", "No obvious syntax errors", False,
                             f"{file}:{e.lineno} {e.msg}"))
    return out


def validate_syntax(sandbox: Sandbox, diff: str) -> list[dict]:
    """Check 6: py_compile the changed python files (pre-apply, from source)."""
    out: list[dict] = []
    for f in diff_files(diff):
        if not is_python_file(f):
            out.append(check("syntax", "No obvious syntax errors", True, f"{f}: not python"))
            continue
        p: Path = sandbox.root / f
        if not p.exists():
            out.append(check("syntax", "No obvious syntax errors", False,
                             f"{f}: file not found in sandbox"))
            continue
        try:
            compile(p.read_text(encoding="utf-8", errors="replace"), f, "exec")
            out.append(check("syntax", "No obvious syntax errors", True, f"{f}: compiles"))
        except SyntaxError as e:
            out.append(check("syntax", "No obvious syntax errors", False,
                             f"{f}:{e.lineno} {e.msg}"))
    if not diff_files(diff):
        out.append(check("syntax", "No obvious syntax errors", True, "no files changed"))
    return out


def stats_from_diff(diff: str) -> dict:
    """Compute {files_changed, lines_added, lines_removed} from a diff string
    (used to validate an LLM-provided diff BEFORE it is applied)."""
    added, removed = diff_lines(diff)
    return {"files_changed": len(diff_files(diff)), "lines_added": len(added),
            "lines_removed": len(removed)}


def all_pass(checks: list[dict]) -> bool:
    return all(c["status"] in ("pass", "skip") for c in checks)


# --------------------------------------------------------------------------
# dynamic checks: regression analysis from test runs
# --------------------------------------------------------------------------

def analyze_regression(baseline: dict, full: dict) -> dict:
    """Checks 1-3. Compare baseline failures against the full post-patch run.

    `baseline` carries failed_ids; `full` is the post-patch run_suite result.
    """
    before_failed = set(baseline.get("failed_ids") or [])
    after_failed = set(full.get("failed_ids") or [])
    new = sorted(after_failed - before_failed)
    fixed_now = sorted(before_failed - after_failed)
    return {
        "status": "new-failures" if new else "none",
        "new_failures": new,
        "fixed_now": fixed_now,
        "before": {"passed": baseline.get("passed", 0), "failed": baseline.get("failed", 0),
                   "total": baseline.get("total", 0), "failed_ids": sorted(before_failed)},
        "after": {"passed": full.get("passed", 0), "failed": full.get("failed", 0),
                  "total": full.get("total", 0), "failed_ids": sorted(after_failed)},
    }


# --------------------------------------------------------------------------
# risk scoring
# --------------------------------------------------------------------------

def score_risk(base_risk: str, checks: list[dict], regression: dict | None = None,
               stats: dict | None = None) -> str:
    """LOW / MEDIUM / HIGH.

    - Any failed static check, or any regression → HIGH (human approval).
    - Otherwise keep the hypothesis' base risk (LOW/MEDIUM).
    """
    if any(c["status"] == "fail" for c in checks):
        return "HIGH"
    if regression and regression["status"] != "none":
        return "HIGH"
    stats = stats or {}
    n_lines = stats.get("lines_added", 0) + stats.get("lines_removed", 0)
    n_files = stats.get("files_changed", 0)
    if n_lines > _MAX_PATCH_LINES or n_files > _MAX_PATCH_FILES:
        return "HIGH"
    base = (base_risk or "MEDIUM").upper()
    return base if base in ("LOW", "MEDIUM") else "HIGH"


# --------------------------------------------------------------------------
# patch report
# --------------------------------------------------------------------------

def build_report(patch: dict, hypothesis: dict, checks: list[dict],
                 regression: dict, tests_affected: list[str]) -> dict:
    """The per-patch report required by the pipeline spec."""
    diff = patch.get("diff", "")
    files = diff_files(diff)
    return {
        "root_cause": hypothesis.get("root_cause", ""),
        "explanation": patch.get("reason") or hypothesis.get("explanation", ""),
        "files": files,
        "files_changed": patch.get("files_changed", len(files)),
        "lines_added": patch.get("lines_added", 0),
        "lines_removed": patch.get("lines_removed", 0),
        "tests_affected": sorted(set(tests_affected)),
        "tests_before": regression.get("before", {}),
        "tests_after": regression.get("after", {}),
        "regression_status": regression.get("status", "none"),
        "regression_new": regression.get("new_failures", []),
        "patch_confidence": patch.get("confidence"),
        "risk": patch.get("risk", "MEDIUM"),
        "checks": checks,
    }
