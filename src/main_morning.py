# src/main_morning.py

import asyncio
import logging
import os
import sys

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.codmon import CodmonClient
from src.gas_api import get_gas_client
from src.meal_copy import find_latest_evening_meal, find_latest_morning_meal
from src.piyolog import PiyologClient
from src.utils import get_jst_date

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

HOLIDAY_API_URL = "https://holidays-jp.github.io/api/v1/date.json"


def is_holiday() -> bool:
    today = get_jst_date().isoformat()
    try:
        response = requests.get(HOLIDAY_API_URL, timeout=10)
        response.raise_for_status()
        holidays = response.json()
        is_h = today in holidays
        logger.info(f"Holiday check: today={today}, is_holiday={is_h}")
        return is_h
    except Exception as e:
        logger.warning(f"Holiday check failed: {e}, assuming not a holiday")
        return False


async def main() -> None:
    logger.info("=== Morning processing started ===")
    logger.info(f"Current JST date: {get_jst_date()}")

    if is_holiday():
        logger.info("Today is a holiday, skipping processing")
        return

    email = os.environ["CODMON_EMAIL"]
    password = os.environ["CODMON_PASSWORD"]
    feed_url = os.environ["PIYOLOG_FEED_URL"]
    headless = os.environ.get("HEADLESS", "false").lower() == "true"
    logger.info(f"Environment loaded: headless={headless}")

    logger.info("Initializing Piyolog client...")
    piyolog = PiyologClient(feed_url)
    data = piyolog.parse()
    logger.info(f"Piyolog data parsed: {data}")

    logger.info("Initializing GAS client...")
    gas_client = get_gas_client()

    logger.info("Launching Playwright browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        logger.info("Browser launched successfully")

        logger.info("Initializing Codmon client...")
        codmon = CodmonClient(page, email, password, headless)

        logger.info("Logging into Codmon...")
        await codmon.login()
        logger.info("Login successful")

        logger.info("Fetching meals from Codmon...")
        meals = await codmon.get_meals()
        logger.info(
            "Meals fetched: "
            f"evening={'set' if meals.evening.strip() else 'empty'}, "
            f"morning={'set' if meals.morning.strip() else 'empty'}"
        )

        if not meals.evening.strip():
            logger.info(
                "Evening meal is empty, searching for latest "
                "evening meal from GAS..."
            )
            evening_meal = await find_latest_evening_meal(
                gas_client=gas_client
            )
            if evening_meal:
                logger.info(f"Found evening meal: {evening_meal[:50]}...")
                await codmon.set_evening_meal(evening_meal)
                logger.info("Evening meal set successfully")
            else:
                logger.info("No evening meal found in GAS")

        if not meals.morning.strip():
            logger.info(
                "Morning meal is empty, searching for latest "
                "morning meal from GAS..."
            )
            morning_meal = await find_latest_morning_meal(
                gas_client=gas_client
            )
            if morning_meal:
                logger.info(f"Found morning meal: {morning_meal[:50]}...")
                await codmon.set_morning_meal(morning_meal)
                logger.info("Morning meal set successfully")
            else:
                logger.info("No morning meal found in GAS")

        logger.info("Filling morning form with Piyolog data...")
        await codmon.fill_morning_form(data)
        logger.info("Morning form filled")

        logger.info("Saving draft...")
        await codmon.save_draft()
        logger.info("Draft saved successfully")

        await browser.close()
        logger.info("Browser closed")

    logger.info("=== Morning processing completed ===")


if __name__ == "__main__":
    asyncio.run(main())
