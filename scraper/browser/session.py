# scraper/browser/session.py

from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.async_api import async_playwright


class BrowserSession:
    _DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Referer": "https://www.google.com/",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, browser_config: dict = None):
        self._browser_config = browser_config or {}
        self._headless = self._browser_config.get("headless", True)
        self._timeout = self._browser_config.get("timeout", 60000)
        self._playwright = None
        self._browser = None
        self._page = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=self._browser_config.get(
                "args", ["--disable-blink-features=AutomationControlled"]
            ),
        )
        self._page = await self._browser.new_page()
        await self._page.set_extra_http_headers(
            self._browser_config.get("headers", self._DEFAULT_HEADERS)
        )
        await self._page.add_init_script(
            self._browser_config.get(
                "init_script",
                "Object.defineProperty(navigator, 'webdriver', {get: () => false})",
            )
        )
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def navigate(self, url: str, wait_until: str = "networkidle") -> None:
        await self._page.goto(url, timeout=self._timeout, wait_until=wait_until)

    async def get_html(self) -> str:
        return await self._page.content()

    async def get_url(self) -> str:
        return self._page.url

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            pass

    async def wait_for_load(self, state: str = "networkidle") -> None:
        await self._page.wait_for_load_state(state, timeout=self._timeout)

    async def find_and_fill_search(self, query: str) -> bool:
        """Find the most likely search form input, fill it, submit, wait for result."""

        form = await self._find_search_form()

        if not form:
            return False

        text_input = await self._find_search_input(form)

        if not text_input:
            return False

        try:
            if await self._is_visible(text_input):
                await self._fill_and_submit_search_input(text_input, query)
            else:
                await self._try_open_search_modal()

                refreshed_form = await self._find_search_form()
                if refreshed_form:
                    refreshed_input = await self._find_search_input(refreshed_form)
                    if refreshed_input and await self._is_visible(refreshed_input):
                        await self._fill_and_submit_search_input(refreshed_input, query)
                        try:
                            await self._page.wait_for_load_state(
                                "networkidle", timeout=self._timeout
                            )

                        except Exception as e:
                            print(f"Error during search submission: {e}")

                        return True

                search_url = await self._build_search_url_from_form(form, query)
                if not search_url:
                    return False
                await self.navigate(search_url)
        except Exception:
            search_url = await self._build_search_url_from_form(form, query)
            if not search_url:
                return False
            await self.navigate(search_url)
        try:
            await self._page.wait_for_load_state("networkidle", timeout=self._timeout)

        except Exception as e:
            print(f"Error during search submission: {e}")

        return True

    async def _find_search_form(self):
        search_form_selectors = [
            "form[role='search']",
            "form[action*='/search']",
            "predictive-search form",
            ".search-modal form",
        ]

        for selector in search_form_selectors:
            form = await self._page.query_selector(selector)
            if form:
                return form

        return await self._page.query_selector("form")

    async def _find_search_input(self, form):
        search_input_selectors = [
            'input[type="search"]',
            'input[name="q"]',
            'input[name="s"]',
            'input[type="text"]',
        ]

        for selector in search_input_selectors:
            text_input = await form.query_selector(selector)
            if text_input:
                return text_input

        return None

    async def _is_visible(self, element) -> bool:
        try:
            return await element.is_visible()
        except Exception:
            return False

    async def _fill_and_submit_search_input(self, text_input, query: str) -> None:
        await text_input.fill(query)
        await text_input.press("Enter")

    async def _try_open_search_modal(self) -> bool:
        search_trigger_selectors = [
            "button[aria-label*='search' i]",
            "summary[aria-label*='search' i]",
            ".header__icon--search",
            ".search-modal__toggle",
            "a[aria-label*='search' i]",
        ]

        for selector in search_trigger_selectors:
            trigger = await self._page.query_selector(selector)
            if not trigger:
                continue
            try:
                await trigger.click()
                return True
            except Exception:
                continue

        return False

    async def _build_search_url_from_form(self, form, query: str) -> str | None:
        action = await form.get_attribute("action")
        if not action:
            return None

        method = (await form.get_attribute("method") or "get").lower()
        if method != "get":
            return None

        input_candidates = [
            "input[type='search']",
            "input[name='q']",
            "input[name='s']",
            "input[type='text']",
        ]
        input_name = None
        for selector in input_candidates:
            field = await form.query_selector(selector)
            if field:
                input_name = await field.get_attribute("name")
                if input_name:
                    break

        if not input_name:
            input_name = "q"

        current_url = self._page.url
        resolved_action = urljoin(current_url, action)
        parsed = urlparse(resolved_action)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params[input_name] = [query]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    async def fresh_context(self) -> "BrowserSession":
        """
        Returns a new BrowserSession sharing the same browser process
        but with a completely fresh context — new cookies, storage, fingerprint.
        Caller is responsible for closing via async with.
        """
        new_session = BrowserSession.__new__(BrowserSession)
        new_session._browser_config = self._browser_config
        new_session._headless = self._headless
        new_session._timeout = self._timeout
        new_session._playwright = self._playwright  # shared
        new_session._browser = self._browser  # shared
        context = await self._browser.new_context()
        new_session._page = await context.new_page()
        await new_session._page.set_extra_http_headers(
            self._browser_config.get("headers", self._DEFAULT_HEADERS)
        )
        await new_session._page.add_init_script(
            self._browser_config.get(
                "init_script",
                "Object.defineProperty(navigator, 'webdriver', {get: () => false})",
            )
        )
        return new_session
