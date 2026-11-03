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


# ------------------------------------------------- repair-rule evidence helpers
# Rules are keyed on the runtime error signature plus the failing test's
# *declared contract* (its literal inputs and expected value), never on a
# corpus id — tests are the specification the code is supposed to satisfy.
_MISSING = object()
_INPLACE_MUTATORS = ("sort", "append", "extend", "reverse", "insert", "update",
                     "remove", "clear", "add", "discard")


def _literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:  # noqa: BLE001 — not a literal expression
        return _MISSING


def _dotted_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _resolve(node, locals_map: dict) -> object:
    """Literal value of a test expression, following simple local names."""
    value = _literal(node)
    if value is not _MISSING:
        return value
    if isinstance(node, ast.Name):
        return locals_map.get(node.id, _MISSING)
    return _MISSING


def _test_contract(sandbox: Sandbox, failure: dict) -> dict:
    """Mine the failing test's declared contract from its source.

    A test states which exception must propagate (`pytest.raises`), which
    literal inputs it exercises, and what output it expects. Reading that is
    observed evidence about the intended behaviour, not a guess.
    """
    test_id = failure.get("test_id") or ""
    if "::" not in test_id:
        return {}
    file, func = test_id.split("::", 1)
    func = func.split("[")[0]
    text = _module_text(sandbox, file)
    if not text:
        return {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == func), None)
    if fn is None:
        return {}
    contract: dict = {"test_file": file, "test_func": func, "raises": "",
                      "call_name": "", "assertions": []}
    # Literal locals (e.g. `sales = [{...}, ...]`) let an assertion's inputs be
    # read as data even when the test passes them by name.
    locals_map: dict[str, object] = {}
    for node in ast.walk(fn):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            value = _literal(node.value)
            if value is not _MISSING:
                locals_map[node.targets[0].id] = value
    for node in ast.walk(fn):
        if isinstance(node, ast.With):
            for item in node.items:
                c = item.context_expr
                if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "raises" and c.args:
                    contract["raises"] = _dotted_name(c.args[0])
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Attribute):
            contract["call_name"] = contract["call_name"] or getattr(node.func, "id", "")
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
            cmp = node.test
            left, right = cmp.left, cmp.comparators[0]
            if isinstance(left, ast.Call):
                contract["call_name"] = contract["call_name"] or getattr(left.func, "id", "")
                arg = _resolve(left.args[0], locals_map) if left.args else _MISSING
            else:
                arg = _resolve(left, locals_map)
            contract["assertions"].append({"arg": arg, "expected": _resolve(right, locals_map)})
    return contract


def _traced_sources(events: list[dict]) -> list[tuple[str, str]]:
    """Project functions the failing test actually reached, in call order."""
    out: list[tuple[str, str]] = []
    for e in events or []:
        if e.get("event") != "call":
            continue
        file, func = e.get("file") or "", e.get("func") or ""
        # Skip test frames and pseudo-frames: the tracer records "<module>"
        # for import-time calls, which names no real function to inspect.
        if not file or "test" in file.lower() or not re.fullmatch(r"[A-Za-z_]\w*", func):
            continue
        if (file, func) not in out:
            out.append((file, func))
    return out


def _test_imported_modules(sandbox: Sandbox, failure: dict) -> list[str]:
    """Project modules the failing test imports — the code under test."""
    test_file = (failure.get("test_id") or "").split("::")[0]
    text = _module_text(sandbox, test_file)
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    files: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            rel = node.module.replace(".", "/") + ".py"
            if (sandbox.root / rel).exists() and rel not in files:
                files.append(rel)
    return files


def _candidate_sources(sandbox: Sandbox, failure: dict, events: list[dict],
                       contract: dict | None = None) -> list[tuple[str, str]]:
    """Functions worth inspecting, strongest evidence first.

    Threaded tests may not appear in the trace at all (work happens on worker
    threads), so the module the test imports is used as a fallback source of
    candidates.
    """
    out = _traced_sources(events)
    name = (contract or {}).get("call_name") or ""
    if name:
        for p in sandbox.root.rglob("*.py"):
            sp = str(p).lower()
            if "test" in sp or ".repro" in sp or "__pycache__" in sp:
                continue
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if re.search(rf"^\s*def\s+{re.escape(name)}\s*\(", t, re.M):
                rel = str(p.relative_to(sandbox.root)).replace("\\", "/")
                if (rel, name) not in out:
                    out.append((rel, name))
    for rel in _test_imported_modules(sandbox, failure):
        try:
            tree = ast.parse((sandbox.root / rel).read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and (rel, n.name) not in out:
                out.append((rel, n.name))
    return out


def _called_source(sandbox: Sandbox, failure: dict, events: list[dict],
                   contract: dict | None = None) -> tuple[str, str]:
    # Prefer what really executed: a broader candidate list must never make a
    # rule inspect code the test did not run.
    cands = _traced_sources(events) or _candidate_sources(sandbox, failure, events, contract)
    if not cands:
        return "", ""
    # The innermost project function the test reached is the one that failed;
    # a constructor is a weaker signal than a regular method.
    non_init = [c for c in cands if c[1] != "__init__"]
    return (non_init or cands)[-1]


def _function_span(sandbox: Sandbox, file: str, func: str) -> tuple[int, list[str]]:
    """(1-based line where the function starts, its source lines)."""
    text = _module_text(sandbox, file)
    if not text:
        return 0, []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0, []
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == func:
            lines = text.splitlines()
            return n.lineno, lines[n.lineno - 1:(n.end_lineno or n.lineno)]
    return 0, []


def _initial_state(sandbox: Sandbox, file: str, func: str, attr: str) -> str:
    """The initial value of `self.<attr>` from the class' `__init__`."""
    text = _module_text(sandbox, file)
    if not text:
        return ""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        if not any(isinstance(n, ast.FunctionDef) and n.name == func for n in cls.body):
            continue
        for n in cls.body:
            if not (isinstance(n, ast.FunctionDef) and n.name == "__init__"):
                continue
            for st in ast.walk(n):
                if not isinstance(st, ast.Assign) or len(st.targets) != 1:
                    continue
                t = st.targets[0]
                if (isinstance(t, ast.Attribute) and t.attr == attr
                        and isinstance(t.value, ast.Name) and t.value.id == "self"):
                    value = _literal(st.value)
                    if isinstance(value, str):
                        return value
    return ""


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

    contract = _test_contract(sandbox, failure)

    if "typeerror" in err and "none" in msg.lower():
        return _rule_none_subscript(sandbox, failure, src, fl, evidence)
    if "typeerror" in err and "not subscriptable" in msg.lower():
        return _rule_not_subscriptable(failure, src, fl, evidence)
    if "typeerror" in err and ("can only concatenate str" in msg.lower()
                               or ("unsupported operand type" in msg.lower()
                                   and "'str'" in msg.lower())):
        return _rule_str_concat(failure, src, fl, evidence)
    if "attributeerror" in err and "none" in msg.lower():
        return _rule_none_attribute(failure, src, fl, evidence)
    if "zerodivision" in err or "division by zero" in msg.lower():
        return _rule_empty_guard(failure, src, fl, contract, evidence)
    if "indexerror" in err or ("index" in msg and "range" in msg):
        return _rule_off_by_one(failure, src, fl, evidence)
    if "keyerror" in err:
        return _rule_key_error(failure, src, fl, evidence, events)
    if "no such column" in msg.lower():
        return _rule_sql_column(sandbox, failure, src, fl, evidence)
    if "did not raise" in msg.lower():
        return (_rule_broad_except(sandbox, failure, contract, events, evidence)
                or _rule_fallback(failure, src, fl, evidence))
    if "assert" in err and any("hash_password" in t for t in _all_python_texts(sandbox)):
        return _rule_auth_hash(sandbox, failure, src, fl, evidence, events)
    if "assert" in err:
        return (_rule_inplace_mutator(sandbox, failure, contract, events, evidence)
                or _rule_boundary_condition(sandbox, failure, contract, events, evidence)
                or _rule_wrong_field_aggregation(sandbox, failure, contract, events, evidence)
                or _rule_state_transition(sandbox, failure, contract, events, evidence)
                or _rule_lock_read_modify_write(sandbox, failure, contract, events, evidence)
                or _rule_fallback(failure, src, fl, evidence))
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


def _rule_str_concat(failure, src, fl, evidence):
    """`"text" + count` where count is an int — coerce the non-string operand."""
    stripped = fl.strip()
    m = re.search(r"['\"]\s*\+\s*([A-Za-z_]\w*)\s*$", stripped)
    side = "right"
    if not m:
        m = re.search(r"^([A-Za-z_]\w*)\s*\+\s*['\"]", stripped)
        side = "left"
    if not m:
        return None
    var = m.group(1)
    return {
        "root_cause": f"String concatenation with a non-string value: `{stripped}`",
        "explanation": f"`{var}` is an int at runtime, and Python cannot concatenate str and int "
                       f"with `+`. Convert it explicitly (str({var})) so the expression builds "
                       f"the intended string.",
        "confidence": 0.85,
        "risk": "LOW",
        "rule": "str_concat_type",
        "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                 "text": f"The `+` operand `{var}` is not a str; the TypeError comes "
                                         f"from implicit concatenation."}],
        "patch_hint": {"rule": "str_concat_type", "file": failure.get("file"),
                       "line": failure.get("line"), "var": var, "side": side},
    }


def _rule_not_subscriptable(failure, src, fl, evidence):
    """Subscripting a generator/iterator — consume the first element instead."""
    var = _subscript_var(fl)
    if not var:
        return None
    return {
        "root_cause": f"`{var}` is a lazy iterator, not a sequence, so `{fl.strip()}` raises",
        "explanation": f"The value returned by the dependency is a generator/iterator. It supports "
                       f"`next(iter(...))` but not subscripting, so the first element must be consumed "
                       f"rather than indexed. This also keeps working for real sequences.",
        "confidence": 0.8,
        "risk": "LOW",
        "rule": "not_subscriptable_iter",
        "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                 "text": f"`{var}` is indexed but is not subscriptable at runtime."}],
        "patch_hint": {"rule": "not_subscriptable_iter", "file": failure.get("file"),
                       "line": failure.get("line"), "var": var},
    }


def _rule_empty_guard(failure, src, fl, contract, evidence):
    """ZeroDivisionError on an unguarded empty sequence — restore the guard."""
    m = re.search(r"len\(([A-Za-z_]\w*)\)", fl)
    if not m:
        return None
    var = m.group(1)
    default = 0
    for a in (contract or {}).get("assertions", []):
        arg, exp = a.get("arg"), a.get("expected")
        if arg is _MISSING or exp is _MISSING:
            continue
        if isinstance(arg, (list, tuple, dict, str)) and len(arg) == 0 \
                and isinstance(exp, (int, float)) and not isinstance(exp, bool):
            default = exp
            break
    return {
        "root_cause": f"`{fl.strip()}` divides by the length of `{var}` without guarding the empty case",
        "explanation": f"The function divides by `len({var})`, which is zero for empty input, so the "
                       f"previously-handled empty case now raises ZeroDivisionError. An early return "
                       f"restores that guard.",
        "confidence": 0.85,
        "risk": "LOW",
        "rule": "empty_guard_zerodiv",
        "evidence": evidence + [{"kind": "observed", "source": "failing test contract",
                                 "text": f"The empty input is expected to return {default!r}."}],
        "patch_hint": {"rule": "empty_guard_zerodiv", "file": failure.get("file"),
                       "line": failure.get("line"), "var": var, "default": default},
    }


def _rule_inplace_mutator(sandbox, failure, contract, events, evidence):
    """`return xs.sort()` returns None — the in-place call mutates xs itself."""
    file, func = _called_source(sandbox, failure, events, contract)
    start, body = _function_span(sandbox, file, func)
    for i, l in enumerate(body):
        m = re.match(r"^(\s*)return\s+([A-Za-z_]\w*)\.(\w+)\s*\((.*)\)\s*$", l)
        if not m or m.group(3) not in _INPLACE_MUTATORS:
            continue
        target, mut, args = m.group(2), m.group(3), m.group(4)
        return {
            "root_cause": f"`{target}.{mut}(...)` mutates in place and returns None, but its result "
                          f"is returned to the caller",
            "explanation": f"`{l.strip()}` returns the result of the in-place `{mut}()` call, which is "
                           f"always None. The method mutates `{target}` itself, so the fix is to perform "
                           f"the call and then return `{target}`.",
            "confidence": 0.9,
            "risk": "LOW",
            "rule": "inplace_mutator_return",
            "evidence": evidence + [{"kind": "inferred", "source": "static analysis",
                                     "text": f"`{mut}()` is an in-place mutator that returns None, but its "
                                             f"return value is used."}],
            "patch_hint": {"rule": "inplace_mutator_return", "file": file, "line": start + i,
                           "target": target, "mutator": mut, "args": args},
        }
    return None


def _rule_boundary_condition(sandbox, failure, contract, events, evidence):
    """Boundary value excluded by a strict comparison (18 rejected by `age > 18`)."""
    pairs = [a for a in (contract or {}).get("assertions", [])
             if a.get("arg") is not _MISSING and isinstance(a.get("expected"), bool)]
    if not pairs:
        return None
    file, func = _called_source(sandbox, failure, events, contract)
    start, body = _function_span(sandbox, file, func)
    flip = {">": ">=", ">=": ">", "<": "<=", "<=": "<"}
    for i, l in enumerate(body):
        m = re.search(r"([A-Za-z_]\w*)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", l)
        if not m:
            continue
        op, literal = m.group(2), m.group(3)
        for a in pairs:
            try:
                if float(literal) != float(a["arg"]):
                    continue
            except (TypeError, ValueError):
                continue
            wanted = a["expected"]
            if not ((wanted and op in (">", "<")) or (not wanted and op in (">=", "<="))):
                continue
            return {
                "root_cause": f"Boundary value {literal} is excluded by the strict comparison "
                              f"`{l.strip()}`",
                "explanation": f"The test requires the boundary value {literal} to be handled as "
                               f"{wanted}, but `{m.group(0).strip()}` excludes it. An inclusive "
                               f"comparison ({flip[op]}) includes the boundary without changing "
                               f"behaviour for any other input.",
                "confidence": 0.75,
                "risk": "LOW",
                "rule": "boundary_comparison",
                "evidence": evidence + [{"kind": "observed", "source": "failing test contract",
                                         "text": f"{func}({literal}) must be {wanted}."}],
                "patch_hint": {"rule": "boundary_comparison", "file": file, "line": start + i,
                               "old_op": op, "new_op": flip[op], "literal": literal},
            }
    return None


def _rule_broad_except(sandbox, failure, contract, events, evidence):
    """A broad `except` swallows a failure the caller must see — re-raise it."""
    exc = (contract or {}).get("raises") or ""
    if not exc:
        return None
    file, func = _called_source(sandbox, failure, events, contract)
    start, body = _function_span(sandbox, file, func)
    for i, l in enumerate(body):
        m = re.match(r"^(\s*)except\b", l)
        if not m:
            continue
        base = len(m.group(1))
        for j in range(i + 1, len(body)):
            bl = body[j]
            if not bl.strip():
                continue
            if len(bl) - len(bl.lstrip()) <= base:
                break
            if re.match(r"^\s*(return\s+None|pass)\s*$", bl):
                return {
                    "root_cause": f"`{func}()` swallows the real failure — `{l.strip()}` converts it "
                                  f"into {bl.strip()}",
                    "explanation": f"The test requires `{exc}` to propagate, but the handler catches it "
                                   f"and returns from the function instead. Re-raising preserves the error "
                                   f"for callers while leaving the handler structure intact.",
                    "confidence": 0.85,
                    "risk": "MEDIUM",
                    "rule": "broad_except_swallow",
                    "evidence": evidence + [{"kind": "observed", "source": "failing test contract",
                                             "text": f"`{exc}` must propagate out of {func}()."}],
                    "patch_hint": {"rule": "broad_except_swallow", "file": file,
                                   "line": start + j, "exc": exc},
                }
    return None


def _rule_wrong_field_aggregation(sandbox, failure, contract, events, evidence):
    """Aggregation sums the wrong field — derived from the test's own data.

    The expected mapping is arithmetic over the test's literal rows: exactly
    one (grouping key, value key) pair reproduces it. That identity is
    observed evidence, not a guess about the corpus.
    """
    rows = expected = None
    for a in (contract or {}).get("assertions", []):
        arg, exp = a.get("arg"), a.get("expected")
        if (isinstance(arg, list) and arg and all(isinstance(r, dict) for r in arg)
                and isinstance(exp, dict) and exp):
            rows, expected = arg, exp
            break
    if not rows:
        return None
    keys: set[str] = set()
    for r in rows:
        keys |= set(r)
    grouping = [k for k in keys if all(isinstance(r.get(k), str) for r in rows)]
    numeric = [k for k in keys
               if all(isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
                      for r in rows)]
    matches: list[tuple[str, str]] = []
    for gk in grouping:
        for vk in numeric:
            if vk == gk:
                continue
            acc: dict = {}
            for r in rows:
                acc[r[gk]] = acc.get(r[gk], 0) + r[vk]
            if acc == expected:
                matches.append((gk, vk))
    if len(matches) != 1:
        return None
    group_key, correct = matches[0]
    for file, func in _candidate_sources(sandbox, failure, events, contract):
        start, body = _function_span(sandbox, file, func)
        for i, l in enumerate(body):
            m = re.search(r"\[(['\"])(\w+)\1\]", l)
            if not m or "+" not in l or m.group(2) == correct or m.group(2) not in keys:
                continue
            wrong = m.group(2)
            return {
                "root_cause": f"Aggregation adds the `{wrong}` field where `{correct}` is required",
                "explanation": f"The accumulating line `{l.strip()}` sums `{wrong}`, but summing "
                               f"`{correct}` per `{group_key}` over the test's own rows reproduces the "
                               f"expected {expected!r} exactly, and `{wrong}` does not.",
                "confidence": 0.8,
                "risk": "LOW",
                "rule": "aggregation_field",
                "evidence": evidence + [{"kind": "observed", "source": "failing test contract",
                                         "text": f"Summing `{correct}` per `{group_key}` reproduces the "
                                                 f"expected values; `{wrong}` does not."}],
                "patch_hint": {"rule": "aggregation_field", "file": file, "line": start + i,
                               "old_key": wrong, "new_key": correct},
            }
    return None


def _rule_state_transition(sandbox, failure, contract, events, evidence):
    """A transition table skips a state the expected sequence requires."""
    seq = None
    for a in (contract or {}).get("assertions", []):
        exp = a.get("expected")
        if isinstance(exp, list) and len(exp) >= 2 and all(isinstance(x, str) for x in exp):
            seq = exp
            break
    if not seq:
        return None
    for file, func in _candidate_sources(sandbox, failure, events, contract):
        start, body = _function_span(sandbox, file, func)
        if not body:
            continue
        attr = ""
        transitions: dict[str, tuple[str, int]] = {}
        current = ""
        for i, l in enumerate(body):
            m = re.search(r"^\s*(?:el)?if\s+self\.(\w+)\s*==\s*['\"](\w+)['\"]\s*:", l)
            if m:
                attr, current = m.group(1), m.group(2)
                continue
            if not attr:
                continue
            m = re.search(rf"^\s*self\.{re.escape(attr)}\s*=\s*['\"](\w+)['\"]\s*$", l)
            if m and current:
                transitions[current] = (m.group(1), start + i)
                current = ""
        if not transitions:
            continue
        initial = _initial_state(sandbox, file, func, attr)
        if not initial:
            continue
        state, seen = initial, []
        for _ in range(len(seq)):
            seen.append(state)
            nxt = transitions.get(state)
            state = nxt[0] if nxt else state
        if seen == seq:
            continue
        # Every edge the expected cycle requires — not just the first mismatch,
        # because fixing one transition can expose the next missing one.
        required = list(dict.fromkeys(
            (seq[i - 1], seq[i]) for i in range(1, len(seq)) if seq[i - 1] != seq[i]))
        retarget: list[dict] = []
        missing: list[dict] = []
        for src_state, dst_state in required:
            current_target, line = transitions.get(src_state, ("", 0))
            if not current_target:
                missing.append({"src": src_state, "dst": dst_state})
            elif current_target != dst_state:
                retarget.append({"src": src_state, "line": line,
                                 "old": current_target, "new": dst_state})
        if not retarget and not missing:
            continue
        chain_indent, chain_end = "        ", 0
        for i, l in enumerate(body):
            m = re.search(rf"^(\s*)self\.{re.escape(attr)}\s*=\s*['\"]\w+['\"]\s*$", l)
            if m:
                chain_indent = m.group(1)[:-4] if len(m.group(1)) >= 4 else m.group(1)
                chain_end = start + i
        described = ", ".join(f"{a}->{b}" for a, b in required)
        return {
            "root_cause": f"Transition table in `{func}()` does not implement the required cycle "
                          f"({described})",
            "explanation": f"The expected sequence is {seq}, but walking the table yields {seen}. "
                           f"Required edges: {described} ({len(retarget)} to retarget, "
                           f"{len(missing)} missing).",
            "confidence": 0.75,
            "risk": "LOW",
            "rule": "state_transition_edges",
            "evidence": evidence + [{"kind": "observed", "source": "failing test contract",
                                     "text": f"Expected sequence {seq}; table produced {seen}."}],
            "patch_hint": {"rule": "state_transition_edges", "file": file, "attr": attr,
                           "retarget": retarget, "missing": missing,
                           "insert_after": chain_end, "indent": chain_indent,
                           # edits_from_hint requires an anchor line; the patch
                           # itself is driven by the retarget/insert lists
                           "line": retarget[0]["line"] if retarget else chain_end},
        }
    return None


def _rule_lock_read_modify_write(sandbox, failure, contract, events, evidence):
    """Unlocked read-modify-write on shared state, exercised by threads."""
    test_file = (failure.get("test_id") or "").split("::")[0]
    if "thread" not in _module_text(sandbox, test_file).lower():
        return None
    for file, func in _candidate_sources(sandbox, failure, events, contract):
        if "Lock" in _module_text(sandbox, file):
            continue
        start, body = _function_span(sandbox, file, func)
        for i, l in enumerate(body):
            m = re.match(r"^\s*(\w+)\s*=\s*self\.(\w+)\s*$", l)
            if not m:
                continue
            local, attr = m.group(1), m.group(2)
            for j in range(i + 1, len(body)):
                if re.match(rf"^\s*self\.{re.escape(attr)}\s*=\s*{re.escape(local)}\s*[+\-]\s*",
                            body[j]):
                    return {
                        "root_cause": f"`{func}()` performs an unlocked read-modify-write on "
                                      f"`self.{attr}`, so concurrent calls lose updates",
                        "explanation": f"The value is read into `{local}`, modified, and written back in "
                                       f"separate steps, which is not atomic: two threads can read the same "
                                       f"value and overwrite each other. The failing test drives this from "
                                       f"multiple threads, so the update must be protected by a lock.",
                        "confidence": 0.8,
                        "risk": "MEDIUM",
                        "rule": "lock_read_modify_write",
                        "evidence": evidence + [
                            {"kind": "observed", "source": "failing test",
                             "text": "The test calls this method from multiple threads."},
                            {"kind": "inferred", "source": "static analysis",
                             "text": f"`{l.strip()}` … `{body[j].strip()}` is a read-modify-write with no "
                                     f"lock in the module."}],
                        "patch_hint": {"rule": "lock_read_modify_write", "file": file,
                                       "line": start, "end": start + len(body) - 1,
                                       "attr": attr, "func": func},
                    }
    return None


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
