# tests/test_main_morning.py

from unittest.mock import patch

import pytest

from src.main_morning import is_holiday


@patch("src.main_morning.requests.get")
def test_is_holiday_true(mock_get) -> None:
    mock_get.return_value.json.return_value = {
        "2026-09-21": "敬老の日",
        "2026-09-22": "敬老の日 振替休日",
    }
    mock_get.return_value.raise_for_status.return_value = None

    with patch("src.main_morning.date") as mock_date:
        mock_date.today.return_value.isoformat.return_value = "2026-09-21"
        assert is_holiday() is True


@patch("src.main_morning.requests.get")
def test_is_holiday_false(mock_get) -> None:
    mock_get.return_value.json.return_value = {
        "2026-09-21": "敬老の日",
        "2026-09-22": "敬老の日 振替休日",
    }
    mock_get.return_value.raise_for_status.return_value = None

    with patch("src.main_morning.date") as mock_date:
        mock_date.today.return_value.isoformat.return_value = "2026-09-20"
        assert is_holiday() is False


@patch("src.main_morning.requests.get")
def test_is_holiday_request_exception(mock_get) -> None:
    mock_get.side_effect = Exception("Network error")

    with patch("src.main_morning.date") as mock_date:
        mock_date.today.return_value.isoformat.return_value = "2026-09-21"
        assert is_holiday() is False


@patch("src.main_morning.requests.get")
def test_is_holiday_http_error(mock_get) -> None:
    mock_get.return_value.raise_for_status.side_effect = Exception("HTTP 500")

    with patch("src.main_morning.date") as mock_date:
        mock_date.today.return_value.isoformat.return_value = "2026-09-21"
        assert is_holiday() is False


@pytest.mark.asyncio
async def test_main_returns_early_on_holiday() -> None:
    from src.main_morning import main

    with (
        patch("src.main_morning.is_holiday", return_value=True),
        patch("src.main_morning.os.environ.get") as mock_env,
        patch("src.main_morning.async_playwright") as mock_playwright,
    ):
        mock_env.side_effect = lambda k, d=None: {
            "CODMON_EMAIL": "test@example.com",
            "CODMON_PASSWORD": "password",  # pragma: allowlist secret
            "PIYOLOG_FEED_URL": "https://example.com/feed",
            "HEADLESS": "true",
        }.get(k, d)
        await main()
        mock_playwright.assert_not_called()
