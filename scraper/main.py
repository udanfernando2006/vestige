import argparse
import asyncio
import json
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

from db.models import Base
from db.writer import DBWriter
from pipeline.orchestrator import Orchestrator
from storage.local_logger import write_run_log

load_dotenv()


async def run_once(db: DBWriter, orchestrator: Orchestrator):
    """One full pipeline run: sync config, run the orchestrator, write the log.
    Shared by the one-shot CLI path (main(), below) and the always-on server's
    /run endpoint in api_server.py — same logic, two callers."""
    config_path = os.environ.get("BOOKS_CONFIG_PATH", "books_config.json")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            db.sync_config(json.load(f))

    summary = await orchestrator.run_all(db)
    write_run_log(summary)
    return summary


async def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)  # safe to call on every run
    db = DBWriter(engine)
    orchestrator = Orchestrator(db)

    await run_once(db, orchestrator)


def serve():
    """Long-running HTTP mode — started by the scraper-server compose service so
    the Spring Boot API can trigger runs/discovery on demand instead of trying
    (and failing) to exec a Python subprocess from inside its own JRE container."""
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run as a long-lived HTTP server instead of a one-shot job",
    )
    args = parser.parse_args()

    if args.serve:
        serve()
    else:
        asyncio.run(main())
