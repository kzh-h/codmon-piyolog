# tests/test_meal_copy.py

import pytest

from src.codmon import MealData
from src.meal_copy import (
    find_latest_evening_meal,
    find_latest_morning_meal,
)
from tests.fakes import FakeCodmon


@pytest.mark.asyncio
async def test_find_latest_evening() -> None:

    codmon = FakeCodmon(
        [
            MealData("", ""),
            MealData("", ""),
            MealData("カレー", "パン"),
        ]
    )

    result = await find_latest_evening_meal(codmon)

    assert result == "カレー"


@pytest.mark.asyncio
async def test_find_today_evening() -> None:

    codmon = FakeCodmon(
        [
            MealData("ハンバーグ", ""),
        ]
    )

    result = await find_latest_evening_meal(codmon)

    assert result == "ハンバーグ"


@pytest.mark.asyncio
async def test_not_found() -> None:

    codmon = FakeCodmon([MealData("", "") for _ in range(30)])

    result = await find_latest_evening_meal(codmon)

    assert result is None


@pytest.mark.asyncio
async def test_find_latest_morning() -> None:

    codmon = FakeCodmon(
        [
            MealData("", ""),
            MealData("", "トースト"),
            MealData("", ""),
        ]
    )

    result = await find_latest_morning_meal(codmon)

    assert result == "トースト"
