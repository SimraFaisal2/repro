"""Launch the REPRO backend (uvicorn).

Binds 0.0.0.0 and honors the PORT env var so the same entrypoint works
locally (default 8000) and on hosts like Render that inject $PORT.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("REPRO_BACKEND_PORT", "8000")))
    uvicorn.run("repro.main:app", host="0.0.0.0", port=port, reload=False)
