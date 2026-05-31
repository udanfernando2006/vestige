import asyncio
from pipeline.crawler import Crawler

async def test_discover_search_endpoints():
    crawler = Crawler(headless=False)  # headless=False to watch it work
    
    stores = [
        "https://sarasavi.lk/",
        "https://jumpbooks.lk/",
        "https://jeyabookcentre.com/"
    ]
    
    for base_url in stores:
        print(f"\n{'='*60}")
        print(f"Testing: {base_url}")
        print('='*60)
        
        result = await crawler.discover_search_endpoint(base_url)
        
        print(f"Success: {result.get('success')}")
        print(f"Endpoint: {result.get('endpoint')}")
        print(f"Param Name: {result.get('param_name')}")
        print(f"Other Params: {result.get('other_params')}")
        print(f"Best URL: {result.get('best_url')}")
        print(f"All URLs:")
        for url in result.get('all_urls', []):
            print(f"  - {url}")
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_discover_search_endpoints())