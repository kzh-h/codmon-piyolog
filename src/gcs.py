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
