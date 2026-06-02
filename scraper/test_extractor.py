import asyncio


from scraper.pipeline.llm_extractor import Extractor
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup



async def get_html(url):
    try:
        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=False, 
                args=['--disable-blink-features=AutomationControlled'])
            
            page = await browser.new_page()

            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                'Referer': 'https://www.google.com/',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            })
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            
            # Wait for main content, but don't wait forever for tracking scripts
            try:
                await page.wait_for_selector('main, .product-main, .product-info', timeout=10000)
            except:
                pass  # Main content might load differently on some sites

            content = await page.content()
            return content

    except Exception as e:
        print(f"Error loading {url}: {e}")
        return None
    

def test_extractor(url, html):
    """Test the Extractor on a single URL."""
    print(f"\n{'='*80}")
    print(f"Testing: {url}")
    print(f"{'='*80}\n")
    
    extractor = Extractor(url)
    cleaned_html = extractor.clean_html(html)
    
    # Test price classification
    print("🔍 Classifying PRICE node...")
    price_result = extractor.classify_price_node(cleaned_html)
    print(f"  Status: {price_result.get('reason') or 'SUCCESS'}")
    print(f"  Selector: {price_result.get('selector')}")
    print(f"  Answer: {price_result.get('answer')}")
    print(f"  Confidence: {price_result.get('confidence'):.2f}\n")
    
    # Test stock classification
    print("🔍 Classifying STOCK node...")
    stock_result = extractor.classify_stock_node(cleaned_html)
    print(f"  Status: {stock_result.get('reason') or 'SUCCESS'}")
    print(f"  Selector: {stock_result.get('selector')}")
    print(f"  Answer: {stock_result.get('answer')}")
    print(f"  Confidence: {stock_result.get('confidence'):.2f}\n")
    
    # Validate selectors work on the HTML
    print("✅ Validating selectors...")
    if price_result.get('selector'):
        try:
            price_elem = cleaned_html.select_one(price_result['selector'])
            if price_elem:
                print(f"  Price selector WORKS: {price_elem.get_text(strip=True)[:50]}")
            else:
                print(f"  Price selector FAILED: No element found")
        except Exception as e:
            print(f"  Price selector ERROR: {e}")
    
    if stock_result.get('selector'):
        try:
            stock_elem = cleaned_html.select_one(stock_result['selector'])
            if stock_elem:
                print(f"  Stock selector WORKS: {stock_elem.get_text(strip=True)[:50]}")
            else:
                print(f"  Stock selector FAILED: No element found")
        except Exception as e:
            print(f"  Stock selector ERROR: {e}")

async def main():
    urls = [
        # "https://sarasavi.lk/product/the-witcher---the-last-wish-147323106x",
        # "https://jumpbooks.lk/product/the-last-wish-reissue-introducing-the-witcher-now-a-major-netflix-show/",
        # "https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5",
        # "https://www.expo-graphic.com/books/The-Witcher---Ehe-Last-Wish-9781399611398/view",
        # "https://books.lk/product/the-last-wish-the-witcher/",
        # "https://mdgunasena.com/product/the-last-wish/",
        
            ]
    for url in urls:
        html = await get_html(url)
        if html:
            test_extractor(url, html)

if __name__ == "__main__":
    asyncio.run(main())