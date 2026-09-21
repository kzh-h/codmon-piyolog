# tests/e2e/test_login.py

import pytest
from playwright.async_api import Page

from src.codmon import CodmonClient


@pytest.mark.asyncio
async def test_login_success(page: Page) -> None:
    """認証済み page fixture 使用時、ログイン不要で即座に操作可能"""
    codmon = CodmonClient(page, "", "", False, pre_authenticated=True)

    # すでに認証済みなので login() はスキップされる (内部で早期リターン)
    await codmon.login()

    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="連絡").wait_for(
        state="visible", timeout=10000
    )
