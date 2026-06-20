import pytest
from pipeline.orchestrator import Orchestrator
from unittest.mock import MagicMock


@pytest.fixture(scope="module")
def orchestrator():
    return Orchestrator(db_writer=MagicMock())


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
    def test_no_url_selector_mode_disabled(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "false")
        assert orchestrator.determine_path(_pair()) == "A"

    def test_no_url_selector_mode_enabled(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "true")
        assert orchestrator.determine_path(_pair()) == "A"

    def test_no_url_direct_mode(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "direct")
        assert orchestrator.determine_path(_pair()) == "A"

    def test_no_url_regardless_of_selectors(self, orchestrator, monkeypatch):
        # Selectors without a URL is an invalid state, but path logic should
        # still key on URL first
        monkeypatch.setenv("LLM_MODE", "selector")
        pair = _pair(price_selector=".price", stock_selector=".stock")
        assert orchestrator.determine_path(pair) == "A"


# ---------------------------------------------------------------------------
# Path C — URL + both selectors present (the production fast path)
# ---------------------------------------------------------------------------


class TestPathC:
    def test_url_and_both_selectors(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            price_selector="div[class*='price'] span",
            stock_selector="div[class*='availability'] span",
        )
        assert orchestrator.determine_path(pair) == "C"

    def test_path_c_regardless_of_llm_mode(self, orchestrator, monkeypatch):
        # When selectors are cached, LLM_MODE is irrelevant
        monkeypatch.setenv("LLM_MODE", "direct")
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            price_selector=".price",
            stock_selector=".stock",
        )
        assert orchestrator.determine_path(pair) == "C"

    def test_only_price_selector_is_not_path_c(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "false")
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            price_selector=".price",
            # stock_selector is None
        )
        assert orchestrator.determine_path(pair) != "C"

    def test_only_stock_selector_is_not_path_c(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "false")
        pair = _pair(
            product_url="https://sarasavi.lk/books/123",
            stock_selector=".stock",
            # price_selector is None
        )
        assert orchestrator.determine_path(pair) != "C"


# ---------------------------------------------------------------------------
# Path D — URL present, no selectors, LLM_MODE=direct
# ---------------------------------------------------------------------------


class TestPathD:
    def test_url_no_selectors_direct_mode(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "direct")
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair) == "D"

    def test_path_d_discovery_enabled_irrelevant_in_direct_mode(
        self, orchestrator, monkeypatch
    ):
        # LLM_DISCOVERY_ENABLED only affects Path B (selector mode)
        monkeypatch.setenv("LLM_MODE", "direct")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "true")
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair) == "D"


# ---------------------------------------------------------------------------
# Path B — URL present, no selectors, LLM_MODE=selector, discovery enabled
# ---------------------------------------------------------------------------


class TestPathB:
    def test_url_no_selectors_selector_mode_enabled(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "true")
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair) == "B"


# ---------------------------------------------------------------------------
# NEEDS_SETUP — URL present, no selectors, selector mode, discovery disabled
# ---------------------------------------------------------------------------


class TestNeedsSetup:
    def test_url_no_selectors_selector_mode_disabled(self, orchestrator, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "selector")
        monkeypatch.setenv("LLM_DISCOVERY_ENABLED", "false")
        pair = _pair(product_url="https://sarasavi.lk/books/123")
        assert orchestrator.determine_path(pair) == "NEEDS_SETUP"
