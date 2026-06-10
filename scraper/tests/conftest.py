import json
import os
from dotenv import load_dotenv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


load_dotenv(Path(__file__).parent.parent.parent / ".env.test")

def load_fixture(filename: str) -> str:
    """Return the text content of a fixture file."""
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


def load_fixture_json(filename: str) -> dict:
    """Return the parsed JSON content of a fixture file."""
    return json.loads(load_fixture(filename))


# ---------------------------------------------------------------------------
# Pytest fixtures — available to all test files
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def product_page_html() -> str:
    return load_fixture("product_page.html")


@pytest.fixture(scope="session")
def search_results_html() -> str:
    return load_fixture("search_results.html")


@pytest.fixture(scope="session")
def llm_selector_response() -> dict:
    return load_fixture_json("llm_selector_response.json")


@pytest.fixture(scope="session")
def llm_direct_response() -> dict:
    return load_fixture_json("llm_direct_response.json")


# ---------------------------------------------------------------------------
# Database fixtures (integration + E2E only)
# ---------------------------------------------------------------------------

def _get_test_db_url() -> str:
    """
    Read DATABASE_URL from the environment and ensure the psycopg3 dialect
    prefix is present. GitHub Actions supplies DATABASE_URL via the workflow
    env block; local runs read it from .env.test if present.
    """
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://booktracker:testpassword@localhost:5432/vestige_test",
    )
    # Normalise plain postgresql:// URLs written before psycopg3 was adopted
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # Also handle postgresql+psycopg2 if someone has that in their local env
    if "psycopg2" in url:
        url = url.replace("psycopg2", "psycopg")
    return url


@pytest.fixture(scope="session")
def db_engine():
    """
    Create the test schema once per test session, yield the engine,
    then drop everything on teardown. Running the full suite twice in a row
    produces a clean slate each time.
    """
    from db.models import Base  # imported here so unit tests never touch db.models

    engine = create_engine(_get_test_db_url())
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Function-scoped session with automatic rollback after every test.
    This means tests can write whatever they like without polluting each other.
    """
    SessionFactory = sessionmaker(bind=db_engine)
    session = SessionFactory()
    try:
        yield session
        session.commit()
    finally:
        session.close()

@pytest.fixture(autouse=True)
def clean_db(db_engine):
    """Truncate all tables after every test for a clean slate."""
    yield
    from db.models import Base
    with db_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture(scope="function")
def db_writer(db_engine):
    """
    A DBWriter instance wired to the test session.
    Adjust the constructor call to match your DBWriter signature.
    If DBWriter creates its own engine from DATABASE_URL, patch that instead:

        with patch("db.writer.create_engine") as mock_engine:
            mock_engine.return_value = db_session.bind
            writer = DBWriter()
    """
    from db.writer import DBWriter
    return DBWriter(db_engine)


# ---------------------------------------------------------------------------
# Browser / LLM mocks (E2E only)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_browser_session(product_page_html):
    """
    An AsyncMock that behaves like BrowserSession.
    get_html() returns the product page fixture by default.
    Override return values per-test with:
        mock_browser_session.get_html.return_value = other_html
    """
    session = AsyncMock()
    session.navigate = AsyncMock(return_value=None)
    session.get_html = AsyncMock(return_value=product_page_html)
    # Support use as an async context manager (async with BrowserSession() as s)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_extractor(llm_selector_response, llm_direct_response):
    """
    A MagicMock that replaces Extractor.
    extract_selectors() returns the selector fixture.
    extract_details()  returns the direct-extraction fixture.
    Patch this into the orchestrator or discover_selectors module as needed.
    """
    extractor = MagicMock()
    extractor.extract_selectors = MagicMock(return_value=llm_selector_response)
    extractor.extract_details = MagicMock(return_value=llm_direct_response)
    extractor.clean_html = MagicMock(side_effect=lambda html, **kwargs: html)
    return extractor