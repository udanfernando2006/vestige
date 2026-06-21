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

        for pair in pairs:
            path = self.determine_path(pair)
            result = await self.run_pair(pair, path)

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
                prev_status = last["status"] if last else None
                if last is None or last["in_stock"] != availability.in_stock:
                    pair_summary["changed"] = True
                    changes.append(
                        {
                            "pair_id": pair["id"],
                            "from": prev_status,
                            "to": availability.status,
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

    def is_llm_discovery_enabled(self) -> bool:
        """Reads LLM_DISCOVERY_ENABLED from env; returns bool."""
        return os.environ.get("LLM_DISCOVERY_ENABLED", "false").lower() == "true"

    def get_llm_mode(self) -> str:
        """Reads LLM_MODE from env; returns 'direct' or 'selector'."""
        return os.environ.get("LLM_MODE", "selector").lower()

    def determine_path(self, pair: TrackingPair) -> str:
        """
        Inspects tracking pair state to return execution path A, B, C, or D.
        """
        has_url = bool(pair["product_url"])
        has_selectors = bool(pair["price_selector"] and pair["stock_selector"])

        if not has_url:
            return "A"
        elif has_url and has_selectors:
            return "C"
        elif self.get_llm_mode() == "direct":
            return "D"
        elif self.is_llm_discovery_enabled():
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

    def collect_run_summary(self, results: List[Dict[str, Any]]) -> dict:
        """Aggregates all results, including a list of skipped pairs due to NEEDS_SETUP."""
        summary = {
            "total": len(results),
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

    async def _run_pair_path_a(
        self, pair: TrackingPair, session: BrowserSession
    ) -> dict:
        """
        Path A: Discovery.
        Crawls the store to find the product URL, updates the DB, and delegates to Path B or D.
        """
        print(f"Path A: Initiating Crawler for '{pair['book_name']}'")
        crawler = Crawler()

        store = self.db_writer.get_store(pair["store_id"])
        urls = {
            "base_url": store["base_url"],
            "search_endpoint_url": store["search_url_template"],
        }

        crawl_result = await crawler.find_product_url(
            urls=urls, title=pair["book_name"], isbn=pair["book_isbn"], session=session
        )

        if not crawl_result or not crawl_result.get("success"):
            raise Exception(
                f"Crawler failed to discover URL: {crawl_result.get('reason', 'Unknown error')}"
            )

        if store["search_url_template"] is None and crawl_result.get(
            "search_url_template"
        ):
            self.db_writer.update_store_search_template(
                pair["store_id"], crawl_result["search_url_template"]
            )

        found_url = crawl_result.get("product_url")
        print(f"Path A: Successfully discovered URL: {found_url}")

        # Save newly discovered URL to DB
        self.db_writer.update_pair_url(pair["id"], found_url)

        # Update local memory pair so subsequent paths have the URL
        pair["product_url"] = found_url

        # Determine next routing based on LLM_MODE
        next_path = "D" if self.get_llm_mode() == "direct" else "B"
        print(f"Path A completed. Routing to Path {next_path}")

        if next_path == "B":
            return await self._run_pair_path_b(pair, session)
        return await self._run_pair_path_d(pair, session)

    async def _run_pair_path_b(
        self, pair: TrackingPair, session: BrowserSession
    ) -> dict:
        """Path B: LLM Discovery of Selectors + Fast Scrape."""
        if not self.is_llm_discovery_enabled():
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
                return await self._run_pair_path_d(pair, session)
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
            updated_pair["product_url"], selectors, session=session
        )

        if scrape_data.raw_stock_text is None and scrape_data.raw_price_text is None:
            raise Exception("selector_not_found")
        scrape_data.source = "scraper"
        return {"pair_id": pair["id"], "status": "COMPLETED", "result": scrape_data}

    async def _run_pair_path_c(
        self, pair: TrackingPair, session: BrowserSession
    ) -> dict:
        """Path C: Standard Cached CSS Selector Scrape."""
        scraper = Scraper()
        selectors = {
            "price": {"selector": pair["price_selector"], "direct_text": True},
            "availability": {"selector": pair["stock_selector"]},
        }

        scrape_data = await scraper.scrape(
            pair["product_url"], selectors, session=session
        )

        if scrape_data.raw_stock_text is None and scrape_data.raw_price_text is None:
            raise Exception("selector_not_found")
        scrape_data.source = "scraper"
        return {"pair_id": pair["id"], "status": "COMPLETED", "result": scrape_data}

    async def _run_pair_path_d(
        self, pair: TrackingPair, session: BrowserSession
    ) -> dict:
        """Path D: LLM Direct Extraction bypassing CSS Selectors."""
        await session.navigate(pair["product_url"])
        html = await session.get_html()

        extractor = Extractor(
            {
                "engine": "stripped",
                "api_base": os.environ.get("DIRECT_API_BASE"),
                "api_key": os.environ.get("DIRECT_API_KEY", ""),
                "model_name": os.environ.get("DIRECT_MODEL"),
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

    async def run_pair(self, pair: TrackingPair, path: str) -> dict:
        """
        Master execution router. Opens one BrowserSession per pair and passes it through the module chain.
        """
        print(f"Running Pair ID {pair['id']} via Path {path}")

        async with BrowserSession() as session:
            try:
                if path == "A":
                    return await self._run_pair_path_a(pair, session)
                elif path == "B":
                    return await self._run_pair_path_b(pair, session)
                elif path == "C":
                    return await self._run_pair_path_c(pair, session)
                elif path == "D":
                    return await self._run_pair_path_d(pair, session)
                else:
                    raise Exception(f"Unknown path routing: {path}")

            except Exception as e:
                err_result = self.handle_error(pair, e)
                return {
                    "pair_id": pair["id"],
                    "status": err_result.status,
                    "reason": err_result.reason,
                }
