import asyncio

from browser.session import BrowserSession
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup


class Crawler:

    def __init__(self, headless: bool = True, timeout: int = 60000):
        self._headless = headless
        self.timeout = timeout

    async def find_product_url(
        self, urls: dict, title: str, isbn: str = None, session=None
    ):
        if session and urls.get("search_url_template"):
            return await self._run_with_session(session, urls, title, isbn)
        else:
            return await self._run_discovery(urls["base_url"], title, isbn)

    async def _run_with_session(
        self, session: BrowserSession, urls: dict, title: str, isbn: str = None
    ) -> dict:
        # search_url_template comes from the store record — built here once DB exists
        # e.g. "https://jumpbooks.lk/?s={query}" → replace {query} with isbn or title
        query = isbn if isbn else title
        search_url = self._build_search_url(urls["search_url_template"], query)

        await session.navigate(search_url)
        html = await session.get_html()
        candidates = self._extract_candidate_links(html)
        scored = self._score_candidates(candidates, isbn, title, urls["base_url"])
        if not scored:
            return {"success": False, "product_url": None, "status": "NOT_LISTED"}
        result = await self._validate_candidates(session, scored, title, isbn)
        if result["success"]:
            result["search_url_template"] = urls["search_url_template"]
        return result

    async def _run_discovery(self, base_url: str, title: str, isbn: str):

        config = {"headless": self._headless, "timeout": self.timeout}

        # Step 1: discover the search URL pattern
        async with BrowserSession(config) as discovery_session:
            await discovery_session.navigate(base_url, wait_until="domcontentloaded")
            filled = await discovery_session.find_and_fill_search("test")
            if not filled:
                return {"success": False, "error": "No search form found"}

            search_url_template = await discovery_session.get_url()

        # Step 2: build the real search URL and fetch results
        async with BrowserSession(config) as search_session:
            query = isbn if isbn else title
            actual_search_url = self._build_search_url(search_url_template, query)
            print("Navigating to search URL:", actual_search_url)
            await search_session.navigate(actual_search_url)
            html = await search_session.get_html()

            # Step 3: score candidates from search results
            candidates = self._extract_candidate_links(html)
            scored = self._score_candidates(candidates, isbn, title, base_url)
            if not scored:
                return {"success": False, "product_url": None, "status": "NOT_LISTED"}
            else:
                result = await self._validate_candidates(
                    search_session, scored, title, isbn
                )
                if result["success"]:
                    result["search_url_template"] = search_url_template
                return result

    def _validate_from_html(
        self, html: str, url: str, title: str, isbn: str = None
    ) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text().lower()
        title_lower = title.lower()

        score = 0
        findings = {}

        title_found = title_lower in text
        if title_found:
            score += 3
        findings["title_found"] = title_found

        isbn_found = bool(isbn and isbn in text)
        if isbn_found:
            score += 2
        findings["isbn_found"] = isbn_found

        has_availability = any(
            w in text
            for w in ["available", "in stock", "shipping", "stock", "qty", "quantity"]
        )
        if has_availability:
            score += 2
        findings["has_availability"] = has_availability

        has_content = len(soup.find_all(["p", "div", "span", "article"])) > 10
        if has_content:
            score += 2
        findings["has_content"] = has_content

        is_cart_page = (
            "/cart" in url.lower()
            or "/shopping" in url.lower()
            or any(
                p in text
                for p in [
                    "items in cart",
                    "cart subtotal",
                    "your cart is empty",
                    "checkout now",
                ]
            )
        )
        if is_cart_page:
            score -= 5
        findings["is_cart_page"] = is_cart_page

        if any(p in text for p in ["not found", "404", "page not found"]):
            score = -99
            findings["is_error_page"] = True
        else:
            findings["is_error_page"] = False

        return {
            "url": url,
            "validation_score": max(score, 0),
            "valid": score >= 3,
            "findings": findings,
        }

    async def _validate_candidates(
        self,
        session: BrowserSession,
        scored: list,
        title: str,
        isbn: str = None,
        depth: int = 3,
    ) -> dict:
        for candidate in scored[:depth]:
            await session.navigate(candidate["url"])
            html = await session.get_html()
            validation = self._validate_from_html(html, candidate["url"], title, isbn)
            if validation["valid"]:
                return {
                    "success": True,
                    "product_url": candidate["url"],
                    "confidence": round(validation["validation_score"] / 9, 2),
                }
        return {"success": False, "product_url": None, "status": "NOT_LISTED"}

    def _build_search_url(self, base_url, query):
        """Replace 'test' query with actual query (URL-encoded)."""
        actual_url = base_url.replace("=test", f"={quote_plus(query)}")
        return actual_url

    def _extract_candidate_links(self, html):
        """Extract all product links (hrefs) from search results HTML."""
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        links = soup.find_all("a", href=True)

        candidates = []
        for link in links:
            href = link["href"]
            text = link.get_text(strip=True)

            candidates.append(
                {
                    "href": href,
                    "text": text,
                    "url": None,  # Will be populated by urljoin in score_candidates
                }
            )
        return candidates

    def _score_candidates(self, links, isbn, title, base_url):
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
            href_lower = link["href"].lower()
            text_lower = link["text"].lower()

            # Count how many title keywords appear in href or text
            keyword_matches = sum(
                keyword in href_lower or keyword in text_lower for keyword in keywords
            )

            # Must have at least 1 keyword in text OR 2+ total
            if keyword_matches == 0:
                continue
            if keyword_matches == 1 and not any(
                keyword in text_lower for keyword in keywords
            ):
                continue

            # EXCLUDE: Social media links
            if any(
                domain in href_lower
                for domain in [
                    "facebook.com",
                    "twitter.com",
                    "linkedin.com",
                    "pinterest.com",
                    "telegram.me",
                    "instagram.com",
                ]
            ):
                continue

            # EXCLUDE: Tag/category pages, pagination, search results (not product pages)
            if any(
                pattern in href_lower
                for pattern in [
                    "/product-tag/",
                    "/tag/",
                    "/category/",
                    "search",
                    "/page/",
                ]
            ):
                continue

            # Normalize to absolute URL
            absolute_url = urljoin(base_url, link["href"])
            score = keyword_matches

            # +10: Likely a product page (has /product/, /item/, /p/, /book/, /BookDetail/ in path)
            if any(
                pattern in href_lower
                for pattern in ["/product/", "/item/", "/p/", "/book/", "/bookdetail"]
            ):
                score += 10

            # -5: Likely just a filter/navigation link (pure query params, no path change)
            elif "?" in link["href"] and not any(
                pattern in href_lower
                for pattern in ["/product/", "/item/", "/p/", "/book/", "/bookdetail"]
            ):
                score -= 5

            # +5: ISBN in URL (if provided)
            if isbn and isbn in href_lower:
                score += 5

            link["match_score"] = score
            link["url"] = absolute_url
            scored.append(link)

        # Sort by match score (descending)
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored
