# scraper/browser/session.py

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
        """Find the first search form input, fill it, submit, wait for result."""

        form = await self._page.query_selector("form")

        if not form:
            return False

        text_input = await form.query_selector(
            'input[type="text"], input[type="search"]'
        )

        if not text_input:
            return False

        await text_input.fill(query)
        await text_input.press("Enter")
        try:
            await self._page.wait_for_load_state("networkidle", timeout=self._timeout)

        except Exception as e:
            print(f"Error during search submission: {e}")

        return True

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
