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

Run these from the repository root — the folder that contains `backend/` and `frontend/`.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt   # Windows (PowerShell)
# .venv/bin/python -m pip install -r requirements.txt      # macOS / Linux
.\.venv\Scripts\python run.py                               # → http://127.0.0.1:8000
```

> In PowerShell a command that starts with `.` is parsed as a module name, so write the
> interpreter as `.\.venv\Scripts\python`. Without the leading `.\` you get
> `The module '.venv' could not be loaded`.

### Frontend (dashboard)

```bash
cd frontend
npm install
npm run dev                                               # → http://localhost:5173
```

Open http://localhost:5173 — the landing page has a **Try Demo** button that runs a real
investigation against a bundled broken repository.

### CLI

```powershell
cd backend
.\.venv\Scripts\python -m repro.cli demo auth                 # investigate a bundled bug
.\.venv\Scripts\python -m repro.cli analyze /path/to/repo     # or a git URL
.\.venv\Scripts\python -m repro.cli status <id>
.\.venv\Scripts\python -m repro.cli report <id>
.\.venv\Scripts\python -m repro.cli diff <id>
.\.venv\Scripts\python -m repro.cli verify <id>
.\.venv\Scripts\python -m repro.cli benchmark                 # run the bug corpus, report fix rate
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
  benchmark.py  bug-corpus benchmark runner (fix-rate reporting)
  cli.py        command-line interface
  db.py         SQLite persistence (projects, investigations, runs, events)
  models.py     Pydantic schemas

benchmark_corpus/  nine real-world-style bug reproductions (one per failure class)
benchmark_results.json  latest benchmark run (fix rate, per-entry detail)

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

## CI/CD

Every push to `main` runs a **benchmark gate** — the full 9-repo bug corpus must
fix 100% before anything deploys. Only then are the services updated:

| Target  | What ships                       | How                          |
|---------|----------------------------------|------------------------------|
| Render  | Backend (FastAPI + agent, Docker)| Deploy-hook `POST`           |
| Vercel  | Frontend dashboard (Vite/React)  | `vercel deploy --prebuilt`   |

Workflow: `.github/workflows/ci.yml`. The benchmark exits non-zero unless every
corpus entry is fixed, so the gate fails the run (and skips both deploys) the
moment the fix rate drops below 100%. The `benchmark_results.json` artifact is
also uploaded for every run.

### Secrets required

Set these in **GitHub → Settings → Secrets and variables → Actions**:

| Secret                  | Where to get it                                                    |
|-------------------------|--------------------------------------------------------------------|
| `RENDER_DEPLOY_HOOK`    | Render dashboard → service → **Settings → Deploy Hook** (URL)      |
| `VERCEL_TOKEN`          | Vercel → Account → **Settings → Tokens**                           |
| `VERCEL_ORG_ID`         | Vercel project → Settings (e.g. `team_…`)                          |
| `VERCEL_PROJECT_ID`     | Vercel project → Settings (e.g. `prj_…`)                           |
| `VITE_API_BASE`         | Backend origin, e.g. `https://repro.onrender.com` (no trailing `/`)|  

> `VITE_API_BASE` is inlined at build time — set it once the backend is live.
> Leave it unset and the dashboard calls same-origin `/api`, which is correct
> for the single-service Docker deploy on Render.

---

## Benchmark

REPRO ships with a **bug-corpus benchmark** (`backend/repro/benchmark_corpus/`) — nine
small, self-contained Python projects, each with a genuine bug modeled on a real-world
failure class and a failing test that defines the expected behaviour. The benchmark runs
the full agent loop against every entry and reports the fix rate, overall and by class:

```powershell
cd backend
.\.venv\Scripts\python -m repro.benchmark                 # all entries, print table + JSON
.\.venv\Scripts\python -m repro.benchmark --only api-v2   # a subset (comma/space-separated)
.\.venv\Scripts\python -m repro.benchmark --db bench.db   # custom dedicated db
```

The same run is available through the CLI (`python -m repro.cli benchmark`). Each entry
uses a fresh project + investigation and a **dedicated SQLite db** (`data/benchmark.db`),
so the benchmark never pollutes dev data and is reproducible. Results are written to
`benchmark_results.json`.

| id                | class                         | rule             |
|-------------------|-------------------------------|------------------|
| `profile-lookup`  | NULL dereference              | `none_subscript` |
| `cache-read`      | NULL dereference              | `none_subscript` |
| `session-attribute` | NULL dereference            | `none_attribute` |
| `slider`          | Off-by-one                    | `off_by_one_range` |
| `paginator`       | Off-by-one                    | `off_by_one_range` |
| `api-v2`          | API response-shape mismatch   | `key_fix`        |
| `payload-key`     | API response-shape mismatch   | `key_fix`        |
| `schema-drift`    | SQL schema drift              | `sql_column_fix` |
| `auth-plaintext`  | Authentication logic          | `auth_hash`      |

Each entry's `meta.json` documents the real-world incident class it models (e.g. `api-v2`
mirrors the Twitter API v1.1 → v2 migration that moved the list under `data`). The corpus
targets the deterministic rule engine's supported failure classes, so the fix rate measures
the offline engine — an LLM provider (OpenAI/Anthropic/Ollama) extends coverage beyond
those classes.

Current result (rule engine, no LLM): **9/9 fixed (100%)** — every failure reproduced,
diagnosed, patched and verified in the sandbox. See `benchmark_results.json` for the
machine-readable run (attempts, confidence, before/after test counts, durations).

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
