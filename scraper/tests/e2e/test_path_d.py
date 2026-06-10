import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from pipeline.orchestrator import Orchestrator
from models.result import AvailabilityResult


@pytest.fixture
def seeded_pair_d(db_session, db_writer):
    from db.models import Book, Store, TrackingPair

    store = Store(name="path_d_store", base_url="https://vijithayapa.com")
    book = Book(name="Dune", isbn="9780441013001", is_series_entry=False)
    db_session.add_all([store, book])
    db_session.commit()
    pair = TrackingPair(
        book_id=book.id,
        store_id=store.id,
        product_url="https://vijithayapa.com/books/dune",
        price_selector=None,
        stock_selector=None,
        status="PENDING",
    )
    db_session.add(pair)
    db_session.commit()
    return db_writer.get_pair(pair.id)


class TestPathD:

    async def test_path_d_writes_snapshot_with_llm_direct_source(
        self,
        db_writer,
        db_session,
        seeded_pair_d,
        mock_browser_session,
        llm_direct_response,
        monkeypatch,
    ):
        from db.models import AvailabilitySnapshot

        monkeypatch.setenv("LLM_MODE", "direct")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "false")

        orchestrator = Orchestrator(db_writer=db_writer)

        # Mock _call_llm so extract_details() returns our fixture without
        # an API key
        with patch(
            "pipeline.llm_extractor.Extractor._call_llm",
            return_value=llm_direct_response,
        ):
            with patch(
                "pipeline.orchestrator.BrowserSession",
                return_value=mock_browser_session,
            ):
                await orchestrator.run_all()

        snapshot = (
            db_session.query(AvailabilitySnapshot)
            .filter_by(pair_id=seeded_pair_d["id"])
            .first()
        )
        assert snapshot is not None
        assert snapshot.source == "llm_direct"

    async def test_path_d_does_not_write_selectors_to_db(
        self,
        db_writer,
        db_session,
        seeded_pair_d,
        mock_browser_session,
        llm_direct_response,
        monkeypatch,
    ):
        """In direct mode, selectors should never be cached."""
        monkeypatch.setenv("LLM_MODE", "direct")

        orchestrator = Orchestrator(db_writer=db_writer)

        with patch(
            "pipeline.llm_extractor.Extractor._call_llm",
            return_value=llm_direct_response,
        ):
            with patch(
                "pipeline.orchestrator.BrowserSession",
                return_value=mock_browser_session,
            ):
                await orchestrator.run_all()

        updated = db_writer.get_pair(seeded_pair_d["id"])
        assert updated["price_selector"] is None
        assert updated["stock_selector"] is None
