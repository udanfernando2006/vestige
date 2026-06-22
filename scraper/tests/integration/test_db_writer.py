import os
import base64
import secrets
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from models.result import AvailabilityResult
from db.models import SettingOverride
from security.crypto import SettingsCipher

# ---------------------------------------------------------------------------
# Helpers — seed minimum required rows
# ---------------------------------------------------------------------------


def seed_store(session, name="sarasavi", base_url="https://sarasavi.lk"):
    from db.models import Store

    store = Store(name=name, base_url=base_url)
    session.add(store)
    session.commit()  # assigns store.id without committing
    return store


def seed_book(session, name="The Last Wish", isbn="9780316452465"):
    from db.models import Book

    book = Book(name=name, isbn=isbn, is_series_entry=False)
    session.add(book)
    session.commit()
    return book


def seed_pair(
    session,
    book_id,
    store_id,
    product_url=None,
    price_selector=None,
    stock_selector=None,
    status="PENDING",
):
    from db.models import TrackingPair

    pair = TrackingPair(
        book_id=book_id,
        store_id=store_id,
        product_url=product_url,
        price_selector=price_selector,
        stock_selector=stock_selector,
        status=status,
    )
    session.add(pair)
    session.commit()
    return pair


def _result(status="IN_STOCK", price=1500.00, in_stock=True, source="scraper"):
    return AvailabilityResult(
        in_stock=in_stock,
        price=price,
        currency="LKR",
        raw_price_text="LKR 1,500.00",
        raw_stock_text="In Stock",
        scraped_at=datetime.now(timezone.utc),
        status=status,
        source=source,
    )


# ---------------------------------------------------------------------------
# get_active_pairs
# ---------------------------------------------------------------------------


class TestGetActivePairs:
    def test_returns_pending_pairs(self, db_writer, db_session):
        store = seed_store(db_session)
        book = seed_book(db_session)
        seed_pair(db_session, book.id, store.id, status="PENDING")
        pairs = db_writer.get_active_pairs()
        assert any(p["status"] == "PENDING" for p in pairs)

    def test_excludes_skip_status(self, db_writer, db_session):
        store = seed_store(
            db_session, name="skipped_store", base_url="https://skipped.lk"
        )
        book = seed_book(db_session, name="Skipped Book", isbn="9990000000001")
        seed_pair(db_session, book.id, store.id, status="SKIP")
        pairs = db_writer.get_active_pairs()
        assert not any(p["status"] == "SKIP" for p in pairs)

    def test_excludes_needs_setup_status(self, db_writer, db_session):
        store = seed_store(db_session, name="setup_store", base_url="https://setup.lk")
        book = seed_book(db_session, name="Setup Book", isbn="9990000000002")
        seed_pair(db_session, book.id, store.id, status="NEEDS_SETUP")
        pairs = db_writer.get_active_pairs()
        assert not any(p["status"] == "NEEDS_SETUP" for p in pairs)

    def test_returns_dicts_not_orm_objects(self, db_writer, db_session):
        store = seed_store(db_session, name="dict_store", base_url="https://dict.lk")
        book = seed_book(db_session, name="Dict Book", isbn="9990000000003")
        seed_pair(db_session, book.id, store.id)
        pairs = db_writer.get_active_pairs()
        for pair in pairs:
            assert isinstance(pair, dict)


# ---------------------------------------------------------------------------
# write_snapshot + get_last_snapshot
# ---------------------------------------------------------------------------


class TestSnapshotRoundTrip:
    def test_write_and_retrieve(self, db_writer, db_session):
        store = seed_store(db_session, name="snap_store", base_url="https://snap.lk")
        book = seed_book(db_session, name="Snap Book", isbn="9990000000010")
        pair = seed_pair(db_session, book.id, store.id)

        db_writer.write_snapshot(pair.id, _result())
        snapshot = db_writer.get_last_snapshot(pair.id)

        assert snapshot is not None
        assert snapshot["status"] == "IN_STOCK"
        assert float(snapshot["price"]) == 1500.00

    def test_get_last_snapshot_no_rows_returns_none(self, db_writer, db_session):
        store = seed_store(db_session, name="empty_store", base_url="https://empty.lk")
        book = seed_book(db_session, name="Empty Book", isbn="9990000000011")
        pair = seed_pair(db_session, book.id, store.id)
        assert db_writer.get_last_snapshot(pair.id) is None

    def test_write_snapshot_updates_pair_status(self, db_writer, db_session):
        store = seed_store(
            db_session, name="status_store", base_url="https://status.lk"
        )
        book = seed_book(db_session, name="Status Book", isbn="9990000000012")
        pair = seed_pair(db_session, book.id, store.id, status="PENDING")

        db_writer.write_snapshot(pair.id, _result(status="IN_STOCK"))
        updated = db_writer.get_pair(pair.id)
        assert updated["status"] == "IN_STOCK"

    def test_source_field_written_to_snapshot(self, db_writer, db_session):
        store = seed_store(db_session, name="src_store", base_url="https://src.lk")
        book = seed_book(db_session, name="Src Book", isbn="9990000000013")
        pair = seed_pair(db_session, book.id, store.id)

        db_writer.write_snapshot(pair.id, _result(source="llm_direct"))
        snapshot = db_writer.get_last_snapshot(pair.id)
        assert snapshot["source"] == "llm_direct"

    def test_snapshots_are_append_only(self, db_writer, db_session):
        """Writing a second snapshot leaves the first row intact."""
        from db.models import AvailabilitySnapshot

        store = seed_store(
            db_session, name="append_store", base_url="https://append.lk"
        )
        book = seed_book(db_session, name="Append Book", isbn="9990000000014")
        pair = seed_pair(db_session, book.id, store.id)

        db_writer.write_snapshot(pair.id, _result(status="IN_STOCK"))
        db_writer.write_snapshot(pair.id, _result(status="OUT_OF_STOCK"))

        count = (
            db_session.query(AvailabilitySnapshot).filter_by(pair_id=pair.id).count()
        )
        assert count == 2


# ---------------------------------------------------------------------------
# update_pair_selectors + clear_pair_selectors
# ---------------------------------------------------------------------------


class TestSelectorManagement:
    def test_update_selectors_transitions_needs_setup_to_pending(
        self, db_writer, db_session
    ):
        store = seed_store(db_session, name="sel_store", base_url="https://sel.lk")
        book = seed_book(db_session, name="Sel Book", isbn="9990000000020")
        pair = seed_pair(db_session, book.id, store.id, status="NEEDS_SETUP")

        db_writer.update_pair_selectors(
            pair.id,
            price_sel="div[class*='price'] span",
            stock_sel="div[class*='availability'] span",
        )
        updated = db_writer.get_pair(pair.id)
        assert updated["status"] == "PENDING"
        assert updated["price_selector"] == "div[class*='price'] span"

    def test_clear_selectors_transitions_to_needs_setup(self, db_writer, db_session):
        store = seed_store(db_session, name="clr_store", base_url="https://clr.lk")
        book = seed_book(db_session, name="Clr Book", isbn="9990000000021")
        pair = seed_pair(
            db_session,
            book.id,
            store.id,
            price_selector=".price",
            stock_selector=".stock",
            status="IN_STOCK",
        )

        db_writer.clear_pair_selectors(pair.id)
        updated = db_writer.get_pair(pair.id)
        assert updated["price_selector"] is None
        assert updated["stock_selector"] is None
        assert updated["status"] == "NEEDS_SETUP"

    def test_update_selectors_sets_selector_found_at(self, db_writer, db_session):
        store = seed_store(db_session, name="ts_store", base_url="https://ts.lk")
        book = seed_book(db_session, name="TS Book", isbn="9990000000022")
        pair = seed_pair(db_session, book.id, store.id, status="NEEDS_SETUP")

        db_writer.update_pair_selectors(pair.id, ".price", ".stock")
        updated = db_writer.get_pair(pair.id)
        assert updated["selector_found_at"] is not None


# ---------------------------------------------------------------------------
# update_store_search_template
# ---------------------------------------------------------------------------


class TestStoreSearchTemplate:
    def test_caches_search_url_template(self, db_writer, db_session):
        store = seed_store(db_session, name="tpl_store", base_url="https://tpl.lk")
        template = "https://tpl.lk/?s=test"

        db_writer.update_store_search_template(store.id, template)
        updated = db_writer.get_store(store.id)
        assert updated["search_url_template"] == template


# ---------------------------------------------------------------------------
# Settings & Configuration
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_cipher():
    """Provides a functional cipher instance using a compliant generated key."""
    raw_key = secrets.token_bytes(32)
    key_b64 = base64.urlsafe_b64encode(raw_key).decode("ascii")
    return SettingsCipher(key_b64)


class TestSettings:
    def test_get_settings_precedence_and_fallback(self, db_writer):
        """Verifies that DB overrides take priority over env vars, falling back safely when missing."""
        # 1. Fallback case: DB is empty, should extract from process environment
        with patch.dict(
            os.environ,
            {"SELECTOR_MODEL": "env-fallback-model", "DIRECT_MODEL": "env-direct"},
        ):
            settings = db_writer.get_settings()
            assert settings["SELECTOR_MODEL"] == "env-fallback-model"
            assert settings["DIRECT_MODEL"] == "env-direct"

        # 2. Precedence case: DB has a record, should override environment entirely
        db_writer.apply_setting_update("SELECTOR_MODEL", "db-priority-model")
        with patch.dict(os.environ, {"SELECTOR_MODEL": "env-fallback-model"}):
            settings = db_writer.get_settings()
            assert settings["SELECTOR_MODEL"] == "db-priority-model"

    def test_encrypted_vs_plain_storage_logic(
        self, db_writer, db_session, valid_cipher
    ):
        """Verifies secret key categories get encrypted at rest, whereas typical config properties sit plain."""
        # Temporarily inject the valid cipher into the existing db_writer fixture
        db_writer._cipher = valid_cipher

        secret_raw = "sk-live-secret-payload-9988"
        plain_model = "claude-3-5-sonnet"

        db_writer.apply_setting_update("SELECTOR_API_KEY", secret_raw)
        db_writer.apply_setting_update("SELECTOR_MODEL", plain_model)

        secret_row = db_session.get(SettingOverride, "SELECTOR_API_KEY")
        model_row = db_session.get(SettingOverride, "SELECTOR_MODEL")

        # Verify secret key encryption metrics
        assert secret_row.is_encrypted is True
        assert secret_row.value != secret_raw
        assert valid_cipher.decrypt(secret_row.value) == secret_raw

        # Verify common configuration visibility metrics
        assert model_row.is_encrypted is False
        assert model_row.value == plain_model

    def test_clear_via_empty_string(self, db_writer):
        """Verifies that passing an empty string deletes the DB override row, triggering fallback."""
        db_writer.apply_setting_update("SELECTOR_MODEL", "temporary-override-value")
        assert db_writer.get_settings()["SELECTOR_MODEL"] == "temporary-override-value"

        # Wipe the database override row out
        with patch.dict(os.environ, {"SELECTOR_MODEL": "original-env-system"}):
            db_writer.apply_setting_update("SELECTOR_MODEL", "")

            # Subsequent requests must cascade to the native environment
            settings = db_writer.get_settings()
            assert settings["SELECTOR_MODEL"] == "original-env-system"

    def test_secret_persistence_without_cipher_raises_runtime_error(self, db_writer):
        """Verifies write actions reject updates to encrypted keys if the encryption key is missing."""
        # Ensure the cipher is None for this test
        db_writer._cipher = None

        with pytest.raises(
            RuntimeError, match="SETTINGS_ENCRYPTION_KEY isn't configured"
        ):
            db_writer.apply_setting_update("SELECTOR_API_KEY", "prohibited-write")
