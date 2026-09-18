# src/main_morning.py

import asyncio
import os

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.codmon import CodmonClient
from src.meal_copy import find_latest_evening_meal, find_latest_morning_meal
from src.piyolog import PiyologClient

load_dotenv()


async def main() -> None:
    email = os.environ["CODMON_EMAIL"]
    password = os.environ["CODMON_PASSWORD"]
    feed_url = os.environ["PIYOLOG_FEED_URL"]
    headless = os.environ.get("HEADLESS", "false").lower() == "true"

    piyolog = PiyologClient(feed_url)
    data = piyolog.parse()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        meals = await codmon.get_meals()

        if not meals.evening.strip():
            evening_meal = await find_latest_evening_meal(codmon)
            if evening_meal:
                await codmon.set_evening_meal(evening_meal)

        if not meals.morning.strip():
            morning_meal = await find_latest_morning_meal(codmon)
            if morning_meal:
                # Return to current day after searching previous days
                for _ in range(codmon._get_days_traversed()):
                    await codmon.move_next_day()
                await codmon.set_morning_meal(morning_meal)

        await codmon.fill_morning_form(data)
        await codmon.save_draft()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
