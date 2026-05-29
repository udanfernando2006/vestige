import requests
import asyncio
import json
import re
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
                await self._setupBrowser()
                await self._rateLimitWait()
                await self._navigatePage(url, wait_selectors)
                html = await self.page.content()
                soup = BeautifulSoup(html, 'lxml')
                extracted = await self._extractData(soup, selectors)
                await self.browser.close()

                result = AvailabilityResult(
                    raw_price_text=extracted.get('price'),
                    raw_stock_text=extracted.get('availability'),
                    scraped_at=datetime.now(timezone.utc),
                )

                if extracted.get('price'):
                    result.price = self.parsePrice(extracted['price'])

                if extracted.get('availability'):
                    result.in_stock = self.parseStockStatus(extracted['availability'])

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

    async def _setupBrowser(self):
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


    async def _navigatePage(self, url, wait_selectors=None):
        # Navigate to the page
        await self.page.goto(url, timeout=60000)
        
        await self.page.wait_for_load_state('domcontentloaded')
        
        # Wait for critical selectors if specified
        if wait_selectors:
            for selector in wait_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                except:
                    pass  # Selector may not exist on this page

    async def _extractData(self, soup, selector_config):
        product_info = {}
        for field, selector in selector_config.items():
            item = None
            
            # Handle special case: find element by text content
            if 'find_by_text' in selector:
                tag, text = selector['find_by_text']
                for element in soup.find_all(tag):
                    if text in element.get_text():
                        item = element.find_next(selector.get('then_next'))
                        break
            else:
                # Use CSS selector
                css_selector = selector.get('selector')
                if css_selector:
                    item = soup.select_one(css_selector)
            
            # Extract text based on extraction method
            if item:
                if selector.get('direct_text'):
                    # Get only the direct text (first child text node)
                    text = item.contents[0].strip() if item.contents else None
                    # Remove non-breaking spaces
                    text = text.replace('\u00a0', ' ') if text else None
                else:
                    text = item.get_text(strip=True)

                if selector.get('preserve_semantics'):
                    h = html2text.HTML2Text()
                    h.ignore_links = True
                    h.ignore_images = True
                    text = h.handle(item.decode_contents())
                
                product_info[field] = text
            else:
                product_info[field] = None

        return product_info
    
    async def _rateLimitWait(self):
        await asyncio.sleep(self._wait_time)
    
    def parsePrice(self, raw_text: str):
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

    def parseStockStatus(self, raw_text: str):
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

    def checkResponseStatus(self, status_code: int):
        if 400 <= status_code < 500:
            raise Exception(f"http_error_{status_code}")  # Client error
        elif 500 <= status_code < 600:
            raise Exception(f"http_error_{status_code}")  # Server error