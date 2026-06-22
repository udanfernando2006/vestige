import os
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy import desc
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from db.models import Series, Book, Store, TrackingPair, AvailabilitySnapshot, SettingOverride
from models.result import AvailabilityResult
from security.crypto import SettingsCipher

_SECRET_KEYS = {"SELECTOR_API_KEY", "DIRECT_API_KEY"}

SETTINGS_KEYS = [
    "LLM_DISCOVERY_ENABLED", "LLM_MODE",
    "SELECTOR_API_BASE", "SELECTOR_API_KEY", "SELECTOR_MODEL",
    "DIRECT_API_BASE", "DIRECT_API_KEY", "DIRECT_MODEL",
]

class DBWriter:
    """
    Handles all database reads and writes.
    All methods serialize ORM objects to dicts before returning to avoid detached session errors.
    """

    def __init__(self, engine, cipher: "SettingsCipher | None" = None):
        self.Session = sessionmaker(bind=engine)
        self.cipher = cipher

    # =========================================================================
    # SECURITY
    # =========================================================================

    def get_settings(self) -> dict[str, str]:
        """Effective config for every settings key: DB override if present
        (decrypted if needed), else the process's own env var, else "".
        One batched query, not one round trip per key."""
        with self.Session as session:
            rows = session.query(SettingOverride).filter(
                SettingOverride.key.in_(SETTINGS_KEYS)
            ).all()
            overrides = {r.key: (r.value, r.is_encrypted) for r in rows}

        result = {}
        for key in SETTINGS_KEYS:
            if key in overrides:
                value, is_encrypted = overrides[key]
                if is_encrypted:
                    if not self._cipher:
                        raise RuntimeError(
                            f"{key} is stored encrypted but SETTINGS_ENCRYPTION_KEY isn't configured"
                        )
                    value = self._cipher.decrypt(value)
                result[key] = value
            else:
                result[key] = os.environ.get(key, "")
        return result
    
    def get_settings_status(self) -> dict:
        """Same as get_settings(), except secret keys are never returned in
        the clear — only whether they're set, plus a masked hint. This is
        what the API layer's GET /config actually calls."""
        full = self.get_settings()
        status = {}
        for key in SETTINGS_KEYS:
            if key in _SECRET_KEYS:
                value = full[key]
                status[key] = {
                    "configured": bool(value),
                    "hint": f"••••{value[-4:]}" if len(value) >= 4 else (None if not value else "••••"),
                }
            else:
                status[key] = full[key]
        return status
    
    def apply_setting_update(self, key: str, value: "str | None") -> None:
        """value=None  -> no change.
        value=""      -> explicit clear (falls back to env on next read).
        value=<text>  -> set/overwrite, encrypting first if it's a secret key."""
        if value is None:
            return
        with self.Session as session:
            if value == "":
                existing = session.get(SettingOverride, key)
                if existing:
                    session.delete(existing)
                    session.commit()
                return

            is_encrypted = key in _SECRET_KEYS
            if is_encrypted and not self._cipher:
                raise RuntimeError("SETTINGS_ENCRYPTION_KEY isn't configured — can't store a secret setting")
            stored_value = self._cipher.encrypt(value) if is_encrypted else value

            existing = session.get(SettingOverride, key)
            if existing:
                existing.value, existing.is_encrypted = stored_value, is_encrypted
            else:
                session.add(SettingOverride(key=key, value=stored_value, is_encrypted=is_encrypted))
            session.commit()

    # =========================================================================
    # CONFIG SEEDING
    # =========================================================================

    def sync_config(self, config_data):
        """Idempotently seeds DB with contents from books_config.json."""
        with self.Session() as session:
            # Sync Series
            for series_data in config_data.get("series", []):
                series = (
                    session.query(Series).filter_by(name=series_data["name"]).first()
                )
                if not series:
                    session.add(Series(name=series_data["name"]))
            session.commit()

            # Sync Books
            for book_data in config_data.get("books", []):
                book = session.query(Book).filter_by(isbn=book_data["isbn"]).first()
                if not book:
                    series = None
                    if book_data.get("series_name"):
                        series = (
                            session.query(Series)
                            .filter_by(name=book_data["series_name"])
                            .first()
                        )

                    book = Book(
                        name=book_data["name"],
                        isbn=book_data["isbn"],
                        is_series_entry=book_data.get("is_series_entry", False),
                        series_id=series.id if series else None,
                    )
                    session.add(book)
            session.commit()

            # Sync Stores
            for store_data in config_data.get("stores", []):
                store = session.query(Store).filter_by(name=store_data["name"]).first()
                if not store:
                    store = Store(
                        name=store_data["name"],
                        base_url=store_data["base_url"],
                        search_url_template=store_data.get("search_url_template"),
                    )
                    session.add(store)
            session.commit()

            # Sync Tracking Pairs
            for tracking_data in config_data.get("tracking", []):
                book = session.query(Book).filter_by(isbn=tracking_data["isbn"]).first()
                store = (
                    session.query(Store).filter_by(name=tracking_data["store"]).first()
                )

                if book and store:
                    pair = (
                        session.query(TrackingPair)
                        .filter_by(book_id=book.id, store_id=store.id)
                        .first()
                    )
                    if not pair:
                        status = "SKIP" if tracking_data.get("skip") else "PENDING"
                        pair = TrackingPair(
                            book_id=book.id,
                            store_id=store.id,
                            product_url=tracking_data.get("product_url"),
                            status=status,
                        )
                        session.add(pair)
            session.commit()
            print("✓ Config synced to database")

    # =========================================================================
    # TRACKING PAIR QUERIES (WITH EAGER LOADING)
    # =========================================================================

    def get_active_pairs(self) -> List[Dict[str, Any]]:
        """
        Returns pairs that are not marked SKIP or NEEDS_SETUP.
        Returns dicts to avoid detached session issues.
        """
        with self.Session() as session:
            pairs = (
                session.query(TrackingPair)
                .filter(TrackingPair.status.notin_(["SKIP", "NEEDS_SETUP"]))
                .options(joinedload(TrackingPair.book), joinedload(TrackingPair.store))
                .all()
            )

            return [
                {
                    "id": p.id,
                    "book_id": p.book_id,
                    "store_id": p.store_id,
                    "product_url": p.product_url,
                    "price_selector": p.price_selector,
                    "stock_selector": p.stock_selector,
                    "status": p.status,
                    "selector_found_at": (
                        p.selector_found_at.isoformat() if p.selector_found_at else None
                    ),
                    "book_name": p.book.name,
                    "book_isbn": p.book.isbn,
                    "store_name": p.store.name,
                }
                for p in pairs
            ]

    def get_all_pairs(self) -> List[Dict[str, Any]]:
        """Get all tracking pairs (including SKIP and NEEDS_SETUP)."""
        with self.Session() as session:
            pairs = (
                session.query(TrackingPair)
                .options(joinedload(TrackingPair.book), joinedload(TrackingPair.store))
                .all()
            )

            return [
                {
                    "id": p.id,
                    "book_id": p.book_id,
                    "store_id": p.store_id,
                    "product_url": p.product_url,
                    "price_selector": p.price_selector,
                    "stock_selector": p.stock_selector,
                    "status": p.status,
                    "selector_found_at": (
                        p.selector_found_at.isoformat() if p.selector_found_at else None
                    ),
                    "book_name": p.book.name,
                    "book_isbn": p.book.isbn,
                    "store_name": p.store.name,
                }
                for p in pairs
            ]

    def get_pair(self, pair_id: int) -> Optional[Dict[str, Any]]:
        """Get a single tracking pair by ID."""
        with self.Session() as session:
            pair = (
                session.query(TrackingPair)
                .filter_by(id=pair_id)
                .options(joinedload(TrackingPair.book), joinedload(TrackingPair.store))
                .first()
            )

            if not pair:
                return None

            return {
                "id": pair.id,
                "book_id": pair.book_id,
                "store_id": pair.store_id,
                "product_url": pair.product_url,
                "price_selector": pair.price_selector,
                "stock_selector": pair.stock_selector,
                "status": pair.status,
                "selector_found_at": (
                    pair.selector_found_at.isoformat()
                    if pair.selector_found_at
                    else None
                ),
                "book_name": pair.book.name,
                "book_isbn": pair.book.isbn,
                "store_name": pair.store.name,
            }

    def get_pairs_needing_setup(self) -> List[Dict[str, Any]]:
        """Get all pairs with status NEEDS_SETUP."""
        with self.Session() as session:
            pairs = (
                session.query(TrackingPair)
                .filter_by(status="NEEDS_SETUP")
                .options(joinedload(TrackingPair.book), joinedload(TrackingPair.store))
                .all()
            )

            return [
                {
                    "id": p.id,
                    "book_id": p.book_id,
                    "store_id": p.store_id,
                    "product_url": p.product_url,
                    "price_selector": p.price_selector,
                    "stock_selector": p.stock_selector,
                    "status": p.status,
                    "book_name": p.book.name,
                    "book_isbn": p.book.isbn,
                    "store_name": p.store.name,
                }
                for p in pairs
            ]

    # =========================================================================
    # STORE QUERIES
    # =========================================================================

    def get_store(self, store_id: int) -> Optional[Dict[str, Any]]:
        """Get a store by ID."""
        with self.Session() as session:
            store = session.query(Store).filter_by(id=store_id).first()

            if not store:
                return None

            return {
                "id": store.id,
                "name": store.name,
                "base_url": store.base_url,
                "search_url_template": store.search_url_template,
            }

    def get_all_stores(self) -> List[Dict[str, Any]]:
        """Get all stores."""
        with self.Session() as session:
            stores = session.query(Store).all()

            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "base_url": s.base_url,
                    "search_url_template": s.search_url_template,
                }
                for s in stores
            ]

    # =========================================================================
    # BOOK QUERIES
    # =========================================================================

    def get_all_books(self) -> List[Dict[str, Any]]:
        """Get all books grouped by series."""
        with self.Session() as session:
            books = session.query(Book).all()

            return [
                {
                    "id": b.id,
                    "name": b.name,
                    "isbn": b.isbn,
                    "is_series_entry": b.is_series_entry,
                    "series_id": b.series_id,
                    "series_name": b.series.name if b.series else None,
                }
                for b in books
            ]

    def get_all_series(self) -> List[Dict[str, Any]]:
        """Get all series."""
        with self.Session() as session:
            series_list = session.query(Series).all()

            return [
                {
                    "id": s.id,
                    "name": s.name,
                }
                for s in series_list
            ]

    # =========================================================================
    # AVAILABILITY SNAPSHOT QUERIES
    # =========================================================================

    def get_last_snapshot(self, pair_id: int) -> Optional[Dict[str, Any]]:
        """Gets the most recent scrape state for a pair, if any."""
        with self.Session() as session:
            snapshot = (
                session.query(AvailabilitySnapshot)
                .filter_by(pair_id=pair_id)
                .order_by(desc(AvailabilitySnapshot.scraped_at))
                .first()
            )

            if not snapshot:
                return None

            return {
                "id": snapshot.id,
                "pair_id": snapshot.pair_id,
                "in_stock": snapshot.in_stock,
                "price": float(snapshot.price) if snapshot.price else None,
                "status": snapshot.status,
                "source": snapshot.source,
                "scraped_at": snapshot.scraped_at.isoformat(),
            }

    def get_history(self, isbn: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get full snapshot history for a book across all stores.
        Used by the UI's History page.
        """
        with self.Session() as session:
            snapshots = (
                session.query(AvailabilitySnapshot)
                .join(TrackingPair)
                .join(Book)
                .filter(Book.isbn == isbn)
                .order_by(desc(AvailabilitySnapshot.scraped_at))
                .limit(limit)
                .options(
                    joinedload(AvailabilitySnapshot.tracking_pair).joinedload(
                        TrackingPair.store
                    )
                )
                .all()
            )

            return [
                {
                    "store_name": s.tracking_pair.store.name,
                    "status": s.status,
                    "price": float(s.price) if s.price else None,
                    "in_stock": s.in_stock,
                    "scraped_at": s.scraped_at.isoformat(),
                    "source": s.source,
                }
                for s in snapshots
            ]

    # =========================================================================
    # SNAPSHOT WRITES
    # =========================================================================

    def write_snapshot(
        self, pair_id: int, result_obj: AvailabilityResult
    ) -> Dict[str, Any]:
        """
        Writes an immutable snapshot and updates the tracking pair's current status.

        Args:
            pair_id: ID of the tracking pair
            result_obj: AvailabilityResult with in_stock, price, status fields
        """
        with self.Session() as session:
            # 1. Append to history
            snapshot = AvailabilitySnapshot(
                pair_id=pair_id,
                in_stock=result_obj.in_stock,
                price=result_obj.price,
                status=result_obj.status,
                source=result_obj.source,
                scraped_at=datetime.now(timezone.utc),
            )
            session.add(snapshot)

            # 2. Update current state pointer on tracking pair
            pair = session.query(TrackingPair).filter_by(id=pair_id).first()
            if pair:
                pair.status = result_obj.status

            session.commit()

            return {
                "id": snapshot.id,
                "pair_id": snapshot.pair_id,
                "status": snapshot.status,
                "price": float(snapshot.price) if snapshot.price else None,
                "in_stock": snapshot.in_stock,
                "source": snapshot.source,
                "scraped_at": snapshot.scraped_at.isoformat(),
            }

    # =========================================================================
    # TRACKING PAIR UPDATES
    # =========================================================================

    def update_pair_status(self, pair_id: int, status: str) -> None:
        """Update the status of a tracking pair."""
        with self.Session() as session:
            pair = session.query(TrackingPair).filter_by(id=pair_id).first()
            if pair:
                pair.status = status
                session.commit()

    def update_pair_url(self, pair_id: int, product_url: str) -> None:
        """Save the product URL discovered by the Crawler."""
        with self.Session() as session:
            pair = session.query(TrackingPair).filter_by(id=pair_id).first()
            if pair:
                pair.product_url = product_url
                session.commit()

    def update_pair_selectors(
        self, pair_id: int, price_sel: str, stock_sel: str
    ) -> None:
        """
        Save validated selectors and transition pair from NEEDS_SETUP to PENDING.
        Called by discover_selectors.py after validation passes.
        Also called by API PATCH endpoint when user manually enters selectors.
        """
        with self.Session() as session:
            pair = session.query(TrackingPair).filter_by(id=pair_id).first()
            if pair:
                pair.price_selector = price_sel
                pair.stock_selector = stock_sel
                pair.selector_found_at = datetime.now(timezone.utc)

                # Auto-transition from NEEDS_SETUP to PENDING when selectors provided
                if pair.status == "NEEDS_SETUP":
                    pair.status = "PENDING"

                session.commit()

    def clear_pair_selectors(self, pair_id: int) -> None:
        """
        Clear cached selectors and transition to NEEDS_SETUP.
        Called by Orchestrator when Scraper reports selector_not_found.
        """
        with self.Session() as session:
            pair = session.query(TrackingPair).filter_by(id=pair_id).first()
            if pair:
                pair.price_selector = None
                pair.stock_selector = None
                pair.selector_found_at = None
                pair.status = "NEEDS_SETUP"
                session.commit()

    # =========================================================================
    # STORE UPDATES
    # =========================================================================

    def update_store_search_template(self, store_id: int, template_url: str) -> None:
        """
        Cache the discovered search URL template on a store.
        Called by Orchestrator after Crawler's discovery phase completes.

        Example: "https://sarasavi.lk/?s=test"
        Crawler replaces '=test' with '={encoded_query}'
        """
        with self.Session() as session:
            store = session.query(Store).filter_by(id=store_id).first()
            if store:
                store.search_url_template = template_url
                session.commit()
