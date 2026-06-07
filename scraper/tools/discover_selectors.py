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

import requests
from bs4 import BeautifulSoup, Comment
from dotenv import load_dotenv

# Ensure project root is on the path so db/browser imports resolve
# whether the script is run from scraper/ or the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from browser.session import BrowserSession
from db.writer import DBWriter

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
            "pair_id": pair_id,
        }

    elif url:
        if not store:
            print("Error: --store is required when using --url", file=sys.stderr)
            sys.exit(1)
        return {"url": url, "store_name": store, "pair_id": None}

    else:
        print("Error: Provide either --pair-id or --url", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 2 — Fetch and trim the product page HTML
# ---------------------------------------------------------------------------

async def fetch_and_trim_html(url: str) -> str:
    """
    Fetches the page via Playwright, removes boilerplate nodes (scripts, styles,
    nav, footer, header, SVG, HTML comments), then extracts only the product
    container subtree. Sending the full page to the LLM wastes tokens and causes
    small models to drift toward promotional elements instead of the main price.
    """
    async with BrowserSession() as session:
        await session.navigate(url)
        html = await session.get_html()

    soup = BeautifulSoup(html, "lxml")

    # Remove boilerplate tags entirely
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "svg"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Find the most specific product container available
    container = (
        soup.find("main")
        or soup.find(id="product")
        or soup.find(class_="product-detail")
        or soup.find(class_="product-container")
        or soup.find(class_="product-page")
        or soup.body
    )

    return str(container)


# ---------------------------------------------------------------------------
# Step 3 — Build the LLM prompt
# ---------------------------------------------------------------------------

def build_prompt(trimmed_html: str) -> str:
    """
    Constructs the selector-discovery prompt. Key constraints baked in:
    - Wildcard attribute selectors only (guards against Next.js hash class suffixes)
    - Target the main retail price, not installment/discount widgets
    - Return JSON only — no preamble, no markdown fences
    """
    return f"""You are analysing a product page HTML snippet from a Sri Lankan online bookstore.
Your task: identify the CSS selectors for the main product PRICE and STOCK STATUS.

STRICT RULES — follow exactly:
1. Output ONLY valid JSON. No preamble, no explanation, no markdown code fences.
2. Use wildcard attribute selectors: e.g. div[class*='price'] span
   NEVER use exact class names — they may contain framework-generated hash suffixes.
3. Select the MAIN retail price only.
   Ignore: instalment amounts, card discount prices, "pay later" widgets, crossed-out prices.
4. confidence must be a float between 0.0 and 1.0.
5. price_sample and stock_sample must be the literal text you expect the selector to return.

Required output format (JSON only):
{{
  "price_selector": "...",
  "stock_selector": "...",
  "price_sample": "...",
  "stock_sample": "...",
  "confidence": 0.0
}}

HTML:
{trimmed_html[:12000]}
"""


# ---------------------------------------------------------------------------
# Step 4 — Call the configured LLM provider
# ---------------------------------------------------------------------------

def call_llm(prompt: str) -> str:
    """
    Dispatches the prompt to the provider set in LLM_PROVIDER.
    Returns the raw text response from the model.
    Raises on HTTP errors or missing environment variables.
    """
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    model = os.environ.get("LLM_MODEL", "qwen2.5-coder:3b")

    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    elif provider == "openrouter":
        api_key = os.environ["OPENROUTER_API_KEY"]
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "anthropic":
        api_key = os.environ["ANTHROPIC_API_KEY"]
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Use ollama, openrouter, or anthropic.")


# ---------------------------------------------------------------------------
# Step 5 — Parse the LLM response
# ---------------------------------------------------------------------------

def parse_llm_response(raw: str) -> dict:
    """
    Extracts the JSON object from the LLM output.
    - Strips markdown code fences if the model included them
    - Falls back to regex extraction if there is surrounding text
    - Raises ValueError with a clear message if no parseable JSON is found
    """
    # Remove markdown fences (```json ... ``` or ``` ... ```)
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Direct parse — the happy path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Regex fallback — find the first {...} block
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract valid JSON from LLM output.\n"
        f"First 500 chars of raw response:\n{raw[:500]}"
    )


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
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    model = os.environ.get("LLM_MODEL", "qwen2.5-coder:3b")

    print(f"Fetching HTML: {target['url']}")
    trimmed_html = await fetch_and_trim_html(target["url"])

    prompt = build_prompt(trimmed_html)

    print(f"Calling LLM ({provider} / {model})...")
    try:
        raw_response = call_llm(prompt)
    except Exception as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        return 1

    try:
        parsed = parse_llm_response(raw_response)
    except ValueError as e:
        print(f"Error parsing LLM response: {e}", file=sys.stderr)
        return 1

    price_sel = parsed.get("price_selector")
    stock_sel = parsed.get("stock_selector")
    confidence = parsed.get("confidence", 0.0)

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
                "confidence": confidence,
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
            "confidence": confidence,
            "model_used": model,
            "committed": True,
        }

    else:
        # No --commit: print suggestion only; user reviews before patching in
        result = {
            "price_selector": price_sel,
            "stock_selector": stock_sel,
            "price_sample": parsed.get("price_sample"),
            "stock_sample": parsed.get("stock_sample"),
            "confidence": confidence,
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