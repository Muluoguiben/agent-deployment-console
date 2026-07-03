"""FastAPI entrypoint. M0: health check + static console serving; agent lands in M1."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Agent Deployment Console", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "agent-deployment-console"}


@app.get("/api/meta")
def meta() -> dict[str, str]:
    return {"milestone": "M0", "agent": "not yet deployed"}


# In the Docker image the console build output is copied next to this module.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="console")
