"""SQLite persistence layer.

Schema follows the product spec: projects, investigations, test_runs,
failures, runtime_events, agent_steps, patches, verification_results.
Heavy per-investigation detail is stored as JSON blobs so the MVP stays
small while the relational shape remains available for queries.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

from .config import cfg, ensure_dirs

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,          -- url | upload | local | demo
    source_url TEXT,
    local_path TEXT NOT NULL,
    overview_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',   -- created|running|investigating|fixed|failed|no-failure
    branch TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    confidence REAL,
    summary_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS test_runs (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    stage TEXT NOT NULL,               -- baseline | reproduce | verify | full
    total INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    duration REAL DEFAULT 0,
    output TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS failures (
    id TEXT PRIMARY KEY,
    test_run_id TEXT,
    investigation_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    error_type TEXT,
    error_msg TEXT,
    file TEXT,
    line INTEGER,
    severity TEXT,
    stack_trace TEXT,
    reproducible INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_events (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    frame_order INTEGER,
    event TEXT,
    func TEXT,
    file TEXT,
    line INTEGER,
    args_json TEXT,
    return_value TEXT,
    exception TEXT,
    exec_time REAL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    ts REAL NOT NULL,
    message TEXT NOT NULL,
    kind TEXT DEFAULT 'info'
);

CREATE TABLE IF NOT EXISTS patches (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    diff TEXT,
    files_changed INTEGER DEFAULT 0,
    lines_added INTEGER DEFAULT 0,
    lines_removed INTEGER DEFAULT 0,
    risk TEXT,
    confidence REAL,
    reason TEXT,
    applied INTEGER DEFAULT 0,
    status TEXT DEFAULT 'proposed',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS verification_results (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    full_json TEXT,
    passed INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(str(cfg.db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _lock:
        conn = get_db()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


def _j(v: Any) -> Optional[str]:
    return json.dumps(v) if v is not None else None


def _uj(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- projects
def create_project(name: str, source_type: str, local_path: str,
                   source_url: str = "", overview: Any = None) -> dict:
    pid = new_id()
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO projects (id,name,source_type,source_url,local_path,overview_json,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (pid, name, source_type, source_url, local_path, _j(overview), time.time()),
            )
            conn.commit()
            return get_project(pid)
        finally:
            conn.close()


def get_project(pid: str) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["overview"] = _uj(d.pop("overview_json"))
        return d
    finally:
        conn.close()


def list_projects(limit: int = 20) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["overview"] = _uj(d.pop("overview_json"))
            out.append(d)
        return out
    finally:
        conn.close()


def update_project_overview(pid: str, overview: Any) -> None:
    with _lock:
        conn = get_db()
        try:
            conn.execute("UPDATE projects SET overview_json=? WHERE id=?", (_j(overview), pid))
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------- investigations
def create_investigation(project_id: str) -> dict:
    iid = new_id()
    now = time.time()
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO investigations (id,project_id,status,created_at,updated_at)"
                " VALUES (?,?,?,?,?)",
                (iid, project_id, "created", now, now),
            )
            conn.commit()
            return get_investigation(iid)
        finally:
            conn.close()


def get_investigation(iid: str) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM investigations WHERE id=?", (iid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["summary"] = _uj(d.pop("summary_json"))
        d["test_runs"] = [dict(r) for r in conn.execute(
            "SELECT * FROM test_runs WHERE investigation_id=? ORDER BY created_at", (iid,))]
        d["failures"] = [dict(r) for r in conn.execute(
            "SELECT * FROM failures WHERE investigation_id=? ORDER BY created_at", (iid,))]
        d["steps"] = [dict(r) for r in conn.execute(
            "SELECT * FROM agent_steps WHERE investigation_id=? ORDER BY ts", (iid,))]
        d["patches"] = [dict(r) for r in conn.execute(
            "SELECT * FROM patches WHERE investigation_id=? ORDER BY created_at", (iid,))]
        d["verifications"] = [dict(r) for r in conn.execute(
            "SELECT * FROM verification_results WHERE investigation_id=? ORDER BY created_at", (iid,))]
        for p in d["patches"]:
            p["applied"] = bool(p["applied"])
        return d
    finally:
        conn.close()


def update_investigation(iid: str, **fields: Any) -> None:
    allowed = {"status", "branch", "attempts", "confidence", "summary_json"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(_j(v) if k == "summary_json" else v)
    if not sets:
        return
    vals.append(time.time())
    with _lock:
        conn = get_db()
        try:
            conn.execute(f"UPDATE investigations SET {', '.join(sets)}, updated_at=? WHERE id=?",
                         (*vals, iid))
            conn.commit()
        finally:
            conn.close()


# ------------------------------------------------------------------- steps
def add_step(iid: str, message: str, kind: str = "info") -> dict:
    row = {"id": new_id(), "investigation_id": iid, "ts": time.time(),
           "message": message, "kind": kind}
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO agent_steps (id,investigation_id,ts,message,kind) VALUES (?,?,?,?,?)",
                (row["id"], iid, row["ts"], message, kind))
            conn.commit()
        finally:
            conn.close()
    return row


def add_test_run(iid: str, stage: str, total: int, passed: int, failed: int,
                 skipped: int, duration: float, output: str = "") -> dict:
    row = {"id": new_id(), "investigation_id": iid, "stage": stage, "total": total,
           "passed": passed, "failed": failed, "skipped": skipped,
           "duration": round(duration, 3), "output": output[:200_000]}
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO test_runs (id,investigation_id,stage,total,passed,failed,skipped,duration,output,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (row["id"], iid, stage, total, passed, failed, skipped, row["duration"], row["output"], time.time()))
            conn.commit()
        finally:
            conn.close()
    return row


def add_failure(iid: str, test_run_id: str, failure: dict) -> dict:
    row = {
        "id": new_id(), "test_run_id": test_run_id, "investigation_id": iid,
        "test_id": failure.get("test_id", ""),
        "error_type": failure.get("error_type", ""),
        "error_msg": failure.get("error_msg", ""),
        "file": failure.get("file", ""),
        "line": failure.get("line"),
        "severity": failure.get("severity", "MEDIUM"),
        "stack_trace": failure.get("stack_trace", ""),
        "reproducible": int(bool(failure.get("reproducible", 0))),
    }
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO failures (id,test_run_id,investigation_id,test_id,error_type,error_msg,file,line,severity,stack_trace,reproducible,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["id"], test_run_id, iid, row["test_id"], row["error_type"], row["error_msg"],
                 row["file"], row["line"], row["severity"], row["stack_trace"], row["reproducible"], time.time()))
            conn.commit()
        finally:
            conn.close()
    return row


def add_events(iid: str, events: list[dict]) -> None:
    if not events:
        return
    with _lock:
        conn = get_db()
        try:
            conn.executemany(
                "INSERT INTO runtime_events (id,investigation_id,frame_order,event,func,file,line,args_json,return_value,exception,exec_time,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(new_id(), iid, e.get("order"), e.get("event"), e.get("func"), e.get("file"),
                  e.get("line"), _j(e.get("args")), e.get("return"), e.get("exception"),
                  e.get("exec_time"), time.time()) for e in events])
            conn.commit()
        finally:
            conn.close()


def get_events(iid: str) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM runtime_events WHERE investigation_id=? ORDER BY frame_order", (iid,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["args"] = _uj(d.pop("args_json"))
            out.append(d)
        return out
    finally:
        conn.close()


def add_patch(iid: str, patch: dict) -> dict:
    row = {
        "id": new_id(), "investigation_id": iid,
        "diff": patch.get("diff", ""),
        "files_changed": patch.get("files_changed", 0),
        "lines_added": patch.get("lines_added", 0),
        "lines_removed": patch.get("lines_removed", 0),
        "risk": patch.get("risk", "MEDIUM"),
        "confidence": patch.get("confidence"),
        "reason": patch.get("reason", ""),
        "applied": int(bool(patch.get("applied", 0))),
        "status": patch.get("status", "proposed"),
    }
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO patches (id,investigation_id,diff,files_changed,lines_added,lines_removed,risk,confidence,reason,applied,status,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["id"], iid, row["diff"], row["files_changed"], row["lines_added"],
                 row["lines_removed"], row["risk"], row["confidence"], row["reason"],
                 row["applied"], row["status"], time.time()))
            conn.commit()
        finally:
            conn.close()
    return row


def update_patch(pid: str, **fields: Any) -> None:
    allowed = {"applied", "status"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(int(v) if k == "applied" else v)
    if not sets:
        return
    with _lock:
        conn = get_db()
        try:
            conn.execute(f"UPDATE patches SET {', '.join(sets)} WHERE id=?", (*vals, pid))
            conn.commit()
        finally:
            conn.close()


def add_verification(iid: str, before: Any, after: Any, full: Any, passed: bool) -> dict:
    row = {"id": new_id(), "investigation_id": iid,
           "before_json": _j(before), "after_json": _j(after), "full_json": _j(full),
           "passed": int(passed)}
    with _lock:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO verification_results (id,investigation_id,before_json,after_json,full_json,passed,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (row["id"], iid, row["before_json"], row["after_json"], row["full_json"],
                 row["passed"], time.time()))
            conn.commit()
        finally:
            conn.close()
    return row


def get_verification(iid: str) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM verification_results WHERE investigation_id=? ORDER BY created_at DESC LIMIT 1",
            (iid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["before"] = _uj(d.pop("before_json"))
        d["after"] = _uj(d.pop("after_json"))
        d["full"] = _uj(d.pop("full_json"))
        d["passed"] = bool(d["passed"])
        return d
    finally:
        conn.close()
