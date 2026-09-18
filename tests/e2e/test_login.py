# tests/e2e/test_login.py

import os

import pytest
from playwright.async_api import async_playwright

from src.codmon import CodmonClient


@pytest.mark.asyncio
async def test_login_success() -> None:
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

        await page.wait_for_load_state("networkidle")
        await page.get_by_role("button", name="連絡").wait_for(
            state="visible", timeout=10000
        )

        await browser.close()
