import pytest
from unittest.mock import MagicMock
from pipeline.orchestrator import Orchestrator
from models.result import AvailabilityResult


@pytest.fixture
def orchestrator():
    # _detect_change touches no DB and reads no settings — a bare MagicMock
    # is enough; unlike test_orchestrator_paths.py's fixture, there's no
    # get_settings() side_effect to wire up here at all.
    return Orchestrator(db_writer=MagicMock())


class TestDetectChange:
    def test_first_ever_snapshot_is_not_a_change(self, orchestrator):
        availability = AvailabilityResult(
            in_stock=True, price=1500.00, status="IN_STOCK"
        )
        assert orchestrator._detect_change(None, availability) is None

    def test_status_change_with_no_price_this_run(self, orchestrator):
        last = {"status": "IN_STOCK", "in_stock": True, "price": 1500.00}
        availability = AvailabilityResult(
            in_stock=False, price=None, status="OUT_OF_STOCK"
        )

        change = orchestrator._detect_change(last, availability)

        assert change == {
            "from_status": "IN_STOCK",
            "to_status": "OUT_OF_STOCK",
            "from_price": 1500.00,
            "to_price": None,
        }

    def test_price_only_change_same_status(self, orchestrator):
        last = {"status": "IN_STOCK", "in_stock": True, "price": 1500.00}
        availability = AvailabilityResult(
            in_stock=True, price=1400.00, status="IN_STOCK"
        )

        change = orchestrator._detect_change(last, availability)

        assert change == {
            "from_status": "IN_STOCK",
            "to_status": "IN_STOCK",
            "from_price": 1500.00,
            "to_price": 1400.00,
        }

    def test_status_and_price_both_change(self, orchestrator):
        last = {"status": "OUT_OF_STOCK", "in_stock": False, "price": None}
        availability = AvailabilityResult(
            in_stock=True, price=1450.00, status="IN_STOCK"
        )

        change = orchestrator._detect_change(last, availability)

        assert change == {
            "from_status": "OUT_OF_STOCK",
            "to_status": "IN_STOCK",
            "from_price": None,
            "to_price": 1450.00,
        }

    def test_identical_status_and_price_is_not_a_change(self, orchestrator):
        last = {"status": "IN_STOCK", "in_stock": True, "price": 1500.00}
        availability = AvailabilityResult(
            in_stock=True, price=1500.00, status="IN_STOCK"
        )

        assert orchestrator._detect_change(last, availability) is None

    def test_floating_point_noise_does_not_trigger_a_change(self, orchestrator):
        # The kind of representation drift a re-parsed price can pick up
        # between runs without the underlying value actually moving — the
        # round(..., 2) calls are what's supposed to absorb this.
        last = {"status": "IN_STOCK", "in_stock": True, "price": 1500.00}
        availability = AvailabilityResult(
            in_stock=True, price=1499.9999999999998, status="IN_STOCK"
        )
        assert orchestrator._detect_change(last, availability) is None


class TestCollectRunSummary:
    # Regression test for the "total" vs "total_pairs" key bug flagged last
    # message — RunService.getRecentRuns() on the Java side reads
    # total_pairs specifically, and silently defaults to 0 if that exact key
    # isn't there.
    def test_returns_total_pairs_key(self, orchestrator):
        results = [
            {"pair_id": 1, "status": "IN_STOCK"},
            {"pair_id": 2, "status": "NEEDS_SETUP"},
            {"pair_id": 3, "status": "ERROR"},
        ]
        summary = orchestrator.collect_run_summary(results)
        assert summary["total_pairs"] == 3
        assert summary["completed"] == 1
        assert summary["needs_setup"] == [2]
        assert summary["errors"] == 1


# ---------------------------------------------------------------------------
# _classify_stock_fallback — DIRECT_* first, then SELECTOR_*, never raises
# ---------------------------------------------------------------------------


class TestClassifyStockFallback:
    def test_uses_direct_credentials_when_present(self, orchestrator, monkeypatch):
        settings = {
            "DIRECT_API_BASE": "http://direct.invalid/v1",
            "DIRECT_API_KEY": "key",
            "DIRECT_MODEL": "direct-model",
            "SELECTOR_API_BASE": "http://selector.invalid/v1",
            "SELECTOR_MODEL": "selector-model",
        }
        captured_configs = []

        class FakeExtractor:
            def __init__(self, config):
                captured_configs.append(config)

            def classify_stock_status(self, raw_text):
                return True

        monkeypatch.setattr("pipeline.orchestrator.Extractor", FakeExtractor)
        result = orchestrator._classify_stock_fallback(settings, "Low stock: 4 left")

        assert result is True
        assert len(captured_configs) == 1
        assert captured_configs[0]["api_base"] == "http://direct.invalid/v1"
        assert captured_configs[0]["model_name"] == "direct-model"

    def test_falls_back_to_selector_when_direct_not_configured(
        self, orchestrator, monkeypatch
    ):
        settings = {
            "SELECTOR_API_BASE": "http://selector.invalid/v1",
            "SELECTOR_API_KEY": "key",
            "SELECTOR_MODEL": "selector-model",
        }
        captured_configs = []

        class FakeExtractor:
            def __init__(self, config):
                captured_configs.append(config)

            def classify_stock_status(self, raw_text):
                return False

        monkeypatch.setattr("pipeline.orchestrator.Extractor", FakeExtractor)
        result = orchestrator._classify_stock_fallback(settings, "Currently unlisted")

        assert result is False
        assert len(captured_configs) == 1
        assert captured_configs[0]["model_name"] == "selector-model"

    def test_falls_back_to_selector_when_direct_returns_none(
        self, orchestrator, monkeypatch
    ):
        # DIRECT_* is configured but the model itself couldn't classify —
        # this should still try SELECTOR_*, not stop at the first attempt.
        settings = {
            "DIRECT_API_BASE": "http://direct.invalid/v1",
            "DIRECT_MODEL": "direct-model",
            "SELECTOR_API_BASE": "http://selector.invalid/v1",
            "SELECTOR_MODEL": "selector-model",
        }
        call_order = []

        class FakeExtractor:
            def __init__(self, config):
                self.model_name = config["model_name"]

            def classify_stock_status(self, raw_text):
                call_order.append(self.model_name)
                if self.model_name == "direct-model":
                    return None
                return True

        monkeypatch.setattr("pipeline.orchestrator.Extractor", FakeExtractor)
        result = orchestrator._classify_stock_fallback(settings, "some text")

        assert result is True
        assert call_order == ["direct-model", "selector-model"]

    def test_returns_none_when_neither_role_configured(self, orchestrator):
        result = orchestrator._classify_stock_fallback({}, "some text")
        assert result is None

    def test_returns_none_when_both_attempts_raise(self, orchestrator, monkeypatch):
        settings = {
            "DIRECT_API_BASE": "http://direct.invalid/v1",
            "DIRECT_MODEL": "direct-model",
            "SELECTOR_API_BASE": "http://selector.invalid/v1",
            "SELECTOR_MODEL": "selector-model",
        }

        class FailingExtractor:
            def __init__(self, config):
                raise ValueError("boom")

        monkeypatch.setattr("pipeline.orchestrator.Extractor", FailingExtractor)
        # Must not raise — falls through to None so the caller keeps ERROR.
        result = orchestrator._classify_stock_fallback(settings, "some text")
        assert result is None

    def test_missing_model_name_skips_that_role(self, orchestrator, monkeypatch):
        # DIRECT_API_BASE present but DIRECT_MODEL missing — must not
        # attempt construction with a None model_name; should skip straight
        # to SELECTOR_*.
        settings = {
            "DIRECT_API_BASE": "http://direct.invalid/v1",
            "SELECTOR_API_BASE": "http://selector.invalid/v1",
            "SELECTOR_MODEL": "selector-model",
        }
        captured_configs = []

        class FakeExtractor:
            def __init__(self, config):
                captured_configs.append(config)

            def classify_stock_status(self, raw_text):
                return True

        monkeypatch.setattr("pipeline.orchestrator.Extractor", FakeExtractor)
        result = orchestrator._classify_stock_fallback(settings, "some text")

        assert result is True
        assert len(captured_configs) == 1
        assert captured_configs[0]["model_name"] == "selector-model"


# ---------------------------------------------------------------------------
# _apply_stock_fallback_if_needed — the gate that decides whether the
# fallback fires at all
# ---------------------------------------------------------------------------


class TestApplyStockFallbackIfNeeded:
    def test_fires_and_overwrites_on_unparseable_stock_status(
        self, orchestrator, monkeypatch
    ):
        scrape_data = AvailabilityResult(
            raw_stock_text="Low stock: 4 left",
            status="ERROR",
            reason="unparseable_stock_status",
        )
        monkeypatch.setattr(
            orchestrator, "_classify_stock_fallback", lambda settings, text: True
        )
        result = orchestrator._apply_stock_fallback_if_needed(scrape_data, {})

        assert result.in_stock is True
        assert result.status == "IN_STOCK"
        assert result.reason is None

    def test_false_fallback_sets_out_of_stock(self, orchestrator, monkeypatch):
        scrape_data = AvailabilityResult(
            raw_stock_text="Currently unlisted",
            status="ERROR",
            reason="unparseable_stock_status",
        )
        monkeypatch.setattr(
            orchestrator, "_classify_stock_fallback", lambda settings, text: False
        )
        result = orchestrator._apply_stock_fallback_if_needed(scrape_data, {})

        assert result.in_stock is False
        assert result.status == "OUT_OF_STOCK"
        assert result.reason is None

    def test_leaves_error_status_when_fallback_also_fails(
        self, orchestrator, monkeypatch
    ):
        scrape_data = AvailabilityResult(
            raw_stock_text="Completely ambiguous text",
            status="ERROR",
            reason="unparseable_stock_status",
        )
        monkeypatch.setattr(
            orchestrator, "_classify_stock_fallback", lambda settings, text: None
        )
        result = orchestrator._apply_stock_fallback_if_needed(scrape_data, {})

        assert result.status == "ERROR"
        assert result.reason == "unparseable_stock_status"

    def test_does_not_fire_when_status_is_not_error(self, orchestrator, monkeypatch):
        scrape_data = AvailabilityResult(
            raw_stock_text="In Stock", status="IN_STOCK", in_stock=True
        )
        fallback = MagicMock()
        monkeypatch.setattr(orchestrator, "_classify_stock_fallback", fallback)
        orchestrator._apply_stock_fallback_if_needed(scrape_data, {})
        fallback.assert_not_called()

    def test_does_not_fire_when_reason_is_not_unparseable_stock_status(
        self, orchestrator, monkeypatch
    ):
        # e.g. a different ERROR reason, like a selector genuinely matching
        # nothing — that's the separate selector_not_found path, not this one.
        scrape_data = AvailabilityResult(
            raw_stock_text="some text", status="ERROR", reason="http_error_500"
        )
        fallback = MagicMock()
        monkeypatch.setattr(orchestrator, "_classify_stock_fallback", fallback)
        orchestrator._apply_stock_fallback_if_needed(scrape_data, {})
        fallback.assert_not_called()

    def test_does_not_fire_when_no_raw_stock_text(self, orchestrator, monkeypatch):
        # Selector matched nothing at all — this is selector_not_found
        # territory, checked separately right after this call in each path;
        # there's no text here to classify in the first place.
        scrape_data = AvailabilityResult(
            raw_stock_text=None, status="ERROR", reason="unparseable_stock_status"
        )
        fallback = MagicMock()
        monkeypatch.setattr(orchestrator, "_classify_stock_fallback", fallback)
        orchestrator._apply_stock_fallback_if_needed(scrape_data, {})
        fallback.assert_not_called()
