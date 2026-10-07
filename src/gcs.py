import logging
import os
from pathlib import Path

from google.cloud import storage

logger = logging.getLogger(__name__)


def upload_trace_to_gcs(
    trace_path: str | Path,
    bucket_name: str | None = None,
) -> str | None:
    bucket_name = bucket_name or os.environ.get("GCS_TRACE_BUCKET")
    if not bucket_name:
        logger.warning(
            "GCS_TRACE_BUCKET is not set. Skipping trace upload to GCS."
        )
        return None

    path = Path(trace_path)
    if not path.exists():
        logger.warning(f"Trace file {path} does not exist. Skipping upload.")
        return None

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob_name = f"traces/{path.name}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(path))
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"Trace successfully uploaded to {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logger.error(
            f"Failed to upload trace to GCS (bucket: {bucket_name}): {e}"
        )
        return None


def upload_directory_to_gcs(
    local_dir: str | Path,
    prefix: str,
    bucket_name: str | None = None,
) -> list[str]:
    """local_dir 配下の全ファイルを gs://<bucket>/<prefix>/<相対パス> へ。

    アップロードできたファイルのGCS URIを返す。
    バケット未設定、またはエラー時は空リスト(例外は投げない)。
    """
    bucket_name = bucket_name or os.environ.get("GCS_TRACE_BUCKET")
    if not bucket_name:
        logger.info("GCS_TRACE_BUCKET is not set. Skipping upload to GCS.")
        return []

    root = Path(local_dir)
    if not root.is_dir():
        logger.warning(f"{root} is not a directory. Skipping upload.")
        return []

    prefix = prefix.strip("/")
    uris: list[str] = []
    try:
        bucket = storage.Client().bucket(bucket_name)
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            blob_name = f"{prefix}/{path.relative_to(root).as_posix()}"
            bucket.blob(blob_name).upload_from_filename(str(path))
            uris.append(f"gs://{bucket_name}/{blob_name}")
    except Exception as e:
        logger.error(
            f"Failed to upload directory to GCS (bucket: {bucket_name}): {e}"
        )
    return uris
