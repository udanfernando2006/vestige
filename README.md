# <img src="ui/src-tauri/icons/Square310x310Logo.png" alt="Vestige logo" width="40" height="40" valign="middle"> Vestige

A config-driven book availability tracker. Add books and stores through the desktop app, and Vestige scrapes price/stock on a schedule, notifying you the moment a tracked book comes into stock.

Vestige is a full-stack system: a Python scraping pipeline, a Java Spring Boot API, a PostgreSQL database, and a Tauri desktop UI — all orchestrated by Docker Compose and installable as a single native app on Windows or Linux.

---

## How It Works

Vestige runs a scraping pipeline on a schedule (or on demand via "Run Now"). For each book-store pair it tracks, it determines the fastest route to current availability data:

| Path | Condition                                    | What happens                                           |
| ---- | -------------------------------------------- | ------------------------------------------------------ |
| A    | No product URL cached                        | Crawler searches the store and finds the product page  |
| B    | URL found, no selectors, `LLM_MODE=selector` | LLM discovers CSS selectors for price and stock fields |
| C    | URL + selectors cached                       | Scraper reads directly — no discovery needed           |
| D    | URL found, `LLM_MODE=direct`                 | LLM reads the page HTML directly on every run          |

Path C is the production fast path. Paths A and B are one-time setup paths that resolve to C. Path D trades selector maintenance for LLM cost on every run.

> **Crawler scoring is heuristic, not exhaustive.** Path A ranks candidate product-page links using common URL conventions (e.g. `/products/`, `/product/`, `/item/`) seen across the stores Vestige has been tested against. A store with an unusual URL convention can occasionally cause the Crawler to pick the wrong page, or none at all. If a tracked pair's resolved URL doesn't look right (check it on the **Tracking** page), the fix is simple: paste the correct product URL directly into that pair's product URL field — this bypasses the Crawler entirely for that pair going forward.

Every result is written to PostgreSQL as an immutable snapshot row. Status changes surface as OS desktop notifications via the Tauri app.

---

## Tech Stack

| Layer                   | Technology                                                     |
| ----------------------- | -------------------------------------------------------------- |
| Scraper pipeline        | Python, FastAPI, Playwright, SQLAlchemy                        |
| API                     | Java Spring Boot 4.1, Hibernate (validate-only), PostgreSQL 18 |
| Desktop UI              | Tauri 2.x, React 19, TypeScript                                |
| Orchestration           | Docker Compose                                                 |
| LLM                     | Any OpenAI-compatible endpoint (e.g. Groq, free tier)          |
| Cloud deploy (optional) | Terraform — AWS, Azure, GCP                                    |

---

## Install & Run (recommended — no dev tools required)

This is the normal way to run Vestige. It gets you a native desktop app backed by a local Docker stack.

### 1. Install Docker Desktop

Docker Engine must be installed and **running** before you launch Vestige.

- [Download Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows or Linux)
- Install it, then start it and make sure it's running (check for the whale icon in your system tray / taskbar)

> **System requirements (observed, not a hard spec):** budget a few GB of free disk space just for the Docker images (Postgres, the API, and the Python scraper/Playwright image).
>
> **On Windows, most of the memory footprint you'll see in Task Manager is Docker Desktop's WSL2 virtual machine (`VmmemWSL`), not Vestige itself.** That process hosts every container Docker Desktop is running on your machine, plus WSL2's own kernel and filesystem cache — so its size reflects your whole Docker/WSL2 setup, not just Vestige. In testing on Windows 11 with 16GB of RAM, `VmmemWSL` idled around ~3.2GB right after a fresh Docker Desktop start (before Vestige's containers had done anything), and rose to ~4GB at peak during an active scrape — so Vestige's own incremental cost was roughly **800MB–1GB on top of whatever your machine's WSL2/Docker Desktop baseline already is**. That idle baseline will vary by machine and by whatever else you're running under WSL2 — it isn't a Vestige-specific cost, and there's no way to give one number that's accurate for every setup.
>
> Per-container view (via `docker stats`) during an active scrape: `scraper-server` ~800–830MB (the Playwright/Chromium instance doing the actual crawling — this is the one that moves with scraping activity), `api` ~500MB (flat, regardless of scrape activity), `postgres` ~80MB (flat). Note `docker stats` numbers don't include WSL2's own VM overhead, so they'll always read lower than what Task Manager shows for `VmmemWSL`.
>
> On a machine with 8GB of RAM or less, keep an eye on Task Manager during your first run — if your baseline WSL2 footprint is already high before Vestige even starts, that's worth knowing regardless of anything this project does.

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

> **Closing the window does not quit Vestige.** Clicking the window's close (X) button just hides it to the system tray — the app keeps running in the background so notification polling keeps working. To actually quit, **right-click the Vestige icon in the system tray and choose Quit.** If auto-start is enabled, quitting this way is also what triggers `docker compose down` — the whole stack shuts down together. If auto-start is off, quitting the app does **not** stop Docker (see Step 5's warning below) — the containers keep running until you stop them yourself.

### 5. (If you opted out) Start and stop the stack manually

> **If you turned auto-start off — in the first-run prompt or later in Settings — Docker is entirely your responsibility.** Vestige will not stop the containers for you when you quit. Get comfortable with the "stop" command below before you forget the stack is running in the background.

Open a terminal in Vestige's app-data folder — this is where the installer seeded `docker-compose.yml`, `.env`, and `books_config.json`:

- **Windows:** `%APPDATA%\vestige\`
- **Linux:** `~/.local/share/vestige/`

**Windows — quickest way to open a terminal there:**

1. Press **Win + R**, type `%APPDATA%\vestige`, and hit Enter — this opens the folder in File Explorer.
2. Click into the address bar at the top of the Explorer window, type `cmd` (or `pwsh` for PowerShell), and hit Enter. A terminal opens already `cd`'d into that folder.

**Linux:** open a terminal and `cd ~/.local/share/vestige/`.

**Start the stack:**

```bash
docker compose up -d
```

(Drop the `-d` if you want to watch the container logs live in that same terminal instead of running detached.)

**Stop the stack** (do this whenever you're done using Vestige, since nothing does it automatically if auto-start is off):

```bash
docker compose down
```

This stops and removes the containers but leaves your database volume intact — your tracked books/history are safe.

> `docker compose down -v` additionally deletes the named volumes tied to _this specific_ `docker-compose.yml` — for Vestige, that means wiping the Postgres volume (`postgres_data`), i.e. every book, store, tracking pair, and snapshot you've recorded. It does **not** touch volumes belonging to other Docker Compose projects or containers elsewhere on your machine — the `-v` flag is scoped to the current project, not global — but within that scope it is a full reset of Vestige's own data. Only run it if you actually want to start over from empty.

**Check the logs** (useful for diagnosing an `ERROR` status or a scrape that isn't behaving):

```bash
# All containers, live-following
docker compose logs -f

# Just one container (api, scraper-server, postgres)
docker compose logs -f api
docker compose logs -f scraper-server
```

Press **Ctrl+C** to stop following without stopping the containers themselves.

### 6. Get a free LLM API key (Groq)

Vestige uses an LLM only for one-time CSS selector discovery per book/store pair (Path B) or, optionally, for direct-extraction mode (Path D) — not for every scrape. Groq's free tier works well for this:

1. Go to the [Groq Console](https://console.groq.com) and create a free API key.
2. Check your org's **Organization Limits → Chat Completions** page to see which models are available on the free tier and their rate limits (requests/tokens per minute and per day).
3. Pick two models:
    - **Selector discovery (`SELECTOR_MODEL`)** — needs to read a full (if trimmed) HTML product page, so a large context/token budget matters most. `meta-llama/llama-4-scout-17b-16e-instruct` (30K tokens/minute on the free tier) worked reliably in testing.
    - **Direct extraction (`DIRECT_MODEL`)** — runs on every scrape for Path D pairs, so speed/cost matters more than raw context size. `llama-3.3-70b-versatile` (12K TPM) worked reliably in testing. `groq/compound` looked appealing on paper (70K TPM, no daily token cap) but **did not work** for this role in practice — stick with `llama-3.3-70b-versatile` unless you've specifically re-tested `groq/compound` against your own pages.

    Both models speak the standard OpenAI chat-completions format, so either works with Vestige's role-based LLM config without any code changes.

    > **Rate limits can surface as pair status, not just an error message.** If you hit a model's requests-per-minute/day or tokens-per-minute/day cap mid-run, a pair can land in `NEEDS_SETUP` (discovery couldn't complete) or stay in `PENDING` (waiting on a run that didn't get to it) instead of the status you expected. If pairs seem stuck, check whether you're bumping into the free-tier limits shown on the Groq Organization Limits page before assuming something's broken.

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

On the pipeline's first pass, pairs without cached selectors go through one-time LLM-assisted discovery (Path B) using your `SELECTOR_MODEL`. After that, they run the fast selector-based path (Path C) on every subsequent scrape.

### Verifying LLM-discovered selectors (recommended)

LLMs don't guarantee correct output, and a wrong selector can silently return stale or empty data instead of failing loudly. **Before trusting a newly-discovered selector, it's worth manually confirming it against the live page** — this is admittedly a bit of an anti-pattern for a tool meant to run unattended, but it's the honest tradeoff of using an LLM for this step rather than hand-written selectors.

For any pair sitting in `NEEDS_SETUP` (or after running the on-demand **Discover** button from the Tracking page), check the suggested selector using your browser's DevTools:

1. Open the product page in your regular browser.
2. Right-click the **price** on the page → **Inspect** (Chrome/Edge) or **Inspect Element** (Firefox). This opens DevTools with that exact HTML element highlighted.
3. In DevTools, right-click the highlighted element → **Copy → Copy selector**, or just read off its `class`/`id` attributes directly from the highlighted line.
4. Compare that against the selector Vestige suggested. They don't need to be identical strings — Vestige's are often written as wildcard attribute selectors (e.g. `div[class*='price']`) to survive framework-hashed class names — but they should be pointing at the same element.
5. Still in DevTools, use **Ctrl+F** inside the **Elements** panel (or the DevTools-wide search) to search for the suggested selector directly and confirm it matches exactly one element, not zero or several.
6. Repeat for the stock/availability selector.
7. Only then save the selector (or accept the pipeline's own `--commit`ed one) — if something looks off, edit it manually in the Tracking page before saving.

### Notifications only cover availability/price changes

Desktop notifications fire **only when a tracked pair's stock status or price actually changes** between runs — not on every run, and not on errors. A `0 changes` run is often completely normal (nothing changed, or the database has nothing yet to diff against) and produces no notification, which is expected behavior, not a sign anything's broken.

This also means **errors and stuck pairs won't notify you** — a pair sitting in `ERROR` or `NEEDS_SETUP` produces no popup. Check the **Dashboard** or **Tracking** page in the UI periodically to catch these rather than relying on notifications alone.

---

## Cloud Deployment (optional)

Vestige can also run on AWS, Azure, or GCP instead of a local Docker stack, provisioned via Terraform. This is a separate, more advanced path intended for continuous unattended scraping rather than everyday desktop use.

Full step-by-step guides for each provider (toolchain setup, credential hardening, provisioning, deployment, and teardown) are in [`/guides`](guides/):

- [Deploying to AWS](guides/vestige_deploy_aws.md)
- [Deploying to Azure](guides/vestige_deploy_azure.md)
- [Deploying to GCP](guides/vestige_deploy_gcp.md)

---

## Availability States

| Status         | Meaning                                                                               |
| -------------- | ------------------------------------------------------------------------------------- |
| `PENDING`      | Ready to scrape on the next run                                                       |
| `NEEDS_SETUP`  | Product URL found but selectors missing; pipeline paused until selectors are provided |
| `IN_STOCK`     | Currently available                                                                   |
| `OUT_OF_STOCK` | Found on the store but currently unavailable                                          |
| `NOT_LISTED`   | Store confirmed not to carry this book                                                |
| `SKIP`         | Manually excluded — never scraped                                                     |
| `ERROR`        | Scrape failed (network error, broken selector, etc.)                                  |

> **Stock-status text that doesn't match a known pattern isn't necessarily an `ERROR`.** Vestige first checks a store's raw availability text (e.g. "In Stock", "Sold Out", "Low stock: 4 left") against a built-in pattern list. If your `SELECTOR_*`/`DIRECT_*` LLM credentials are configured, an unrecognized string is automatically classified by the LLM as a fallback before giving up — a pair only lands in `ERROR` with reason `unparseable_stock_status` if that fallback also can't tell, or no LLM credentials are set at all.
>
> If a particular store's phrasing keeps needing the LLM fallback (which costs a request per occurrence), you can teach Vestige the pattern directly instead: add an `"availability-regex"` block to `books_config.json`:
>
> ```json
> {
>     "availability-regex": {
>         "in_stock": ["ships in \\d+-\\d+ days"],
>         "out_of_stock": ["backordered", "discontinued"]
>     }
> }
> ```
>
> These are plain regex strings, checked before the LLM fallback is ever tried. They're re-read from the file on every run — no restart or DB wipe needed to pick up an edit.

---

## Development Setup

The instructions above are for running the packaged app. If you want to build Vestige from source, run its test suites, or contribute:

- `scraper/` — Python FastAPI service (Playwright, SQLAlchemy). See its own `requirements.txt`/`requirements-dev.txt`.
- `api/` — Java Spring Boot 4.1 service (JDK 25, Maven wrapper).
- `ui/` — Tauri 2.x + React 19 + TypeScript desktop app (npm, Vite).
- `infra/` — Terraform configs for AWS/Azure/GCP.
- `docker-compose.yml` at the repo root builds all services locally with `--build` instead of pulling published images.

A CI pipeline (GitHub Actions) runs the Python and Java test suites on every push; a separate tag-triggered workflow builds and publishes the Docker images and desktop installers referenced in the Install & Run section above.

---
