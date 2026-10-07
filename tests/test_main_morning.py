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
        assert config.context_options == {
            "locale": "ja-JP",
            "timezone_id": "Asia/Tokyo",
        }


def test_get_browser_config_headless_is_same_for_local_and_gcp() -> None:
    from src.main_morning import get_browser_config

    with patch.dict("os.environ", {"HEADLESS": "true"}, clear=True):
        local = get_browser_config()
    with patch.dict(
        "os.environ",
        {"CLOUD_RUN_JOB": "codmon-piyolog", "HEADLESS": "true"},
        clear=True,
    ):
        gcp = get_browser_config()

    assert local.pattern_name == "local_headless"
    assert gcp.pattern_name == "gcp_headless"
    assert local.headless is gcp.headless is True
    assert (
        local.launch_args
        == gcp.launch_args
        == [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ]
    )
    assert (
        local.context_options
        == gcp.context_options
        == {
            "locale": "ja-JP",
            "timezone_id": "Asia/Tokyo",
            "viewport": {"width": 1280, "height": 1080},
        }
    )


def test_build_user_agent_uses_browser_version() -> None:
    from src.main_morning import build_user_agent

    ua = build_user_agent("141.0.7390.37")
    assert "Chrome/141.0.0.0" in ua
    assert "Headless" not in ua
    assert "X11; Linux x86_64" in ua


def test_build_context_options_ua_only_for_headless() -> None:
    from src.main_morning import build_context_options, get_browser_config

    with patch.dict("os.environ", {"HEADLESS": "true"}, clear=True):
        headless = build_context_options(get_browser_config(), "141.0.1.2")
    assert "Chrome/141.0.0.0" in headless["user_agent"]
    assert headless["locale"] == "ja-JP"

    with patch.dict("os.environ", {}, clear=True):
        headed = build_context_options(get_browser_config(), "141.0.1.2")
    assert "user_agent" not in headed
