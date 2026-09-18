# tests/e2e/test_navigation_and_draft.py

import os

import pytest
from playwright.async_api import async_playwright

from src.codmon import CodmonClient


@pytest.mark.asyncio
async def test_move_prev_day() -> None:
    email = os.environ.get("CODMON_EMAIL")
    password = os.environ.get("CODMON_PASSWORD")

    if not email or not password:
        pytest.skip("CODMON_EMAIL and CODMON_PASSWORD required for E2E test")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        meals_before = await codmon.get_meals()

        await codmon.move_prev_day()

        meals_after = await codmon.get_meals()

        assert (
            meals_before.evening != meals_after.evening
            or meals_before.morning != meals_after.morning
        )

        await browser.close()


@pytest.mark.asyncio
async def test_move_next_day() -> None:
    email = os.environ.get("CODMON_EMAIL")
    password = os.environ.get("CODMON_PASSWORD")

    if not email or not password:
        pytest.skip("CODMON_EMAIL and CODMON_PASSWORD required for E2E test")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        meals_before = await codmon.get_meals()

        await codmon.move_next_day()

        meals_after = await codmon.get_meals()

        assert (
            meals_before.evening != meals_after.evening
            or meals_before.morning != meals_after.morning
        )

        await browser.close()


@pytest.mark.asyncio
async def test_save_draft() -> None:
    email = os.environ.get("CODMON_EMAIL")
    password = os.environ.get("CODMON_PASSWORD")

    if not email or not password:
        pytest.skip("CODMON_EMAIL and CODMON_PASSWORD required for E2E test")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        meals_before = await codmon.get_meals()

        if not meals_before.evening.strip():
            await codmon.set_evening_meal("テスト夕食")

        await codmon.save_draft()

        await browser.close()
