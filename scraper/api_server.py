# scraper/api_server.py
import asyncio
import json
import os
import sys
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from typing import Literal, Optional
from pydantic import BaseModel

from db.models import Base
from db.writer import DBWriter
from pipeline.orchestrator import Orchestrator
from security.crypto import build_cipher_from_env
from main import run_once

app = FastAPI(title="Vestige Scraper Service")

# Built once at process startup, not per-request. Unlike the one-shot CLI script
# (which creates a fresh engine and exits), this process stays alive for days —
# recreating the engine on every "Run Now" click would leak a new connection
# pool each time. pool_pre_ping=True guards against a connection Postgres has
# silently dropped during a long-lived process's idle periods.
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Base.metadata.create_all(_engine)
_db = DBWriter(_engine, cipher=build_cipher_from_env())
_orchestrator = Orchestrator(_db)

# Prevents two overlapping runs if "Run Now" is clicked twice in a row.
_run_lock = asyncio.Lock()

logger = logging.getLogger("uvicorn.error")


class SettingsStatusResponse(BaseModel):
    llm_discovery_enabled: bool
    llm_mode: str
    selector_api_base: str
    selector_api_key_configured: bool
    selector_api_key_hint: Optional[str] = None
    selector_model: str
    direct_api_base: str
    direct_api_key_configured: bool
    direct_api_key_hint: Optional[str] = None
    direct_model: str


class SettingsUpdateRequest(BaseModel):
    llm_discovery_enabled: Optional[bool] = None
    llm_mode: Optional[Literal["direct", "selector"]] = None
    selector_api_base: Optional[str] = None
    selector_api_key: Optional[str] = None
    selector_model: Optional[str] = None
    direct_api_base: Optional[str] = None
    direct_api_key: Optional[str] = None
    direct_model: Optional[str] = None


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
            logger.exception("Pipeline run failed")
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

    # Progress messages go to stderr by design — stdout is reserved for the final
    # JSON result only (see discover_selectors.py). Log the progress separately so
    # it's actually visible in `docker compose logs scraper-server`: this call's
    # own stdout/stderr are piped to us, not inherited by the container's console,
    # so without this they'd otherwise be silently discarded on every success.
    if stderr_text:
        logger.info("discover_selectors.py (pair %s):\n%s", pair_id, stderr_text)

    if proc.returncode != 0:
        return JSONResponse(
            status_code=422, content={"output": stdout_text or stderr_text}
        )

    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError:
        logger.exception(
            "Failed to parse discover_selectors.py stdout:\n%s", stdout_text
        )
        raise HTTPException(
            status_code=500, detail="Invalid JSON from discover_selectors.py"
        )


@app.get("/config", response_model=SettingsStatusResponse)
async def get_config():
    s = _db.get_settings_status()
    return SettingsStatusResponse(
        llm_discovery_enabled=s["LLM_DISCOVERY_ENABLED"].strip().lower() == "true",
        llm_mode=s["LLM_MODE"],
        selector_api_base=s["SELECTOR_API_BASE"],
        selector_api_key_configured=s["SELECTOR_API_KEY"]["configured"],
        selector_api_key_hint=s["SELECTOR_API_KEY"]["hint"],
        selector_model=s["SELECTOR_MODEL"],
        direct_api_base=s["DIRECT_API_BASE"],
        direct_api_key_configured=s["DIRECT_API_KEY"]["configured"],
        direct_api_key_hint=s["DIRECT_API_KEY"]["hint"],
        direct_model=s["DIRECT_MODEL"],
    )


@app.put("/config")
async def update_config(payload: SettingsUpdateRequest):
    updates = {
        "LLM_DISCOVERY_ENABLED": (
            None
            if payload.llm_discovery_enabled is None
            else str(payload.llm_discovery_enabled).lower()
        ),
        "LLM_MODE": payload.llm_mode,
        "SELECTOR_API_BASE": payload.selector_api_base,
        "SELECTOR_API_KEY": payload.selector_api_key,
        "SELECTOR_MODEL": payload.selector_model,
        "DIRECT_API_BASE": payload.direct_api_base,
        "DIRECT_API_KEY": payload.direct_api_key,
        "DIRECT_MODEL": payload.direct_model,
    }
    try:
        for key, value in updates.items():
            _db.apply_setting_update(key, value)
        return {"status": "success"}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
