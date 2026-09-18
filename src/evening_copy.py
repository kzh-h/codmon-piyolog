# src/evening_copy.py

from src.codmon import CodmonClient


async def copy_evening_to_tomorrow(codmon: CodmonClient) -> bool:
    today_meals = await codmon.get_meals()
    today_evening = today_meals.evening

    if not today_evening.strip():
        return False

    await codmon.move_next_day()

    tomorrow_meals = await codmon.get_meals()
    tomorrow_evening = tomorrow_meals.evening

    if tomorrow_evening.strip():
        await codmon.move_prev_day()
        return False

    await codmon.fill_evening_meal(today_evening)
    await codmon.save_draft()
    await codmon.move_prev_day()

    return True
