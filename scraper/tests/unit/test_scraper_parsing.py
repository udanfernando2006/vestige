import pytest
from pipeline.scraper import Scraper


@pytest.fixture(scope="module")
def scraper():
    return Scraper()


# ---------------------------------------------------------------------------
# parse_price
# ---------------------------------------------------------------------------


class TestParsePrice:
    def test_lkr_with_comma_formatting(self, scraper):
        assert scraper.parse_price("LKR 1,500.00") == 1500.00

    def test_lkr_no_space(self, scraper):
        assert scraper.parse_price("LKR1500.00") == 1500.00

    def test_rs_prefix(self, scraper):
        assert scraper.parse_price("Rs. 850") == 850.00

    def test_rs_no_period(self, scraper):
        assert scraper.parse_price("Rs 850") == 850.00

    def test_usd(self, scraper):
        assert scraper.parse_price("$12.99") == 12.99

    def test_bare_number_with_commas(self, scraper):
        assert scraper.parse_price("2,499.00") == 2499.00

    def test_bare_integer(self, scraper):
        assert scraper.parse_price("1500") == 1500.00

    def test_surrounding_whitespace_stripped(self, scraper):
        assert scraper.parse_price("  LKR 1,200.00  ") == 1200.00

    def test_empty_string_returns_none(self, scraper):
        assert scraper.parse_price("") is None

    def test_none_input_returns_none(self, scraper):
        assert scraper.parse_price(None) is None

    def test_non_numeric_text_returns_none(self, scraper):
        assert scraper.parse_price("Out of Stock") is None

    def test_leading_punctuation_stripped(self, scraper):
        # Some stores have artefacts like ": LKR 1,500.00"
        assert scraper.parse_price(": LKR 1,500.00") == 1500.00

    def test_multiple_numbers_returns_first(self, scraper):
        # "Save LKR 200 | Now LKR 1,300" — should return the first price found
        result = scraper.parse_price("Save LKR 200 | Now LKR 1,300")
        assert result == 200.00  # first numeric value wins

    def test_zero_price(self, scraper):
        # Free books / promotional items
        assert scraper.parse_price("LKR 0.00") == 0.00


# ---------------------------------------------------------------------------
# parse_stock_status
# ---------------------------------------------------------------------------


class TestParseStockStatus:
    # --- in-stock signals ---

    def test_in_stock(self, scraper):
        assert scraper.parse_stock_status("In Stock") is True

    def test_in_stock_uppercase(self, scraper):
        assert scraper.parse_stock_status("IN STOCK") is True

    def test_add_to_cart(self, scraper):
        assert scraper.parse_stock_status("Add to Cart") is True

    def test_add_to_basket(self, scraper):
        assert scraper.parse_stock_status("Add to Basket") is True

    def test_available(self, scraper):
        assert scraper.parse_stock_status("Available") is True

    def test_in_stock_with_quantity(self, scraper):
        # "Only 3 left in stock" should still read as in-stock
        assert scraper.parse_stock_status("Only 3 left in stock") is True

    def test_low_stock_with_count(self, scraper):
        # Regression test: the confirmed real-world case that prompted the
        # built-in "low stock:? \d+ left" pattern — previously fell through
        # to None (surfaced as status=ERROR, reason=unparseable_stock_status).
        assert scraper.parse_stock_status("Low stock: 4 left") is True

    def test_low_stock_without_colon(self, scraper):
        # Pattern uses ":?" — colon is optional
        assert scraper.parse_stock_status("Low stock 12 left") is True

    def test_low_stock_case_insensitive(self, scraper):
        assert scraper.parse_stock_status("LOW STOCK: 1 LEFT") is True

    # --- custom_in / custom_out patterns ---

    def test_custom_in_pattern_matches(self, scraper):
        assert (
            scraper.parse_stock_status(
                "Ships in 2-3 days", custom_in=r"ships in \d+-\d+ days"
            )
            is True
        )

    def test_custom_out_pattern_matches(self, scraper):
        assert (
            scraper.parse_stock_status(
                "Currently backordered", custom_out=r"backordered"
            )
            is False
        )

    def test_custom_patterns_are_comma_separated(self, scraper):
        patterns = r"backordered,discontinued,no longer sold"
        assert (
            scraper.parse_stock_status(
                "This title is discontinued", custom_out=patterns
            )
            is False
        )

    def test_custom_pattern_does_not_override_builtin_when_absent(self, scraper):
        # A custom_in pattern that doesn't match the text shouldn't
        # accidentally suppress the built-in phrase list from still working.
        assert (
            scraper.parse_stock_status(
                "In Stock", custom_in=r"totally unrelated pattern"
            )
            is True
        )

    def test_custom_out_pattern_still_beats_builtin_in_stock_phrase(self, scraper):
        # Out-of-stock-first ordering must hold even when the out-of-stock
        # signal comes from a *custom* pattern and the in-stock signal comes
        # from the *built-in* phrase list — same substring-trap precedence
        # rule applies regardless of which list a match came from.
        text = "Available now, ships when restocked"
        assert (
            scraper.parse_stock_status(text, custom_out=r"ships when restocked")
            is False
        )

    def test_blank_custom_patterns_do_not_error(self, scraper):
        # Empty string is the default — must not raise or match everything.
        assert (
            scraper.parse_stock_status("some random text", custom_in="", custom_out="")
            is None
        )

    def test_custom_patterns_with_stray_whitespace_are_trimmed(self, scraper):
        assert (
            scraper.parse_stock_status(
                "Item is currently reserved", custom_out=" reserved , held "
            )
            is False
        )

    # --- out-of-stock signals ---

    def test_out_of_stock(self, scraper):
        assert scraper.parse_stock_status("Out of Stock") is False

    def test_sold_out(self, scraper):
        assert scraper.parse_stock_status("Sold Out") is False

    def test_unavailable(self, scraper):
        assert scraper.parse_stock_status("Unavailable") is False

    def test_not_available(self, scraper):
        assert scraper.parse_stock_status("Not Available") is False

    def test_out_of_stock_lowercase(self, scraper):
        assert scraper.parse_stock_status("out of stock") is False

    # --- unrecognisable / edge cases ---

    def test_empty_string_returns_none(self, scraper):
        assert scraper.parse_stock_status("") is None

    def test_none_returns_none(self, scraper):
        assert scraper.parse_stock_status(None) is None

    def test_random_text_returns_none(self, scraper):
        assert scraper.parse_stock_status("Click here to buy") is None

    def test_pure_whitespace_returns_none(self, scraper):
        assert scraper.parse_stock_status("   ") is None
