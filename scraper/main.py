# scraper/main.py
import asyncio
import json
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

from db.models import Base
from db.writer import DBWriter
from pipeline.orchestrator import run_all
from storage.local_logger import write_run_log

load_dotenv()

async def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)  # safe to call on every run
    db = DBWriter(engine)

    with open("books_config.json") as f:
        db.sync_config(json.load(f))

    summary = await run_all(db)
    write_run_log(summary)

asyncio.run(main())