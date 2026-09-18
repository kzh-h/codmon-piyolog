# tests/fakes.py

from datetime import date

from src.codmon import MealData
from src.gas_api import MealRecord


class FakeGasClient:
    def __init__(self, records: dict[tuple[str, str], MealRecord | None]):
        self.records = records

    def get_meal(self, target_date: date, meal_type: str) -> MealRecord | None:
        key = (target_date.strftime("%Y/%m/%d"), meal_type)
        return self.records.get(key)


class FakeCodmon:
    def __init__(self, days: list[MealData]):
        self.days = days
        self.index = 0
        self.saved = False

    async def get_meals(self) -> MealData:
        return self.days[self.index]

    async def set_evening_meal(self, value: str) -> None:
        self.days[self.index].evening = value

    async def set_morning_meal(self, value: str) -> None:
        self.days[self.index].morning = value

    async def move_prev_day(self) -> None:
        self.index += 1

    async def move_next_day(self) -> None:
        self.index -= 1

    async def save_draft(self) -> None:
        self.saved = True

    async def fill_evening_meal(self, value: str) -> None:
        self.days[self.index].evening = value
