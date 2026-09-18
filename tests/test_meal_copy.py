# tests/test_meal_copy.py


import pytest

from src.gas_api import MealRecord
from src.meal_copy import (
    find_latest_evening_meal,
    find_latest_morning_meal,
)
from tests.fakes import FakeGasClient


@pytest.mark.asyncio
async def test_find_latest_evening() -> None:

    gas_client = FakeGasClient(
        {
            ("2026/09/17", "dinner"): MealRecord(
                "2026/09/17", "dinner", "カレー", True
            ),
        }
    )

    result = await find_latest_evening_meal(gas_client=gas_client)

    assert result == "カレー"


@pytest.mark.asyncio
async def test_find_today_evening() -> None:

    gas_client = FakeGasClient(
        {
            ("2026/09/17", "dinner"): MealRecord(
                "2026/09/17", "dinner", "ハンバーグ", True
            ),
        }
    )

    result = await find_latest_evening_meal(gas_client=gas_client)

    assert result == "ハンバーグ"


@pytest.mark.asyncio
async def test_not_found() -> None:

    gas_client = FakeGasClient({})

    result = await find_latest_evening_meal(max_days=30, gas_client=gas_client)

    assert result is None


@pytest.mark.asyncio
async def test_find_latest_morning() -> None:

    gas_client = FakeGasClient(
        {
            ("2026/09/18", "morning"): MealRecord(
                "2026/09/18", "morning", "トースト", True
            ),
        }
    )

    result = await find_latest_morning_meal(gas_client=gas_client)

    assert result == "トースト"
