# tests/test_diagnostics.py

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.diagnostics import (
    REPO_ROOT,
    JsonLogFormatter,
    RunDiagnostics,
    SecretRedactFilter,
    build_run_id,
    resolve_artifacts_base,
    set_run_id,
)

NOW = datetime(2026, 10, 6, 22, 30, 5, tzinfo=UTC)


def test_run_id_local_uses_jst() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert build_run_id(False, NOW) == "20261007-073005"


def test_run_id_gcp_includes_execution_and_task() -> None:
    env = {"CLOUD_RUN_EXECUTION": "job-abc", "CLOUD_RUN_TASK_INDEX": "0"}
    with patch.dict("os.environ", env, clear=True):
        assert build_run_id(True, NOW) == "20261007-073005-job-abc-task0"
    with patch.dict("os.environ", {}, clear=True):
        assert build_run_id(True, NOW) == "20261007-073005"


def test_artifacts_base() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert resolve_artifacts_base(False) == REPO_ROOT / "tmp"
        assert resolve_artifacts_base(True) == Path("/tmp")
    with patch.dict("os.environ", {"ARTIFACTS_DIR": "/data/x"}, clear=True):
        assert resolve_artifacts_base(False) == Path("/data/x")
        assert resolve_artifacts_base(True) == Path("/data/x")


def test_json_log_formatter() -> None:
    set_run_id("rid")
    record = logging.LogRecord(
        "my.logger", logging.WARNING, "f.py", 1, "hello %s", ("w",), None
    )
    line = JsonLogFormatter().format(record)
    assert "\n" not in line
    assert json.loads(line) == {
        "severity": "WARNING",
        "message": "hello w",
        "run_id": "rid",
        "logger": "my.logger",
    }
    set_run_id("")


def test_secret_redact_filter() -> None:
    f = SecretRedactFilter(["s3cret", ""])
    record = logging.LogRecord(
        "l", logging.INFO, "f.py", 1, "pw=%s", ("s3cret",), None
    )
    f.filter(record)
    assert record.getMessage() == "pw=***"


def make_page() -> MagicMock:
    page = MagicMock()
    page.url = "https://parents.codmon.com/x"
    page.evaluate = AsyncMock(return_value={"selects": []})
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    return page


def make_context() -> MagicMock:
    context = MagicMock()
    context.tracing.start = AsyncMock()
    context.tracing.stop = AsyncMock()
    context.tracing.start_chunk = AsyncMock()
    context.tracing.stop_chunk = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_tracing_is_split_around_untraced(tmp_path: Path) -> None:
    diag = RunDiagnostics("rid", tmp_path, None)
    context = make_context()
    await diag.start_tracing(context, "title")
    async with diag.untraced("password"):
        pass
    await diag.stop_tracing()
    await diag.stop_tracing()  # 2回目は何もしない

    context.tracing.stop_chunk.assert_awaited_once_with(
        path=tmp_path / "trace-01.zip"
    )
    context.tracing.start_chunk.assert_awaited_once()
    context.tracing.stop.assert_awaited_once_with(
        path=tmp_path / "trace-02.zip"
    )


@pytest.mark.asyncio
async def test_untraced_resumes_when_body_raises(tmp_path: Path) -> None:
    diag = RunDiagnostics("rid", tmp_path, None)
    context = make_context()
    await diag.start_tracing(context, "title")
    with pytest.raises(ValueError):
        async with diag.untraced("password"):
            raise ValueError("boom")
    context.tracing.start_chunk.assert_awaited_once()


@pytest.mark.asyncio
async def test_diagnostics_never_raises(tmp_path: Path) -> None:
    diag = RunDiagnostics("rid", tmp_path, None)
    context = make_context()
    context.tracing.stop.side_effect = RuntimeError("not started")
    await diag.start_tracing(context, "t")
    await diag.stop_tracing()

    page = make_page()
    page.screenshot.side_effect = RuntimeError("closed")
    page.evaluate.side_effect = RuntimeError("closed")
    diag.attach_page(page)
    await diag.checkpoint("broken")


@pytest.mark.asyncio
async def test_checkpoint_and_summary(tmp_path: Path) -> None:
    diag = RunDiagnostics(
        "rid", tmp_path, "bucket", SecretRedactFilter(["s3cret"])
    )
    diag.attach_page(make_page())
    await diag.checkpoint("after login")
    with diag.step("login"):
        pass

    assert (tmp_path / "checkpoints" / "01-after-login.html").exists()
    info = json.loads(
        (tmp_path / "checkpoints" / "01-after-login.json").read_text()
    )
    assert info["url"] == "https://parents.codmon.com/x"
    assert info["form"] == {"selects": []}

    diag.write_summary(
        ValueError("bad s3cret"), {"save_draft": {"verified": False}}
    )
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["error"]["type"] == "ValueError"
    assert "s3cret" not in json.dumps(summary)
    assert summary["steps"][0]["name"] == "login"
    assert "summary.json" in summary["files"]
    assert summary["gcs_uris"][0].startswith("gs://bucket/runs/rid/")
    assert summary["save_draft"] == {"verified": False}


@pytest.mark.asyncio
async def test_upload_skipped_without_bucket(tmp_path: Path) -> None:
    diag = RunDiagnostics("rid", tmp_path, None)
    with patch("src.diagnostics.upload_directory_to_gcs") as upload:
        await diag.upload()
    upload.assert_not_called()


@pytest.mark.asyncio
async def test_upload_with_bucket(tmp_path: Path) -> None:
    diag = RunDiagnostics("rid", tmp_path, "bucket")
    with patch(
        "src.diagnostics.upload_directory_to_gcs", return_value=["gs://x"]
    ) as upload:
        await diag.upload()
    upload.assert_called_once_with(tmp_path, "runs/rid", "bucket")
