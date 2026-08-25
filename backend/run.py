"""Launch the REPRO backend (uvicorn).

Binds 0.0.0.0 and honors the PORT env var so the same entrypoint works
locally (default 8000) and on hosts like Render that inject $PORT.

Port priority: REPRO_BACKEND_PORT > PORT > 8000. REPRO_BACKEND_PORT is
checked first so local dev shells that inject an unrelated PORT (e.g. the
Freebuff orchestrator) can't hijack the backend away from the frontend's
proxy target (127.0.0.1:8000).
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("REPRO_BACKEND_PORT") or os.environ.get("PORT") or "8000")
    uvicorn.run("repro.main:app", host="0.0.0.0", port=port, reload=False)
