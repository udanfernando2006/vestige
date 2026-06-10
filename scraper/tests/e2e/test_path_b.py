import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from pipeline.orchestrator import Orchestrator
from models.result import AvailabilityResult


@pytest.fixture
def seeded_pair_b(db_session, db_writer):
    from db.models import Book, Store, TrackingPair

    store = Store(name="path_b_store", base_url="https://sarasavi.lk")
    book = Book(name="Sword of Destiny", isbn="9780316389001", is_series_entry=True)
    db_session.add_all([store, book])
    db_session.commit()
    pair = TrackingPair(
        book_id=book.id,
        store_id=store.id,
        product_url="https://sarasavi.lk/books/sword-of-destiny",
        price_selector=None,
        stock_selector=None,
        status="NEEDS_SETUP",
    )
    db_session.add(pair)
    db_session.commit()
    return db_writer.get_pair(pair.id)


def _mock_subprocess_success(pair_id: int) -> MagicMock:
    """
    Simulates a successful discover_selectors.py --pair-id N --commit run.
    stdout is the JSON the tool prints; returncode=0 means committed.
    """
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(
        {
            "price_selector": "div[class*='price'] span",
            "stock_selector": "div[class*='availability'] span",
            "price_sample": "LKR 1,500.00",
            "stock_sample": "In Stock",
            "model_used": "anthropic/claude-haiku-4-5",
            "committed": True,
        }
    )
    result.stderr = ""
    return result


def _mock_subprocess_failure() -> MagicMock:
    result = MagicMock()
    result.returncode = 1
    result.stdout = json.dumps(
        {
            "committed": False,
            "reason": "stock_selector_returned_no_match",
        }
    )
    result.stderr = ""
    return result


class TestPathB:

    async def test_path_b_successful_discovery_transitions_to_pending(
        self, db_writer, db_session, seeded_pair_b, monkeypatch, mock_browser_session
    ):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "true")

        orchestrator = Orchestrator(db_writer=db_writer)
        mock_result = _mock_subprocess_success(seeded_pair_b["id"])

        def simulate_subprocess_db_write(*args, **kwargs):
            from db.models import TrackingPair

            pair = (
                db_session.query(TrackingPair).filter_by(id=seeded_pair_b["id"]).first()
            )
            if pair:
                pair.price_selector = "div[class*='price'] span"
                pair.stock_selector = "div[class*='availability'] span"
                pair.status = "PENDING"
                db_session.commit()
            return mock_result

        validation_result = AvailabilityResult(
            in_stock=True,
            price=1500.00,
            currency="LKR",
            raw_price_text="LKR 1,500.00",
            raw_stock_text="In Stock",
            scraped_at=datetime.now(timezone.utc),
            status="IN_STOCK",
            source="scraper",
        )

        with patch("subprocess.run", side_effect=simulate_subprocess_db_write):
            with patch(
                "pipeline.scraper.Scraper.scrape",
                new=AsyncMock(return_value=validation_result),
            ):
                with patch(
                    "pipeline.orchestrator.BrowserSession",
                    return_value=mock_browser_session,
                ):
                    await orchestrator.run_pair(seeded_pair_b, path="B")

        updated = db_writer.get_pair(seeded_pair_b["id"])
        assert updated["status"] == "PENDING"

    async def test_path_b_failed_discovery_leaves_needs_setup(
        self, db_writer, db_session, seeded_pair_b, monkeypatch
    ):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "true")

        orchestrator = Orchestrator(db_writer=db_writer)
        mock_result = _mock_subprocess_failure()

        with patch("subprocess.run", return_value=mock_result):
            await orchestrator.run_pair(seeded_pair_b, path="B")

        updated = db_writer.get_pair(seeded_pair_b["id"])
        assert updated["status"] == "NEEDS_SETUP"

    async def test_path_b_discovery_disabled_marks_needs_setup_without_subprocess(
        self, db_writer, db_session, seeded_pair_b, monkeypatch
    ):
        """
        When LLM_DISCOVERY_ENABLED=false, the Orchestrator should not invoke
        the subprocess at all and the pair stays NEEDS_SETUP.
        """
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "false")

        orchestrator = Orchestrator(db_writer=db_writer)

        with patch("subprocess.run") as mock_sub:
            await orchestrator.run_pair(seeded_pair_b, path="B")
            mock_sub.assert_not_called()

        updated = db_writer.get_pair(seeded_pair_b["id"])
        assert updated["status"] == "NEEDS_SETUP"
