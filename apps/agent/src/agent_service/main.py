"""FastAPI entrypoint: API routes + static console serving."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("DEMO_SEED") == "1":
        from . import db, registry
        from .seed import seed

        conn = db.connect()
        db.init_db(conn)
        registry.ensure_seed_version(conn)
        try:
            seed(conn)
        finally:
            conn.close()
    yield


app = FastAPI(title="Agent Deployment Console", version="0.2.0", lifespan=lifespan)
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "agent-deployment-console"}


# In the Docker image the console build output is copied next to this module.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="console")
