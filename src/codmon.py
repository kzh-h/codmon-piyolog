# src/codmon.py

from dataclasses import dataclass

from playwright.async_api import Locator as PlaywrightLocator
from playwright.async_api import Page

from src.models import CodmonData


@dataclass
class MealData:
    evening: str
    morning: str


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
        email: str,
        password: str,
        headless: bool = False,
    ):
        self.page = page
        self.email = email
        self.password = password
        self.headless = headless
        self._logged_in = False

    async def login(self) -> None:
        await self.page.goto("https://parents.codmon.com/home")
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        reload_button = self.page.locator(Locators.RELOAD_BUTTON)
        if await reload_button.count() > 0:
            await reload_button.click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)

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
        await self.page.get_by_role("textbox", name="パスワード").fill(
            self.password
        )
        await self.page.wait_for_timeout(1000)
        await self.page.get_by_text("ログインする").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        # Wait 2 seconds for page transition, then click contact button
        await self.page.wait_for_timeout(2000)
        await self.page.get_by_role("button", name="連絡").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        self._logged_in = True

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

    async def set_evening_meal(self, value: str) -> None:
        self._ensure_logged_in()
        meal_section = self._get_meal_section()
        await meal_section.locator(Locators.MEAL_TEXTAREA).nth(0).fill(value)
        await self.page.wait_for_timeout(1000)

    async def set_morning_meal(self, value: str) -> None:
        self._ensure_logged_in()
        meal_section = self._get_meal_section()
        await meal_section.locator(Locators.MEAL_TEXTAREA).nth(1).fill(value)
        await self.page.wait_for_timeout(1000)

    async def fill_morning_form(self, data: CodmonData) -> None:
        self._ensure_logged_in()

        await self._fill_mood()
        await self._fill_poop(data)
        await self._fill_sleep(data)
        await self._fill_temperature(data)

    async def _fill_mood(self) -> None:
        mood_section = self.page.locator("section").filter(
            has=self.page.locator(Locators.MOOD_ICON)
        )
        mood_icons = mood_section.locator(".icon-mood")
        if await mood_icons.count() > 0:
            await mood_icons.nth(0).click()
            await self.page.wait_for_timeout(1000)

    async def _fill_poop(self, data: CodmonData) -> None:
        poop_section = self.page.locator("div.block__white--padding").filter(
            has=self.page.locator(Locators.POOP_ICON)
        )
        selects = poop_section.locator(Locators.SELECT)

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

        if data.sleep_start:
            await selects.nth(0).select_option(data.sleep_start)
            await self.page.wait_for_timeout(1000)
        if data.sleep_end:
            await selects.nth(1).select_option(data.sleep_end)
            await self.page.wait_for_timeout(1000)

    async def _fill_temperature(self, data: CodmonData) -> None:
        if not data.temperature or not data.temperature_time:
            return

        temp_section = self.page.locator(
            "section.block__white--padding"
        ).filter(has=self.page.locator(Locators.TEMP_ICON))
        selects = temp_section.locator(Locators.SELECT)

        await selects.nth(0).select_option(data.temperature)
        await self.page.wait_for_timeout(1000)
        await selects.nth(1).select_option(data.temperature_time)
        await self.page.wait_for_timeout(1000)

    async def fill_evening_meal(self, value: str) -> None:
        self._ensure_logged_in()
        meal_section = self._get_meal_section()
        await meal_section.locator(Locators.MEAL_TEXTAREA).nth(0).fill(value)
        await self.page.wait_for_timeout(1000)

    async def save_draft(self) -> None:
        self._ensure_logged_in()
        await self.page.get_by_text("下書き保存").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

    def _get_meal_section(self) -> PlaywrightLocator:
        return self.page.locator("section.block__white--padding").filter(
            has=self.page.locator(Locators.MEAL_ICON)
        )
