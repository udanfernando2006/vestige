import asyncio
import re
import json
from datetime import datetime, timezone

from models.result import AvailabilityResult
from browser.session import BrowserSession
from bs4 import BeautifulSoup

class Scraper:
    def __init__(self, headless: bool = True, wait_time: int = 5, timeout: int = 60000):
        self._headless = headless
        self._wait_time = wait_time
        self._timeout = timeout

    async def scrape(self, url: str, selectors: dict, wait_selectors = None, session: BrowserSession = None) -> AvailabilityResult:
        if session:
            return await self._do_scrape(session, url, selectors, wait_selectors)
        else:
            async with BrowserSession({'headless': self._headless, 'timeout': self._timeout}) as session:
                return await self._do_scrape(session, url, selectors, wait_selectors)

    async def _do_scrape(self, session: BrowserSession, url: str, selectors: dict, wait_selectors=None) -> AvailabilityResult:
        await self._rate_limit_wait()
        await session.navigate(url)
        
        # Wait for critical selectors if specified
        if wait_selectors:
            for selector in wait_selectors:
                await session.wait_for_selector(selector)
        
        html = await session.get_html()
        soup = BeautifulSoup(html, 'lxml')
        extracted = await self._extract_data(soup, selectors)
        print(json.dumps(extracted, indent=2))
        result = AvailabilityResult(
            raw_price_text=extracted.get('price'),
            raw_stock_text=extracted.get('availability'),
            scraped_at=datetime.now(timezone.utc),
        )

        if extracted.get('price'):
            result.price = self.parse_price(extracted['price'])

        if extracted.get('availability'):
            result.in_stock = self.parse_stock_status(extracted['availability'])

        if result.in_stock is True:
            result.status = "IN_STOCK"
        elif result.in_stock is False:
            result.status = "OUT_OF_STOCK"
        else:
            result.status = "ERROR"
            result.reason = "unparseable_stock_status"

        return result

    async def _extract_data(self, soup: BeautifulSoup, selectors: dict) -> dict:
        product_info = {}
        
        for field, config in selectors.items():
            if not config:
                product_info[field] = None
                continue
                
            try:
                element = None
                
                # 1. Handle TEXT LOOKUP FALLBACK strategy
                if "find_by_text" in config:
                    lookup = config["find_by_text"]
                    if isinstance(lookup, (list, tuple)) and len(lookup) >= 2:
                        target_tag, search_text = lookup[0], lookup[1]
                        
                        # Find the label element containing the target text identifier
                        label_node = soup.find(target_tag, string=lambda t: t and search_text.lower() in t.lower())
                        
                        if label_node and config.get("then_next"):
                            # Traversal strategy: step over to the next matching sibling element node
                            element = label_node.find_next(config["then_next"])
                        elif label_node:
                            element = label_node

                # 2. Handle STANDARD CSS SELECTOR strategy
                elif "selector" in config and config["selector"]:
                    selector_str = config["selector"]
                    
                    if config.get("direct_text"):
                        # soup.select_one might return None, so we handle it gracefully below
                        element = soup.select_one(selector_str)
                    else:
                        element = soup.select_one(selector_str)

                # 3. Clean and Extract String Values
                if element is not None:
                    if config.get("preserve_semantics"):
                        # Keep HTML structural text intact for descriptions
                        extracted_value = str(element)
                    elif config.get("direct_text"):
                        # Capture only immediate node character structures
                        extracted_value = "".join(element.find_all(text=True, recursive=False)).strip()
                        if not extracted_value:
                            extracted_value = element.get_text().strip()
                    else:
                        extracted_value = element.get_text().strip()
                        
                    # Universal Sanity Cleanup Layer: strip out leading/trailing design punctuation
                    if extracted_value and isinstance(extracted_value, str):
                        extracted_value = extracted_value.strip().lstrip(':-•').strip()
                        
                    product_info[field] = extracted_value
                else:
                    product_info[field] = None
                    
            except Exception as e:
                product_info[field] = None
                print(f"⚠️ Warning: Failed extracting field '{field}': {e}")
                
        return product_info
    
    async def _rate_limit_wait(self):
        await asyncio.sleep(self._wait_time)
    
    def parse_price(self, raw_text: str):
        if not raw_text:
            return None
        
        # Remove common currency prefixes
        text = re.sub(r'(LKR|Rs\.?|USD|\$|€|£)', '', raw_text, flags=re.IGNORECASE).strip()
        
        # Extract numeric value (handles both "1,500.00" and "1500")
        match = re.search(r'[\d,]+\.?\d*', text)
        if match:
            try:
                return float(match.group().replace(',', ''))
            except ValueError:
                return None
        return None

    def parse_stock_status(self, raw_text: str):
        if not raw_text:
            return None

        text = raw_text.lower().strip()

        # Out of stock checked FIRST — "unavailable" contains "available"
        # so order between the two blocks is critical
        if any(phrase in text for phrase in [
            'out of stock', 'sold out', 'unavailable',
            'not available', 'pre-order', 'out-of-stock',
        ]):
            return False

        if any(phrase in text for phrase in [
            'in stock', 'in-stock', 'available',
            'add to cart', 'add to basket',
            'in stock now', 'ready to ship', 'buy now',
        ]):
            return True

        return None

    def check_response_status(self, status_code: int):
        if 400 <= status_code < 500:
            raise Exception(f"http_error_{status_code}")  # Client error
        elif 500 <= status_code < 600:
            raise Exception(f"http_error_{status_code}")  # Server error