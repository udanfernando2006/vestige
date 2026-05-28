from bs4 import BeautifulSoup
import requests
import asyncio
from playwright.async_api import async_playwright
import json


class Scraper:
    def __init__(self, headless: bool = True, wait_time: int = 5):
        self._headless = headless
        self._wait_time = wait_time

    async def scrape(self, url, selectors) -> dict:
        async with async_playwright() as self.p:
            await self._setupBrowser()
            await asyncio.sleep(self._wait_time)
            await self._navigatePage(url)
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            result = await self._extractData(soup, selectors)
            await self.browser.close()
            return result

    async def _setupBrowser(self):
        self.browser = await self.p.chromium.launch(headless=self._headless,
            args=['--disable-blink-features=AutomationControlled'])
        self.page = await self.browser.new_page()
        
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Referer': 'https://www.google.com/',
        })
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")


    async def _navigatePage(self, url):
        # Navigate to the page
        await self.page.goto(url, timeout=60000)
        
        # Wait for content to load (wait for all JS to finish rendering)
        await self.page.wait_for_load_state('networkidle')

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
                    product_info[field] = text.replace('\u00a0', ' ') if text else None
                else:
                    product_info[field] = item.get_text(strip=True)
            else:
                product_info[field] = None

        return product_info

# def scrapePage(url, selectors, headless, wait_time: int = 5) -> dict:
#     async def scrape():
#         async with async_playwright() as p:
#             browser = await p.chromium.launch(headless=headless,
#                 args=['--disable-blink-features=AutomationControlled'])
#             page = await browser.new_page()
            
#             await page.set_extra_http_headers({
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
#                 'Referer': 'https://www.google.com/',
#             })
#             await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")

#             await asyncio.sleep(wait_time)

#             # Navigate to the page
#             await page.goto(url, timeout=60000)
            
#             # Wait for content to load (wait for all JS to finish rendering)
#             await page.wait_for_load_state('networkidle')
            
#             # # Wait for price to be populated with actual value
#             # await page.wait_for_function("() => document.querySelector('span.woocommerce-Price-amount').innerText.trim().length > 0")
            
#             # Extract data
#             content = await page.content()
#             soup = BeautifulSoup(content, 'lxml')

#             product_info = {}
#             for field, selector in selectors.items():
#                 item = None
                
#                 # Handle special case: find element by text content
#                 if 'find_by_text' in selector:
#                     tag, text = selector['find_by_text']
#                     for element in soup.find_all(tag):
#                         if text in element.get_text():
#                             item = element.find_next(selector.get('then_next'))
#                             break
#                 else:
#                     # Use CSS selector
#                     css_selector = selector.get('selector')
#                     if css_selector:
#                         item = soup.select_one(css_selector)
                
#                 # Extract text based on extraction method
#                 if item:
#                     if selector.get('direct_text'):
#                         # Get only the direct text (first child text node)
#                         text = item.contents[0].strip() if item.contents else None
#                         # Remove non-breaking spaces
#                         product_info[field] = text.replace('\u00a0', ' ') if text else None
#                     else:
#                         product_info[field] = item.get_text(strip=True)
#                 else:
#                     product_info[field] = None
                
#             await browser.close()

#             return product_info

#     return asyncio.run(scrape())

# if __name__ == "__main__":
#     selectors = {
#         'title': {
#             'selector': 'h1.text-3xl.font-bold.text-gray-900.mb-2'
#         },
#         'price': {
#             'selector': 'span.text-xl.font-bold.text-gray-900',
#             'direct_text': True
#         },
#         'availability': {
#             'selector': 'span.text-sm.text-green-600.font-semibold'
#         },
#         'isbn': {
#             'find_by_text': ('dt', 'ISBN'),
#             'then_next': 'dd'
#         },
#         'description': {
#             'selector': 'div.text-gray-700'
#         }
#     }
    
#     result = scrapePage(
#         'https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5',
#         selectors,
#         True
#     )
#     print(json.dumps(result, indent=2))

