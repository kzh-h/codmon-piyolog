# tests/fakes.py

from src.codmon import MealData


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
