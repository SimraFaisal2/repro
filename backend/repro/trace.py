"""Runtime tracing.

The failing test is re-run with a Python-level tracer (sys.settrace) that
records every call/return/exception inside the repository, so the trace
shown in the UI is real execution evidence: actual function arguments,
actual return values, real call order and durations. Nothing is guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

from .sandbox import Sandbox

_RUNNER = r"""
import sys, os, json, time
import pytest

repo_root = os.path.abspath(os.environ["REPRO_REPO_ROOT"])
events = []
order = [0]
t0 = time.time()

def _trunc(x, n=140):
    try:
        s = repr(x)
    except Exception:
        s = "<unrepresentable>"
    return s[:n]

def _args(frame):
    out = {}
    for k, v in frame.f_locals.items():
        if k in ("self", "cls", "frame", "tb", "exc", "e"):
            out[k] = "<frame/local>"
        else:
            out[k] = _trunc(v, 110)
        if len(out) >= 10:
            break
    return out

_cache = {}

def tracer(frame, event, arg):
    fname = frame.f_code.co_filename
    inside = _cache.get(fname)
    if inside is None:
        try:
            absf = os.path.abspath(fname)
            inside = (not fname.startswith("<")
                      and os.path.isfile(fname)
                      and absf.startswith(repo_root + os.sep))
        except Exception:
            inside = False
        _cache[fname] = inside
    if not inside:
        return None
    order[0] += 1
    rec = {"order": order[0], "event": event, "func": frame.f_code.co_name,
           "file": os.path.relpath(fname, repo_root).replace("\\", "/"),
           "line": frame.f_lineno, "ts": round(time.time() - t0, 5)}
    if event == "call":
        rec["args"] = _args(frame)
        events.append(rec)
        return tracer
    elif event == "return":
        rec["return"] = _trunc(arg, 160)
        events.append(rec)
    elif event == "exception":
        exc = arg[1] if arg else None
        rec["exception"] = (f"{type(exc).__name__}: {exc}" if exc else "")[:300]
        events.append(rec)
    return tracer

sys.settrace(tracer)
code = pytest.main([
    os.environ.get("REPRO_TEST_ID", ""),
    "-p", "no:cacheprovider", "--no-header", "--tb=long", "-q", "--disable-warnings",
])
sys.settrace(None)
with open(os.environ.get("REPRO_TRACE_OUT", "trace.json"), "w", encoding="utf-8") as f:
    json.dump({"exit_code": code, "events": events}, f)
print("TRACE_DONE")
"""


def run_traced(sandbox: Sandbox, test_id: str, timeout: int | None = None) -> dict:
    """Re-run one failing test under the tracer. Returns the raw event log."""
    runner = sandbox.root / "repro_trace_runner.py"
    out_file = sandbox.root / "repro_trace.json"
    runner.write_text(_RUNNER, encoding="utf-8")
    if out_file.exists():
        out_file.unlink()
    proc = sandbox.run_python(
        [str(runner)],
        timeout=timeout or 90,
        extra_env={"REPRO_TEST_ID": test_id, "REPRO_TRACE_OUT": str(out_file),
                   "REPRO_REPO_ROOT": str(sandbox.root),
                   "PYTHONPATH": str(sandbox.root)},
    )
    data = {"exit_code": -1, "events": []}
    if out_file.exists():
        try:
            data = json.loads(out_file.read_text(encoding="utf-8"))
        except Exception:
            data = {"exit_code": -1, "events": []}
    data["stderr_tail"] = (proc.stderr or "")[-3000:]
    return data


def build_trace(failure: dict, events: list[dict], sandbox: Sandbox) -> list[dict]:
    """Enrich the real traceback frames with traced args/returns/timings."""
    frames = failure.get("frames") or []
    calls = [e for e in events if e.get("event") == "call"]
    by_order = {e.get("order"): e for e in events}

    def norm(p: str) -> str:
        return (p or "").replace("\\", "/")

    def find_call(file: str, func: str) -> dict | None:
        f = norm(file)
        for c in calls:
            if norm(c.get("file")) == f and c.get("func") == func:
                return c
        return None

    def find_return(call: dict) -> dict | None:
        """The next return event for the same function after this call."""
        for e in events:
            if (e.get("event") == "return" and e.get("func") == call.get("func")
                    and (e.get("order") or 0) > (call.get("order") or 0)):
                return e
        return None

    out: list[dict] = []
    for fr in frames:
        file, line, func = fr.get("file", ""), fr.get("line"), fr.get("func", "")
        call = find_call(file, func)
        line = line or 0
        ret = find_return(call) if call else None
        exec_time = None
        if call and ret and call.get("ts") is not None:
            exec_time = round(max(ret.get("ts", 0) - call.get("ts", 0), 0.0), 4)
        out.append({
            "func": func,
            "file": file,
            "line": line,
            "args": (call or {}).get("args") or {},
            "return_value": (ret or {}).get("return"),
            "exec_time": exec_time,
            "exception": None,
            "source": _source_snippet(sandbox, file, line),
        })
    # mark the erroring line in the deepest frame
    if out:
        out[-1]["exception"] = f"{failure.get('error_type')}: {failure.get('error_msg')}".strip()
        src = out[-1].get("source") or []
        for s in src:
            if s.get("line") == out[-1]["line"]:
                s["failing"] = True
    return out


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
