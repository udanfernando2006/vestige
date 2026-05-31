import asyncio


from playwright.async_api import async_playwright
from urllib.parse import quote_plus, urlparse, parse_qs, urljoin
from bs4 import BeautifulSoup

class Crawler:

    def __init__(self, headless: bool = True, timeout: int = 60000):
        self._headless = headless
        self.timeout = timeout

    async def discover_search_endpoint(self, base_url: str, query: str = "test"):
        """
        Discover the search endpoint by submitting a search form and reading page.url.
        
        Returns ALL query parameters, not just one.
        """
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
                await page.goto(base_url, timeout=self.timeout)
                await page.wait_for_load_state('domcontentloaded')

                form = await page.query_selector('form')
                if form:
                    text_input = await form.query_selector('input[type="text"], input[type="search"]')
                    if text_input:
                        initial_url = page.url    

                        await text_input.fill(query)
                        await text_input.press('Enter')

                        # Wait until all network activity completes (SPA update)
                        await page.wait_for_load_state('networkidle', timeout=self.timeout)

                        # NOW read the page state (what the user sees in browser)
                        final_url = page.url
                        
                        # Parse final_url to get endpoint + ALL params
                        parsed = urlparse(final_url)
                        param_names = list(parse_qs(parsed.query).keys())
                        
                        return {
                            "endpoint": parsed.path,
                            "param_names": param_names,  # ALL parameters, not just first one
                            "initial_url": initial_url,
                            "final_url": final_url,
                            "success": True
                        }
                
                return {"success": False, "error": "No search form found"}

        except Exception as e:
            print(f"Error discovering search endpoint for {base_url}: {e}")
            return {"success": False, "error": str(e)}

    def build_search_url(self, base_url, query):
        """Replace 'test' query with actual query (URL-encoded)."""
        actual_url = base_url.replace('=test', f'={quote_plus(query)}')
        return actual_url

    async def fetch_search_results(self, search_url):
        """Navigate to search URL and return HTML."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless,
                    args=['--disable-blink-features=AutomationControlled'])
                page = await browser.new_page()
                
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                    'Accept-Language': 'en-US,en;q=0.9',
                })
                
                await page.goto(search_url, timeout=60000)
                await page.wait_for_load_state('networkidle', timeout=self.timeout)
                
                html = await page.content()
                await browser.close()
                
                return html
        except Exception as e:
            print(f"Error fetching search results: {e}")
            return None

    def extract_candidate_links(self, html):
        """Extract all product links (hrefs) from search results HTML."""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        links = soup.find_all('a', href=True)
        
        candidates = []
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            
            candidates.append({
                'href': href,
                'text': text,
                'url': None  # Will be populated by urljoin in score_candidates
            })
        
        return candidates

    def score_candidates(self, links, isbn, title, base_url):
        """
        Score and filter candidates by matching title keywords in href/text.
        Prioritizes actual product pages over filter/navigation links.
        Normalizes relative URLs to absolute.
        Returns sorted list with normalized URLs.
        """
        scored = []
        title_lower = title.lower()
        keywords = title_lower.split()
        
        for link in links:
            href_lower = link['href'].lower()
            text_lower = link['text'].lower()
            
            # Count how many title keywords appear in href or text
            keyword_matches = sum(
                keyword in href_lower or keyword in text_lower 
                for keyword in keywords
            )
            
            # Must have at least 1 keyword in text OR 2+ total
            if keyword_matches == 0:
                continue
            if keyword_matches == 1 and not any(keyword in text_lower for keyword in keywords):
                continue
            
            # EXCLUDE: Social media links
            if any(domain in href_lower for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'pinterest.com', 'telegram.me', 'instagram.com']):
                continue
            
            # EXCLUDE: Tag/category pages, pagination, search results (not product pages)
            if any(pattern in href_lower for pattern in ['/product-tag/', '/tag/', '/category/', 'search', '/page/']):
                continue
            
            # Normalize to absolute URL
            absolute_url = urljoin(base_url, link['href'])
            score = keyword_matches
            
            # +10: Likely a product page (has /product/, /item/, /p/, /book/, /BookDetail/ in path)
            if any(pattern in href_lower for pattern in ['/product/', '/item/', '/p/', '/book/', '/bookdetail']):
                score += 10
            
            # -5: Likely just a filter/navigation link (pure query params, no path change)
            elif '?' in link['href'] and not any(pattern in href_lower for pattern in ['/product/', '/item/', '/p/', '/book/', '/bookdetail']):
                score -= 5
            
            # +5: ISBN in URL (if provided)
            if isbn and isbn in href_lower:
                score += 5
            
            link['match_score'] = score
            link['url'] = absolute_url
            scored.append(link)
        
        # Sort by match score (descending)
        scored.sort(key=lambda x: x['match_score'], reverse=True)
        return scored

    async def validate_product_page(self, url, title, isbn=None):
        """
        Corroborate that URL is actually the product page for the target book.
        Check for title, description, ISBN, availability presence.
        Returns validation details and relevance score (0-10).
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless,
                    args=['--disable-blink-features=AutomationControlled'])
                page = await browser.new_page()
                
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                    'Accept-Language': 'en-US,en;q=0.9',
                })
                
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')
                
                # Get page text
                text = soup.get_text().lower()
                title_lower = title.lower()
                
                score = 0
                findings = {}
                
                # +3: Title present on page
                title_found = title_lower in text
                if title_found:
                    score += 3
                findings['title_found'] = title_found
                
                # +2: ISBN present (if provided)
                isbn_found = isbn and isbn in text if isbn else None
                if isbn_found:
                    score += 2
                findings['isbn_found'] = isbn_found
                
                # +2: Availability keywords
                has_availability = any(word in text for word in ['available', 'in stock', 'shipping', 'stock', 'qty', 'quantity'])
                if has_availability:
                    score += 2
                findings['has_availability'] = has_availability
                
                # +2: Description indicators (content-rich page)
                content_elements = soup.find_all(['p', 'div', 'span', 'article'])
                has_content = len(content_elements) > 10
                if has_content:
                    score += 2
                findings['has_content'] = has_content
                
                # -5: Actual cart page indicators (not just "add to cart" button)
                is_cart_page = (
                    '/cart' in url.lower() or 
                    '/shopping' in url.lower() or 
                    any(phrase in text for phrase in ['items in cart', 'cart subtotal', 'your cart is empty', 'checkout now'])
                )
                if is_cart_page:
                    score -= 5
                findings['is_cart_page'] = is_cart_page
                
                # -3: Error page indicators
                if any(phrase in text for phrase in ['not found', '404', 'page not found', 'error']):
                    score = -99
                    findings['is_error_page'] = True
                else:
                    findings['is_error_page'] = False
                
                await browser.close()
                
                return {
                    'url': url,
                    'validation_score': max(score, 0),
                    'valid': score >= 3,
                    'findings': findings
                }
        
        except Exception as e:
            print(f"Error validating product page {url}: {e}")
            return {
                'url': url,
                'validation_score': 0,
                'valid': False,
                'error': str(e),
                'findings': {}
            }

    def mark_not_listed(self, pair_id):
        pass