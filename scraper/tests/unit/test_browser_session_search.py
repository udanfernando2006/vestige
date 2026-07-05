import pytest
from unittest.mock import AsyncMock, MagicMock

from browser.session import BrowserSession


def _make_session(page):
    session = BrowserSession.__new__(BrowserSession)
    session._page = page
    session._timeout = 60000
    return session


@pytest.mark.asyncio
async def test_find_and_fill_search_prefers_search_form_over_generic_form():
    localization_form = AsyncMock()
    localization_form.query_selector = AsyncMock(return_value=None)

    search_input = AsyncMock()
    search_input.fill = AsyncMock(return_value=None)
    search_input.press = AsyncMock(return_value=None)

    search_form = AsyncMock()
    search_form.query_selector = AsyncMock(return_value=search_input)
    search_form.get_attribute = AsyncMock(
        side_effect=lambda name: {
            "action": "/search",
            "method": "get",
        }.get(name)
    )

    page = MagicMock()
    page.url = "https://booxworm.lk/"

    async def query_selector(selector):
        if selector == "form[role='search']":
            return search_form
        if selector == "form":
            return localization_form
        return None

    page.query_selector = AsyncMock(side_effect=query_selector)
    page.wait_for_load_state = AsyncMock(return_value=None)

    session = _make_session(page)

    result = await session.find_and_fill_search("Chainsaw Man")

    assert result is True
    search_input.fill.assert_awaited_once_with("Chainsaw Man")
    search_input.press.assert_awaited_once_with("Enter")
    localization_form.query_selector.assert_not_called()
    page.query_selector.assert_any_await("form[role='search']")
    assert not any(
        call.args == ("form",) for call in page.query_selector.await_args_list
    )


@pytest.mark.asyncio
async def test_find_and_fill_search_keeps_generic_form_fallback():
    search_input = AsyncMock()
    search_input.fill = AsyncMock(return_value=None)
    search_input.press = AsyncMock(return_value=None)

    generic_form = AsyncMock()
    generic_form.query_selector = AsyncMock(return_value=search_input)
    generic_form.get_attribute = AsyncMock(
        side_effect=lambda name: {
            "action": "/search",
            "method": "get",
        }.get(name)
    )

    page = MagicMock()
    page.url = "https://example.com/"

    async def query_selector(selector):
        if selector == "form":
            return generic_form
        return None

    page.query_selector = AsyncMock(side_effect=query_selector)
    page.wait_for_load_state = AsyncMock(return_value=None)

    session = _make_session(page)

    result = await session.find_and_fill_search("The Last Wish")

    assert result is True
    search_input.fill.assert_awaited_once_with("The Last Wish")
    search_input.press.assert_awaited_once_with("Enter")
