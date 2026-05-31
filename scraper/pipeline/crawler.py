import asyncio


from playwright.async_api import async_playwright
from urllib.parse import urlparse, parse_qs

class Crawler:

    def __init__(self, headless: bool = True):
        self._headless = headless

    async def discover_search_endpoint(self, base_url, query: str = "test"):
        try:
            async with async_playwright() as p:

                browser = await p.chromium.launch(headless=self._headless, 
                    args=['--disable-blink-features=AutomationControlled'])
                
                page = await browser.new_page()
        
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                    'Referer': 'https://www.google.com/',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                })
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
                await page.goto(base_url, timeout=60000)
                await page.wait_for_load_state('domcontentloaded')

                captured_requests = []

                def capture_request(request):
                    captured_requests.append(request)

                # forms = await page.query_selector_all('form')
                results = []  # Initialize as list, not dict
                
                page.on('request', capture_request)
                form = await page.query_selector('form')
                if form:
                # for form in forms:
                    text_input = await form.query_selector('input[type="text"], input[type="search"]')
                    if text_input:
                        await text_input.fill(query)

                        await form.evaluate("(form) => form.submit()")

                        # Wait for search response (hybrid approach)
                        await self._wait_for_search_response(page, query)

                        # Score each captured request
                        for request in captured_requests:
                            score = self.score_request(request, query)
                            results.append((score, request))

                        # Clear for next form
                        captured_requests.clear()

                await browser.close()
    
                if results:
                    best_request = max(results, key=lambda x: x[0])[1]
                    
                    # Parse the URL to extract endpoint and param_name
                    parsed = urlparse(best_request.url)
                    endpoint = parsed.path
                    params = parse_qs(parsed.query)  # {"s": ["test"], "post_type": ["product"]}

                    search_param_name = None
                    for param_name, values in params.items():
                        if query in values[0]:
                            search_param_name = param_name
                            break

                    if search_param_name is None:
                        # No param contained the test query
                        # Fallback: use first parameter
                        if params:
                            search_param_name = list(params.keys())[0]
                        else:
                            return {"success": False, "error": "No query parameters found"}
                    
                    # Store other params (filter out the search parameter)
                    other_params = {k: v[0] for k, v in params.items() if k != search_param_name}

                    return {
                        "endpoint": endpoint,
                        "param_name": search_param_name,
                        "other_params": other_params,
                        "success": True,
                        "best_url": best_request.url,
                        "all_urls": [req.url for _, req in results]
                    }
                else:
                    return {"success": False, "error": "No search endpoint found"}

                


        except Exception as e:
            print(f"Error discovering search endpoint for {base_url}: {e}")
            return {"success": False, "error": str(e)}

    async def _wait_for_search_response(self, page, query: str, timeout: int = 3000):
        """
        Wait for a network response that indicates the search was processed.
        Uses hybrid approach: tries to catch response with query, falls back to networkidle.
        
        Args:
            page: Playwright page object
            query: The search query that was submitted
            timeout: Timeout in milliseconds
        """
        try:
            # First, try to wait for a response containing the query
            await page.wait_for_response(
                lambda response: query in response.url if response.url else False,
                timeout=timeout
            )
        except Exception:
            # If that fails, wait for network to become idle
            try:
                await page.wait_for_load_state('networkidle', timeout=timeout)
            except Exception:
                # If even that fails, just continue - requests may have already been captured
                pass

    def build_search_url(self, base_url, query):
        pass
    
    def fetch_search_results(self, search_url):
        pass

    def extract_candidate_links(self, html):
        pass

    def score_candidates(self, links, isbn, title):
        pass

    def validate_product_page(self, url, isbn):
        pass

    def mark_not_listed(self, pair_id):
        pass

    def score_request(self, request, query):
        url = request.url
        resource_type = request.resource_type
        parsed = urlparse(url)
        path = parsed.path          # "/serach-result"
        query_string = parsed.query # "keyword=test"

        # If it's a static asset, return -100 (skip immediately)
        if any(ext in url.lower() for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.map']):
            return -100

        score = 0

        # -100: Eliminate static assets immediately
        if resource_type in ['stylesheet', 'image', 'font', 'media']:
            return -100

        # -5: XHR/fetch requests are less reliable for traditional forms
        if resource_type == 'xhr':
            score -= 5

        # +3: Document navigation is the strongest signal (page load)
        if resource_type == 'document':
            score += 3

        # +10: Query parameter contains the test value
        if query in url:
            score += 10

        # +8: Path is different from homepage (/)
        if path != "/" and path != "":
            score += 8

        # +6: Path contains search-related keywords
        if any(keyword in path.lower() for keyword in ['search', 'results', 'products', 'catalog', 'query']):
            score += 6

        # +4: Has query parameters
        if query_string:
            score += 4

        # -8: Path is identical to homepage
        if path == "/":
            score -= 8

        return score