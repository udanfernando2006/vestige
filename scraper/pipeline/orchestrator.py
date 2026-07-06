import os
import sys
import subprocess
import datetime

from typing import List, Dict, Any, Union
from browser.session import BrowserSession
from pipeline.scraper import Scraper
from pipeline.crawler import Crawler
from pipeline.llm_extractor import Extractor
from models.result import AvailabilityResult
from db.models import TrackingPair
from db.writer import DBWriter


class Orchestrator:
    def __init__(self, db_writer: DBWriter):
        self.db_writer = db_writer

    async def run_all(self) -> dict:
        """
        Top-level orchestration loop. Called by main.py on each scheduled run.
        Loads all active pairs, routes each through the correct path, writes
        snapshots, detects changes, and returns the run summary.
        """
        run_id = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        start_time = datetime.datetime.now(datetime.timezone.utc)

        pairs = self.load_active_pairs()
        print(f"[{run_id}] Starting run — {len(pairs)} active pairs")

        all_results = []
        changes = []
        errors = []
        settings = self.db_writer.get_settings()

        for pair in pairs:
            path = self.determine_path(pair, settings)
            result = await self.run_pair(pair, path, settings)

            pair_summary = {
                "pair_id": pair["id"],
                "book": pair["book_name"],
                "store": pair["store_name"],
                "status": result.get("status"),
                "changed": False,
            }

            if result.get("status") == "COMPLETED":
                # Capture previous state BEFORE writing new snapshot
                last = self.db_writer.get_last_snapshot(pair["id"])

                availability = result["result"]

                self.db_writer.write_snapshot(pair["id"], availability)

                pair_summary["price"] = availability.price
                pair_summary["status"] = availability.status

                # Detect changes
                change = self._detect_change(last, availability)
                if change is not None:
                    pair_summary["changed"] = True
                    changes.append(
                        {
                            "pair_id": pair["id"],
                            "book_name": pair["book_name"],
                            "store_name": pair["store_name"],
                            "product_url": pair.get("product_url"),
                            **change,
                        }
                    )
            elif result.get("status") == "NEEDS_SETUP":
                pass  # DBWriter already updated status; just record it

            else:
                errors.append({"pair_id": pair["id"], "reason": result.get("reason")})

            all_results.append(pair_summary)

        duration = (
            datetime.datetime.now(datetime.timezone.utc) - start_time
        ).total_seconds()
        summary = self.collect_run_summary(all_results)
        summary.update(
            {
                "run_id": run_id,
                "results": all_results,
                "changes": changes,
                "errors": errors,
                "duration_seconds": round(duration, 1),
            }
        )

        print(
            f"[{run_id}] Done — {summary['completed']} completed, "
            f"{len(changes)} changes, {len(errors)} errors in {duration:.1f}s"
        )
        return summary

    def is_llm_discovery_enabled(self, settings: dict) -> bool:
        """Reads LLM_DISCOVERY_ENABLED from settings; returns bool."""
        return settings["LLM_DISCOVERY_ENABLED"].strip().lower() == "true"

    def get_llm_mode(self, settings: dict) -> str:
        """Reads LLM_MODE from settings; returns 'direct' or 'selector'."""
        return settings["LLM_MODE"].strip().lower()

    def determine_path(self, pair: TrackingPair, settings: dict) -> str:
        """
        Inspects tracking pair state to return execution path A, B, C, or D.
        """
        has_url = bool(pair["product_url"])
        has_selectors = bool(pair["price_selector"] and pair["stock_selector"])

        if not has_url:
            return "A"
        elif has_url and has_selectors:
            return "C"
        elif self.get_llm_mode(settings) == "direct":
            return "D"
        elif self.is_llm_discovery_enabled(settings):
            return "B"
        else:
            return "NEEDS_SETUP"

    def load_active_pairs(self) -> List[Dict]:
        """Fetches all tracking pairs where status is not SKIP or NEEDS_SETUP."""
        return self.db_writer.get_active_pairs()

    def handle_error(
        self, pair: TrackingPair, error: Union[str, Exception]
    ) -> AvailabilityResult:
        """
        Logs the error. If failure reason is selector_not_found, clears selectors
        and transitions to NEEDS_SETUP. Otherwise marks ERROR.
        """
        error_msg = str(error)
        print(f"[ERROR] Pair {pair['id']} ({pair['book_name']}): {error_msg}")

        result = AvailabilityResult(status="ERROR", reason=error_msg)

        if "selector_not_found" in error_msg.lower():
            self.db_writer.clear_pair_selectors(pair["id"])
            result.status = "NEEDS_SETUP"
            result.reason = "selector_not_found"

        return result

    def _classify_stock_fallback(self, settings: dict, raw_text: str) -> "bool | None":
        """
        Last-resort classification for a raw stock-status string that both
        the hardcoded phrase list and any CUSTOM_STOCK_*_PATTERNS regex
        failed to parse. Tries DIRECT_* credentials first, then falls back
        to SELECTOR_* credentials if DIRECT_* isn't configured (the
        selector-discovery model is chosen for large-context HTML parsing,
        which is strictly more capable than what this short-text call
        needs — the reverse substitution is NOT attempted elsewhere).
        Returns None (never raises) if neither role is configured or both
        calls fail, so callers can fall through to the existing ERROR
        status unchanged.
        """
        for base_key, key_key, model_key in (
            ("DIRECT_API_BASE", "DIRECT_API_KEY", "DIRECT_MODEL"),
            ("SELECTOR_API_BASE", "SELECTOR_API_KEY", "SELECTOR_MODEL"),
        ):
            api_base = settings.get(base_key)
            model_name = settings.get(model_key)
            if not api_base or not model_name:
                continue
            try:
                extractor = Extractor(
                    {
                        "api_base": api_base,
                        "api_key": settings.get(key_key),
                        "model_name": model_name,
                    }
                )
                result = extractor.classify_stock_status(raw_text)
                if result is not None:
                    return result
            except Exception as e:
                print(f"[Stock Fallback] {base_key} attempt failed: {e}")
                continue
        return None

    def _apply_stock_fallback_if_needed(
        self, scrape_data: AvailabilityResult, settings: dict
    ) -> AvailabilityResult:
        """
        Shared by Path B and Path C (both end in an identical cached-selector
        scrape). If the regex parse left the result as ERROR/unparseable_stock_status,
        attempts the LLM fallback and overwrites in_stock/status/reason on
        success. Leaves scrape_data untouched (still ERROR) if the fallback
        can't resolve it either, or if there's no stock text to classify at all
        (e.g. selector matched nothing — that's the separate selector_not_found
        case checked immediately after this call, in each path).
        """
        if (
            scrape_data.status == "ERROR"
            and scrape_data.reason == "unparseable_stock_status"
            and scrape_data.raw_stock_text
        ):
            fallback_result = self._classify_stock_fallback(
                settings, scrape_data.raw_stock_text
            )
            if fallback_result is not None:
                scrape_data.in_stock = fallback_result
                scrape_data.status = "IN_STOCK" if fallback_result else "OUT_OF_STOCK"
                scrape_data.reason = None
        return scrape_data

    def collect_run_summary(self, results: List[Dict[str, Any]]) -> dict:
        """Aggregates all results, including a list of skipped pairs due to NEEDS_SETUP."""
        summary = {
            "total_pairs": len(results),
            "completed": 0,
            "errors": 0,
            "needs_setup": [],
        }

        for res in results:
            status = res.get("status")
            pair_id = res.get("pair_id")

            if status in ("IN_STOCK", "OUT_OF_STOCK", "NOT_LISTED"):
                summary["completed"] += 1
            elif status == "NEEDS_SETUP":
                summary["needs_setup"].append(pair_id)
            else:
                summary["errors"] += 1

        return summary

    def _detect_change(
        self, last: dict | None, availability: AvailabilityResult
    ) -> dict | None:
        """
        Compares `availability` against `last` (the previous snapshot dict
        from DBWriter.get_last_snapshot(), or None on a pair's first-ever
        snapshot). Returns a change record if status or price differs, else
        None.

        A first-ever snapshot is never reported as a change — there's nothing
        to diff against, and reporting it as one would notify on every newly
        added book the moment it's first scraped.
        """
        if last is None:
            return None

        status_changed = last["in_stock"] != availability.in_stock
        price_changed = (
            last["price"] is not None
            and availability.price is not None
            and round(float(last["price"]), 2) != round(float(availability.price), 2)
        )
        if not status_changed and not price_changed:
            return None

        return {
            "from_status": last["status"],
            "to_status": availability.status,
            "from_price": (
                round(float(last["price"]), 2) if last["price"] is not None else None
            ),
            "to_price": (
                round(float(availability.price), 2)
                if availability.price is not None
                else None
            ),
        }

    async def _run_pair_path_a(
        self, pair: TrackingPair, session: BrowserSession, settings: dict
    ) -> dict:
        """
        Path A: Discovery.
        Crawls the store to find the product URL, updates the DB, and delegates to Path B or D.
        """
        crawler = Crawler()

        store = self.db_writer.get_store(pair["store_id"])
        urls = {
            "base_url": store["base_url"],
            "search_url_template": store["search_url_template"],
        }
        try:
            crawl_result = await crawler.find_product_url(
                urls=urls,
                title=pair["book_name"],
                isbn=pair["book_isbn"],
                session=session,
            )
        except Exception as e:
            raise

        if not crawl_result or not crawl_result.get("success"):
            raise Exception(
                f"Crawler failed to discover URL: {crawl_result.get('error', 'Unknown error') if crawl_result else 'No result returned'}"
            )

        if store["search_url_template"] is None and crawl_result.get(
            "search_url_template"
        ):
            self.db_writer.update_store_search_template(
                pair["store_id"], crawl_result["search_url_template"]
            )

        found_url = crawl_result.get("product_url")

        # Save newly discovered URL to DB
        self.db_writer.update_pair_url(pair["id"], found_url)

        # Update local memory pair so subsequent paths have the URL
        pair["product_url"] = found_url

        # Determine next routing based on LLM_MODE
        next_path = "D" if self.get_llm_mode(settings) == "direct" else "B"

        if next_path == "B":
            return await self._run_pair_path_b(pair, session, settings)
        return await self._run_pair_path_d(pair, session, settings)

    async def _run_pair_path_b(
        self, pair: TrackingPair, session: BrowserSession, settings: dict
    ) -> dict:
        """Path B: LLM Discovery of Selectors + Fast Scrape."""
        if not self.is_llm_discovery_enabled(settings):
            print(
                f"Path B skipped for Pair {pair['id']}: LLM discovery disabled. Marking NEEDS_SETUP."
            )
            self.db_writer.update_pair_status(pair["id"], "NEEDS_SETUP")
            return {"pair_id": pair["id"], "status": "NEEDS_SETUP"}

        print(f"Path B: Running discover_selectors.py for Pair {pair['id']}")
        proc = subprocess.run(
            [
                sys.executable,
                "tools/discover_selectors.py",
                "--pair-id",
                str(pair["id"]),
                "--commit",
            ],
            capture_output=False,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        if proc.returncode != 0:
            print(
                f"Path B: Discovery/validation failed for Pair {pair['id']} — falling back to direct extraction this run."
            )
            try:
                return await self._run_pair_path_d(pair, session, settings)
            except Exception as e:
                print(
                    f"Path B: Direct-extraction fallback also failed for Pair {pair['id']}: {e}"
                )
                self.db_writer.update_pair_status(pair["id"], "NEEDS_SETUP")
                return {"pair_id": pair["id"], "status": "NEEDS_SETUP"}

        # Selectors are now committed in DB — re-fetch to get them
        updated_pair = self.db_writer.get_pair(pair["id"])
        if not updated_pair or not updated_pair["price_selector"]:
            raise Exception("Selectors not found in DB after discovery commit")

        # Scrape with the fresh selectors — identical to Path C from here
        scraper = Scraper()
        selectors = {
            "price": {"selector": updated_pair["price_selector"], "direct_text": True},
            "availability": {"selector": updated_pair["stock_selector"]},
        }
        scrape_data = await scraper.scrape(
            updated_pair["product_url"],
            selectors,
            session=session,
            custom_in=settings.get("CUSTOM_STOCK_IN_PATTERNS", ""),
            custom_out=settings.get("CUSTOM_STOCK_OUT_PATTERNS", ""),
        )
        scrape_data = self._apply_stock_fallback_if_needed(scrape_data, settings)

        if scrape_data.raw_stock_text is None and scrape_data.raw_price_text is None:
            raise Exception("selector_not_found")
        scrape_data.source = "scraper"
        return {"pair_id": pair["id"], "status": "COMPLETED", "result": scrape_data}

    async def _run_pair_path_c(
        self, pair: TrackingPair, session: BrowserSession, settings: dict
    ) -> dict:
        """Path C: Standard Cached CSS Selector Scrape."""
        scraper = Scraper()
        selectors = {
            "price": {"selector": pair["price_selector"], "direct_text": True},
            "availability": {"selector": pair["stock_selector"]},
        }

        scrape_data = await scraper.scrape(
            pair["product_url"],
            selectors,
            session=session,
            custom_in=settings.get("CUSTOM_STOCK_IN_PATTERNS", ""),
            custom_out=settings.get("CUSTOM_STOCK_OUT_PATTERNS", ""),
        )
        scrape_data = self._apply_stock_fallback_if_needed(scrape_data, settings)

        if scrape_data.raw_stock_text is None and scrape_data.raw_price_text is None:
            raise Exception("selector_not_found")
        scrape_data.source = "scraper"
        return {"pair_id": pair["id"], "status": "COMPLETED", "result": scrape_data}

    async def _run_pair_path_d(
        self, pair: TrackingPair, session: BrowserSession, settings: dict
    ) -> dict:
        """Path D: LLM Direct Extraction bypassing CSS Selectors."""
        await session.navigate(pair["product_url"])
        html = await session.get_html()
        extractor = Extractor(
            {
                "engine": "stripped",
                "api_base": settings["DIRECT_API_BASE"],
                "api_key": settings["DIRECT_API_KEY"],
                "model_name": settings["DIRECT_MODEL"],
            }
        )
        cleaned_html = extractor.clean_html(html)

        details = extractor.extract_details(
            cleaned_html, pair["book_name"], fields=["price", "stock_status"]
        )

        if "error" in details:
            raise Exception(f"LLM Direct Extraction failed: {details['error']}")

        scraper = Scraper()
        parsed_price = scraper.parse_price(details.get("price"))
        parsed_stock = scraper.parse_stock_status(details.get("stock_status"))

        availability_result = AvailabilityResult(
            in_stock=parsed_stock,
            price=parsed_price,
            raw_price_text=details.get("price"),
            raw_stock_text=details.get("stock_status"),
            status=(
                "IN_STOCK"
                if parsed_stock
                else ("OUT_OF_STOCK" if parsed_stock is False else "ERROR")
            ),
            source="llm_direct",
        )

        return {
            "pair_id": pair["id"],
            "status": "COMPLETED",
            "result": availability_result,
        }

    async def run_pair(self, pair: TrackingPair, path: str, settings: dict) -> dict:
        """
        Master execution router. Opens one BrowserSession per pair and passes it through the module chain.
        """
        print(f"Running Pair ID {pair['id']} via Path {path}")

        if path == "NEEDS_SETUP":
            self.db_writer.update_pair_status(pair["id"], "NEEDS_SETUP")
            return {"pair_id": pair["id"], "status": "NEEDS_SETUP"}

        async with BrowserSession() as session:
            try:
                if path == "A":
                    return await self._run_pair_path_a(pair, session, settings)
                elif path == "B":
                    return await self._run_pair_path_b(pair, session, settings)
                elif path == "C":
                    return await self._run_pair_path_c(pair, session, settings)
                elif path == "D":
                    return await self._run_pair_path_d(pair, session, settings)
                else:
                    raise Exception(f"Unknown path routing: {path}")

            except Exception as e:
                err_result = self.handle_error(pair, e)
                return {
                    "pair_id": pair["id"],
                    "status": err_result.status,
                    "reason": err_result.reason,
                }
