import asyncio
import json
from pipeline.llm_extractor import Extractor
from playwright.async_api import async_playwright


async def get_html(url):
    """Fetches the raw HTML content of the page using Playwright."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"]
            )

            page = await browser.new_page()
            await page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
                    "Referer": "https://www.google.com/",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => false})"
            )
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            try:
                # Wait briefly for main content containers to render
                await page.wait_for_selector(
                    "main, .product-main, .product-info, .col-md-6", timeout=10000
                )
            except Exception as e:
                print(f"Error waiting for main content selectors: {e}")
                pass  # If specific selectors aren't found, just proceed with what we have

            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        print(f"Playwright execution failed: {e}")
        return None


async def test_local_extraction(target_book_title, test_urls):
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"Testing URL: {url}")
        print(f"Target Title: '{target_book_title}'")
        print("=" * 80)

        # 1. Fetch raw HTML
        print("🌐 Fetching HTML...")
        raw_html = await get_html(url)

        if not raw_html:
            print("❌ Failed to retrieve HTML.")
            continue

        # 2. Sanity Check
        if target_book_title.lower() not in raw_html.lower():
            print(
                f"⚠️ Warning: Target title '{target_book_title}' not found in raw HTML payload."
            )

        # 3. Instantiate Extractor and Clean HTML
        extractor = Extractor({})
        print("🧹 Cleaning HTML payload...")
        cleaned_html = extractor.clean_html(raw_html)

        # 4. Prompt Local LLM
        print("🧠 Sending prompt to Local LLM (Qwen 3B)...")
        result = extractor.extract_details(
            cleaned_html, target_book_title, ["price", "stock_status"]
        )

        # 5. Print Results
        if "error" in result and result["error"]:
            print(f"❌ Extraction Error: {result['error']}")
        else:
            # print(f"✅ Extraction Successful!")
            # print(f"  💰 Price:       {result.get('price')}")
            # print(f"  📦 Stock:       {result.get('stock_status')}")
            # print(f"  🆔 ISBN:        {result.get('isbn')}")

            # desc = result.get('description')
            # if desc:
            #     print(f"  📝 Description: {desc[:20]}")
            # else:
            #     print(f"  📝 Description: None")
            for key, value in result.items():
                print(f"  {key.capitalize()}: {value}")


async def test_cloud_extraction(target_book_title, test_urls, cloud_config):

    extractor = Extractor(cloud_config)

    for url in test_urls:
        print("\n" + "=" * 80)
        print(f"☁️ Cloud Testing Selectors for: {url}")
        print("=" * 80)

        raw_html = await get_html(url)
        if not raw_html:
            print("❌ HTML Payload retrieval failed.")
            continue

        print("🧹 Cleaning HTML (Cloud mode: Retaining attributes)...")
        cleaned_html = extractor.clean_html(raw_html)

        print(f"🧠 Prompting OpenRouter Cloud Model ({cloud_config['model_name']})...")
        selectors_config = extractor.extract_selectors(cleaned_html, target_book_title)

        print("\n✅ Generated Selectors Mapping:")
        print(json.dumps(selectors_config, indent=2))


test_urls = [
    # "https://sarasavi.lk/product/the-witcher---the-last-wish-147323106x",
    "https://jumpbooks.lk/product/the-last-wish-reissue-introducing-the-witcher-now-a-major-netflix-show/",
    # "https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5",
    # "https://www.expo-graphic.com/books/The-Witcher---Ehe-Last-Wish-9781399611398/view",
    # "https://mdgunasena.com/product/the-last-wish/"
]

target_book_title = "The Last Wish"

if __name__ == "__main__":
    # asyncio.run(test_cloud_extraction(target_book_title, test_urls, cloud_config))
    asyncio.run(test_local_extraction(target_book_title, test_urls))
