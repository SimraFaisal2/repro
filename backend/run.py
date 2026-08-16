"""Launch the REPRO backend (uvicorn)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("repro.main:app", host="127.0.0.1", port=8000, reload=False)
