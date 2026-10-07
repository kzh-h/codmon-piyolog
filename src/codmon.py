# src/codmon.py

import logging
import re
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from playwright.async_api import Locator as PlaywrightLocator
from playwright.async_api import Page, Response
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.models import CodmonData
from src.utils import get_jst_date

logger = logging.getLogger(__name__)


@dataclass
class MealData:
    evening: str
    morning: str


@dataclass
class SaveResult:
    verified: bool
    status: int | None = None
    url: str | None = None


class DiagnosticsHook(Protocol):
    async def checkpoint(self, name: str) -> None: ...

    def untraced(self, label: str) -> AbstractAsyncContextManager[None]: ...


class NullDiagnostics:
    async def checkpoint(self, name: str) -> None:
        pass

    @asynccontextmanager
    async def untraced(self, label: str) -> AsyncIterator[None]:  # noqa: ARG002
        yield


class Locators:
    PREV_DAY = '[data-testid="movePrevDay"]'
    NEXT_DAY = '[data-testid="moveNextDay"]'

    MEAL_ICON = ".icon-meal"
    SLEEP_ICON = ".icon-sleep"
    TEMP_ICON = ".icon-temperature"
    POOP_ICON = ".icon-diaper"
    MOOD_ICON = ".icon-mood"

    MEAL_TEXTAREA = "textarea.notebookInput__textArea"
    SELECT = "select.select__inner"

    LOGIN_EMAIL = 'textbox[name="メールアドレス"]'
    LOGIN_PASSWORD = 'textbox[name="パスワード"]'
    LOGIN_BUTTON = "text=ログインする"
    NOTEBOOK_BUTTON = 'button[name="連絡"]'
    RELOAD_BUTTON = '[data-test="reloadButton"]'
    ALREADY_HAVE_ACCOUNT = "text=すでにアカウントをお持ちの方"

    DRAFT_SAVE = "text=下書き保存"


class CodmonClient:
    def __init__(
        self,
        page: Page,
        email: str = "",
        password: str = "",
        headless: bool = False,
        pre_authenticated: bool = False,
        diagnostics: DiagnosticsHook | None = None,
    ):
        self.page = page
        self.email = email
        self.password = password
        self.headless = headless
        self._logged_in = pre_authenticated
        self._diag: DiagnosticsHook = diagnostics or NullDiagnostics()

    async def login(self) -> None:
        await self.page.goto("https://parents.codmon.com/home")
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        reload_button = self.page.locator(Locators.RELOAD_BUTTON)
        if await reload_button.count() > 0:
            await reload_button.click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)

        # Check if already logged in (contact button "連絡" is visible)
        contact_button = self.page.get_by_role("button", name="連絡")
        if await contact_button.count() > 0:
            self._logged_in = True
            return

        already_have_account = self.page.get_by_text(
            "すでにアカウントをお持ちの方"
        )
        if await already_have_account.count() > 0:
            await already_have_account.click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)

        await self.page.get_by_role("textbox", name="メールアドレス").fill(
            self.email
        )
        await self.page.wait_for_timeout(1000)
        # DOMスナップショットにパスワードが残るため、入力からログイン完了
        # までをトレース対象外にする
        async with self._diag.untraced("password"):
            await self.page.get_by_role("textbox", name="パスワード").fill(
                self.password
            )
            await self.page.wait_for_timeout(1000)
            await self.page.get_by_text("ログインする").click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)

            # Retry login up to 3 times if still on login page
            max_retries = 3
            for attempt in range(max_retries):
                login_button = self.page.get_by_text("ログインする")
                if await login_button.count() == 0:
                    break
                if attempt < max_retries - 1:
                    await self.page.wait_for_timeout(3000)
                    await login_button.click()
                    await self.page.wait_for_load_state("networkidle")
                    await self.page.wait_for_timeout(1000)
            else:
                raise RuntimeError("Login failed after 3 retries")

        # Wait 2 seconds for page transition, then click contact button
        await self.page.wait_for_timeout(2000)
        await self.page.get_by_role("button", name="連絡").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        self._logged_in = True
        await self._log_visible_date()

    async def _log_visible_date(self) -> None:
        """画面上の日付表示とJST日付を比較してログに出す (best effort)。"""
        try:
            text = await self.page.locator(Locators.PREV_DAY).first.evaluate(
                "el => el.parentElement.textContent", timeout=3000
            )
            visible = re.sub(r"\s+", " ", text or "").strip()
            today = get_jst_date()
            logger.info(f"Visible date text: '{visible}' (JST today={today})")
            if f"{today.month}月{today.day}日" not in visible.replace(" ", ""):
                logger.warning(
                    "Visible date text may not match JST today; "
                    "the notebook of another day might be open"
                )
        except Exception as e:
            logger.info(f"Could not read visible date: {e}")

    def _ensure_logged_in(self) -> None:
        if not self._logged_in:
            raise RuntimeError("Not logged in. Call login() first.")

    async def move_prev_day(self) -> None:
        self._ensure_logged_in()
        await self.page.get_by_test_id("movePrevDay").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

    async def move_next_day(self) -> None:
        self._ensure_logged_in()
        await self.page.get_by_test_id("moveNextDay").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

    async def get_meals(self) -> MealData:
        self._ensure_logged_in()
        meal_section = self._get_meal_section()
        textareas = meal_section.locator(Locators.MEAL_TEXTAREA)
        evening = await textareas.nth(0).input_value()
        morning = await textareas.nth(1).input_value()
        return MealData(evening=evening, morning=morning)

    async def get_committed_meals(self) -> MealData:
        # value属性 = Vueのstateの反映 (DOMプロパティではない)
        self._ensure_logged_in()
        textareas = self._get_meal_section().locator(Locators.MEAL_TEXTAREA)
        evening = await textareas.nth(0).get_attribute("value")
        morning = await textareas.nth(1).get_attribute("value")
        return MealData(evening=evening or "", morning=morning or "")

    async def _fill_meal_textarea(self, index: int, value: str) -> None:
        textarea = self._get_meal_section().locator(Locators.MEAL_TEXTAREA)
        textarea = textarea.nth(index)
        await textarea.scroll_into_view_if_needed()
        await textarea.fill(value)
        # fill()はinputのみ発火。Vueはchange/blurでstateに反映するため必要
        await textarea.dispatch_event("change")
        await textarea.blur()
        await self.page.wait_for_timeout(500)
        committed = await textarea.get_attribute("value")
        if committed != value:
            await textarea.click()
            await textarea.press("Tab")
            await self.page.wait_for_timeout(500)
            committed = await textarea.get_attribute("value")
        if committed != value:
            logger.warning(
                f"Meal textarea {index} not committed: "
                f"value attribute={committed!r}"
            )
            await self._diag.checkpoint(f"meal-{index}-not-committed")
        await self.page.wait_for_timeout(1000)

    async def set_evening_meal(self, value: str) -> None:
        self._ensure_logged_in()
        await self._fill_meal_textarea(0, value)

    async def set_morning_meal(self, value: str) -> None:
        self._ensure_logged_in()
        await self._fill_meal_textarea(1, value)

    async def fill_morning_form(self, data: CodmonData) -> None:
        self._ensure_logged_in()

        await self._fill_mood(data)
        await self._diag.checkpoint("filled-mood")
        await self._fill_poop(data)
        await self._diag.checkpoint("filled-poop")
        await self._fill_sleep(data)
        await self._diag.checkpoint("filled-sleep")
        await self._fill_temperature(data)
        await self._diag.checkpoint("filled-temperature")

    async def _fill_mood(self, _data: CodmonData) -> None:
        mood_section = self.page.locator("section").filter(
            has=self.page.locator(Locators.MOOD_ICON)
        )

        # Night mood: "夜のごきげんはいかがでしたか?"
        night_normal = mood_section.locator(
            ".emoticon-radio-wrapper .icon-mood-normal"
        ).first
        if await night_normal.count() > 0:
            await self._scroll_and_click(night_normal)
            await self.page.wait_for_timeout(1000)

        # Morning mood: "朝のごきげんはいかがでしたか?"
        morning_normal = mood_section.locator(
            ".emoticon-radio-wrapper .icon-mood-normal"
        ).nth(1)
        if await morning_normal.count() > 0:
            await self._scroll_and_click(morning_normal)
            await self.page.wait_for_timeout(1000)

    async def _fill_poop(self, data: CodmonData) -> None:
        poop_section = self.page.locator("div.block__white--padding").filter(
            has=self.page.locator(Locators.POOP_ICON)
        )
        selects = poop_section.locator(Locators.SELECT)

        # Check if the first select is visible and enabled (form is editable)
        first_select = selects.nth(0)
        is_visible = await first_select.is_visible()
        is_enabled = await first_select.is_enabled()
        if not is_visible or not is_enabled:
            logger.info("Poop section not editable, skipping")
            return

        await selects.nth(0).select_option("普通")
        await self.page.wait_for_timeout(1000)
        await selects.nth(1).select_option(str(data.poop_evening_count))
        await self.page.wait_for_timeout(1000)
        await selects.nth(2).select_option("普通")
        await self.page.wait_for_timeout(1000)
        await selects.nth(3).select_option(str(data.poop_morning_count))
        await self.page.wait_for_timeout(1000)

    async def _fill_sleep(self, data: CodmonData) -> None:
        sleep_section = self.page.locator(
            "section.block__white--padding"
        ).filter(has=self.page.locator(Locators.SLEEP_ICON))
        selects = sleep_section.locator(Locators.SELECT)

        # Check if the first select is visible and enabled (form is editable)
        first_select = selects.nth(0)
        is_visible = await first_select.is_visible()
        is_enabled = await first_select.is_enabled()
        if not is_visible or not is_enabled:
            logger.info("Sleep section not editable, skipping")
            return

        if data.sleep_start:
            select = selects.nth(0)
            await select.select_option(data.sleep_start)
            await self.page.wait_for_timeout(1000)
        if data.sleep_end:
            select = selects.nth(1)
            await select.select_option(data.sleep_end)
            await self.page.wait_for_timeout(1000)

    async def _fill_temperature(self, data: CodmonData) -> None:
        if not data.temperature or not data.temperature_time:
            return

        temp_section = self.page.locator(
            "section.block__white--padding"
        ).filter(has=self.page.locator(Locators.TEMP_ICON))
        selects = temp_section.locator(Locators.SELECT)

        # Check if the first select is visible and enabled (form is editable)
        first_select = selects.nth(0)
        is_visible = await first_select.is_visible()
        is_enabled = await first_select.is_enabled()
        if not is_visible or not is_enabled:
            logger.info("Temperature section not editable, skipping")
            return

        select = selects.nth(0)
        await select.select_option(data.temperature)
        await self.page.wait_for_timeout(1000)

        select = selects.nth(1)
        await select.select_option(data.temperature_time)
        await self.page.wait_for_timeout(1000)

    async def fill_evening_meal(self, value: str) -> None:
        self._ensure_logged_in()
        await self._fill_meal_textarea(0, value)

    async def _scroll_and_click(self, locator: PlaywrightLocator) -> None:
        js_click = """el => {
            try {
                el.scrollIntoView({ block: 'center', inline: 'center' });
            } catch (_) {}
            try {
                el.click();
            } catch (_) {}
            try {
                const wrapper = el.closest('.emoticon-radio-wrapper') || el;
                if (wrapper !== el) {
                    wrapper.click();
                }
                const input = wrapper.querySelector('input') ||
                    el.querySelector('input');
                if (input && !input.checked) {
                    input.checked = true;
                    input.dispatchEvent(
                        new Event('change', { bubbles: true })
                    );
                    input.dispatchEvent(
                        new Event('input', { bubbles: true })
                    );
                }
            } catch (_) {}
        }"""
        await locator.evaluate(js_click)
        try:
            if await locator.is_visible():
                await locator.click(force=True)
        except Exception:
            pass

    async def save_draft(self) -> SaveResult:
        self._ensure_logged_in()
        draft_btn = self.page.get_by_role("button", name="下書き保存")
        if await draft_btn.count() == 0:
            draft_btn = self.page.get_by_text("下書き保存")
        draft_btn = draft_btn.first
        await draft_btn.scroll_into_view_if_needed()
        await draft_btn.wait_for(state="visible")
        for _ in range(20):
            if await draft_btn.is_enabled():
                break
            await self.page.wait_for_timeout(500)

        clicked = False
        response: Response | None = None
        try:
            async with self.page.expect_response(
                _is_codmon_write, timeout=10_000
            ) as response_info:
                await draft_btn.click()
                clicked = True
            response = await response_info.value
        except PlaywrightTimeoutError:
            if not clicked:
                raise

        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        if response is None:
            logger.warning(
                "Draft save could not be verified: no non-GET response "
                "from codmon within 10s after clicking the save button"
            )
            await self._diag.checkpoint("save-unverified")
            return SaveResult(verified=False)

        method = response.request.method
        logger.info(
            f"Draft save response: {method} {response.url} "
            f"-> {response.status}"
        )
        if response.status >= 400:
            logger.warning(
                "Draft save could not be verified: "
                f"status={response.status} url={response.url}"
            )
            await self._diag.checkpoint("save-unverified")
        return SaveResult(
            verified=response.status < 400,
            status=response.status,
            url=response.url,
        )

    def _get_meal_section(self) -> PlaywrightLocator:
        return self.page.locator("section.block__white--padding").filter(
            has=self.page.locator(Locators.MEAL_ICON)
        )


def _is_codmon_write(response: Response) -> bool:
    host = urlparse(response.url).hostname or ""
    return response.request.method != "GET" and host.endswith("codmon.com")
