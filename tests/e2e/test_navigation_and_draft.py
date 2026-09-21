# tests/e2e/test_navigation_and_draft.py

import pytest
from playwright.async_api import Page

from src.codmon import CodmonClient


@pytest.mark.asyncio
async def test_move_prev_day(page: Page) -> None:
    codmon = CodmonClient(page, "", "", False, pre_authenticated=True)

    meals_before = await codmon.get_meals()

    await codmon.move_prev_day()

    meals_after = await codmon.get_meals()

    assert (
        meals_before.evening != meals_after.evening
        or meals_before.morning != meals_after.morning
    )


@pytest.mark.asyncio
async def test_move_next_day(page: Page) -> None:
    codmon = CodmonClient(page, "", "", False, pre_authenticated=True)

    meals_before = await codmon.get_meals()

    await codmon.move_next_day()

    meals_after = await codmon.get_meals()

    assert (
        meals_before.evening != meals_after.evening
        or meals_before.morning != meals_after.morning
    )


@pytest.mark.asyncio
async def test_save_draft(page: Page) -> None:
    codmon = CodmonClient(page, "", "", False, pre_authenticated=True)

    meals_before = await codmon.get_meals()

    if not meals_before.evening.strip():
        await codmon.set_evening_meal("テスト夕食")

    await codmon.save_draft()
