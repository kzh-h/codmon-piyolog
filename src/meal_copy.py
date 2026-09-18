# src/meal_copy.py

from datetime import date, timedelta

from src.gas_api import GasApiClient, find_meal_from_gas, get_gas_client


async def find_latest_evening_meal(
    max_days: int = 30,
    gas_client: GasApiClient | None = None,
) -> str | None:
    if gas_client is None:
        gas_client = get_gas_client()
    target_date = date.today() - timedelta(days=1)
    meal = await find_meal_from_gas(
        gas_client, target_date, "dinner", max_days
    )
    return meal


async def find_latest_morning_meal(
    max_days: int = 30,
    gas_client: GasApiClient | None = None,
) -> str | None:
    if gas_client is None:
        gas_client = get_gas_client()
    target_date = date.today()
    meal = await find_meal_from_gas(
        gas_client, target_date, "morning", max_days
    )
    return meal
