# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — dependency installer
#
# Purpose: install every Python package listed in requirements.txt into a
# dedicated prefix (/install) so we can copy them cleanly to the runtime stage
# without dragging the build tools along.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /install

# gcc is only needed if any package in requirements.txt compiles a C extension
# at install time. psycopg2-binary ships pre-compiled wheels so it doesn't need
# it, but other packages (lxml, etc.) may. Kept here for safety; the final
# runtime stage does not carry gcc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --prefix /install puts everything (scripts, site-packages) under /install.
# The runtime stage copies /install → /usr/local, which is already on PATH and
# on Python's sys.path — no extra configuration needed.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime
#
# Lean image that contains only what the pipeline actually needs to run.
# The build-time toolchain (gcc, pip cache, wheel build artefacts) is absent.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Tell Playwright where to install and later find browser binaries.
# Setting this here means both the `playwright install` command below AND the
# Python code at runtime will resolve browsers from the same explicit path,
# regardless of which user the container runs as.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy all installed Python packages from the deps stage.
# This includes the `playwright` CLI script at /usr/local/bin/playwright.
COPY --from=deps /install /usr/local

# Install Chromium and every system-level library it depends on.
# --with-deps tells Playwright to run apt-get itself and install the full
# dependency tree for Chromium (libnss3, libgbm1, libasound2, etc.).
# This is the canonical Playwright-in-Docker approach — do not list the
# individual libraries manually; the set changes between browser versions.
RUN playwright install --with-deps chromium

# Copy application source last.
# Placing source after all dependency and browser-install layers means Docker's
# layer cache still applies to those expensive steps when only source changes.
COPY . .

# ── Runtime environment ──────────────────────────────────────────────────────

# Prevents UnicodeEncodeError when the LLM extractor or other modules write
# non-ASCII output to stdout and the subprocess caller reads it.
# Required for discover_selectors.py → Orchestrator subprocess calls on any OS.
ENV PYTHONIOENCODING=utf-8

# Do not write .pyc bytecode files — no performance benefit in a container and
# keeps the image filesystem clean.
ENV PYTHONDONTWRITEBYTECODE=1

# Flush stdout/stderr immediately so `docker logs -f` shows real-time output
# rather than buffered batches.
ENV PYTHONUNBUFFERED=1

# ── Entry point ──────────────────────────────────────────────────────────────
# The scraper is a one-shot pipeline: it runs, writes results, and exits.
# It is not a long-running server. Invoke it via:
#   docker-compose run scraper             (manual run)
#   docker-compose run scraper python scraper/tools/discover_selectors.py ...
# The systemd timer / cron job on the host calls docker-compose run on schedule.
CMD ["python", "main.py"]
