# tests/test_main_morning.py

from datetime import date
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

    with patch("src.main_morning.get_jst_date") as mock_get_jst_date:
        mock_get_jst_date.return_value = date(2026, 9, 21)
        assert is_holiday() is True


@patch("src.main_morning.requests.get")
def test_is_holiday_false(mock_get) -> None:
    mock_get.return_value.json.return_value = {
        "2026-09-21": "敬老の日",
        "2026-09-22": "敬老の日 振替休日",
    }
    mock_get.return_value.raise_for_status.return_value = None

    with patch("src.main_morning.get_jst_date") as mock_get_jst_date:
        mock_get_jst_date.return_value = date(2026, 9, 20)
        assert is_holiday() is False


@patch("src.main_morning.requests.get")
def test_is_holiday_request_exception(mock_get) -> None:
    mock_get.side_effect = Exception("Network error")

    with patch("src.main_morning.get_jst_date") as mock_get_jst_date:
        mock_get_jst_date.return_value = date(2026, 9, 21)
        assert is_holiday() is False


@patch("src.main_morning.requests.get")
def test_is_holiday_http_error(mock_get) -> None:
    mock_get.return_value.raise_for_status.side_effect = Exception("HTTP 500")

    with patch("src.main_morning.get_jst_date") as mock_get_jst_date:
        mock_get_jst_date.return_value = date(2026, 9, 21)
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


def test_is_gcp() -> None:
    from src.main_morning import is_gcp

    with patch.dict("os.environ", {}, clear=True):
        assert is_gcp() is False

    with patch.dict("os.environ", {"K_SERVICE": "my-service"}, clear=True):
        assert is_gcp() is True

    with patch.dict("os.environ", {"CLOUD_RUN_JOB": "my-job"}, clear=True):
        assert is_gcp() is True

    with patch.dict("os.environ", {"ENVIRONMENT": "gcp"}, clear=True):
        assert is_gcp() is True

    with patch.dict("os.environ", {"GCP": "true"}, clear=True):
        assert is_gcp() is True


def test_get_browser_config_local_headed() -> None:
    from src.main_morning import get_browser_config

    with patch.dict("os.environ", {"HEADLESS": "false"}, clear=True):
        config = get_browser_config()
        assert config.pattern_name == "local_headed"
        assert config.headless is False
        assert "--ozone-platform=wayland" in config.launch_args
        assert config.context_options == {}


def test_get_browser_config_local_headless() -> None:
    from src.main_morning import get_browser_config

    with patch.dict("os.environ", {"HEADLESS": "true"}, clear=True):
        config = get_browser_config()
        assert config.pattern_name == "local_headless"
        assert config.headless is True
        assert config.launch_args == [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--headless=new",
        ]
        assert config.context_options == {
            "viewport": {"width": 1280, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }


def test_get_browser_config_gcp_headless() -> None:
    from src.main_morning import get_browser_config

    with patch.dict(
        "os.environ",
        {"CLOUD_RUN_JOB": "codmon-piyolog", "HEADLESS": "true"},
        clear=True,
    ):
        config = get_browser_config()
        assert config.pattern_name == "gcp_headless"
        assert config.headless is True
        assert "--no-sandbox" in config.launch_args
        assert "--disable-dev-shm-usage" in config.launch_args
        assert "--disable-gpu" in config.launch_args
        assert config.context_options == {
            "viewport": {"width": 1280, "height": 1080}
        }
