import asyncio
import json
import os
import sys
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone


from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from typing import Literal, Optional
from pydantic import BaseModel, Field

from db.models import Base
from db.writer import DBWriter
from pipeline.orchestrator import Orchestrator
from security.crypto import build_cipher_from_env
from storage.local_logger import list_recent_runs
from main import run_once

# Built once at process startup, not per-request. Unlike the one-shot CLI script
# (which creates a fresh engine and exits), this process stays alive for days —
# recreating the engine on every "Run Now" click would leak a new connection
# pool each time. pool_pre_ping=True guards against a connection Postgres has
# silently dropped during a long-lived process's idle periods.
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Base.metadata.create_all(_engine)
_db = DBWriter(_engine, cipher=build_cipher_from_env())
_orchestrator = Orchestrator(_db)

# Prevents two overlapping runs if "Run Now" is clicked twice in a row, and is
# shared with the scheduler below via _execute_run() so a scheduled tick and a
# manual click can never run concurrently either.
_run_lock = asyncio.Lock()

logger = logging.getLogger("uvicorn.error")

# Scheduler state — see _scheduler_tick()/_scheduler_loop() below.
_last_run_at: Optional[datetime] = None
SCHEDULER_POLL_SECONDS = 60


def _parse_interval(raw: str) -> Optional[int]:
    """Returns the configured interval in hours, or None if disabled/unset/garbage.
    Defensive on purpose — a hand-edited or stale setting_overrides row shouldn't
    be able to crash the scheduler loop, only disable it for that tick."""
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "SCRAPE_INTERVAL_HOURS=%r is not a valid integer; treating as disabled", raw
        )
        return None
    return value if value > 0 else None


def _seed_last_run_at() -> Optional[datetime]:
    """Reads the most recent run log on startup so a container restart doesn't
    immediately re-trigger a run that already happened minutes ago. Best-effort:
    any failure just means the schedule starts fresh, which is safe (worst case,
    one extra run fires sooner than it strictly needed to)."""
    try:
        recent = list_recent_runs(1)
        if not recent:
            return None
        with open(recent[0], "r", encoding="utf-8") as f:
            run_id = json.load(f).get("run_id")
        if not run_id:
            return None
        return datetime.fromisoformat(run_id.replace("Z", "+00:00"))
    except Exception:
        logger.exception(
            "Could not seed last-run time from log history; starting fresh"
        )
        return None


async def _execute_run():
    """The one place a pipeline run actually happens and _last_run_at is recorded.
    Both POST /run and the scheduler go through this, so the schedule is always
    measured from the last *actual* run regardless of what triggered it."""
    global _last_run_at
    async with _run_lock:
        await run_once(_db, _orchestrator)
        _last_run_at = datetime.now(timezone.utc)


async def _scheduler_tick():
    if _run_lock.locked():
        # A manual run is already in flight — skip this tick. _execute_run()
        # updates _last_run_at when that run finishes, so the next tick's
        # due-check naturally accounts for it. No queuing needed.
        return

    settings = _db.get_settings()
    interval_hours = _parse_interval(settings.get("SCRAPE_INTERVAL_HOURS", ""))
    logger.warning(
        "SCHEDULER DIAGNOSTIC: tick fired, interval_hours=%s last_run_at=%s",
        interval_hours,
        _last_run_at,
    )
    if interval_hours is None:
        return

    now = datetime.now(timezone.utc)
    due = _last_run_at is None or (now - _last_run_at) >= timedelta(
        hours=interval_hours
    )
    if not due:
        return

    logger.info(
        "Scheduled interval elapsed (every %sh, last run %s) — starting scrape run",
        interval_hours,
        _last_run_at.isoformat() if _last_run_at else "never",
    )
    try:
        await _execute_run()
    except Exception:
        logger.exception("Scheduled scrape run failed")


async def _scheduler_loop():
    while True:
        await asyncio.sleep(SCHEDULER_POLL_SECONDS)
        try:
            await _scheduler_tick()
        except Exception:
            # Belt-and-suspenders on top of _scheduler_tick's own try/except —
            # nothing here should ever be able to kill the loop permanently.
            logger.exception("Scheduler tick raised unexpectedly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _last_run_at
    _last_run_at = _seed_last_run_at()
    logger.warning(
        "SCHEDULER DIAGNOSTIC: loop starting, seeded last_run_at=%s", _last_run_at
    )
    task = asyncio.create_task(_scheduler_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Vestige Scraper Service", lifespan=lifespan)


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
    scrape_interval_hours: Optional[int] = None  # None = disabled


class SettingsUpdateRequest(BaseModel):
    llm_discovery_enabled: Optional[bool] = None
    llm_mode: Optional[Literal["direct", "selector"]] = None
    selector_api_base: Optional[str] = None
    selector_api_key: Optional[str] = None
    selector_model: Optional[str] = None
    direct_api_base: Optional[str] = None
    direct_api_key: Optional[str] = None
    direct_model: Optional[str] = None
    # None = no change. 0 = explicit disable. >0 = set/enable at that interval.
    # ge=0 rejects negative values as a 422 before this ever reaches DBWriter.
    scrape_interval_hours: Optional[int] = Field(default=None, ge=0)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run_pipeline():
    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="A run is already in progress")
    try:
        await _execute_run()
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
        scrape_interval_hours=_parse_interval(s.get("SCRAPE_INTERVAL_HOURS", "")),
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
        "SCRAPE_INTERVAL_HOURS": (
            None
            if payload.scrape_interval_hours is None
            else (
                ""
                if payload.scrape_interval_hours == 0
                else str(payload.scrape_interval_hours)
            )
        ),
    }
    try:
        for key, value in updates.items():
            _db.apply_setting_update(key, value)
        return {"status": "success"}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
