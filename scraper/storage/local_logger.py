# scraper/storage/local_logger.py

import json
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = os.environ.get("LOG_DIR", "logs")


def build_log_path(run_id: str) -> str:
    """
    Converts a run_id timestamp string to a file path.
    e.g. "2026-05-16T08:00:00Z" → "logs/2026/05/16/08-00-00.json"
    """
    dt = datetime.strptime(run_id, "%Y-%m-%dT%H:%M:%SZ")
    return os.path.join(
        LOG_DIR,
        dt.strftime("%Y"),
        dt.strftime("%m"),
        dt.strftime("%d"),
        dt.strftime("%H-%M-%S") + ".json"
    )


def write_run_log(run_data: dict) -> None:
    """
    Serialises the run summary dict to JSON and writes it to
    logs/YYYY/MM/DD/HH-MM-SS.json, creating directories as needed.
    Nothing is returned — the function writes and confirms via stdout.
    """
    run_id = run_data.get("run_id")
    if not run_id:
        raise ValueError("run_data must contain a 'run_id' field")

    path = build_log_path(run_id)
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        # default=str handles datetime objects that may appear in the summary
        json.dump(run_data, f, indent=2, default=str)

    print(f"[LocalLogger] Run log written → {path}")


def list_recent_runs(limit: int = 20) -> list:
    """
    Returns file paths of the most recent run logs, newest first.
    Used by the Spring Boot RunController to serve GET /api/runs.
    """
    base = Path(LOG_DIR)
    if not base.exists():
        return []

    # rglob collects all .json files under logs/; sort descending = newest first
    all_logs = sorted(base.rglob("*.json"), reverse=True)
    return [str(p) for p in all_logs[:limit]]