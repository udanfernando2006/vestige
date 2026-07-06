import os
import pytest
from pipeline.orchestrator import Orchestrator
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(scope="module")
def orchestrator():
    db_writer = MagicMock()

    # Force the mock get_settings() to return active env vars dynamically
    db_writer.get_settings.side_effect = lambda: {
        "LLM_MODE": os.environ.get("LLM_MODE", ""),
        "LLM_DISCOVERY_ENABLED": os.environ.get("LLM_DISCOVERY_ENABLED", ""),
    }

    return Orchestrator(db_writer=db_writer)


def _pair(
    product_url=None,
    price_selector=None,
    stock_selector=None,
    status="PENDING",
) -> dict:
    """Minimal tracking pair dict matching the shape returned by DBWriter.get_active_pairs()."""
    return {
        "id": 1,
        "book_id": 1,
        "store_id": 1,
        "product_url": product_url,
        "price_selector": price_selector,
        "stock_selector": stock_selector,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Path A — no product URL
# ---------------------------------------------------------------------------


class TestPathA:
    def test_no_url_selector_mode_disabled(self, orchestrator):
        settings = {"LLM_MODE": "selector", "LLM_DISCOVERY_ENABLED": "false"}
        assert orchestrator.determine_path(_pair(), settings) == "A"

    def test_no_url_selector_mode_enabled(self, orchestrator):
        settings = {"LLM_MODE": "selector", "LLM_DISCOVERY_ENABLED": "true"}
        assert orchestrator.determine_path(_pair(), settings) == "A"

    def test_no_url_direct_mode(self, orchestrator):
        settings = {"LLM_MODE": "direct"}
        assert orchestrator.determine_path(_pair(), settings) == "A"

    def test_no_url_regardless_of_selectors(self, orchestrator):
        settings = {"LLM_MODE": "selector", "LLM_DISCOVERY_ENABLED": "true"}
        pair = _pair(price_selector="div.price", stock_selector="div.stock")
        assert orchestrator.determine_path(pair, settings) == "A"


# ---------------------------------------------------------------------------
# Path C — URL + both selectors present (the production fast path)
# ---------------------------------------------------------------------------


class TestPathC:
    def test_url_and_both_selectors(self, orchestrator):
        settings = {"LLM_MODE": "selector", "LLM_DISCOVERY_ENABLED": "false"}
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            price_selector="div[class*='price'] span",
            stock_selector="div[class*='availability'] span",
        )
        assert orchestrator.determine_path(pair, settings) == "C"

    def test_path_c_regardless_of_llm_mode(self, orchestrator):
        settings = {"LLM_MODE": "direct"}
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            price_selector=".price",
            stock_selector=".stock",
        )
        assert orchestrator.determine_path(pair, settings) == "C"

    def test_only_price_selector_is_not_path_c(self, orchestrator):
        settings = {"LLM_MODE": "direct"}
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            price_selector=".price",
            # stock_selector is None
        )
        assert orchestrator.determine_path(pair, settings) != "C"

    def test_only_stock_selector_is_not_path_c(self, orchestrator):
        settings = {"LLM_MODE": "direct"}
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            stock_selector=".stock",
            # price_selector is None
        )
        assert orchestrator.determine_path(pair, settings) != "C"


# ---------------------------------------------------------------------------
# Path D — URL present, no selectors, LLM_MODE=direct
# ---------------------------------------------------------------------------


class TestPathD:
    def test_url_no_selectors_direct_mode(self, orchestrator):
        settings = {"LLM_MODE": "direct"}
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair, settings) == "D"

    def test_path_d_discovery_enabled_irrelevant_in_direct_mode(self, orchestrator):
        # LLM_DISCOVERY_ENABLED only affects Path B (selector mode)
        settings = {"LLM_MODE": "direct", "LLM_DISCOVERY_ENABLED": "true"}
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair, settings) == "D"


# ---------------------------------------------------------------------------
# Path B — URL present, no selectors, LLM_MODE=selector, discovery enabled
# ---------------------------------------------------------------------------


class TestPathB:
    def test_url_no_selectors_selector_mode_enabled(self, orchestrator):
        settings = {"LLM_MODE": "selector", "LLM_DISCOVERY_ENABLED": "true"}
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair, settings) == "B"


# ---------------------------------------------------------------------------
# NEEDS_SETUP — URL present, no selectors, selector mode, discovery disabled
# ---------------------------------------------------------------------------


class TestNeedsSetup:
    def test_url_no_selectors_selector_mode_disabled(self, orchestrator):
        settings = {"LLM_MODE": "selector", "LLM_DISCOVERY_ENABLED": "false"}
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair, settings) == "NEEDS_SETUP"


# ---------------------------------------------------------------------------
# Path A failure regression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "crawl_result",
    [None, {"success": False, "error": "No search form found"}],
)
async def test_path_a_raises_when_crawl_fails(orchestrator, crawl_result):
    pair = {
        "id": 1,
        "book_id": 1,
        "store_id": 1,
        "book_name": "The Last Wish",
        "book_isbn": "9780316452465",
        "store_name": "Sarasavi",
        "product_url": None,
        "price_selector": None,
        "stock_selector": None,
        "status": "PENDING",
    }
    session = MagicMock()
    settings = {"LLM_MODE": "direct", "LLM_DISCOVERY_ENABLED": "false"}

    orchestrator.db_writer.get_store.return_value = {
        "base_url": "https://sarasavi.lk",
        "search_url_template": "https://sarasavi.lk/?s=test",
    }
    orchestrator.db_writer.update_pair_url = MagicMock()
    orchestrator.db_writer.update_store_search_template = MagicMock()

    with patch(
        "pipeline.orchestrator.Crawler.find_product_url",
        new=AsyncMock(return_value=crawl_result),
    ):
        with pytest.raises(Exception, match="Crawler failed to discover URL"):
            await orchestrator._run_pair_path_a(pair, session, settings)
