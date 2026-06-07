import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from db.models import Base
from db.writer import DBWriter


load_dotenv()

# Adjust your database credentials if they are different!
DATABASE_URL = os.getenv("DATABASE_URL")

def run_test():
    print("🔌 Connecting to database...")
    # echo=False keeps the console clean. Change to True to see the raw SQL queries!
    engine = create_engine(DATABASE_URL, echo=False)

    print("🏗️ Creating tables...")
    # This will create all 5 tables if they don't exist yet
    Base.metadata.create_all(engine)

    print("📝 Initializing DBWriter...")
    writer = DBWriter(engine)

    # A tiny fake version of your books_config.json
    dummy_config = {
        "series": [{"name": "The Stormlight Archive"}],
        "books": [{
            "name": "The Way of Kings",
            "isbn": "9780765365279",
            "is_series_entry": True,
            "series_name": "The Stormlight Archive"
        }],
        "stores": [{
            "name": "Sarasavi",
            "base_url": "https://sarasavi.lk",
            "search_url_template": "https://sarasavi.lk/?s="
        }],
        "tracking": [{
            "isbn": "9780765365279",
            "store": "Sarasavi",
            "product_url": "https://sarasavi.lk/book/1",
            "skip": False
        }]
    }

    print("🔄 Testing sync_config()...")
    writer.sync_config(dummy_config)
    print("✅ Config synced successfully!")

    print("\n🔍 Testing get_active_pairs()...")
    pairs = writer.get_active_pairs()
    for pair in pairs:
        print(f"   -> Found pair: {pair['book_name']} at {pair['store_name']} (Status: {pair['status']})")
    
    if not pairs:
        print("❌ No pairs found! Something went wrong.")
        sys.exit(1)

    print("\n📸 Testing write_snapshot()...")
    # We create a dummy object to mimic the Crawler's AvailabilityResult
    class DummyResult:
        in_stock = True
        price = 2900.00
        status = 'SUCCESS'

    snapshot = writer.write_snapshot(
        pair_id=pairs[0]['id'], 
        result_obj=DummyResult(), 
        source="test_script"
    )
    print(f"✅ Snapshot written with ID {snapshot['id']}! Price: {snapshot['price']}, Stock: {snapshot['in_stock']}")

    print("\n📜 Testing get_history()...")
    history = writer.get_history(isbn="9780765365279")
    print(f"   -> History length: {len(history)} entries")
    print(f"   -> Latest entry price: {history[0]['price']}")

    print("\n🎉 All database tests passed!")

if __name__ == "__main__":
    run_test()