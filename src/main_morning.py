# src/main_morning.py

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.codmon import CodmonClient, SaveResult
from src.diagnostics import (
    RunDiagnostics,
    add_redaction,
    attach_file_log,
    build_run_id,
    resolve_artifacts_base,
    set_run_id,
    setup_logging,
)
from src.gas_api import GasApiClient, get_gas_client
from src.meal_copy import find_latest_evening_meal, find_latest_morning_meal
from src.models import CodmonData
from src.piyolog import PiyologClient
from src.utils import get_jst_date

load_dotenv()


def is_gcp() -> bool:
    return bool(
        os.environ.get("K_SERVICE")
        or os.environ.get("CLOUD_RUN_JOB")
        or os.environ.get("CLOUD_RUN_EXECUTION")
        or os.environ.get("ENVIRONMENT", "").lower()
        in ("gcp", "production", "prod")
        or os.environ.get("GCP", "").lower() == "true"
    )


@dataclass
class BrowserConfig:
    headless: bool
    launch_args: list[str]
    context_options: dict[str, Any]
    pattern_name: str


# ローカルheadlessとGCPで同一にし、ローカルでGCPを再現できるようにする
HEADLESS_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-blink-features=AutomationControlled",
]
LOCALE_OPTIONS: dict[str, Any] = {
    "locale": "ja-JP",
    "timezone_id": "Asia/Tokyo",
}


def get_browser_config() -> BrowserConfig:
    headless_env = os.environ.get("HEADLESS", "false").lower() == "true"

    if is_gcp() or headless_env:
        # パターン2/3: ローカルHEADLESS true / デプロイ先GCP
        return BrowserConfig(
            headless=True,
            launch_args=list(HEADLESS_ARGS),
            context_options={
                **LOCALE_OPTIONS,
                "viewport": {"width": 1280, "height": 1080},
            },
            pattern_name="gcp_headless" if is_gcp() else "local_headless",
        )
    # パターン1: ローカル開発でのHEADLESS false
    return BrowserConfig(
        headless=False,
        launch_args=[
            "--enable-features=UseOzonePlatform",
            "--ozone-platform=wayland",
        ],
        context_options=dict(LOCALE_OPTIONS),
        pattern_name="local_headed",
    )


def build_user_agent(browser_version: str) -> str:
    """実際のChromeバージョンから、Headlessを含まないUAを作る。"""
    major = browser_version.split(".")[0]
    return (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def build_context_options(
    config: BrowserConfig, browser_version: str
) -> dict[str, Any]:
    options = dict(config.context_options)
    if config.headless:
        options["user_agent"] = build_user_agent(browser_version)
    return options


logger = logging.getLogger(__name__)
setup_logging(is_gcp())

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


async def fill_codmon(
    codmon: CodmonClient,
    diag: RunDiagnostics,
    gas_client: GasApiClient,
    data: CodmonData,
) -> SaveResult:
    with diag.step("get_meals"):
        logger.info("Fetching meals from Codmon...")
        meals = await codmon.get_meals()
        logger.info(
            "Meals fetched: "
            f"evening={'set' if meals.evening.strip() else 'empty'}, "
            f"morning={'set' if meals.morning.strip() else 'empty'}"
        )
    await diag.checkpoint("after-get-meals")

    set_meals: dict[str, str] = {}
    with diag.step("set_meals"):
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
                set_meals["evening"] = evening_meal
                logger.info("Evening meal set successfully")
                await diag.checkpoint("after-set-evening-meal")
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
                set_meals["morning"] = morning_meal
                logger.info("Morning meal set successfully")
                meals_after = await codmon.get_meals()
                logger.info(f"Morning meal after set: '{meals_after.morning}'")
                await diag.checkpoint("after-set-morning-meal")
            else:
                logger.info("No morning meal found in GAS")

    with diag.step("fill_morning_form"):
        logger.info("Filling morning form with Piyolog data...")
        await codmon.fill_morning_form(data)
        logger.info("Morning form filled")
        meals_after_form = await codmon.get_meals()
        logger.info(
            f"Morning meal after fill_morning_form: "
            f"'{meals_after_form.morning}'"
        )
        committed = await codmon.get_committed_meals()
        logger.info(
            f"Committed meals after fill_morning_form: "
            f"evening='{committed.evening}', morning='{committed.morning}'"
        )
        if "evening" in set_meals and not committed.evening.strip():
            logger.warning("Evening meal was lost, setting it again")
            await codmon.set_evening_meal(set_meals["evening"])
        if "morning" in set_meals and not committed.morning.strip():
            logger.warning("Morning meal was lost, setting it again")
            await codmon.set_morning_meal(set_meals["morning"])

    await diag.checkpoint("before-save")
    with diag.step("save_draft"):
        logger.info("Saving draft...")
        result = await codmon.save_draft()
    await diag.checkpoint("after-save")
    if result.verified:
        logger.info("Draft saved (save request succeeded)")
    return result


async def main() -> None:
    gcp = is_gcp()
    run_id = build_run_id(gcp)
    set_run_id(run_id)
    logger.info("=== Morning processing started ===")
    logger.info(f"Current JST date: {get_jst_date()}")

    if is_holiday():
        logger.info("Today is a holiday, skipping processing")
        return

    email = os.environ["CODMON_EMAIL"]
    password = os.environ["CODMON_PASSWORD"]
    feed_url = os.environ["PIYOLOG_FEED_URL"]
    browser_config = get_browser_config()

    run_dir = resolve_artifacts_base(gcp) / "runs" / run_id
    diag = RunDiagnostics(
        run_id,
        run_dir,
        os.environ.get("GCS_TRACE_BUCKET"),
    )
    attach_file_log(run_dir / "run.log")
    diag.redactor = add_redaction([email, password, feed_url])
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Artifacts dir: {run_dir.resolve()}")
    logger.info(
        f"Execution pattern: {browser_config.pattern_name} "
        f"(headless={browser_config.headless}, is_gcp={gcp})"
    )

    error: BaseException | None = None
    save_result: SaveResult | None = None
    try:
        logger.info("Initializing Piyolog client...")
        piyolog = PiyologClient(feed_url)
        feed = piyolog.fetch()
        logger.debug(
            f"Piyolog raw feed: {json.dumps(feed, ensure_ascii=False)}"
        )
        data = piyolog.parse(feed)
        logger.info(
            "Piyolog data parsed: "
            f"date={data.data_date}, time={data.temperature_time}, {data}"
        )

        logger.info("Initializing GAS client...")
        gas_client = get_gas_client()

        logger.info(
            f"Launching Playwright browser "
            f"(pattern={browser_config.pattern_name}, "
            f"args={browser_config.launch_args})..."
        )
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=browser_config.headless,
                args=browser_config.launch_args,
            )
            failed = False
            try:
                context_options = build_context_options(
                    browser_config, browser.version
                )
                context = await browser.new_context(**context_options)
                await diag.start_tracing(context, f"codmon-piyolog {run_id}")
                page = await context.new_page()
                diag.attach_page(page)
                codmon = CodmonClient(
                    page, email, password, browser_config.headless,
                    diagnostics=diag,
                )  # fmt: skip

                with diag.step("login"):
                    logger.info("Logging into Codmon...")
                    await codmon.login()
                    logger.info("Login successful")
                await diag.write_environment(
                    browser,
                    browser_config.pattern_name,
                    browser_config.headless,
                    browser_config.launch_args,
                    context_options,
                )
                await diag.checkpoint("after-login")

                save_result = await fill_codmon(codmon, diag, gas_client, data)
            except Exception:
                failed = True
                await diag.checkpoint("error")
                raise
            finally:
                keep_trace = os.environ.get("KEEP_TRACE", "").lower() == "true"
                await diag.stop_tracing(keep=failed or keep_trace)
                await browser.close()
                logger.info("Browser closed")
    except Exception as e:
        error = e
        logger.error(f"Error during execution: {e}", exc_info=True)
        raise
    finally:
        extra: dict[str, Any] = {
            "pattern_name": browser_config.pattern_name,
            "save_draft": None if save_result is None else vars(save_result),
        }
        diag.write_summary(error, extra)
        await diag.upload()
        logger.info(f"Artifacts dir: {run_dir.resolve()}")

    logger.info("=== Morning processing completed ===")


if __name__ == "__main__":
    asyncio.run(main())
