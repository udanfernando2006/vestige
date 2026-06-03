import asyncio
import re
import json
import html2text
from datetime import datetime, timezone

from models.result import AvailabilityResult
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class Scraper:
    def __init__(self, headless: bool = True, wait_time: int = 5):
        self._headless = headless
        self._wait_time = wait_time

    async def scrape(self, url, selectors, wait_selectors=None) -> dict:
        try:
            async with async_playwright() as self.p:
                await self._setup_browser()
                await self._rate_limit_wait()
                await self._navigate_page(url, wait_selectors)
                html = await self.page.content()
                soup = BeautifulSoup(html, 'lxml')
                extracted = await self._extract_data(soup, selectors)
                print(json.dumps(extracted, indent=2))
                await self.browser.close()

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

                return result
        
        except Exception as e:
            return AvailabilityResult(
                status="ERROR",
                reason=str(e),
                scraped_at=datetime.now(timezone.utc)
            )

    async def _setup_browser(self):
        self.browser = await self.p.chromium.launch(headless=self._headless,
            args=['--disable-blink-features=AutomationControlled'])
        self.page = await self.browser.new_page()
        
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Referer': 'https://www.google.com/',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")


    async def _navigate_page(self, url, wait_selectors=None):
        # Navigate to the page
        await self.page.goto(url, timeout=60000)
        
        await self.page.wait_for_load_state('networkidle')
        
        # Wait for critical selectors if specified
        if wait_selectors:
            for selector in wait_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                except:
                    pass  # Selector may not exist on this page

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
        
        # In stock indicators
        if any(phrase in text for phrase in ['in stock', 'available', 'in stock now', 'ready to ship']):
            return True
        
        # Out of stock indicators
        if any(phrase in text for phrase in ['out of stock', 'sold out', 'unavailable', 'pre-order']):
            return False
        
        # Unclear
        return None

    def check_response_status(self, status_code: int):
        if 400 <= status_code < 500:
            raise Exception(f"http_error_{status_code}")  # Client error
        elif 500 <= status_code < 600:
            raise Exception(f"http_error_{status_code}")  # Server error