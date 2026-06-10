# Vestige

A config-driven book availability tracker for Sri Lankan online bookstores. Define books and stores in a JSON file, run the pipeline, and get notified the moment a tracked book comes into stock.

---

## How It Works

Vestige runs a scraping pipeline on a schedule. For each book-store pair it tracks, it determines the fastest route to current availability data:

| Path | Condition | What happens |
|---|---|---|
| A | No product URL cached | Crawler searches the store and finds the product page |
| B | URL found, no selectors, `LLM_MODE=selector` | LLM discovers CSS selectors for price and stock fields |
| C | URL + selectors cached | Scraper reads directly — no discovery needed |
| D | URL found, `LLM_MODE=direct` | LLM reads the page HTML directly on every run |

Path C is the production fast path. Paths A and B are one-time setup paths that resolve to C. Path D trades selector maintenance for LLM cost on every run.

Every result is written to PostgreSQL as an immutable snapshot row. A local JSON log is written per run under `logs/`. Email and desktop notifications fire when availability status changes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | Python, Playwright, BeautifulSoup |
| Database | PostgreSQL 16, SQLAlchemy 2, psycopg3 |
| LLM | OpenRouter or Anthropic API (via OpenAI-compatible client) |
| Config | `books_config.json`, `python-dotenv` |
| CI | GitHub Actions |

---

## Project Structure

```
vestige/
├── scraper/
│   ├── main.py                     # Entry point — run this to start a pipeline run
│   ├── browser/
│   │   └── session.py              # BrowserSession — shared Playwright abstraction
│   ├── pipeline/
│   │   ├── orchestrator.py         # Routes each pair through the correct path
│   │   ├── crawler.py              # Finds product URLs via store search
│   │   ├── scraper.py              # Extracts price and stock via CSS selectors
│   │   └── llm_extractor.py        # LLM-based selector discovery and direct extraction
│   ├── tools/
│   │   └── discover_selectors.py   # Offline CLI tool for selector discovery
│   ├── db/
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   └── writer.py               # All database reads and writes
│   ├── storage/
│   │   └── local_logger.py         # Writes run summaries to logs/
│   ├── notifications/
│   │   ├── email_notifier.py       # Email via Gmail SMTP
│   │   └── desktop_notifier.py     # Windows toast via plyer
│   ├── models/
│   │   └── result.py               # AvailabilityResult dataclass
│   ├── tests/                      # pytest test suite
│   ├── requirements.txt            # Runtime dependencies
│   ├── requirements-dev.txt        # Testing, linting, and security tooling
│   └── pyproject.toml              # pytest configuration
├── logs/                           # Run logs written here (gitignored)
├── books_config.json               # Your books, stores, and tracking pairs
├── .env.example                    # Template — copy to .env and fill in
└── docker-compose.yml              # PostgreSQL for local development
```

---

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 16 (or Docker for the compose approach below)
- An OpenRouter or Anthropic API key (only required if using LLM features)

### 1. Clone the repository

```bash
git clone https://github.com/udanfernando2006/vestige.git
cd vestige
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r scraper/requirements.txt
playwright install chromium
```

### 3. Start PostgreSQL

If you have Docker, the compose file handles it:

```bash
docker-compose up -d postgres
```

Or point at an existing PostgreSQL instance by setting `DATABASE_URL` in your `.env`.

### 4. Create the database and user

```sql
CREATE DATABASE vestige;
CREATE USER booktracker WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE vestige TO booktracker;

\c vestige
GRANT ALL ON SCHEMA public TO booktracker;
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` — the required fields are:

```env
DATABASE_URL=postgresql+psycopg://booktracker:yourpassword@localhost:5432/vestige
POSTGRES_USER=booktracker
POSTGRES_PASSWORD=yourpassword

# LLM — set LLM_DISCOVERY_ENABLED=false to skip LLM entirely on first run
LLM_DISCOVERY_ENABLED=false
LLM_MODE=direct
LLM_ENGINE=cloud
LLM_PROVIDER=openrouter
LLM_MODEL=anthropic/claude-haiku-4-5
OPENROUTER_API_KEY=

# Notifications
SMTP_HOST=smtp.gmail.com
SMTP_USER=
SMTP_PASSWORD=
NOTIFY_EMAIL=
```

### 6. Configure books and stores

Edit `books_config.json`:

```json
{
  "series": [
    { "name": "The Witcher" }
  ],
  "books": [
    {
      "name": "The Last Wish",
      "isbn": "9780316452465",
      "is_series_entry": true,
      "series_name": "The Witcher"
    }
  ],
  "stores": [
    { "name": "sarasavi", "base_url": "https://sarasavi.lk", "search_url_template": null },
    { "name": "vijitha_yapa", "base_url": "https://vijithayapa.com", "search_url_template": null }
  ],
  "tracking": [
    { "isbn": "9780316452465", "store": "sarasavi", "product_url": null },
    { "isbn": "9780316452465", "store": "vijitha_yapa", "product_url": null }
  ],
  "notifications": {
    "email": "you@example.com",
    "desktop": true
  }
}
```

Set `product_url` to `null` to have the Crawler find it automatically, or supply it directly to skip crawling.

### 7. Run the pipeline

```bash
cd scraper
python main.py
```

On first run, `sync_config` seeds the database from `books_config.json`. The Orchestrator then routes each tracking pair through the appropriate path. Results are written to PostgreSQL and a log file is created under `logs/`.

---

## LLM Selector Discovery

If a product URL is known but CSS selectors are not yet cached, you can run discovery manually without triggering a full pipeline run:

```bash
# Preview suggested selectors (no database changes)
python scraper/tools/discover_selectors.py --pair-id 1

# Validate and commit selectors to the database
python scraper/tools/discover_selectors.py --pair-id 1 --commit

# Run against a URL directly
python scraper/tools/discover_selectors.py --url "https://sarasavi.lk/books/..." --store sarasavi
```

Requires `LLM_PROVIDER` and the corresponding API key to be set in `.env`. Ollama is not supported for selector discovery — use `openrouter` or `anthropic`.

---

## Availability States

| Status | Meaning |
|---|---|
| `PENDING` | Ready to scrape on the next run |
| `NEEDS_SETUP` | Product URL found but selectors missing; pipeline paused until selectors are provided |
| `IN_STOCK` | Currently available |
| `OUT_OF_STOCK` | Found on the store but currently unavailable |
| `NOT_LISTED` | Store confirmed not to carry this book |
| `SKIP` | Manually excluded — never scraped |
| `ERROR` | Scrape failed (network error, broken selector, etc.) |

---

## Running Tests

```bash
cd scraper

# Unit tests only (no database required)
pytest tests/unit -v

# Integration tests (requires PostgreSQL)
pytest tests/integration -v

# E2E tests (requires PostgreSQL; browser and LLM are mocked)
pytest tests/e2e -v

# Full suite
pytest
```

Integration and E2E tests require a `vestige_test` database. Follow the same steps as the main database setup, substituting `vestige_test` for `vestige`, then create `scraper/.env.test` with the test `DATABASE_URL`.

---

## Environment Variable Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | psycopg3 connection string |
| `LLM_DISCOVERY_ENABLED` | No | `true` to auto-run selector discovery in the pipeline; default `false` |
| `LLM_MODE` | No | `direct` (LLM reads HTML each run) or `selector` (CSS selectors cached); default `selector` |
| `LLM_ENGINE` | No | `cloud` or `local`; controls HTML attribute stripping before LLM call |
| `LLM_PROVIDER` | No | `openrouter` or `anthropic` |
| `LLM_MODEL` | No | Model string, e.g. `anthropic/claude-haiku-4-5` |
| `OPENROUTER_API_KEY` | If using OpenRouter | |
| `ANTHROPIC_API_KEY` | If using Anthropic | |
| `SMTP_HOST` | No | Required for email notifications |
| `SMTP_USER` | No | Gmail address |
| `SMTP_PASSWORD` | No | Gmail App Password |
| `NOTIFY_EMAIL` | No | Recipient address for notifications |
| `LOG_DIR` | No | Directory for run log files; default `logs` |

---

## Author

**Udan Fernando**
