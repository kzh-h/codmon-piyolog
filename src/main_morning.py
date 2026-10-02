# src/main_morning.py

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.codmon import CodmonClient
from src.gas_api import get_gas_client
from src.gcs import upload_trace_to_gcs
from src.meal_copy import find_latest_evening_meal, find_latest_morning_meal
from src.piyolog import PiyologClient
from src.utils import get_jst_date

load_dotenv()


def is_gcp() -> bool:
    return bool(os.environ.get("K_SERVICE"))


logging.basicConfig(
    level=logging.DEBUG if not is_gcp() else logging.INFO,
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
    feed = piyolog.fetch()
    logger.debug(f"Piyolog raw feed: {json.dumps(feed, ensure_ascii=False)}")
    data = piyolog.parse(feed)
    logger.info(
        "Piyolog data parsed: "
        f"date={data.data_date}, time={data.temperature_time}, {data}"
    )

    logger.info("Initializing GAS client...")
    gas_client = get_gas_client()

    logger.info("Launching Playwright browser...")
    async with async_playwright() as p:
        if headless:
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        else:
            launch_args = [
                "--enable-features=UseOzonePlatform",
                "--ozone-platform=wayland",
            ]
        browser = await p.chromium.launch(headless=headless, args=launch_args)
        if headless:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1080}
            )
        else:
            context = await browser.new_context()
        await context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True,
        )

        try:
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

            await context.tracing.stop()
        except Exception as e:
            logger.error(f"Error during execution: {e}", exc_info=True)
            timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            trace_path = Path(f"/tmp/trace_{timestamp_str}.zip")
            await context.tracing.stop(path=str(trace_path))
            logger.info(f"Trace recorded to local file: {trace_path}")
            gcs_uri = upload_trace_to_gcs(trace_path)
            if gcs_uri:
                logger.info(f"Playwright trace uploaded to GCS: {gcs_uri}")
            raise
        finally:
            await browser.close()
            logger.info("Browser closed")

    logger.info("=== Morning processing completed ===")


if __name__ == "__main__":
    asyncio.run(main())
