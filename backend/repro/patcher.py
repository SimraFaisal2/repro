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

    if rule == "str_concat_type":
        var, side = hint.get("var"), hint.get("side")
        if not var:
            return None
        if side == "left":
            new = re.sub(rf"\b{re.escape(var)}\s*\+", f"str({var}) +", failing, count=1)
        else:
            new = re.sub(rf"\+\s*{re.escape(var)}\b", f"+ str({var})", failing, count=1)
        if new == failing:
            return None
        return [(file, line, [new])]

    if rule == "not_subscriptable_iter":
        var = hint.get("var")
        if not var:
            return None
        new = re.sub(rf"\b{re.escape(var)}\s*\[[^\]]*\]", f"next(iter({var}))", failing, count=1)
        if new == failing:
            return None
        return [(file, line, [new])]

    if rule == "inplace_mutator_return":
        target, mut = hint.get("target"), hint.get("mutator")
        if not target or not mut:
            return None
        indent = re.match(r"^(\s*)", failing).group(1)
        call = f"{indent}{target}.{mut}({hint.get('args', '')})"
        return [(file, line, [call, f"{indent}return {target}"])]

    if rule == "boundary_comparison":
        old_op, new_op, literal = hint.get("old_op"), hint.get("new_op"), hint.get("literal")
        if not old_op or not new_op or literal is None:
            return None
        pattern = rf"{re.escape(old_op)}(?![=])\s*{re.escape(str(literal))}\b"
        new = re.sub(pattern, f"{new_op} {literal}", failing, count=1)
        if new == failing:
            return None
        return [(file, line, [new])]

    if rule == "empty_guard_zerodiv":
        var = hint.get("var")
        if not var:
            return None
        indent = re.match(r"^(\s*)", failing).group(1)
        guard = [f"{indent}if not {var}:", f"{indent}    return {hint.get('default', 0)!r}"]
        return [(file, line, guard + [failing])]

    if rule == "broad_except_swallow":
        indent = re.match(r"^(\s*)", failing).group(1)
        if indent == "":
            return None
        return [(file, line, [f"{indent}raise"])]

    if rule == "aggregation_field":
        old_key, new_key = hint.get("old_key"), hint.get("new_key")
        if not old_key or not new_key:
            return None
        new = re.sub(rf"\[(['\"]){re.escape(old_key)}\1\]", f"['{new_key}']", failing, count=1)
        if new == failing:
            return None
        return [(file, line, [new])]

    if rule == "state_transition_edges":
        attr = hint.get("attr")
        retarget = hint.get("retarget") or []
        missing = hint.get("missing") or []
        insert_after = hint.get("insert_after") or 0
        indent = hint.get("indent") or "        "
        if not attr or (not retarget and not missing):
            return None
        edges: list[tuple[str, int, list[str]]] = []
        all_lines = _read_lines(sandbox, file)
        if not all_lines:
            return None
        for r in retarget:
            idx = r.get("line") or 0
            if not 1 <= idx <= len(all_lines):
                return None
            new_line = re.sub(rf"(['\"]){re.escape(r['old'])}\1", f"'{r['new']}'",
                              all_lines[idx - 1], count=1)
            if new_line == all_lines[idx - 1]:
                return None
            edges.append((file, idx, [new_line]))
        if missing:
            if not 1 <= insert_after <= len(all_lines):
                return None
            anchor = all_lines[insert_after - 1]
            added = [anchor]
            for m in missing:
                added.append(f"{indent}elif self.{attr} == \"{m['src']}\":")
                added.append(f"{indent}    self.{attr} = \"{m['dst']}\"")
            edges.append((file, insert_after, added))
        return edges

    if rule == "lock_read_modify_write":
        attr, end = hint.get("attr"), hint.get("end")
        if not attr or not end:
            return None
        all_lines = _read_lines(sandbox, file)
        if not all_lines:
            return None
        class_idx = next((i for i in range(line - 2, -1, -1)
                          if re.match(r"^class\s+\w+", all_lines[i])), None)
        if class_idx is None:
            return None
        edits: list[tuple[str, int, list[str]]] = []
        if not any(re.match(r"^import\s+threading\b", l) for l in all_lines):
            edits.append((file, class_idx + 1, ["import threading", all_lines[class_idx]]))
        init_idx = next((i for i in range(line - 2, class_idx, -1)
                         if re.match(r"^(\s*)def\s+__init__\s*\(", all_lines[i])), None)
        if init_idx is None:
            return None
        init_indent = " " * (len(all_lines[init_idx]) - len(all_lines[init_idx].lstrip()) + 4)
        edits.append((file, init_idx + 1,
                      [all_lines[init_idx], f"{init_indent}self._lock = threading.Lock()"]))
        # wrap the method body, leaving a leading docstring outside the lock
        first, last = line, end - 1
        if first <= last and all_lines[first].strip()[:3] in ('"""', "'''"):
            quote = all_lines[first].strip()[:3]
            while first <= last:
                closed = (all_lines[first].strip().endswith(quote)
                          and len(all_lines[first].strip()) >= 6)
                first += 1
                if closed:
                    break
        block = [all_lines[i] for i in range(first, last + 1)]
        if not block:
            return None
        first_code = next((b for b in block if b.strip()), "")
        base_indent = re.match(r"^(\s*)", first_code).group(1)
        edits.append((file, first + 1, [f"{base_indent}with self._lock:", "    " + block[0]]))
        for off, l in enumerate(block[1:], start=1):
            edits.append((file, first + off + 1, ["    " + l if l.strip() else l]))
        return edits

    return None


def apply_edits(sandbox: Sandbox, edits: list[tuple[str, int, list[str]]]) -> bool:
    """Apply edits bottom-up so earlier insertions cannot shift later lines."""
    for file in dict.fromkeys(e[0] for e in edits):
        lines = _read_lines(sandbox, file)
        if not lines:
            return False
        for _, lineno, new_lines in sorted(
                [e for e in edits if e[0] == file], key=lambda e: -e[1]):
            if lineno < 1 or lineno > len(lines):
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
