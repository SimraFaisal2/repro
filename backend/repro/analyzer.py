"""Evidence-based analysis.

Collects *observed* facts from real execution (error type, message, stack
frames, traced arguments/returns, source) and produces a structured
hypothesis. Deterministic rules cover the common failure classes; the LLM
layer (ai.py) can refine the same evidence when a provider is configured.

Every hypothesis explicitly separates OBSERVED evidence from INFERRED
reasoning, and carries a patch_hint consumed by the patcher.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .sandbox import Sandbox

_FUNC_RE = re.compile(r"^(\s*)(async\s+)?def\s+(\w+)\s*\(")


def _module_text(sandbox: Sandbox, file: str) -> str:
    p = sandbox.root / file
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _function_body(text: str, line: int) -> str:
    """Return the text of the function containing `line` (1-indexed)."""
    lines = text.splitlines()
    def_lines = [i for i, l in enumerate(lines) if _FUNC_RE.match(l) and i + 1 <= line]
    if not def_lines:
        return ""
    start = def_lines[-1]
    # next top-level def/class or end
    end = len(lines)
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if (_FUNC_RE.match(l) or re.match(r"^(\s*)class\s+\w+", l)) and not l.startswith((" ", "\t")):
            end = i
            break
    return "\n".join(lines[start:end])


def _failing_line(text: str, line: int) -> str:
    lines = text.splitlines()
    return lines[line - 1] if 0 < line <= len(lines) else ""


def _subscript_var(line: str) -> str | None:
    m = re.search(r"([A-Za-z_][\w.]*)\s*\[", line)
    return m.group(1) if m else None


def _assignment_source(body: str, var: str, before_line: int) -> str | None:
    """Find `var = <expr>` lines in the function body above `before_line`."""
    for i, l in enumerate(body.splitlines(), start=1):
        if i >= before_line:
            break
        m = re.match(rf"^\s*{re.escape(var)}\s*=\s*(.+)$", l)
        if m:
            return m.group(1).strip()
    return None


def _call_name(expr: str) -> str | None:
    m = re.search(r"([A-Za-z_][\w.]*)\s*\(", expr)
    return m.group(1).split(".")[-1] if m else None


def _has_return_none(text: str) -> bool:
    return bool(re.search(r"return\s+None", text)) or bool(re.search(r"return\s*$", text, re.M))


def _collect_evidence(failure: dict, trace: list[dict], sandbox: Sandbox, test_run: dict) -> list[dict]:
    ev: list[dict] = []
    ev.append({"kind": "observed", "source": "test execution",
               "text": f"Test {failure.get('test_id')} failed with "
                       f"{failure.get('error_type')}: {failure.get('error_msg')}"})
    frames = failure.get("frames") or []
    if frames:
        ev.append({"kind": "observed", "source": "stack trace",
                   "text": " -> ".join(f"{f['func']} ({f['file']}:{f['line']})" for f in frames[:5])})
    if failure.get("file"):
        src = _module_text(sandbox, failure["file"])
        fl = _failing_line(src, failure.get("line") or 0)
        if fl:
            ev.append({"kind": "observed", "source": f"source {failure['file']}:{failure.get('line')}",
                       "text": fl.strip()})
    for fr in trace:
        if fr.get("args"):
            ev.append({"kind": "observed", "source": "runtime trace",
                       "text": f"{fr['func']}() called with {fr['args']}"})
        if fr.get("return_value") is not None:
            ev.append({"kind": "observed", "source": "runtime trace",
                       "text": f"{fr['func']}() returned {fr['return_value']}"})
    return ev


def _traced_value(events: list[dict], file: str, func: str) -> str | None:
    """Find a traced return value for the given file/function."""
    for e in events:
        if e.get("event") == "return" and e.get("file") == file and e.get("func") == func:
            rv = e.get("return")
            if rv is not None and rv != "None":
                return rv
    return None


def _dict_keys_from_repr(repr_str: str) -> list[str]:
    try:
        obj = ast.literal_eval(repr_str)
        if isinstance(obj, dict):
            return [str(k) for k in obj.keys()]
    except Exception:
        pass
    return []


def analyze_failure(sandbox: Sandbox, failure: dict, events: list[dict],
                    trace: list[dict], test_run: dict, graph: dict | None = None) -> dict:
    """Build the full evidence + hypothesis for a failure."""
    evidence = _collect_evidence(failure, trace, sandbox, test_run)
    graph = graph or {"modules": [], "edges": []}
    related = related_tests(failure, graph)
    hypothesis = _rule_hypothesis(sandbox, failure, events, evidence)
    hypothesis["related_tests"] = related
    hypothesis["severity"] = failure.get("severity", "MEDIUM")
    return hypothesis


def related_tests(failure: dict, graph: dict) -> list[str]:
    """Tests that import the module containing the failing file."""
    file = (failure.get("file") or "").replace("\\", "/")
    mod = file[: -len(".py")].replace("/", ".") if file.endswith(".py") else file
    if not mod:
        return []
    edges = graph.get("edges", [])
    modules = graph.get("modules", [])
    importers = [a for (a, b) in edges if b == mod]
    out = []
    for imp in importers:
        if "test" in imp.lower():
            out.append(imp)
    # test files that live under tests/ dirs regardless of import graph
    return sorted(set(out))[:10]


# ------------------------------------------------------------------ rules
def _rule_hypothesis(sandbox: Sandbox, failure: dict, events: list[dict],
                     evidence: list[dict]) -> dict:
    err = (failure.get("error_type") or "").lower()
    msg = failure.get("error_msg") or ""
    file = failure.get("file") or ""
    line = failure.get("line") or 0
    src = _module_text(sandbox, file)
    fl = _failing_line(src, line)

    if "typeerror" in err and "none" in msg.lower():
        return _rule_none_subscript(sandbox, failure, src, fl, evidence)
    if "attributeerror" in err and "none" in msg.lower():
        return _rule_none_attribute(failure, src, fl, evidence)
    if "indexerror" in err or ("index" in msg and "range" in msg):
        return _rule_off_by_one(failure, src, fl, evidence)
    if "keyerror" in err:
        return _rule_key_error(failure, src, fl, evidence, events)
    if "no such column" in msg.lower():
        return _rule_sql_column(sandbox, failure, src, fl, evidence)
    if "assert" in err and any("hash_password" in t for t in _all_python_texts(sandbox)):
        return _rule_auth_hash(sandbox, failure, src, fl, evidence, events)
    return _rule_fallback(failure, src, fl, evidence)


def _rule_none_subscript(sandbox, failure, src, fl, evidence):
    var = _subscript_var(fl)
    body = _function_body(src, failure.get("line") or 0)
    assign = _assignment_source(body, var, (failure.get("line") or 0) - (src.splitlines().index(fl) if fl in src else 0)) if var else None
    # simpler: find assignment by searching body before failing line
    assign = None
    if var and body:
        failing_idx = body.find(fl)
        prefix = body[:failing_idx] if failing_idx >= 0 else body
        m = re.search(rf"^\s*{re.escape(var)}\s*=\s*(.+)$", prefix, re.M)
        assign = m.group(1).strip() if m else None
    call = _call_name(assign) if assign else None
    confident = False
    if call:
        mod = _module_text_for_call(sandbox, failure, call)
        confident = bool(mod and _has_return_none(mod))
    conf = 0.9 if confident else 0.72
    explanation = (f"{var} can be None here: it is assigned from {assign or 'a call'} whose result is "
                   f"not validated before subscripting `{fl.strip()}`.")
    root = f"{var} is None when `{fl.strip()}` executes"
    return {
        "root_cause": root,
        "explanation": explanation,
        "confidence": conf,
        "risk": "LOW",
        "rule": "none_subscript",
        "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                 "text": f"`{var}` is assigned from {assign or 'a call'}; the failing line "
                                         f"subscribes it without a None check."}],
        "patch_hint": {"rule": "none_subscript", "file": failure.get("file"),
                       "line": failure.get("line"), "var": var},
    }


def _all_python_texts(sandbox: Sandbox) -> list[str]:
    texts = []
    for p in sandbox.root.rglob("*.py"):
        if ".repro" in str(p) or "__pycache__" in str(p):
            continue
        try:
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    return texts


def _module_text_for_call(sandbox: Sandbox, failure: dict, call: str) -> str:
    """Find the source of a called function defined in the same module."""
    file = failure.get("file") or ""
    text = _module_text(sandbox, file)
    if f"def {call}" in text:
        return text
    # search other project files
    for p in sandbox.root.rglob("*.py"):
        if ".repro" in str(p) or "__pycache__" in str(p):
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if f"def {call}" in t:
            return t
    return ""


def _rule_none_attribute(failure, src, fl, evidence):
    var = None
    m = re.search(r"([A-Za-z_][\w.]*)\.", fl)
    if m:
        var = m.group(1).split(".")[0]
    return {
        "root_cause": f"{var or 'value'} is None when `{fl.strip()}` executes",
        "explanation": f"The code calls a method/attribute on a value that was None at runtime "
                       f"({failure.get('error_msg')}). A guard is needed before the failing line.",
        "confidence": 0.75,
        "risk": "LOW",
        "rule": "none_attribute",
        "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                 "text": "Attribute access on a None value at runtime."}],
        "patch_hint": {"rule": "none_attribute", "file": failure.get("file"),
                       "line": failure.get("line"), "var": var},
    }


def _rule_off_by_one(failure, src, fl, evidence):
    body = _function_body(src, failure.get("line") or 0)
    m = re.search(r"\[(\w+)\s*\+\s*1\]", fl)
    if not m:
        m = re.search(r"\[(\w+)\s*-\s*1\]", fl)
    idx = m.group(1) if m else None
    loop = None
    if idx:
        lm = re.search(rf"for\s+{re.escape(idx)}\s+in\s+range\(len\((\w+)\)\)", body)
        if lm:
            loop = lm.group(0)
    if loop and "+ 1" in fl:
        return {
            "root_cause": f"Off-by-one: `{fl.strip()}` indexes past the end inside `{loop}`",
            "explanation": f"The loop iterates over every index of the sequence, but the body accesses "
                           f"`{idx} + 1`, which is out of range on the final iteration. The loop should "
                           f"stop one element earlier.",
            "confidence": 0.9,
            "risk": "LOW",
            "rule": "off_by_one_range",
            "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                     "text": f"`{loop}` accesses `{idx}+1` on the last element → IndexError."}],
            "patch_hint": {"rule": "off_by_one_range", "file": failure.get("file"),
                           "line": failure.get("line"), "idx": idx},
        }
    return {
        "root_cause": f"IndexError at `{fl.strip()}`",
        "explanation": "An index was out of range at runtime; the code likely assumes the sequence "
                       "is longer than it is.",
        "confidence": 0.5,
        "risk": "MEDIUM",
        "rule": "index_range_generic",
        "evidence": evidence,
        "patch_hint": None,
    }


def _rule_key_error(failure, src, fl, evidence, events):
    msg = failure.get("error_msg") or ""
    m = re.search(r"KeyError:\s*['\"]([^'\"]+)['\"]", msg)
    if not m:
        m = re.search(r"['\"]([^'\"]+)['\"]", msg)
    if not m:
        m = re.search(r"KeyError:\s*(\w+)", msg)
    key = m.group(1) if m else None
    var = _subscript_var(fl)
    replacement = None
    # Evidence-first: find a traced dict return that has keys
    for e in events:
        if e.get("event") == "return":
            keys = _dict_keys_from_repr(e.get("return") or "")
            if keys and key not in keys:
                replacement = keys[0]
                break
    if replacement:
        return {
            "root_cause": f"Wrong response key: `{fl.strip()}` reads '{key}' but the value has '{replacement}'",
            "explanation": f"The traced runtime value is a dict with keys {replacement} — the code reads "
                           f"'{key}', which does not exist. This is an API response-shape mismatch.",
            "confidence": 0.85,
            "risk": "LOW",
            "rule": "key_fix_traced",
            "evidence": evidence + [{"kind": "observed", "source": "runtime trace",
                                     "text": f"Traced dict value contains key '{replacement}' but not '{key}'."}],
            "patch_hint": {"rule": "key_fix", "file": failure.get("file"),
                           "line": failure.get("line"), "old_key": key, "new_key": replacement},
        }
    return {
        "root_cause": f"Missing key '{key}' at `{fl.strip()}`",
        "explanation": "A dict access used a key that does not exist in the runtime value.",
        "confidence": 0.5,
        "risk": "MEDIUM",
        "rule": "key_error_generic",
        "evidence": evidence,
        "patch_hint": None,
    }


def _rule_sql_column(sandbox, failure, src, fl, evidence):
    m = re.search(r"no such column:\s*(\w+)", failure.get("error_msg") or "")
    missing = m.group(1) if m else None
    columns = []
    for text in _all_python_texts(sandbox):
        for cm in re.finditer(r"CREATE\s+TABLE[^;]*?\(([^)]*)\)", text, re.S | re.I):
            for col in re.findall(r'^\s*["\']?\s*(\w+)\s', cm.group(1), re.M):
                columns.append(col)
    columns = list(dict.fromkeys(columns))
    replacement = None
    if columns and missing:
        # prefer a column matching the SQL parameter variable near the failing line
        param = None
        pm = re.search(r"\((\w+),?\)", fl)
        if pm:
            param = pm.group(1)
        if param and param in columns:
            replacement = param
        else:
            for c in columns:
                if c != missing and c != "id":
                    replacement = c
                    break
    if replacement:
        return {
            "root_cause": f"SQL query references column '{missing}' which does not exist in the table",
            "explanation": f"The query in `{fl.strip()}` uses column '{missing}', but the schema "
                           f"(CREATE TABLE in the same module) defines {columns}. The intended column "
                           f"is likely '{replacement}'.",
            "confidence": 0.85,
            "risk": "LOW",
            "rule": "sql_column_fix",
            "evidence": evidence + [{"kind": "observed", "source": "schema",
                                     "text": f"Table columns: {columns}"}],
            "patch_hint": {"rule": "sql_column_fix", "file": failure.get("file"),
                           "line": failure.get("line"), "missing": missing, "replacement": replacement},
        }
    return {
        "root_cause": f"SQL error: {failure.get('error_msg')}",
        "explanation": "The executed SQL references a column that does not exist in the schema.",
        "confidence": 0.6,
        "risk": "MEDIUM",
        "rule": "sql_generic",
        "evidence": evidence,
        "patch_hint": None,
    }


def _rule_auth_hash(sandbox, failure, src, fl, evidence, events):
    # The failing line is usually in the test file (assert). Find the module
    # function the test called, from the real runtime trace.
    target_file, target_line = failure.get("file"), failure.get("line")
    for e in events:
        if e.get("event") == "call" and e.get("file") and "test" not in e.get("file", "").lower():
            target_file = e.get("file")
            target_line = e.get("line")
            break
    mod_text = _module_text(sandbox, target_file or "")
    if not mod_text:
        return _rule_fallback(failure, src, fl, evidence)
    # find the plaintext comparison inside the target module
    lines = mod_text.splitlines()
    cmp_line = None
    for i, l in enumerate(lines, start=1):
        if "==" in l and "password" in l:
            cmp_line = i
            break
    if not cmp_line:
        return _rule_fallback(failure, src, fl, evidence)
    cmp = lines[cmp_line - 1]
    return {
        "root_cause": "Password compared in plaintext instead of via the hash function",
        "explanation": f"`{cmp.strip()}` compares the raw password with the stored value, but the module "
                       f"defines `hash_password` — stored credentials are hashed, so the comparison must "
                       f"hash the incoming password first.",
        "confidence": 0.8,
        "risk": "MEDIUM",
        "rule": "auth_hash",
        "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                 "text": "Module defines hash_password() but the failing comparison uses the raw password."}],
        "patch_hint": {"rule": "auth_hash", "file": target_file, "line": cmp_line},
    }


def _rule_fallback(failure, src, fl, evidence):
    return {
        "root_cause": f"Failure in {failure.get('file')}:{failure.get('line')}",
        "explanation": (f"{failure.get('error_type')}: {failure.get('error_msg')}. "
                        f"No deterministic repair rule matched this failure class; an LLM provider "
                        f"is required for confident repair."),
        "confidence": 0.4,
        "risk": "HIGH",
        "rule": "fallback",
        "evidence": evidence,
        "patch_hint": None,
    }
