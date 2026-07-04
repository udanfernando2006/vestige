SAMPLE_CONFIG = {
    "series": [{"name": "The Witcher"}],
    "books": [
        {
            "name": "The Last Wish",
            "isbn": "9780316452465",
            "is_series_entry": True,
            "series_name": "The Witcher",
        },
        {
            "name": "Dune",
            "isbn": "9780441013593",
            "is_series_entry": False,
            "series_name": None,
        },
    ],
    "stores": [
        {
            "name": "sarasavi",
            "base_url": "https://sarasavi.lk",
            "search_url_template": None,
        },
        {
            "name": "vijitha_yapa",
            "base_url": "https://vijithayapa.com",
            "search_url_template": None,
        },
    ],
    "tracking": [
        {"isbn": "9780316452465", "store": "sarasavi", "product_url": None},
        {"isbn": "9780316452465", "store": "vijitha_yapa", "product_url": None},
    ],
}


class TestSyncConfig:
    def test_seeds_books(self, db_writer, db_session):
        from db.models import Book

        db_writer.sync_config(SAMPLE_CONFIG)
        count = db_session.query(Book).count()
        assert count >= 2

    def test_seeds_stores(self, db_writer, db_session):
        from db.models import Store

        db_writer.sync_config(SAMPLE_CONFIG)
        count = db_session.query(Store).count()
        assert count >= 2

    def test_seeds_tracking_pairs(self, db_writer, db_session):
        from db.models import TrackingPair

        db_writer.sync_config(SAMPLE_CONFIG)
        count = db_session.query(TrackingPair).count()
        assert count >= 2

    def test_seeds_series(self, db_writer, db_session):
        from db.models import Series

        db_writer.sync_config(SAMPLE_CONFIG)
        series = db_session.query(Series).filter_by(name="The Witcher").first()
        assert series is not None

    def test_idempotent_on_repeat_call(self, db_writer, db_session):
        from db.models import Book

        db_writer.sync_config(SAMPLE_CONFIG)
        count_before = db_session.query(Book).count()
        db_writer.sync_config(SAMPLE_CONFIG)
        count_after = db_session.query(Book).count()
        assert count_before == count_after

    def test_does_not_reset_status_of_existing_pairs(self, db_writer, db_session):
        from db.models import TrackingPair

        db_writer.sync_config(SAMPLE_CONFIG)

        # Simulate pipeline having run and changed the status
        pair = (
            db_session.query(TrackingPair)
            .join(TrackingPair.book)
            .filter_by(isbn="9780316452465")
            .first()
        )
        pair.status = "IN_STOCK"
        db_session.flush()

        # Re-running sync_config must not overwrite runtime status
        db_writer.sync_config(SAMPLE_CONFIG)
        db_session.refresh(pair)
        assert pair.status == "IN_STOCK"

    def test_skip_flag_sets_status_on_new_pair(self, db_writer, db_session):
        from db.models import TrackingPair

        config_with_skip = {
            **SAMPLE_CONFIG,
            "tracking": [
                {
                    "isbn": "9780316452465",
                    "store": "sarasavi",
                    "product_url": None,
                    "skip": True,
                },
            ],
        }
        db_writer.sync_config(config_with_skip)
        pair = (
            db_session.query(TrackingPair)
            .join(TrackingPair.book)
            .filter_by(isbn="9780316452465")
            .first()
        )
        assert pair.status == "SKIP"

    def test_new_book_added_on_incremental_run(self, db_writer, db_session):
        from db.models import Book

        db_writer.sync_config(SAMPLE_CONFIG)

        extended_config = {
            **SAMPLE_CONFIG,
            "books": SAMPLE_CONFIG["books"]
            + [
                {
                    "name": "Blood of Elves",
                    "isbn": "9780316029193",
                    "is_series_entry": True,
                    "series_name": "The Witcher",
                }
            ],
        }
        db_writer.sync_config(extended_config)
        new_book = db_session.query(Book).filter_by(isbn="9780316029193").first()
        assert new_book is not None
