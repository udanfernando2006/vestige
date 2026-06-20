# scraper/api_server.py
import asyncio
import json
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine

from db.models import Base
from db.writer import DBWriter
from pipeline.orchestrator import Orchestrator
from main import run_once

app = FastAPI(title="Vestige Scraper Service")

# Built once at process startup, not per-request. Unlike the one-shot CLI script
# (which creates a fresh engine and exits), this process stays alive for days —
# recreating the engine on every "Run Now" click would leak a new connection
# pool each time. pool_pre_ping=True guards against a connection Postgres has
# silently dropped during a long-lived process's idle periods.
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Base.metadata.create_all(_engine)
_db = DBWriter(_engine)
_orchestrator = Orchestrator(_db)

# Prevents two overlapping runs if "Run Now" is clicked twice in a row.
_run_lock = asyncio.Lock()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run_pipeline():
    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="A run is already in progress")
    async with _run_lock:
        try:
            await run_once(_db, _orchestrator)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/discover/{pair_id}")
async def discover(pair_id: int):
    # Mirrors RunService's original contract exactly: invoke the existing CLI
    # tool without --commit, exit 0 -> parsed JSON, exit != 0 -> 422 with raw output.
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "tools/discover_selectors.py",
        "--pair-id",
        str(pair_id),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    stdout, stderr = await proc.communicate()
    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        return JSONResponse(
            status_code=422, content={"output": stdout_text or stderr_text}
        )

    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, detail="Invalid JSON from discover_selectors.py"
        )
