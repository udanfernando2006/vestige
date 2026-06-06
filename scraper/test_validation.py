import asyncio
from pipeline.crawler import Crawler

async def test_validate_candidates():
    """
    Demonstrate the validation workflow:
    1. Get candidates from crawler
    2. User picks one
    3. Validate it before passing to NLP
    """
    crawler = Crawler(headless=False)
    
    # Test data
    test_url = "https://sarasavi.lk/"
    book_title = "The Last Wish"
    
    print(f"Testing: {book_title}")
    print("="*70)
    
    # Step 1: Get candidates (existing flow)
    print("\n[1] Discovering search endpoint...")
    discovery = await crawler.discover_search_endpoint(test_url)
    
    if not discovery['success']:
        print(f"Failed: {discovery['error']}")
        return
    
    test_url = discovery['final_url']
    search_url = crawler.build_search_url(test_url, book_title)
    
    print(f"[2] Fetching search results for '{book_title}'...")
    html = await crawler.fetch_search_results(search_url)
    
    if not html:
        print("Failed to fetch")
        return
    
    links = crawler.extract_candidate_links(html)
    from urllib.parse import urlparse
    parsed = urlparse(test_url)
    base_url_normalized = f"{parsed.scheme}://{parsed.netloc}"
    
    candidates = crawler.score_candidates(links, isbn=None, title=book_title, base_url=base_url_normalized)
    
    print(f"\n[3] Got {len(candidates)} candidates\n")
    
    # Show top 3 candidates
    for i, candidate in enumerate(candidates[:3], 1):
        print(f"    [{i}] {candidate['url']}")
    
    # Step 2: User picks one (simulate: pick first)
    picked_candidate = candidates[0]
    print(f"\n[4] User selected candidate [1]")
    print(f"    URL: {picked_candidate['url']}")
    
    # Step 3: Validate before passing to NLP
    print(f"\n[5] Validating product page...")
    validation = await crawler.validate_product_page(
        picked_candidate['url'],
        title=book_title,
        isbn=None
    )
    
    print(f"\n    Validation Score: {validation['validation_score']}/10")
    print(f"    Valid: {validation['valid']}")
    print(f"    Findings:")
    for key, value in validation['findings'].items():
        print(f"      - {key}: {value}")
    
    if validation['valid']:
        print("\n    ✅ VALID - Ready to pass to NLP Extractor")
    else:
        print("\n    ❌ INVALID - Ask user to pick another candidate")

if __name__ == "__main__":
    asyncio.run(test_validate_candidates())
