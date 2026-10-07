# tests/test_codmon_meal.py

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.codmon import CodmonClient


def make_client(attrs: list[str | None]):
    client = CodmonClient.__new__(CodmonClient)
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    client.page = page
    client._diag = MagicMock()
    client._diag.checkpoint = AsyncMock()
    client._ensure_logged_in = MagicMock()  # type: ignore[method-assign]
    ta = MagicMock()
    ta.scroll_into_view_if_needed = AsyncMock()
    ta.fill = AsyncMock()
    ta.dispatch_event = AsyncMock()
    ta.blur = AsyncMock()
    ta.click = AsyncMock()
    ta.press = AsyncMock()
    ta.get_attribute = AsyncMock(side_effect=attrs)
    section = MagicMock()
    section.locator.return_value.nth.return_value = ta
    client._get_meal_section = MagicMock(  # type: ignore[method-assign]
        return_value=section
    )
    return client, ta, section


async def test_commit_ok_no_fallback() -> None:
    client, ta, section = make_client(["abc"])
    await client._fill_meal_textarea(1, "abc")
    section.locator.return_value.nth.assert_called_with(1)
    ta.fill.assert_awaited_once_with("abc")
    ta.dispatch_event.assert_awaited_once_with("change")
    ta.blur.assert_awaited_once()
    ta.click.assert_not_awaited()
    ta.press.assert_not_awaited()
    client._diag.checkpoint.assert_not_awaited()


async def test_fallback_tab_commits() -> None:
    client, ta, _ = make_client([None, "abc"])
    await client._fill_meal_textarea(0, "abc")
    ta.click.assert_awaited_once()
    ta.press.assert_awaited_once_with("Tab")
    client._diag.checkpoint.assert_not_awaited()


async def test_not_committed_warns_without_raising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _, _ = make_client([None, None])
    with caplog.at_level(logging.WARNING):
        await client._fill_meal_textarea(1, "abc")
    assert "not committed" in caplog.text
    client._diag.checkpoint.assert_awaited_once_with("meal-1-not-committed")


async def test_get_committed_meals_none_to_empty() -> None:
    client, _, _ = make_client(["x", None])
    meals = await client.get_committed_meals()
    assert meals.evening == "x"
    assert meals.morning == ""
