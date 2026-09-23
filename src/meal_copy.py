# src/meal_copy.py

from datetime import timedelta

from src.gas_api import GasApiClient, find_meal_from_gas, get_gas_client
from src.utils import get_jst_date


async def find_latest_evening_meal(
    max_days: int = 30,
    gas_client: GasApiClient | None = None,
) -> str | None:
    if gas_client is None:
        gas_client = get_gas_client()
    target_date = get_jst_date() - timedelta(days=1)
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
    target_date = get_jst_date()
    meal = await find_meal_from_gas(
        gas_client, target_date, "morning", max_days
    )
    return meal
