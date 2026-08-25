"""Patch generation + application.

The heuristic patcher turns a hypothesis into a minimal, line-precise edit.
The edit is applied to the SANDBOX copy only, on a dedicated git branch
(`repro/fix-<id>`), so the user's repository is never touched without an
explicit apply request.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .sandbox import Sandbox


def _read_lines(sandbox: Sandbox, file: str) -> list[str] | None:
    p = sandbox.root / file
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None


def _write_lines(sandbox: Sandbox, file: str, lines: list[str]) -> None:
    p = sandbox.root / file
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def edits_from_hint(hint: dict | None, sandbox: Sandbox) -> list[tuple[str, int, list[str]]] | None:
    """Return [(file, lineno (1-based), replacement_lines)] or None."""
    if not hint or not hint.get("rule"):
        return None
    rule = hint["rule"]
    file = hint.get("file")
    line = hint.get("line")
    if not file or not line:
        return None
    lines = _read_lines(sandbox, file)
    if not lines or line < 1 or line > len(lines):
        return None
    failing = lines[line - 1]

    if rule == "none_subscript":
        var = hint.get("var")
        if not var:
            return None
        indent = re.match(r"^(\s*)", failing).group(1)
        guard = [f"{indent}if {var} is None:",
                 f"{indent}    return None"]
        return [(file, line, guard + [failing])]

    if rule == "none_attribute":
        var = hint.get("var")
        if not var:
            return None
        indent = re.match(r"^(\s*)", failing).group(1)
        guard = [f"{indent}if {var} is None:",
                 f"{indent}    return None"]
        return [(file, line, guard + [failing])]

    if rule == "off_by_one_range":
        idx = hint.get("idx")
        body_start = max(0, line - 40)
        for i in range(line - 1, body_start - 1, -1):
            m = re.search(rf"for\s+{re.escape(idx)}\s+in\s+range\(len\((\w+)\)\)", lines[i])
            if m:
                old = lines[i]
                new = re.sub(rf"range\(len\(({re.escape(m.group(1))})\)\)",
                             r"range(len(\1) - 1)", old)
                return [(file, i + 1, [new])]
        return None

    if rule == "key_fix":
        old_key, new_key = hint.get("old_key"), hint.get("new_key")
        if not old_key or not new_key:
            return None
        new = failing.replace(f'["{old_key}"]', f'["{new_key}"]')
        new = new.replace(f"['{old_key}']", f"['{new_key}']")
        if new == failing:
            return None
        return [(file, line, [new])]

    if rule == "sql_column_fix":
        missing, replacement = hint.get("missing"), hint.get("replacement")
        if not missing or not replacement:
            return None
        new = re.sub(rf"\b{re.escape(missing)}\b", replacement, failing)
        if new == failing:
            return None
        return [(file, line, [new])]

    if rule == "auth_hash":
        if "==" not in failing:
            return None
        left, right = failing.split("==", 1)
        new_right = re.sub(r"\bpassword\b", "hash_password(password)", right)
        if new_right == right:
            return None
        return [(file, line, [left + "==" + new_right])]

    return None


def apply_edits(sandbox: Sandbox, edits: list[tuple[str, int, list[str]]]) -> bool:
    for file, lineno, new_lines in edits:
        lines = _read_lines(sandbox, file)
        if not lines or lineno < 1 or lineno > len(lines):
            return False
        lines[lineno - 1:lineno] = new_lines
        _write_lines(sandbox, file, lines)
    return True


def _git(sandbox: Sandbox, *args: str) -> subprocess.CompletedProcess:
    env = dict(sandbox.env)
    return subprocess.run(
        ["git", "-c", "user.name=REPRO", "-c", "user.email=repro@local", *args],
        capture_output=True, text=True, cwd=str(sandbox.root), env=env,
        timeout=60, shell=False)


def ensure_branch(sandbox: Sandbox, branch: str) -> None:
    """Ensure the sandbox is a git repo with a baseline commit and the branch checked out."""
    if not (sandbox.root / ".git").exists():
        _git(sandbox, "init", "-q", "-b", "main")
    have_commits = _git(sandbox, "rev-parse", "--verify", "HEAD").returncode == 0
    if not have_commits:
        _git(sandbox, "add", "-A")
        _git(sandbox, "commit", "-q", "-m", "baseline")
    branches = _git(sandbox, "branch", "--list", branch).stdout.strip()
    if branches:
        _git(sandbox, "checkout", "-q", branch)
    else:
        _git(sandbox, "checkout", "-q", "-b", branch)


def git_diff(sandbox: Sandbox, branch: str) -> tuple[str, dict]:
    proc = _git(sandbox, "diff", "main..." + branch)
    if proc.returncode != 0:
        proc = _git(sandbox, "diff", branch)
    diff = proc.stdout
    added = removed = 0
    for l in diff.splitlines():
        if l.startswith(("+++", "---", "@@", "diff", "index", "new file", "deleted")):
            continue
        if l.startswith("+"):
            added += 1
        elif l.startswith("-"):
            removed += 1
    files = len(re.findall(r"^diff --git a/", diff, re.M))
    return diff, {"files_changed": files, "lines_added": added, "lines_removed": removed}


def plan_patch(sandbox: Sandbox, hypothesis: dict, iid: str) -> dict | None:
    """Compute the candidate patch (diff + stats) WITHOUT touching the sandbox.

    The pipeline validates a patch *before* it is applied, so generation is
    split into `plan_patch` (pure computation) and `apply_plan` (git commit).
    """
    hint = hypothesis.get("patch_hint")
    edits = edits_from_hint(hint, sandbox)
    if not edits:
        return None
    branch = f"repro/fix-{iid}"
    diff, stats = diff_from_edits(sandbox, edits)
    return {
        "diff": diff,
        "edits": edits,
        **stats,
        "risk": hypothesis.get("risk", "MEDIUM"),
        "confidence": hypothesis.get("confidence"),
        "reason": hypothesis.get("explanation", ""),
        "explanation": hypothesis.get("explanation", ""),
        "root_cause": hypothesis.get("root_cause", ""),
        "rule": hypothesis.get("rule", ""),
        "status": "proposed",
        "applied": False,
        "branch": branch,
    }


def diff_from_edits(sandbox: Sandbox, edits: list[tuple[str, int, list[str]]]) -> tuple[str, dict]:
    """Compute the unified diff + stats a set of edits would produce."""
    import difflib
    by_file: dict[str, list[tuple[int, list[str]]]] = {}
    for file, lineno, new_lines in edits:
        by_file.setdefault(file, []).append((lineno, new_lines))
    chunks: list[str] = []
    added = removed = 0
    for file in sorted(by_file):
        lines = _read_lines(sandbox, file)
        if not lines:
            continue
        old = list(lines)
        # apply edits bottom-up so line numbers stay valid
        for lineno, new_lines in sorted(by_file[file], key=lambda e: -e[0]):
            lines[lineno - 1:lineno] = new_lines
        # unified_diff with lineterm="" yields newline-free lines; joining with
        # "\n" (plus a trailing newline) produces a proper, git-applyable diff.
        # (lineterm="\n" would only terminate header lines, mashing the content
        # lines together and corrupting the stats.) Also normalize separators,
        # since Windows sandboxes produce backslash paths.
        norm = file.replace("\\", "/")
        diff_text = "\n".join(difflib.unified_diff(
            old, lines, fromfile=f"a/{norm}", tofile=f"b/{norm}", lineterm="")) + "\n"
        if not diff_text.strip():
            continue
        chunks.append(f"diff --git a/{norm} b/{norm}\n{diff_text}")
        for l in diff_text.splitlines():
            if l.startswith("+") and not l.startswith("+++"):
                added += 1
            elif l.startswith("-") and not l.startswith("---"):
                removed += 1
    return "\n".join(chunks), {"files_changed": len(by_file), "lines_added": added,
                               "lines_removed": removed}


def apply_plan(sandbox: Sandbox, plan: dict) -> bool:
    """Commit the planned edits onto the isolated branch (sandbox only)."""
    branch = plan["branch"]
    ensure_branch(sandbox, branch)          # baseline first — original code
    if not apply_edits(sandbox, plan["edits"]):
        return False
    _git(sandbox, "add", "-A")
    _git(sandbox, "commit", "-q", "-m", f"repro: apply fix ({plan.get('rule', '')})")
    return True


def revert_patch(sandbox: Sandbox, iid: str) -> None:
    """Discard the sandbox fix branch entirely, returning to baseline."""
    branch = f"repro/fix-{iid}"
    _git(sandbox, "checkout", "-q", "main")
    _git(sandbox, "branch", "-D", branch)


def apply_llm_diff(sandbox: Sandbox, diff: str, iid: str) -> bool:
    """Apply a unified diff produced by an LLM provider inside the sandbox."""
    branch = f"repro/fix-{iid}"
    ensure_branch(sandbox, branch)
    patch_file = sandbox.root / "repro_llm.patch"
    patch_file.write_text(diff, encoding="utf-8")
    proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_file.name)],
        capture_output=True, text=True, cwd=str(sandbox.root), env=dict(sandbox.env),
        timeout=60, shell=False)
    if proc.returncode != 0:
        return False
    _git(sandbox, "add", "-A")
    _git(sandbox, "commit", "-q", "-m", "repro: apply LLM fix")
    return True


def llm_diff_to_patch(sandbox: Sandbox, fix: dict, hypothesis: dict, iid: str) -> dict | None:
    diff = (fix or {}).get("diff") or ""
    if not diff:
        return None
    if not apply_llm_diff(sandbox, diff, iid):
        return None
    d, stats = git_diff(sandbox, f"repro/fix-{iid}")
    return {
        "diff": d,
        **stats,
        "risk": hypothesis.get("risk", "MEDIUM"),
        "confidence": hypothesis.get("confidence"),
        "reason": (fix or {}).get("reason") or hypothesis.get("explanation", ""),
        "status": "proposed",
        "applied": True,
        "branch": f"repro/fix-{iid}",
        "origin": "llm",
    }
