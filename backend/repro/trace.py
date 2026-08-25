"""Runtime tracing (v2).

The failing test is re-run with a Python-level tracer (sys.settrace) that
records a *structured execution trace* — a call tree, not just a flat list.
Each event knows its depth, its enclosing call (parent), and returns are
paired to the exact call they unwind via a LIFO stack, so recursion and
repeated calls are matched correctly.

The tracer answers WHY a failure happened, not merely that calls happened:

  * call          — function name, module, file, line, depth, parent, bounded args
  * return        — value + duration, paired to its call
  * line          — first visit to each line within a call (bounded; branch edges
                    are derived from non-sequential transitions in build_trace)
  * exception     — type, message, the redacted locals at the exact failure point,
                    and the call it fired inside

Values are summarized defensively: arbitrary objects are never repr'd (broken
``__repr__`` can raise), containers are size-capped, circular references are
guarded, secrets (password/token/key/...) are redacted, and the whole stream
is bounded by MAX_EVENTS / MAX_DEPTH. The event stream is deterministic and
JSON-serializable; the only measurement field is duration_ms.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .sandbox import Sandbox

# Default caps (the runner reads these from env so a host can tune them).
MAX_EVENTS = int(os.environ.get("REPRO_TRACE_MAX_EVENTS", "4000"))
MAX_DEPTH = int(os.environ.get("REPRO_TRACE_MAX_DEPTH", "60"))
MAX_LOCALS = int(os.environ.get("REPRO_TRACE_MAX_LOCALS", "12"))
BUDGET = int(os.environ.get("REPRO_TRACE_BUDGET", "120"))

_RUNNER = r"""
import sys, os, json, time
import pytest

repo_root = os.path.abspath(os.environ["REPRO_REPO_ROOT"])
max_events = int(os.environ.get("REPRO_TRACE_MAX_EVENTS", "4000"))
max_depth = int(os.environ.get("REPRO_TRACE_MAX_DEPTH", "60"))
max_locals = int(os.environ.get("REPRO_TRACE_MAX_LOCALS", "12"))
budget = int(os.environ.get("REPRO_TRACE_BUDGET", "120"))

events = []
order = [0]                 # strictly increasing sequence per emitted event
stack = []                  # LIFO of call event ids (None = depth-exceeded marker)
truncated = [False]
_start = {}                 # call id -> monotonic start (for duration_ms)

# ------------------------------------------------------------------ value safety
_REDACT = ("password", "passwd", "token", "secret", "apikey", "api_key",
           "authorization", "cookie", "credential")

def _redact(name):
    n = (name or "").lower()
    return any(k in n for k in _REDACT)


def _est_size(x, depth=0, limit=256):
    # Cheap, string-free estimate of a value's repr size. Used to avoid
    # building huge intermediate strings: a full repr is only attempted when
    # the estimate fits. Builds nothing, is bounded by depth + container
    # count caps (so cycles terminate), and arbitrary objects count as
    # "too big" (their __repr__ is never invoked).
    if depth > 3:
        return 0
    t = type(x)
    if x is None or t is bool:
        return 8
    if t in (int, float):
        return 16
    if t in (str, bytes):
        return min(len(x) + 2, limit)
    if t in (list, tuple, set, frozenset):
        if len(x) > 12:
            return limit
        return sum(_est_size(i, depth + 1, limit) for i in x)
    if t is dict:
        if len(x) > 12:
            return limit
        return sum(_est_size(k, depth + 1, limit) + _est_size(v, depth + 1, limit)
                   for k, v in x.items())
    return limit          # arbitrary object — treat as too big to repr


def _sum(x, budget=budget, depth=0, seen=None):
    # Bounded, guarded, cycle-safe value summarizer:
    #  - scalars (str/int/float/bool/bytes) are repr'd and truncated
    #  - huge containers are summarized by size, never dumped
    #  - small dicts keep a full repr when it fits AND a cheap size probe
    #    says the repr is bounded (preserves literal-eval key extraction
    #    used by the key_fix rule without building huge strings)
    #  - arbitrary objects are rendered as "<ClassName>" — their __repr__ is
    #    NEVER called (a broken __repr__ can raise or recurse forever)
    #  - circular references are guarded via a seen-id set
    if depth > 5:
        return "<deep>"
    seen = seen if seen is not None else set()
    oid = id(x)
    if oid in seen:
        return "<circular>"
    t = type(x)
    if x is None:
        return "None"
    if t in (bool, int, float):
        return repr(x)
    if t is str:
        s = repr(x)
        return s if len(s) <= budget else s[: budget - 1] + "..."
    if t is bytes:
        s = repr(x)
        return s if len(s) <= budget else s[: budget - 1] + "..."
    if t in (list, tuple, set, frozenset):
        if len(x) > 8:
            return "<%s len=%d>" % (t.__name__, len(x))
        seen.add(oid)
        try:
            items = [_sum(i, max(10, budget // 2), depth + 1, seen) for i in list(x)[:8]]
        finally:
            seen.discard(oid)
        if t is tuple:
            return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
        if t is set:
            return "{" + ", ".join(items) + "}"
        return "[" + ", ".join(items) + "]"
    if t is dict:
        if len(x) > 12:
            return "<dict len=%d>" % len(x)
        if _est_size(x, limit=256) <= 256:
            try:
                r = repr(x)      # builtin container repr is cycle-safe
                if len(r) <= budget:
                    return r
            except Exception:
                pass
        seen.add(oid)
        try:
            items = []
            for k, v in list(x.items())[:8]:
                ks = _sum(k, 20, depth + 1, seen)
                vs = _sum(v, max(10, budget // 2), depth + 1, seen)
                items.append(ks + ": " + vs)
        finally:
            seen.discard(oid)
        return "{" + ", ".join(items) + "}"
    # arbitrary object: never repr
    try:
        return "<" + t.__name__ + ">"
    except Exception:
        return "<obj>"


def _snapshot(frame, limit=max_locals):
    # Bounded, redacted locals snapshot (call entry or failure point).
    out = {}
    try:
        locals_ = frame.f_locals
    except Exception:
        return out
    for k, v in locals_.items():
        if k in ("self", "cls", "frame", "tb", "exc", "e", "__traceback__"):
            continue
        if _redact(k):
            out[k] = "<redacted>"
        else:
            out[k] = _sum(v, 110)
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ the tracer
_inside = {}

def tracer(frame, event, arg):
    fname = frame.f_code.co_filename
    inside = _inside.get(fname)
    if inside is None:
        try:
            absf = os.path.abspath(fname)
            inside = (not fname.startswith("<")
                      and os.path.isfile(fname)
                      and absf.startswith(repo_root + os.sep))
        except Exception:
            inside = False
        _inside[fname] = inside
    if not inside:
        # Returning None disables tracing *within this frame only*; the global
        # trace function is still consulted for every new frame entered, so
        # repo code called from pytest internals is still captured. This keeps
        # the tracer cheap on unfamiliar repositories (stdlib/pytest hot paths
        # are not traced line-by-line).
        return None
    if truncated[0]:
        return None              # cap reached — stop paying the tracing cost

    # line events: record only the first visit to each line within the
    # enclosing call (bounded by function size; loop iterations collapse)
    if event == "line":
        cid = stack[-1] if stack else None
        if cid is None:
            return tracer
        seen = _line_seen.get(cid)
        if seen is None:
            seen = _line_seen.setdefault(cid, set())
        if frame.f_lineno in seen:
            return tracer
        seen.add(frame.f_lineno)

    rel = os.path.relpath(fname, repo_root).replace("\\", "/")
    order[0] += 1
    depth = len(stack) - 1 if event != "call" else len(stack)
    parent = stack[-1] if stack else None
    rec = {"id": order[0], "order": order[0], "event": event,
           "func": frame.f_code.co_name,
           "module": rel[:-3].replace("/", ".") if rel.endswith(".py") else rel,
           "file": rel, "line": frame.f_lineno, "depth": depth,
           "parent": parent}

    if event == "call":
        if depth > max_depth:
            stack.append(None)   # depth-exceeded marker; not recorded
            return tracer
        rec["args"] = _snapshot(frame)
        events.append(rec)
        stack.append(rec["id"])
        _start[rec["id"]] = time.monotonic()
    elif event == "return":
        if not stack:
            return tracer
        cid = stack.pop()
        if cid is None:
            return tracer       # returning from a depth-exceeded call
        rec["call_id"] = cid
        try:
            rec["return"] = _sum(arg, 160)
        except Exception:
            rec["return"] = "<unrepresentable>"
        s = _start.pop(cid, None)
        if s is not None:
            rec["duration_ms"] = round((time.monotonic() - s) * 1000.0, 3)
        events.append(rec)
    elif event == "exception":
        if not stack:
            return tracer
        cid = stack[-1]
        if cid is None:
            return tracer
        exc = arg[1] if arg else None
        rec["call_id"] = cid
        rec["exc_type"] = type(exc).__name__ if exc is not None else ""
        try:
            rec["exc_msg"] = str(exc)[:300]
        except Exception:
            rec["exc_msg"] = "<unprintable>"
        rec["exception"] = (rec["exc_type"] + ": " + rec["exc_msg"])[:340]
        rec["locals"] = _snapshot(frame)      # values immediately before failure
        events.append(rec)
    elif event == "line":
        events.append(rec)
    else:
        return tracer

    if len(events) >= max_events:
        truncated[0] = True
        events.append({"event": "truncated", "order": order[0] + 1})
    return tracer


_line_seen = {}
sys.settrace(tracer)
code = pytest.main([
    os.environ.get("REPRO_TEST_ID", ""),
    "-p", "no:cacheprovider", "--no-header", "--tb=long", "-q", "--disable-warnings",
])
sys.settrace(None)
with open(os.environ.get("REPRO_TRACE_OUT", "trace.json"), "w", encoding="utf-8") as f:
    json.dump({"schema": 2, "truncated": truncated[0], "exit_code": code, "events": events}, f)
print("TRACE_DONE")
"""


def run_traced(sandbox: Sandbox, test_id: str, timeout: int | None = None) -> dict:
    """Re-run one failing test under the tracer. Returns the v2 event log."""
    runner = sandbox.root / "repro_trace_runner.py"
    out_file = sandbox.root / "repro_trace.json"
    runner.write_text(_RUNNER, encoding="utf-8")
    if out_file.exists():
        out_file.unlink()
    proc = sandbox.run_python(
        [str(runner)],
        timeout=timeout or 90,
        extra_env={
            "REPRO_TEST_ID": test_id,
            "REPRO_TRACE_OUT": str(out_file),
            "REPRO_REPO_ROOT": str(sandbox.root),
            "REPRO_TRACE_MAX_EVENTS": str(MAX_EVENTS),
            "REPRO_TRACE_MAX_DEPTH": str(MAX_DEPTH),
            "REPRO_TRACE_MAX_LOCALS": str(MAX_LOCALS),
            "REPRO_TRACE_BUDGET": str(BUDGET),
            "PYTHONPATH": str(sandbox.root),
        },
    )
    data = {"schema": 2, "truncated": False, "exit_code": -1, "events": []}
    if out_file.exists():
        try:
            data = json.loads(out_file.read_text(encoding="utf-8"))
        except Exception:
            data = {"schema": 2, "truncated": False, "exit_code": -1, "events": []}
    data["stderr_tail"] = (proc.stderr or "")[-3000:]
    return data


# ------------------------------------------------------------------ derivation
def _module_of(file: str) -> str:
    f = (file or "").replace("\\", "/")
    return f[:-3].replace("/", ".") if f.endswith(".py") else f


def build_trace(failure: dict, events: list[dict], sandbox: Sandbox,
                truncated: bool = False) -> dict:
    """Build the display trace {frames, slice, summary} from the v2 event log.

    - reconstructs the call tree (depth/parent/call_id)
    - pairs every return to its exact call
    - derives branch decisions from non-sequential line transitions
    - computes the minimal FAILURE SLICE: the root->failure call path
    - diffs call-time args vs failure-time locals for state changes
    """
    calls: dict[int, dict] = {}
    for e in events:
        if e.get("event") == "call" and e.get("id") is not None:
            calls[e["id"]] = e
    returns: dict[int, dict] = {
        e["call_id"]: e for e in events
        if e.get("event") == "return" and e.get("call_id") is not None
    }

    # failure event = the first exception event (deepest, where it was raised)
    fail_ev = next((e for e in events if e.get("event") == "exception"), None)

    # failure slice: walk parents from the failing call to the root
    path_ids: list[int] = []
    cid = (fail_ev or {}).get("call_id")
    while cid is not None and cid not in path_ids:
        path_ids.append(cid)
        c = calls.get(cid)
        cid = c.get("parent") if c else None
    path_ids.reverse()
    path_set = set(path_ids)

    # line visits per call -> branch edges (non-sequential transitions)
    lines_by_call: dict[int, list[int]] = {}
    for e in events:
        if e.get("event") == "line" and e.get("parent") is not None:
            lines_by_call.setdefault(e["parent"], []).append(e["line"])

    def branches_for(call_id: int | None) -> list[dict]:
        if call_id is None:
            return []
        ls = lines_by_call.get(call_id, [])
        out = []
        prev = None
        for ln in ls:
            if prev is not None and ln != prev + 1:
                out.append({"from": prev, "to": ln})
            prev = ln
        return out

    def norm(p: str) -> str:
        return (p or "").replace("\\", "/")

    def find_call(file: str, func: str) -> dict | None:
        f = norm(file)
        # prefer calls on the failure path (deepest match)
        for cid in reversed(path_ids):
            c = calls.get(cid)
            if c and norm(c.get("file")) == f and c.get("func") == func:
                return c
        # fallback: earliest call matching file+func
        for e in events:
            if (e.get("event") == "call" and norm(e.get("file")) == f
                    and e.get("func") == func and e.get("id") is not None):
                return e
        return None

    frames = failure.get("frames") or []
    out: list[dict] = []
    for fr in frames:
        file, line, func = fr.get("file", ""), fr.get("line"), fr.get("func", "")
        call = find_call(file, func)
        ret = returns.get(call["id"]) if call else None
        on_path = bool(call and call["id"] in path_set)

        state_changes: dict = {}
        if on_path and fail_ev and call and fail_ev.get("call_id") == call["id"]:
            args = call.get("args") or {}
            locs = fail_ev.get("locals") or {}
            for k, v in locs.items():
                if k in args and args[k] != v and k not in ("self", "cls"):
                    state_changes[k] = v

        out.append({
            "func": func,
            "module": _module_of(file),
            "file": file,
            "line": line or 0,
            "depth": (call or {}).get("depth"),
            "call_id": (call or {}).get("id"),
            "parent_id": (call or {}).get("parent"),
            "args": (call or {}).get("args") or {},
            "return_value": (ret or {}).get("return"),
            "duration_ms": (ret or {}).get("duration_ms"),
            "exception": None,
            "branches": branches_for((call or {}).get("id")) if call else [],
            "state_changes": state_changes,
            "in_slice": on_path,
            "traced": call is not None,
            "source": _source_snippet(sandbox, file, line),
        })

    # mark the erroring line in the deepest frame + attach failure locals
    # (always stamp the exception from the failure record — even when the
    # trace was truncated before an exception event, or the exception was
    # raised in an untraced frame). The locals/state_changes are attributed
    # to the exact frame the exception fired inside (fail_ev.call_id), so
    # "values at failure" and "state changes" always describe the same call.
    if out:
        out[-1]["exception"] = (fail_ev.get("exception") if fail_ev
                                else f"{failure.get('error_type')}: {failure.get('error_msg')}".strip())
        fail_frame = out[-1]
        if fail_ev and fail_ev.get("call_id") is not None:
            for f_ in out:
                if f_.get("call_id") == fail_ev.get("call_id"):
                    fail_frame = f_
                    break
        if fail_ev and fail_ev.get("locals"):
            fail_frame["locals"] = fail_ev.get("locals")
        if fail_ev and fail_ev.get("exc_type"):
            fail_frame["exc_type"] = fail_ev.get("exc_type")
        if fail_ev and fail_ev.get("exc_msg"):
            fail_frame["exc_msg"] = fail_ev.get("exc_msg")
        src = out[-1].get("source") or []
        for s in src:
            if s.get("line") == out[-1]["line"]:
                s["failing"] = True

    max_depth = max([f.get("depth") or 0 for f in out] + [0])
    n_branches = sum(len(f.get("branches") or []) for f in out)
    slice_path = []
    for cid in path_ids:
        c = calls.get(cid)
        if c:
            slice_path.append(f"{c.get('func')} ({c.get('file')}:{c.get('line')})")

    def _on_path(e: dict) -> bool:
        if e.get("event") == "call":
            return e.get("id") in path_set
        return e.get("parent") in path_set

    return {
        "schema": 2,
        "frames": out,
        "slice": {
            "path": slice_path,
            "events": sum(1 for e in events if _on_path(e)),
            "frames": sum(1 for f in out if f.get("in_slice")),
            "max_depth": max_depth,
        },
        "summary": {
            "calls": len(calls),
            "branches": n_branches,
            "max_depth": max_depth,
            "truncated": bool(truncated),
        },
    }


def _source_snippet(sandbox: Sandbox, file: str, line: int, radius: int = 6) -> list[dict]:
    p = sandbox.root / file
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out = []
    for ln in range(max(1, line - radius), min(len(lines), line + radius) + 1):
        out.append({"line": ln, "text": lines[ln - 1], "failing": False})
    return out
