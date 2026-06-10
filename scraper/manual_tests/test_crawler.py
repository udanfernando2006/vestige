import asyncio
from pipeline.crawler import Crawler


async def test_discover_search_endpoints():
    crawler = Crawler(headless=False, timeout=60000)  # headless=False to watch it work

    stores = [
        # "https://sarasavi.lk/",
        # "https://jumpbooks.lk/",
        # "https://jeyabookcentre.com/"
    ]

    title = "The Last Wish"

    for base_url in stores:
        print(f"\n{'='*60}")
        print(f"Testing: {base_url}")
        print("=" * 60)

        result = await crawler.find_product_url({"base_url": base_url}, title)

        print(f"Success: {result.get('success')}")
        print(f"Product URL: {result.get('product_url')}")
        print(f"Confidence: {result.get('confidence')}")
        print(f"Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_discover_search_endpoints())
