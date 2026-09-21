# tests/e2e/test_fill_morning_form.py

import os

import pytest
from playwright.async_api import Page

from src.codmon import CodmonClient
from src.models import CodmonData
from src.piyolog import PiyologClient


@pytest.mark.asyncio
async def test_fill_morning_form(page: Page) -> None:
    feed_url = os.environ.get("PIYOLOG_FEED_URL")

    if not feed_url:
        pytest.skip("PIYOLOG_FEED_URL required for E2E test")

    piyolog = PiyologClient(feed_url)
    data = piyolog.parse()

    codmon = CodmonClient(page, "", "", False, pre_authenticated=True)

    await codmon.fill_morning_form(data)


@pytest.mark.asyncio
async def test_fill_morning_form_with_mock_data(page: Page) -> None:
    data = CodmonData(
        poop_evening_count=2,
        poop_morning_count=1,
        sleep_start="21:00",
        sleep_end="6:30",
        temperature="36.8",
        temperature_time="7:15",
        mood_evening="good",
        mood_morning="good",
    )

    codmon = CodmonClient(page, "", "", False, pre_authenticated=True)

    await codmon.fill_morning_form(data)
