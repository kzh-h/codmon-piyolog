# src/evening_copy.py

from datetime import date, timedelta

from src.codmon import CodmonClient
from src.gas_api import GasApiClient, find_meal_from_gas, get_gas_client


async def copy_evening_to_tomorrow(
    codmon: CodmonClient,
    gas_client: GasApiClient | None = None,
) -> bool:
    if gas_client is None:
        gas_client = get_gas_client()

    target_date = date.today() - timedelta(days=1)
    meal = await find_meal_from_gas(
        gas_client, target_date, "dinner", max_days=30
    )

    if not meal:
        return False

    await codmon.move_next_day()

    tomorrow_meals = await codmon.get_meals()
    tomorrow_evening = tomorrow_meals.evening

    if tomorrow_evening.strip():
        await codmon.move_prev_day()
        return False

    await codmon.fill_evening_meal(meal)
    await codmon.save_draft()
    await codmon.move_prev_day()

    return True
