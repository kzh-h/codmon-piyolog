from pathlib import Path
from unittest.mock import MagicMock, patch

from src.gcs import upload_trace_to_gcs


def test_upload_trace_no_bucket_returns_none(tmp_path: Path) -> None:
    test_file = tmp_path / "trace.zip"
    test_file.write_text("dummy")

    with patch.dict("os.environ", {}, clear=True):
        result = upload_trace_to_gcs(test_file)
        assert result is None


def test_upload_trace_file_not_found() -> None:
    result = upload_trace_to_gcs(
        "/nonexistent/trace.zip", bucket_name="my-bucket"
    )
    assert result is None


def test_upload_trace_success(tmp_path: Path) -> None:
    test_file = tmp_path / "trace_20261002.zip"
    test_file.write_text("trace content")

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    with patch("src.gcs.storage.Client", return_value=mock_client):
        result = upload_trace_to_gcs(test_file, bucket_name="my-bucket")

        mock_client.bucket.assert_called_once_with("my-bucket")
        mock_bucket.blob.assert_called_once_with("traces/trace_20261002.zip")
        mock_blob.upload_from_filename.assert_called_once_with(str(test_file))
        assert result == "gs://my-bucket/traces/trace_20261002.zip"


def test_upload_trace_exception_handled(tmp_path: Path) -> None:
    test_file = tmp_path / "trace.zip"
    test_file.write_text("dummy")

    with patch("src.gcs.storage.Client", side_effect=Exception("Auth error")):
        result = upload_trace_to_gcs(test_file, bucket_name="my-bucket")
        assert result is None
