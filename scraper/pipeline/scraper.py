import asyncio

from bs4 import BeautifulSoup
import requests
import asyncio
from playwright.async_api import async_playwright
import json

def scrapePage(url, selectors, headless, wait_time: int = 5) -> dict:
    async def scrape():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless,
                args=['--disable-blink-features=AutomationControlled'])
            page = await browser.new_page()
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.google.com/',
            })
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")

            await asyncio.sleep(wait_time)

            # Navigate to the page
            await page.goto(url, timeout=60000)
            
            # Wait for content to load (wait for all JS to finish rendering)
            await page.wait_for_load_state('networkidle')
            
            # # Wait for price to be populated with actual value
            # await page.wait_for_function("() => document.querySelector('span.woocommerce-Price-amount').innerText.trim().length > 0")
            
            # Extract data
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')

            product_info = {}
            for field, selector in selectors.items():
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
                
            await browser.close()

            return product_info

    return asyncio.run(scrape())

if __name__ == "__main__":
    selectors = {
        'title': {
            'selector': 'h1.text-3xl.font-bold.text-gray-900.mb-2'
        },
        'price': {
            'selector': 'span.text-xl.font-bold.text-gray-900',
            'direct_text': True
        },
        'availability': {
            'selector': 'span.text-sm.text-green-600.font-semibold'
        },
        'isbn': {
            'find_by_text': ('dt', 'ISBN'),
            'then_next': 'dd'
        },
        'description': {
            'selector': 'div.text-gray-700'
        }
    }
    
    result = scrapePage(
        'https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5',
        selectors,
        True
    )
    print(json.dumps(result, indent=2))

# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# }
# html_text = requests.get('https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5', headers=headers)

# # Check if request was successful
# if html_text.status_code != 200:
#     print(f"Error: Got status code {html_text.status_code}")
# else:
#     soup = BeautifulSoup(html_text.text, 'lxml')
#     price = soup.find('span', class_='text-xl font-bold text-gray-900')
    
#     if price:
#         # Get only the current price (first direct text, ignore nested spans)
#         current_price = str(price.contents[0]).strip()
#         print(current_price)
#     else:
#         print("Price element not found")
