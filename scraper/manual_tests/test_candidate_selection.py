import asyncio
from pipeline.crawler import Crawler
from urllib.parse import urlparse


async def test_candidate_selection():
    crawler = Crawler(headless=False)

    stores = [
        ("https://sarasavi.lk/", "sarasavi"),
        ("https://jumpbooks.lk/", "jumpbooks"),
        ("https://jeyabookcentre.com/", "jeyabookcentre"),
        ("https://www.expo-graphic.com/", "expo-graphic"),
        ("https://bookswap.lk/", "bookswap"),
        ("https://books.lk/", "books.lk"),
        ("https://mdgunasena.com/", "mdgunasena"),
    ]

    book_title = "The Last Wish"

    for base_url, store_name in stores:
        print(f"\n{'='*70}")
        print(f"STORE: {store_name.upper()}")
        print("=" * 70)

        # 1. Discover search endpoint
        print("\n[1] Discovering search endpoint...")
        discovery = await crawler.discover_search_endpoint(base_url)

        if not discovery["success"]:
            print(f"Failed: {discovery['error']}")
            continue

        test_url = discovery["final_url"]
        print(f"    Found: {test_url}")

        # 2. Build search URL with actual query
        print(f"\n[2] Building search URL for '{book_title}'...")
        search_url = crawler.build_search_url(test_url, book_title)
        print(f"    URL: {search_url}")

        # 3. Fetch search results
        print("\n[3] Fetching search results...")
        html = await crawler.fetch_search_results(search_url)
        if html:
            print(f"    Got {len(html)} bytes of HTML")
        else:
            print("    Failed to fetch")
            continue

        # 4. Extract candidate links
        print("\n[4] Extracting candidate links...")
        links = crawler.extract_candidate_links(html)
        print(f"    Found {len(links)} total links")

        # 5. Score candidates
        print("\n[5] Scoring candidates by title match...")
        parsed = urlparse(base_url)
        base_url_normalized = f"{parsed.scheme}://{parsed.netloc}"

        candidates = crawler.score_candidates(
            links, isbn=None, title=book_title, base_url=base_url_normalized
        )
        print(f"    Matched {len(candidates)} candidates\n")

        # 6. Display candidates for user selection
        if candidates:
            print("    CANDIDATES (sorted by match quality):")
            print("    " + "-" * 66)
            for i, candidate in enumerate(candidates, 1):
                print(
                    f"    [{i}] Score: {candidate['match_score']} | Text: {candidate['text'][:50]}"
                )
                print(f"        URL: {candidate['url']}")
                print()
        else:
            print("    No matching candidates found!")


if __name__ == "__main__":
    asyncio.run(test_candidate_selection())
