# src/main_evening.py

import asyncio
import os

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.codmon import CodmonClient
from src.evening_copy import copy_evening_to_tomorrow
from src.gas_api import get_gas_client

load_dotenv()


async def main() -> None:
    email = os.environ["CODMON_EMAIL"]
    password = os.environ["CODMON_PASSWORD"]
    headless = os.environ.get("HEADLESS", "false").lower() == "true"

    gas_client = get_gas_client()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        codmon = CodmonClient(page, email, password, headless)
        await codmon.login()

        copied = await copy_evening_to_tomorrow(codmon, gas_client=gas_client)

        if copied:
            print("Evening meal copied to tomorrow and saved as draft")
        else:
            print(
                "No copy needed (today's evening empty or tomorrow "
                "already has meal)"
            )

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
