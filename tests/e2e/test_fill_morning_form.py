# tests/e2e/test_fill_morning_form.py

import os

import pytest
from playwright.async_api import async_playwright

from src.codmon import CodmonClient
from src.models import CodmonData
from src.piyolog import PiyologClient


@pytest.mark.asyncio
async def test_fill_morning_form() -> None:
    email = os.environ.get("CODMON_EMAIL")
    password = os.environ.get("CODMON_PASSWORD")
    feed_url = os.environ.get("PIYOLOG_FEED_URL")

    if not email or not password or not feed_url:
        pytest.skip(
            "CODMON_EMAIL, CODMON_PASSWORD, PIYOLOG_FEED_URL "
            "required for E2E test"
        )

    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    piyolog = PiyologClient(feed_url)
    data = piyolog.parse()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        await codmon.fill_morning_form(data)

        await browser.close()


@pytest.mark.asyncio
async def test_fill_morning_form_with_mock_data() -> None:
    email = os.environ.get("CODMON_EMAIL")
    password = os.environ.get("CODMON_PASSWORD")

    if not email or not password:
        pytest.skip("CODMON_EMAIL and CODMON_PASSWORD required for E2E test")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    data = CodmonData(
        poop_evening_count=2,
        poop_morning_count=1,
        sleep_start="21:00",
        sleep_end="6:30",
        temperature="36.8",
        temperature_time="7:15",
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        await codmon.fill_morning_form(data)

        await browser.close()
