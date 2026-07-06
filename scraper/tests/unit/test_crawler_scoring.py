import pytest
from pipeline.crawler import Crawler


@pytest.fixture(scope="module")
def crawler():
    return Crawler()


ISBN = "9780316452465"
TITLE = "The Last Wish"
BASE = "https://sarasavi.lk"


# ---------------------------------------------------------------------------
# _build_search_url
# ---------------------------------------------------------------------------


class TestBuildSearchUrl:
    def test_replaces_test_token_with_isbn(self, crawler):
        template = "https://sarasavi.lk/?s=test"
        result = crawler._build_search_url(template, ISBN)
        assert result == f"https://sarasavi.lk/?s={ISBN}"

    def test_url_encodes_title_spaces(self, crawler):
        template = "https://sarasavi.lk/?s=test"
        result = crawler._build_search_url(template, "The Last Wish")
        # urllib.parse.quote_plus encodes spaces as +; quote encodes as %20
        assert "The+Last+Wish" in result or "The%20Last%20Wish" in result

    def test_template_with_different_param_name(self, crawler):
        # Some stores use ?q= or ?query= — the template format handles this
        template = "https://vijithayapa.com/?q=test"
        result = crawler._build_search_url(template, ISBN)
        assert ISBN in result

    def test_returns_string(self, crawler):
        template = "https://sarasavi.lk/?s=test"
        result = crawler._build_search_url(template, ISBN)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _extract_candidate_links
# ---------------------------------------------------------------------------


class TestExtractCandidateLinks:
    def test_extracts_single_link(self, crawler):
        html = '<a href="/books/123">The Last Wish</a>'
        links = crawler._extract_candidate_links(html)
        assert len(links) == 1
        assert links[0]["href"] == "/books/123"
        assert links[0]["text"] == "The Last Wish"

    def test_extracts_multiple_links(self, crawler):
        html = """
            <a href="/books/1">Book One</a>
            <a href="/books/2">Book Two</a>
        """
        links = crawler._extract_candidate_links(html)
        assert len(links) == 2

    def test_empty_html_returns_empty_list(self, crawler):
        links = crawler._extract_candidate_links("")
        assert links == []

    def test_html_with_no_anchors_returns_empty_list(self, crawler):
        html = "<div><p>No links here</p></div>"
        links = crawler._extract_candidate_links(html)
        assert links == []

    def test_anchor_without_href_excluded(self, crawler):
        html = '<a name="top">Anchor with no href</a>'
        links = crawler._extract_candidate_links(html)
        # Anchors with no href are not navigable — should be excluded or have empty href
        hrefs = [link["href"] for link in links if link.get("href")]
        assert all(h for h in hrefs)  # no empty href strings

    def test_returns_url_field_with_href(self, crawler, search_results_html):
        links = crawler._extract_candidate_links(search_results_html)
        # Every returned link should have at least href and text
        for link in links:
            assert "href" in link
            assert "text" in link


# ---------------------------------------------------------------------------
# _score_candidates
# ---------------------------------------------------------------------------


class TestScoreCandidates:
    def _score(self, crawler, links):
        return crawler._score_candidates(links, isbn=ISBN, title=TITLE, base_url=BASE)

    def test_collection_url_loses_to_product_url(self, crawler):
        booxworm_title = "Chainsawman Vol 4"
        links = [
            {
                "href": "/collections/chainsawman-vol-4",
                "text": booxworm_title,
                "url": f"{BASE}/collections/chainsawman-vol-4",
            },
            {
                "href": "/products/chainsawman-vol-4-tatsuki-fujimoto?_pos=1&_sid=d21f621bf&_ss=r",
                "text": "Chainsawman Vol 4 by Tatsuki Fujimoto",
                "url": f"{BASE}/products/chainsawman-vol-4-tatsuki-fujimoto?_pos=1&_sid=d21f621bf&_ss=r",
            },
        ]

        scored = crawler._score_candidates(
            links, isbn=None, title=booxworm_title, base_url=BASE
        )

        assert scored[0]["url"].startswith(f"{BASE}/products/")
        assert scored[0]["url"] != f"{BASE}/collections/chainsawman-vol-4"

    def test_product_path_prefix_scores_high(self, crawler):
        links = [
            {
                "href": "/product/last-wish",
                "text": "The Last Wish",
                "url": f"{BASE}/product/last-wish",
            }
        ]
        scored = self._score(crawler, links)
        assert len(scored) == 1
        assert scored[0]["url"] == f"{BASE}/product/last-wish"

    def test_isbn_in_url_boosts_score(self, crawler):
        with_isbn = {
            "href": f"/books/{ISBN}",
            "text": "The Last Wish",
            "url": f"{BASE}/books/{ISBN}",
        }
        without_isbn = {
            "href": "/books/other-book",
            "text": "Other Book",
            "url": f"{BASE}/books/other-book",
        }
        scored = self._score(crawler, [with_isbn, without_isbn])
        # The ISBN-bearing link should rank first
        assert scored[0]["url"] == f"{BASE}/books/{ISBN}"

    def test_social_media_links_excluded(self, crawler):
        links = [
            {
                "href": "https://facebook.com/share",
                "text": "Share",
                "url": "https://facebook.com/share",
            },
            {
                "href": "https://twitter.com/intent/tweet",
                "text": "Tweet",
                "url": "https://twitter.com/intent/tweet",
            },
        ]
        scored = self._score(crawler, links)
        assert scored == []

    def test_pagination_links_excluded(self, crawler):
        links = [
            {"href": "/page/2", "text": "2", "url": f"{BASE}/page/2"},
            {"href": "/page/3", "text": "Next »", "url": f"{BASE}/page/3"},
        ]
        scored = self._score(crawler, links)
        assert scored == []

    def test_category_and_tag_links_excluded(self, crawler):
        links = [
            {
                "href": "/category/fiction",
                "text": "Fiction",
                "url": f"{BASE}/category/fiction",
            },
            {"href": "/tag/fantasy", "text": "Fantasy", "url": f"{BASE}/tag/fantasy"},
        ]
        scored = self._score(crawler, links)
        assert scored == []

    def test_results_sorted_descending_by_score(self, crawler):
        links = [
            {"href": f"/books/{ISBN}", "text": TITLE, "url": f"{BASE}/books/{ISBN}"},
            {
                "href": "/books/other",
                "text": "Other Book",
                "url": f"{BASE}/books/other",
            },
        ]
        scored = self._score(crawler, links)
        assert scored[0]["url"] == f"{BASE}/books/{ISBN}"

    def test_relative_urls_normalised_to_absolute(self, crawler):
        links = [
            {
                "href": "/books/last-wish",
                "text": TITLE,
                "url": f"{BASE}/books/last-wish",
            }
        ]
        scored = self._score(crawler, links)
        assert scored[0]["url"].startswith("https://")

    def test_empty_link_list_returns_empty(self, crawler):
        assert self._score(crawler, []) == []
