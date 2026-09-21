# src/main_morning.py

import asyncio
import os
from datetime import date

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.codmon import CodmonClient
from src.gas_api import get_gas_client
from src.meal_copy import find_latest_evening_meal, find_latest_morning_meal
from src.piyolog import PiyologClient

load_dotenv()

HOLIDAY_API_URL = "https://holidays-jp.github.io/api/v1/date.json"


def is_holiday() -> bool:
    today = date.today().isoformat()
    try:
        response = requests.get(HOLIDAY_API_URL, timeout=10)
        response.raise_for_status()
        holidays = response.json()
        return today in holidays
    except Exception:
        return False


async def main() -> None:
    if is_holiday():
        return

    email = os.environ["CODMON_EMAIL"]
    password = os.environ["CODMON_PASSWORD"]
    feed_url = os.environ["PIYOLOG_FEED_URL"]
    headless = os.environ.get("HEADLESS", "false").lower() == "true"

    piyolog = PiyologClient(feed_url)
    data = piyolog.parse()

    gas_client = get_gas_client()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        meals = await codmon.get_meals()

        if not meals.evening.strip():
            evening_meal = await find_latest_evening_meal(
                gas_client=gas_client
            )
            if evening_meal:
                await codmon.set_evening_meal(evening_meal)

        if not meals.morning.strip():
            morning_meal = await find_latest_morning_meal(
                gas_client=gas_client
            )
            if morning_meal:
                await codmon.set_morning_meal(morning_meal)

        await codmon.fill_morning_form(data)
        await codmon.save_draft()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
