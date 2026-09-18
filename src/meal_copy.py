# src/meal_copy.py

from src.codmon import CodmonClient


async def find_latest_evening_meal(
    codmon: CodmonClient,
    max_days: int = 30,
) -> str | None:

    for _ in range(max_days):
        meal = await codmon.get_meals()

        if meal.evening.strip():
            return meal.evening

        await codmon.move_prev_day()

    return None


async def find_latest_morning_meal(
    codmon: CodmonClient,
    max_days: int = 30,
) -> str | None:

    for _ in range(max_days):
        meal = await codmon.get_meals()

        if meal.morning.strip():
            return meal.morning

        await codmon.move_prev_day()

    return None
