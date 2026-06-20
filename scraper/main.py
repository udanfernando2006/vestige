# scraper/main.py
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


async def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)  # safe to call on every run
    db = DBWriter(engine)
    orchestrator = Orchestrator(db)

    config_path = os.environ.get("BOOKS_CONFIG_PATH", "books_config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            db.sync_config(json.load(f))

    summary = await orchestrator.run_all(db)
    write_run_log(summary)


asyncio.run(main())
