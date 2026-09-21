# tests/conftest.py

import os

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from src.codmon import CodmonClient


@pytest_asyncio.fixture(scope="session")
async def authenticated_context():
    """セッション全体で1回だけログインし、認証状態を保存した context を返す"""
    email = os.environ.get("CODMON_EMAIL")
    password = os.environ.get("CODMON_PASSWORD")
    if not email or not password:
        pytest.skip("CODMON_EMAIL and CODMON_PASSWORD required for E2E test")

    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)

        # 最初のコンテキストでログイン
        context = await browser.new_context()
        page = await context.new_page()
        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        # 認証状態を保存
        storage_state = await context.storage_state()
        await context.close()

        # 認証済みの新しいコンテキストを作成して返す
        auth_context = await browser.new_context(storage_state=storage_state)
        yield auth_context
        await auth_context.close()
        await browser.close()


@pytest.fixture
async def page(authenticated_context):
    """各テストで使う page (認証済み)"""
    page = await authenticated_context.new_page()
    yield page
    await page.close()


@pytest.fixture
def codmon_client(page) -> CodmonClient:
    """認証済みの CodmonClient インスタンス"""
    return CodmonClient(page, "", "", False, pre_authenticated=True)
