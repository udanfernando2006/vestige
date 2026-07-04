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
