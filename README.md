# REPRO — Runtime Error Investigation & Repair Orchestrator

**REPRO** is an AI-powered software debugging agent for Python repositories. It takes a
repository, runs its tests, reproduces failures, captures real runtime evidence, diagnoses
the root cause, generates and verifies a minimal patch — then presents the whole
investigation in a developer dashboard with an activity log, dependency graph, trace view,
and diff.

The core philosophy:

```
Observe → Reproduce → Investigate → Diagnose → Patch → Verify
```

Nothing is fabricated. Every metric, runtime value, test result, and trace shown in the UI
comes from actual execution inside an isolated sandbox.

---

## Deploy (one click)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/SimraFaisal2/repro)

REPRO ships as a **single self-contained service** — the FastAPI backend serves
the built React dashboard, so the whole product deploys with one click. The
Render Blueprint (`render.yaml`) uses the multi-stage `Dockerfile`, mounts a
persistent disk for the SQLite DB and sandbox workspaces, and runs the offline
rule-engine path — **no API keys required**. It also deploys to any Docker
host (Railway, Fly.io, a VPS):

```bash
docker build -t repro .
docker run -p 8000:8000 -v repro-data:/app/data -e REPRO_DATA_DIR=/app/data repro
```

> **Why not Vercel?** REPRO's backend runs the user's tests in an isolated
> sandbox, streams live events (SSE), and persists to SQLite — all things
> serverless functions can't do (read-only filesystem, 60s timeouts). A
> persistent host is the right fit.

---

## Quick start

### Backend (API + agent)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt      # macOS / Linux
.venv/Scripts/python run.py                                # → http://127.0.0.1:8000
```

### Frontend (dashboard)

```bash
cd frontend
npm install
npm run dev                                               # → http://localhost:5173
```

Open http://localhost:5173 — the landing page has a **Try Demo** button that runs a real
investigation against a bundled broken repository.

### CLI

```bash
cd backend
.venv/Scripts/python -m repro.cli demo auth                 # investigate a bundled bug
.venv/Scripts/python -m repro.cli analyze /path/to/repo     # or a git URL
.venv/Scripts/python -m repro.cli status <id>
.venv/Scripts/python -m repro.cli report <id>
.venv/Scripts/python -m repro.cli diff <id>
.venv/Scripts/python -m repro.cli verify <id>
```

---

## What REPRO does

1. **Analyze** — detects language, framework, dependency files, test framework, and builds
   a module dependency graph of the repository.
2. **Reproduce** — runs the test suite in an isolated sandbox copy and parses the failures
   (error type, message, file, line, stack trace).
3. **Investigate** — re-runs the failing test under a runtime tracer that records function
   calls, arguments, return values, and timing for the exact code path that failed.
4. **Diagnose** — an analysis engine reasons over the observed evidence (error, stack trace,
   trace, source, schema) and produces a root-cause hypothesis with confidence, cleanly
   separating **Observed Evidence** from **Inferred Reasoning**.
5. **Patch** — generates a minimal code patch targeting the root cause.
6. **Verify** — applies the patch in the sandbox, re-runs the failing test, then the full
   suite. Only a green run is ever presented as verified. At most `MAX_ATTEMPTS = 3`
   autonomous repair rounds; after that REPRO stops and explains why.
7. **Apply** — with your explicit confirmation, the verified fix is committed to your
   checkout on a branch named `repro/fix-<investigation-id>`. The repository is never
   modified silently.

The AI layer is an abstraction (`repro/ai.py`) that supports OpenAI-compatible APIs,
Anthropic, and Ollama — and falls back to a deterministic rule engine when no LLM is
configured, so the demo works offline with zero API keys.

## Security

- Repositories are copied into an isolated workspace (`data/workspace/`) before anything
  executes; the host checkout is never run directly.
- Optional Docker isolation (`REPRO_USE_DOCKER=1`), execution timeouts, and a minimal
  environment (PATH/secret-stripping) for every subprocess.
- Fixes are only ever applied to your real checkout after you click **Confirm**.

## Architecture

```
backend/repro/
  main.py       FastAPI app + REST endpoints + SSE event stream
  agent.py      the investigation orchestrator (the agent loop)
  analyzer.py   rule-based root-cause engine (diagnosis + patch templates)
  ai.py         LLM provider abstraction (OpenAI / Anthropic / Ollama / rules)
  sandbox.py    isolated execution sandbox
  trace.py      runtime tracer (call/return instrumentation)
  tests.py      pytest discovery + execution + failure parsing
  patcher.py    minimal patch generation + sandbox verification
  report.py     markdown report builder
  repo.py       repository analysis (structure, deps, graph)
  demo.py       bundled broken demo repositories
  cli.py        command-line interface
  db.py         SQLite persistence (projects, investigations, runs, events)
  models.py     Pydantic schemas

frontend/src/
  pages/        Landing · Dashboard · Investigation workspace
  components/   CodeView · DiffView · TraceView · GraphView · ActivityLog
  api.ts        typed REST + SSE client
```

## Demo repositories

Five intentionally broken Python projects ship with REPRO (`backend/repro/demo_repos/`),
each with a genuine bug and a failing test:

| Demo         | Bug                          |
|--------------|------------------------------|
| `auth`       | Null / None handling         |
| `offbyone`   | Off-by-one error             |
| `api`        | Incorrect API response handling |
| `sql`        | Incorrect SQL query          |
| `auth2`      | Authentication logic bug     |

## Configuration

Environment variables (see `backend/repro/config.py`):

| Variable            | Default                | Purpose                          |
|---------------------|------------------------|----------------------------------|
| `REPRO_DATA_DIR`    | `<repo>/data`          | SQLite DB, projects, workspaces  |
| `REPRO_DB`          | `data/repro.db`        | database path                    |
| `REPRO_WORKSPACE`   | `data/workspace`       | sandbox copies                   |
| `REPRO_BACKEND_PORT`| `8000`                 | backend port (frontend proxy)    |
| `REPRO_USE_DOCKER`  | unset                  | `1` to run tests in Docker       |
| `REPRO_EXEC_TIMEOUT`| `120`                  | per-command timeout (s)          |
| `REPRO_MAX_ATTEMPTS`| `3`                    | max autonomous repair rounds     |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_BASE_URL` | — | LLM providers (optional) |
