# src/gas_api.py

import os
from dataclasses import dataclass
from datetime import date, timedelta

import requests


@dataclass
class MealRecord:
    date: str
    morning_dinner: str
    detail: str
    success: bool


class GasApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def get_meal(self, target_date: date, meal_type: str) -> MealRecord | None:
        params = {
            "api_key": self.api_key,
            "date": target_date.strftime("%Y/%m/%d"),
            "morning_dinner": meal_type,
        }
        response = requests.get(self.base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            return MealRecord(
                date=data["date"],
                morning_dinner=data["morning_dinner"],
                detail=data.get("detail", ""),
                success=True,
            )
        return None


async def find_meal_from_gas(
    client: GasApiClient,
    start_date: date,
    meal_type: str,
    max_days: int = 30,
) -> str | None:
    current_date = start_date
    for _ in range(max_days):
        record = client.get_meal(current_date, meal_type)
        if record and record.detail is not None:
            return record.detail
        current_date -= timedelta(days=1)
    return None


def get_gas_client() -> GasApiClient:
    base_url = os.environ.get("GAS_URL")
    api_key = os.environ.get("GAS_KEY")
    if not base_url or not api_key:
        raise ValueError(
            "GAS_URL and GAS_KEY environment variables are required"
        )
    return GasApiClient(base_url, api_key)
