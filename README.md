# Vestige

A config-driven book availability tracker. Add books and stores through the desktop app, and Vestige scrapes price/stock on a schedule, notifying you the moment a tracked book comes into stock.

Vestige is a full-stack system: a Python scraping pipeline, a Java Spring Boot API, a PostgreSQL database, and a Tauri desktop UI — all orchestrated by Docker Compose and installable as a single native app on Windows or Linux.

---

## How It Works

Vestige runs a scraping pipeline on a schedule (or on demand via "Run Now"). For each book-store pair it tracks, it determines the fastest route to current availability data:

| Path | Condition | What happens |
|---|---|---|
| A | No product URL cached | Crawler searches the store and finds the product page |
| B | URL found, no selectors, `LLM_MODE=selector` | LLM discovers CSS selectors for price and stock fields |
| C | URL + selectors cached | Scraper reads directly — no discovery needed |
| D | URL found, `LLM_MODE=direct` | LLM reads the page HTML directly on every run |

Path C is the production fast path. Paths A and B are one-time setup paths that resolve to C. Path D trades selector maintenance for LLM cost on every run.

Every result is written to PostgreSQL as an immutable snapshot row. Status changes surface as OS desktop notifications via the Tauri app.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraper pipeline | Python, FastAPI, Playwright, SQLAlchemy |
| API | Java Spring Boot 4.1, Hibernate (validate-only), PostgreSQL 18 |
| Desktop UI | Tauri 2.x, React 19, TypeScript |
| Orchestration | Docker Compose |
| LLM | Any OpenAI-compatible endpoint (e.g. Groq, free tier) |
| Cloud deploy (optional) | Terraform — AWS, Azure, GCP |

---

## Install & Run (recommended — no dev tools required)

This is the normal way to run Vestige. It gets you a native desktop app backed by a local Docker stack.

### 1. Install Docker Desktop

Docker Engine must be installed and **running** before you launch Vestige.

- [Download Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows or Linux)
- Install it, then start it and make sure it's running (check for the whale icon in your system tray / taskbar)

### 2. Download the Vestige installer

Grab the latest installer from the project's [GitHub Releases](../../releases) page:

- **Windows** — `Vestige_x.y.z_x64-setup.exe` (NSIS) or the `.msi`
- **Linux** — the `.AppImage`

### 3. Run the installer

Standard install — accept the defaults unless you have a reason not to.

### 4. First launch — Docker auto-start prompt

On first launch (when pointed at a local backend), Vestige asks whether it should automatically start and stop the local Docker stack for you:

- **Enable auto-start** — Vestige runs `docker compose up -d` when it opens and `docker compose down` when you quit. Nothing further to do — skip to Step 6.
- **Not now** — Vestige will not manage Docker for you. Continue to Step 5.

You can change this choice later from **Settings → Local backend automation**.

### 5. (If you opted out) Start the stack manually

Open a terminal in Vestige's app-data folder — this is where the installer seeded `docker-compose.yml`, `.env`, and `books_config.json`:

- **Windows:** `%APPDATA%\vestige\`
- **Linux:** `~/.local/share/vestige/`

Then run:

```bash
docker compose up -d
```

(Drop the `-d` if you want to watch the container logs in that terminal instead of running detached.)

### 6. Get a free LLM API key (Groq)

Vestige uses an LLM only for one-time CSS selector discovery per book/store pair (Path B) or, optionally, for direct-extraction mode (Path D) — not for every scrape. Groq's free tier works well for this:

1. Go to the [Groq Console](https://console.groq.com) and create a free API key.
2. Check your org's **Organization Limits → Chat Completions** page to see which models are available on the free tier and their rate limits (requests/tokens per minute and per day).
3. Pick two models:
   - **Selector discovery (`SELECTOR_MODEL`)** — needs to read a full (if trimmed) HTML product page, so a large context/token budget matters most. `meta-llama/llama-4-scout-17b-16e-instruct` (30K tokens/minute on the free tier) is a solid choice for this.
   - **Direct extraction (`DIRECT_MODEL`)** — runs on every scrape for Path D pairs, so speed/cost matters more than raw context size. `llama-3.3-70b-versatile` (12K TPM) or `groq/compound` (70K TPM, no daily token cap, but newer — worth testing against your pages first) are good candidates.

   Both models above speak the standard OpenAI chat-completions format, so either works with Vestige's role-based LLM config without any code changes.

### 7. Add your API key and models to Vestige

Pick **one** of these — they have the same effect:

**Option A — Settings page (recommended, no restart needed):**
1. Open Vestige → **Settings**.
2. Under **Pipeline configuration**, set:
   - `Selector API Base` → `https://api.groq.com/openai/v1`
   - `Selector API Key` → your Groq key
   - `Selector Model` → `meta-llama/llama-4-scout-17b-16e-instruct`
   - `Direct API Base` → `https://api.groq.com/openai/v1`
   - `Direct API Key` → your Groq key
   - `Direct Model` → `llama-3.3-70b-versatile` (or whichever you settled on)
3. Save. Changes apply on the very next pipeline run — no restart required.

**Option B — Edit `.env` directly:**
1. Open the `.env` file in your app-data folder (same folder as Step 5).
2. Fill in:
   ```env
   SELECTOR_API_BASE=https://api.groq.com/openai/v1
   SELECTOR_API_KEY=your-groq-key-here
   SELECTOR_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
   DIRECT_API_BASE=https://api.groq.com/openai/v1
   DIRECT_API_KEY=your-groq-key-here
   DIRECT_MODEL=llama-3.3-70b-versatile
   LLM_DISCOVERY_ENABLED=true
   LLM_MODE=selector
   ```
3. Restart the app (or restart the Docker stack: `docker compose down && docker compose up -d`) for `.env` changes to take effect — unlike Settings-page changes, these are only read at container startup.

> API keys entered via the Settings page are encrypted at rest (AES-256-GCM) and never echoed back to the UI — only a "configured" indicator and a masked hint are shown.

### 8. Add your books, stores, and tracking pairs

In the Vestige UI:

1. **Stores** — add each bookstore you want to track (name + base URL).
2. **Books** — add the books you want to track (name + ISBN), optionally grouped into a series.
3. **Tracking** — pair each book with a store. Leave the product URL blank to let the Crawler find it automatically, or paste it directly if you already have it.
4. Click **Run Now** on the Dashboard.

On the pipeline's first pass, pairs without cached selectors go through one-time LLM-assisted discovery (Path B) using your `SELECTOR_MODEL`. After that, they run the fast selector-based path (Path C) on every subsequent scrape. You'll get an OS notification whenever a tracked book's stock status or price changes.

---

## Cloud Deployment (optional)

Vestige can also run on AWS, Azure, or GCP instead of a local Docker stack, provisioned via Terraform. This is a separate, more advanced path intended for continuous unattended scraping rather than everyday desktop use — see the project's cloud deployment blueprint for the full toolchain setup, credential hardening, and teardown steps for each provider.

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

## Development Setup

The instructions above are for running the packaged app. If you want to build Vestige from source, run its test suites, or contribute:

- `scraper/` — Python FastAPI service (Playwright, SQLAlchemy). See its own `requirements.txt`/`requirements-dev.txt`.
- `api/` — Java Spring Boot 4.1 service (JDK 25, Maven wrapper).
- `ui/` — Tauri 2.x + React 19 + TypeScript desktop app (npm, Vite).
- `infra/` — Terraform configs for AWS/Azure/GCP.
- `docker-compose.yml` at the repo root builds all services locally with `--build` instead of pulling published images.

Full architecture, module maps, and API contracts are documented in the project's blueprint files (`vestige_guide.md`, `vestige_api_implementation.md`, `vestige_ui_implementation.md`, `vestige_publishing_guide.md`, `vestige_cloud_deployment.md`). A CI pipeline (GitHub Actions) runs the Python and Java test suites on every push; a separate tag-triggered workflow builds and publishes the Docker images and desktop installers referenced in the Install & Run section above.

---

## Author

**Udan Fernando**
