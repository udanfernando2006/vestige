#!/usr/bin/env python3
"""
scraper/tools/discover_selectors.py

Standalone CLI tool for LLM-assisted CSS selector discovery.
Identifies price and stock CSS selectors for a product page, validates them
against the live page, and optionally commits them to the database.

Usage:
    # Discover selectors for a tracked pair (resolves URL from DB)
    python scraper/tools/discover_selectors.py --pair-id 3

    # Discover from a direct URL (no DB lookup)
    python scraper/tools/discover_selectors.py --url "https://sarasavi.lk/books/..." --store sarasavi

    # Validate output and write to DB if both selectors pass
    python scraper/tools/discover_selectors.py --pair-id 3 --commit
"""

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Ensure project root is on the path so db/browser imports resolve
# whether the script is run from scraper/ or the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scraper.browser.session import BrowserSession
from scraper.db.writer import DBWriter
from scraper.pipeline.llm_extractor import Extractor

load_dotenv()


# ---------------------------------------------------------------------------
# Data container for selector validation outcome
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    price_passed: bool
    stock_passed: bool
    price_sample: Optional[str] = None
    stock_sample: Optional[str] = None
    reason: Optional[str] = None  # e.g. "stock_selector_returned_no_match"


# ---------------------------------------------------------------------------
# Step 1 — Resolve the target URL
# ---------------------------------------------------------------------------

def load_target(pair_id: Optional[int], url: Optional[str], store: Optional[str]) -> dict:
    """
    Resolves the product URL and store name.
    - --pair-id mode: fetches URL from the database
    - --url mode:     uses the supplied URL directly; --store is required

    Returns dict with keys: 'url', 'store_name', 'pair_id' (None in --url mode).
    Exits with a clear error message if the inputs are invalid.
    """
    if pair_id is not None:
        from sqlalchemy import create_engine
        engine = create_engine(os.environ["DATABASE_URL"])
        db = DBWriter(engine)
        pair = db.get_pair(pair_id)

        if not pair:
            print(f"Error: No tracking pair found with id={pair_id}", file=sys.stderr)
            sys.exit(1)
        if not pair.get("product_url"):
            print(
                f"Error: Pair {pair_id} has no product_url. "
                "Run the Crawler first or supply a URL with --url.",
                file=sys.stderr,
            )
            sys.exit(1)

        return {
            "url": pair["product_url"],
            "store_name": pair["store_name"],
            "book_name": pair["book_name"],
            "pair_id": pair_id,
        }

    elif url:
        if not store:
            print("Error: --store is required when using --url", file=sys.stderr)
            sys.exit(1)
        return {"url": url, "store_name": store, "book_name": None, "pair_id": None}

    else:
        print("Error: Provide either --pair-id or --url", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 2 — Fetch the product page HTML
# ---------------------------------------------------------------------------

async def fetch_html(url: str) -> str:
    """Fetches the raw page HTML via Playwright. Cleaning is handled by extractor.clean_html()."""
    async with BrowserSession() as session:
        await session.navigate(url)
        return await session.get_html()


# ---------------------------------------------------------------------------
# Step 6 — Validate selectors against the live page
# ---------------------------------------------------------------------------

async def validate_selectors(url: str, price_sel: str, stock_sel: str) -> ValidationResult:
    """
    Re-fetches the live page and runs both selectors with BeautifulSoup.
    A selector passes when it matches an element and the extracted text is plausible:
    - price: must contain at least one digit
    - stock: must contain at least one known stock-status word
    """
    async with BrowserSession() as session:
        await session.navigate(url)
        html = await session.get_html()

    soup = BeautifulSoup(html, "lxml")
    price_passed = False
    stock_passed = False
    price_sample = None
    stock_sample = None
    reasons = []

    # --- Price ---
    if price_sel:
        el = soup.select_one(price_sel)
        if el:
            text = el.get_text().strip()
            if text and re.search(r"\d", text):
                price_sample = text
                price_passed = True
            else:
                reasons.append("price_selector_returned_no_digit")
        else:
            reasons.append("price_selector_returned_no_match")
    else:
        reasons.append("price_selector_missing")

    # --- Stock ---
    if stock_sel:
        el = soup.select_one(stock_sel)
        if el:
            text = el.get_text().strip()
            stock_words = ["stock", "available", "sold", "unavailable", "order", "ship"]
            if text and any(w in text.lower() for w in stock_words):
                stock_sample = text
                stock_passed = True
            else:
                reasons.append("stock_selector_returned_no_match")
        else:
            reasons.append("stock_selector_returned_no_match")
    else:
        reasons.append("stock_selector_missing")

    return ValidationResult(
        price_passed=price_passed,
        stock_passed=stock_passed,
        price_sample=price_sample,
        stock_sample=stock_sample,
        reason=", ".join(reasons) if reasons else None,
    )


# ---------------------------------------------------------------------------
# Step 7 — Commit validated selectors to the database
# ---------------------------------------------------------------------------

def commit_to_db(pair_id: int, price_sel: str, stock_sel: str) -> None:
    """
    Writes price_selector and stock_selector to tracking_pairs.
    Uses DBWriter.update_pair_selectors() which also sets selector_found_at
    and transitions pair status from NEEDS_SETUP → PENDING automatically.
    """
    from sqlalchemy import create_engine
    engine = create_engine(os.environ["DATABASE_URL"])
    db = DBWriter(engine)
    db.update_pair_selectors(pair_id, price_sel, stock_sel)


# ---------------------------------------------------------------------------
# Core async run logic
# ---------------------------------------------------------------------------

async def _run(args) -> int:
    """
    Orchestrates the full discovery flow.
    Returns exit code: 0 = success, 1 = failure.
    The Orchestrator checks this exit code when running as a subprocess.
    """
    target = load_target(args.pair_id, args.url, args.store)

    print(f"Fetching HTML: {target['url']}")
    raw_html = await fetch_html(target["url"])

    provider = os.environ.get("LLM_PROVIDER", "openrouter")
    model = os.environ.get("LLM_MODEL", "openrouter/free")

    if provider == "ollama":
        print("Warning: Local models are not reliable for selector discovery. "
            "Set LLM_PROVIDER=openrouter or LLM_PROVIDER=anthropic.", file=sys.stderr)
        return 1
    
    api_base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    extractor = Extractor({"engine": "cloud", "api_base": api_base, "api_key": api_key, "model_name": model, "provider": provider})

    cleaned_html = extractor.clean_html(raw_html)

    title_context = target['book_name'] or 'unknown'
    print(f"Calling LLM ({provider} / {model})...")
    selectors = extractor.extract_selectors(cleaned_html, title_context)

    if 'error' in selectors:
        print(f"Error: {selectors['error']}", file=sys.stderr)
        return 1

    price_sel = selectors.get('price', {}).get('selector') if selectors.get('price') else None
    stock_sel = selectors.get('availability', {}).get('selector') if selectors.get('availability') else None

    # --commit: validate against the live page, then write to DB if both pass
    if args.commit:
        if not target["pair_id"]:
            print("Error: --commit requires --pair-id (not available in --url mode)", file=sys.stderr)
            return 1

        print("Validating selectors against live page...")
        validation = await validate_selectors(target["url"], price_sel, stock_sel)

        if not (validation.price_passed and validation.stock_passed):
            result = {
                "price_selector": price_sel if validation.price_passed else None,
                "stock_selector": stock_sel if validation.stock_passed else None,
                "model_used": model,
                "committed": False,
                "reason": validation.reason,
            }
            print(json.dumps(result, indent=2))
            return 1  # non-zero exit → Orchestrator keeps pair as NEEDS_SETUP

        commit_to_db(target["pair_id"], price_sel, stock_sel)
        result = {
            "price_selector": price_sel,
            "stock_selector": stock_sel,
            "price_sample": validation.price_sample,
            "stock_sample": validation.stock_sample,
            "model_used": model,
            "committed": True,
        }

    else:
        # No --commit: print suggestion only; user reviews before patching in
        result = {
            "price_selector": price_sel,
            "stock_selector": stock_sel,
            "model_used": model,
            "committed": False,
        }

    print(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LLM-assisted CSS selector discovery for Vestige tracking pairs"
    )
    parser.add_argument(
        "--pair-id", type=int,
        help="Resolve product URL from a DB tracking pair by ID"
    )
    parser.add_argument(
        "--url", type=str,
        help="Direct product page URL (use with --store)"
    )
    parser.add_argument(
        "--store", type=str,
        help="Store name — required when using --url"
    )
    parser.add_argument(
        "--commit", action="store_true",
        help="Validate selectors against the live page and write to DB on success"
    )
    args = parser.parse_args()

    if not args.pair_id and not args.url:
        parser.print_help()
        sys.exit(1)

    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()