# tests/test_evening_copy.py


import pytest

from src.codmon import MealData
from src.evening_copy import copy_evening_to_tomorrow
from src.gas_api import MealRecord
from tests.fakes import FakeCodmon, FakeGasClient


@pytest.mark.asyncio
async def test_copy_to_empty() -> None:

    codmon = FakeCodmon(
        [
            MealData("ビビンバ", ""),
            MealData("", ""),
        ]
    )

    gas_client = FakeGasClient(
        {
            ("2026/09/17", "dinner"): MealRecord(
                "2026/09/17", "dinner", "ビビンバ", True
            ),
        }
    )

    result = await copy_evening_to_tomorrow(codmon, gas_client=gas_client)

    assert result is True
    assert codmon.days[1].evening == "ビビンバ"
    assert codmon.saved is True


@pytest.mark.asyncio
async def test_skip_if_exists() -> None:

    codmon = FakeCodmon(
        [
            MealData("ビビンバ", ""),
            MealData("カレー", ""),
        ]
    )

    gas_client = FakeGasClient(
        {
            ("2026/09/17", "dinner"): MealRecord(
                "2026/09/17", "dinner", "ビビンバ", True
            ),
        }
    )

    result = await copy_evening_to_tomorrow(codmon, gas_client=gas_client)

    assert result is False
    assert codmon.days[1].evening == "カレー"
    assert codmon.saved is False


@pytest.mark.asyncio
async def test_skip_if_today_empty() -> None:

    codmon = FakeCodmon(
        [
            MealData("", ""),
            MealData("", ""),
        ]
    )

    gas_client = FakeGasClient({})

    result = await copy_evening_to_tomorrow(codmon, gas_client=gas_client)

    assert result is False
    assert codmon.saved is False
