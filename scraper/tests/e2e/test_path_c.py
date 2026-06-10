import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from pipeline.orchestrator import Orchestrator
from models.result import AvailabilityResult


@pytest.fixture
def seeded_pair_c(db_session, db_writer):
    """A tracking pair in PENDING state with URL and selectors already set."""
    from db.models import Book, Store, TrackingPair

    store = Store(name="path_c_store", base_url="https://sarasavi.lk")
    book = Book(name="The Last Wish", isbn="9780316452001", is_series_entry=False)
    db_session.add_all([store, book])
    db_session.commit()
    pair = TrackingPair(
        book_id=book.id,
        store_id=store.id,
        product_url="https://sarasavi.lk/books/9780316452001",
        price_selector="div[class*='price'] span",
        stock_selector="div[class*='availability'] span",
        status="PENDING",
    )
    db_session.add(pair)
    db_session.commit()
    return db_writer.get_pair(pair.id)


class TestPathC:

    async def test_path_c_writes_in_stock_snapshot(
        self, db_writer, db_session, seeded_pair_c, mock_browser_session
    ):
        from db.models import AvailabilitySnapshot

        expected_result = AvailabilityResult(
            in_stock=True,
            price=1500.00,
            currency="LKR",
            raw_price_text="LKR 1,500.00",
            raw_stock_text="In Stock",
            scraped_at=datetime.now(timezone.utc),
            status="IN_STOCK",
            source="scraper",
        )

        orchestrator = Orchestrator(db_writer=db_writer)

        with patch(
            "pipeline.scraper.Scraper.scrape",
            new=AsyncMock(return_value=expected_result),
        ):
            with patch(
                "pipeline.orchestrator.BrowserSession",
                return_value=mock_browser_session,
            ):
                await orchestrator.run_all()

        snapshot = (
            db_session.query(AvailabilitySnapshot)
            .filter_by(pair_id=seeded_pair_c["id"])
            .first()
        )
        assert snapshot is not None
        assert snapshot.status == "IN_STOCK"

    async def test_path_c_updates_pair_status_to_in_stock(
        self, db_writer, db_session, seeded_pair_c, mock_browser_session
    ):

        result = AvailabilityResult(
            in_stock=True,
            price=1500.00,
            currency="LKR",
            raw_price_text="LKR 1,500.00",
            raw_stock_text="In Stock",
            scraped_at=datetime.now(timezone.utc),
            status="IN_STOCK",
            source="scraper",
        )

        orchestrator = Orchestrator(db_writer=db_writer)

        with patch(
            "pipeline.scraper.Scraper.scrape", new=AsyncMock(return_value=result)
        ):
            with patch(
                "pipeline.orchestrator.BrowserSession",
                return_value=mock_browser_session,
            ):
                await orchestrator.run_all()

        updated = db_writer.get_pair(seeded_pair_c["id"])
        assert updated["status"] == "IN_STOCK"

    async def test_path_c_selector_not_found_clears_selectors(
        self, db_writer, db_session, seeded_pair_c, mock_browser_session
    ):
        """
        When the Scraper returns reason='selector_not_found', the Orchestrator
        must clear the cached selectors and transition the pair to NEEDS_SETUP.
        """

        error_result = AvailabilityResult(
            in_stock=None,
            price=None,
            currency=None,
            raw_price_text=None,
            raw_stock_text=None,
            scraped_at=datetime.now(timezone.utc),
            status="ERROR",
            reason="selector_not_found",
            source="scraper",
        )

        orchestrator = Orchestrator(db_writer=db_writer)

        with patch(
            "pipeline.scraper.Scraper.scrape", new=AsyncMock(return_value=error_result)
        ):
            with patch(
                "pipeline.orchestrator.BrowserSession",
                return_value=mock_browser_session,
            ):
                await orchestrator.run_all()

        updated = db_writer.get_pair(seeded_pair_c["id"])
        assert updated["status"] == "NEEDS_SETUP"
        assert updated["price_selector"] is None
        assert updated["stock_selector"] is None
