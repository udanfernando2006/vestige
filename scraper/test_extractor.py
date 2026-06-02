import asyncio
import html2text

from pipeline.llm_extractor import Extractor
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
            await browser.close()
            return content

    except Exception as e:
        print(f"Error loading {url}: {e}")
        return None
    

def extract_clean_value(soup, selector: str, field_name: str) -> str:
    """
    Safely executes a CSS selector against the DOM tree. 
    Converts complex content domains like description blocks into clean, 
    structured Markdown, while maintaining neat string formats for inline tags.
    """
    if not selector:
        return None
        
    element = soup.select_one(selector)
    if not element:
        return None
        
    # If dealing with complex structural blocks, use html2text to preserve Markdown formatting
    if field_name.lower() in ["description", "product status / availability"]:
        converter = html2text.HTML2Text()
        
        # --- Configure Converter Options ---
        converter.ignore_links = False         # Keep links if they occur in description blocks
        converter.ignore_emphasis = False      # Keep bold (** text **) and italics (* text *)
        converter.ignore_images = True         # Drop layout tracker images/tracking pixels
        converter.body_width = 0               # Prevent wrapping text at an arbitrary line break width
        
        # Turn the element back into raw HTML string and convert it
        markdown_text = converter.handle(str(element))
        return markdown_text.strip()
        
    # Standard fallback for clean flat properties (Title, Price, ISBN)
    return element.get_text(strip=True)

async def main():
    urls = [
        # "https://sarasavi.lk/product/the-witcher---the-last-wish-147323106x",
        "https://jumpbooks.lk/product/the-last-wish-reissue-introducing-the-witcher-now-a-major-netflix-show/",
        # "https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5",
        # "https://www.expo-graphic.com/books/The-Witcher---Ehe-Last-Wish-9781399611398/view",
        # "https://books.lk/product/the-last-wish-the-witcher/",
        # "https://mdgunasena.com/product/the-last-wish/",
        
            ]
    
    target_fields = ["title", "price", "stock status / availability", "description", "isbn"]

    for url in urls:
        print("\n" + "="*80)
        print(f"Testing: {url}")
        print("="*80)
        
        raw_html = await get_html(url)
        if not raw_html:
            print("❌ Exiting: HTML Payload content empty.")
            continue
            
        extractor = Extractor(url)
        cleaned_html = extractor.clean_html(raw_html)
        
        for field in target_fields:
            print(f"🔍 Asking LLM for direct structure selector: '{field.upper()}'...")
            
            # The LLM looks at the unparsed context hierarchy natively
            res = extractor.query_selector_from_html(cleaned_html, field)
            
            status = res["status"]
            selector = res["selector"]
            confidence = res["confidence"]
            reason = res["reason"]
            
            print(f"  Status: {status}")
            print(f"  Selector: {selector}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Technical Logic: {reason}")
            
            # Verification Step using our structural formatting helper
            if selector:
                try:
                    extracted_text = extract_clean_value(cleaned_html, selector, field)
                    if extracted_text:
                        print(f"  ✅ Verification Works: '{extracted_text[:90]}...'")
                    else:
                        print(f"  ❌ Verification Failed: Element found but text values returned empty.")
                except Exception as e:
                    print(f"  ❌ Verification Selector Error: {e}")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())