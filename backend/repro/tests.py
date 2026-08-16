"""Test discovery + execution via pytest.

Everything here is grounded in real subprocess execution: counts come from
pytest's summary, failures are re-run individually with long tracebacks so
the stack frames, error type, file and line are genuine.
"""
from __future__ import annotations

import re
from pathlib import Path

from .sandbox import Sandbox

_FRAME_RE = re.compile(r"^(\S+\.py):(\d+): in (.+)$")
_ERR_RE = re.compile(r"^(\S+\.py):(\d+): ([\w.]+)(?:: (.*))?$")
_E_RE = re.compile(r"^E\s+(.+)$")
_SUMMARY_RE = re.compile(r"(\d+)\s+(passed|failed|error|skipped)")
_FAILED_LINE_RE = re.compile(r"^FAILED (\S+?)(?: - .*)?$", re.MULTILINE)


def _pp(sandbox: Sandbox) -> dict:
    """Make the repo root importable so `from src...` works like a dev install."""
    return {"PYTHONPATH": str(sandbox.root)}


def discover(sandbox: Sandbox) -> list[str]:
    """Return collected pytest node ids, e.g. tests/test_auth.py::test_login."""
    proc = sandbox.run_python(["-m", "pytest", "--collect-only", "-q",
                               "-p", "no:cacheprovider", "--no-header"],
                              extra_env=_pp(sandbox))
    ids: list[str] = []
    if proc.returncode != 0:
        return ids
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith(("=", "<", "no tests", "ERROR")):
            ids.append(line)
    return ids


def parse_summary(output: str) -> dict:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for m in _SUMMARY_RE.finditer(output):
        counts[m.group(2)] = int(m.group(1))
    return counts


def run_suite(sandbox: Sandbox, test_ids: list[str] | None = None,
              timeout: int | None = None) -> dict:
    """Run pytest (whole suite or a subset). Returns run + failure records."""
    args = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header",
            "--tb=line", "-rfE", "--disable-warnings"]
    if test_ids:
        args.extend(test_ids)
    proc = sandbox.run_python(args, timeout=timeout, extra_env=_pp(sandbox))
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    counts = parse_summary(output)
    # failed ids: "FAILED path::test - reason" lines (only present with -rA/-rN)
    failed_ids: list[str] = []
    for m in _FAILED_LINE_RE.finditer(output):
        failed_ids.append(m.group(1))
    total = sum(counts.values())
    return {
        "ok": proc.returncode in (0, 1),
        "returncode": proc.returncode,
        "total": total,
        "passed": counts["passed"],
        "failed": counts["failed"],
        "error": counts["error"],
        "skipped": counts["skipped"],
        "failed_ids": failed_ids,
        "duration": _duration_of(output),
        "output": output[-80_000:],
    }


def _duration_of(output: str) -> float:
    m = re.search(r"in ([\d.]+)s", output)
    return float(m.group(1)) if m else 0.0


def run_single(sandbox: Sandbox, test_id: str, timeout: int | None = None) -> dict:
    """Run one test with a long traceback and parse its failure precisely."""
    proc = sandbox.run_python(["-m", "pytest", test_id, "-p", "no:cacheprovider",
                               "--no-header", "--tb=long", "-q", "--disable-warnings"],
                              timeout=timeout, extra_env=_pp(sandbox))
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    counts = parse_summary(output)
    failed = counts["failed"] + counts["error"] > 0
    failure = parse_failure(output, test_id) if failed else None
    return {"ok": not failed, "failure": failure, "output": output[-60_000:],
            "duration": _duration_of(output)}


_ENTRY_RE = re.compile(r"^(\S+\.py):(\d+):(?:\s+in\s+(\w+))?\s*$")
_DEF_RE = re.compile(r"^def\s+(\w+)\s*\(")


def parse_failure(output: str, test_id: str) -> dict | None:
    """Extract the failure record (frames, error type, file, line) from output.

    Handles both pytest classic tracebacks (`path.py:12: in func`) and the
    pytest 8 entry-line format (`path.py:12:` with the `def` above it).
    """
    frames: list[dict] = []
    err_type = ""
    err_msg = ""
    e_lines: list[str] = []
    pending_func = ""
    for line in output.splitlines():
        s = line.strip()
        m = _FRAME_RE.match(s)
        if m:
            frames.append({"file": m.group(1), "line": int(m.group(2)), "func": m.group(3)})
            continue
        m = _ENTRY_RE.match(s)
        if m:
            frames.append({"file": m.group(1), "line": int(m.group(2)),
                           "func": m.group(3) or pending_func or ""})
            continue
        dm = _DEF_RE.match(s)
        if dm:
            pending_func = dm.group(1)
            continue
        if s.startswith("E"):
            e_lines.append(s[2:].strip() if s.startswith("E ") else s[1:].strip())
            continue
        m = _ERR_RE.match(s)
        if m and " in " not in s and "::" not in s and "FAILED" not in s:
            err_type = m.group(3)
            if m.group(4):
                err_msg = m.group(4).strip()
            # pytest 8 entry format: "path.py:NN: ErrorType" is itself the
            # deepest traceback frame (the line where the error surfaced)
            frames.append({"file": m.group(1), "line": int(m.group(2)),
                           "func": pending_func or ""})
    if not e_lines and not frames:
        return None
    if not err_type and e_lines:
        em = re.match(r"^([\w.]+)(?::\s*(.*))?$", e_lines[0])
        if em:
            err_type = em.group(1)
            err_msg = em.group(2) or ""
    if not err_msg and e_lines:
        err_msg = re.sub(r"^[\w.]+:\s*", "", e_lines[0])
    file = ""
    line = None
    if frames:
        # the deepest frame is where the error surfaced
        last = frames[-1]
        file, line = last["file"], last["line"]
    severity = severity_of(err_type, line)
    return {
        "test_id": test_id,
        "error_type": err_type or "AssertionError",
        "error_msg": err_msg,
        "file": file,
        "line": line,
        "severity": severity,
        "stack_trace": "\n".join(
            [f'  File "{f["file"]}", line {f["line"]}, in {f["func"]}' for f in frames]),
        "frames": frames,
        "e_lines": e_lines[:6],
    }


def severity_of(err_type: str, line: int | None) -> str:
    t = err_type.lower()
    if any(x in t for x in ("typeerror", "attributeerror", "keyerror", "indexerror",
                            "valueerror", "recursionerror", "memoryerror", "zerodivision")):
        return "HIGH"
    if "assert" in t:
        return "MEDIUM"
    if any(x in t for x in ("timeout", "connection", "socket")):
        return "MEDIUM"
    return "LOW"


def is_reproducible(sandbox: Sandbox, test_id: str) -> bool:
    """A failure is reproducible if it fails again in isolation."""
    res = run_single(sandbox, test_id)
    return res["failure"] is not None
