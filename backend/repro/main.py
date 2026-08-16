"""REPRO FastAPI application.

Security model: repository code only ever executes inside the isolated
sandbox (subprocess with stripped env + timeout, or Docker when enabled).
Applying a patch to the user's checkout requires explicit confirmation.
"""
from __future__ import annotations

import asyncio
import json
import queue
import shutil
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import agent, db, demo, patcher, repo as repo_mod, report, tests
from .config import REPRO_ROOT, cfg, ensure_dirs
from .sandbox import Sandbox

ensure_dirs()
db.init_db()

app = FastAPI(title="REPRO", version="0.1.0", description="Runtime Error Investigation & Repair Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ production single-service
# The frontend calls /api/* — in development the Vite proxy strips that
# prefix; in a single-service deployment (Docker/Render) the backend does
# it here so the same built frontend works unchanged.
@app.middleware("http")
async def api_prefix_rewrite(request: Request, call_next):
    path = request.scope.get("path", "")
    if path == "/api" or path.startswith("/api/"):
        request.scope["orig_path"] = path
        request.scope["path"] = path[4:] or "/"
    return await call_next(request)


FRONTEND_DIST = REPRO_ROOT / "frontend" / "dist"

TERMINAL = {"fixed", "failed", "no-failure"}


# ------------------------------------------------------------------ health
@app.get("/health")
def health() -> dict:
    return {"ok": True, "provider": "heuristic-rules"}


# ---------------------------------------------------------------- projects
@app.post("/projects")
def create_project(payload: dict) -> dict:
    name = (payload.get("name") or "").strip()
    source_type = payload.get("source_type") or "url"
    url = (payload.get("url") or "").strip()
    local = (payload.get("local_path") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")

    if source_type == "url":
        if not url:
            raise HTTPException(400, "url is required for source_type=url")
        dest = cfg.projects_dir / f"repo-{db.new_id()}"
        try:
            repo_mod.clone_repo(url, dest)
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from e
        return db.create_project(name, "url", str(dest), source_url=url)
    if source_type == "local":
        if not local or not Path(local).exists():
            raise HTTPException(400, "local_path does not exist")
        dest = cfg.projects_dir / f"local-{db.new_id()}"
        repo_mod.copy_dir(Path(local), dest)
        return db.create_project(name, "local", str(dest), source_url="")
    raise HTTPException(400, "source_type must be url or local")


@app.post("/projects/upload")
async def upload_project(file: UploadFile = File(...)) -> dict:
    name = (file.filename or "upload").rsplit(".", 1)[0]
    dest = cfg.projects_dir / f"up-{db.new_id()}"
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / "archive.zip"
    tmp.write_bytes(await file.read())
    try:
        with zipfile.ZipFile(tmp) as z:
            z.extractall(dest)
    except zipfile.BadZipFile as e:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(400, "uploaded file is not a valid zip archive") from e
    tmp.unlink(missing_ok=True)
    # if the archive wrapped everything in a single folder, hoist it
    children = [p for p in dest.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        inner = children[0]
        for p in list(inner.iterdir()):
            shutil.move(str(p), str(dest / p.name))
        shutil.rmtree(inner, ignore_errors=True)
    return db.create_project(name, "upload", str(dest), source_url="")


@app.post("/projects/{pid}/analyze")
def analyze_project(pid: str) -> dict:
    proj = db.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    overview = repo_mod.analyze_project(Path(proj["local_path"]))
    db.update_project_overview(pid, overview)
    return {"id": pid, **overview}


@app.get("/projects")
def list_projects(limit: int = 20) -> list[dict]:
    return db.list_projects(limit)


@app.get("/projects/{pid}")
def get_project(pid: str) -> dict:
    proj = db.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    return proj


# --------------------------------------------------------------------- demo
@app.post("/demo")
def run_demo(payload: dict) -> dict:
    proj = demo.create_demo_project(payload.get("bug", "auth"))
    inv = db.create_investigation(proj["id"])
    return {"project": proj, "investigation": inv}


# ----------------------------------------------------------- investigations
@app.post("/investigations")
def create_investigation(payload: dict) -> dict:
    pid = payload.get("project_id")
    proj = db.get_project(pid) if pid else None
    if not proj:
        raise HTTPException(404, "project not found")
    return db.create_investigation(pid)


@app.post("/investigations/{iid}/run")
def run_investigation(iid: str) -> dict:
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    db.update_investigation(iid, status="running")
    agent.start_agent(iid)
    return {"id": iid, "status": "running"}


@app.get("/investigations/{iid}")
def get_investigation(iid: str) -> dict:
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    return inv


@app.get("/investigations/{iid}/events")
async def investigation_events(iid: str, request: Request):
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    q = agent.bus.for_inv(iid)

    async def gen():
        sent = 0
        while True:
            if await request.is_disconnected():
                break
            try:
                item = q.get_nowait()
            except queue.Empty:
                if inv["status"] in TERMINAL and sent == 0:
                    yield f"data: {json.dumps({'type': 'done', 'status': inv['status']})}\n\n"
                    yield "data: {\"type\":\"__close__\"}\n\n"
                    break
                await asyncio.sleep(0.3)
                continue
            if item is None:
                yield "data: {\"type\":\"__close__\"}\n\n"
                break
            sent += 1
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/investigations/{iid}/trace")
def investigation_trace(iid: str) -> dict:
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    events = db.get_events(iid)
    summary = inv.get("summary") or {}
    return {"events": events, "trace": summary.get("_trace") or []}


@app.get("/investigations/{iid}/diff")
def investigation_diff(iid: str) -> dict:
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    patches = inv.get("patches") or []
    if not patches:
        return {"diff": ""}
    return {"diff": patches[-1].get("diff", "")}


@app.get("/investigations/{iid}/report")
def investigation_report(iid: str) -> str:
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    proj = db.get_project(inv["project_id"])
    summary = inv.get("summary")
    if not summary:
        summary = report.build_summary(inv, proj)
    return report.render_markdown(summary)


@app.post("/investigations/{iid}/apply")
def apply_patch(iid: str, payload: dict) -> dict:
    """Apply the latest patch to the user's checkout — requires explicit confirm."""
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    patches = inv.get("patches") or []
    if not patches:
        raise HTTPException(400, "no patch to apply")
    if not payload.get("confirm"):
        raise HTTPException(400, "confirmation required — set confirm=true to apply the patch")
    proj = db.get_project(inv["project_id"])
    last = patches[-1]

    branch = f"repro/fix-{iid}"
    root = Path(proj["local_path"])
    diff = last.get("diff", "")
    if not diff:
        raise HTTPException(400, "patch has no diff to apply")
    if not (root / ".git").exists():
        _git(root, "init", "-q", "-b", "main")
    if _git(root, "rev-parse", "--verify", "HEAD").returncode != 0:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "baseline")
    branches = _git(root, "branch", "--list", branch).stdout.strip()
    if branches:
        _git(root, "checkout", "-q", branch)
    else:
        _git(root, "checkout", "-q", "-b", branch)
    pf = root / "repro_apply.patch"
    # write LF endings explicitly — Path.write_text converts \n to CRLF on
    # Windows, and `git apply` cannot match context lines against a CRLF patch
    pf.write_bytes(diff.encode("utf-8"))
    proc = _git(root, "apply", "--whitespace=nowarn", pf.name)
    pf.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise HTTPException(500, f"could not apply patch: {proc.stderr.strip()[:400]}")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"repro: apply verified fix ({iid})")
    db.update_investigation(iid, branch=branch)
    for p in patches:
        db.update_patch(p["id"], applied=True, status="applied")
    return {"branch": branch, "message": f"Patch applied on branch `{branch}`"}


def _git(root: Path, *args: str):
    import subprocess
    env = dict(__import__("os").environ)
    return subprocess.run(
        ["git", "-c", "user.name=REPRO", "-c", "user.email=repro@local", *args],
        capture_output=True, text=True, cwd=str(root), env=env, timeout=60, shell=False)


@app.post("/investigations/{iid}/verify")
def verify_investigation(iid: str) -> dict:
    inv = db.get_investigation(iid)
    if not inv:
        raise HTTPException(404, "investigation not found")
    proj = db.get_project(inv["project_id"])
    sb = Sandbox(f"verify-{iid}", Path(proj["local_path"]))
    run = tests.run_suite(sb)
    sb.cleanup()
    db.add_test_run(iid, "verify-full", run["total"], run["passed"],
                    run["failed"], run["skipped"], run["duration"])
    db.add_verification(iid, None, run, run, run["failed"] == 0)
    return {"total": run["total"], "passed": run["passed"], "failed": run["failed"],
            "skipped": run["skipped"], "duration": run["duration"]}


# ------------------------------------------------------------------ static frontend (production)
# Serves the built dashboard so the whole product is a single service.
# Registered last, so it never shadows the API routes above.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str, request: Request):
        # Never mask API errors: unknown /api/* must 404 as JSON, not return
        # HTML. The middleware stashes the original path before rewriting.
        orig = request.scope.get("orig_path", "")
        if orig == "/api" or orig.startswith("/api/"):
            raise HTTPException(404, "not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
