"""Every Cloudflare R2 call Monday makes.

R2 speaks the S3 API, so this uses boto3. This module never imports from a
service; object keys and link lifetimes are passed in by the caller.
"""

import logging
from functools import cache
from pathlib import Path

import boto3
from boto3.exceptions import Boto3Error
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from config.settings import (
    R2_ACCESS_KEY_ID,
    R2_ACCOUNT_ID,
    R2_BUCKET,
    R2_SECRET_ACCESS_KEY,
)

logger = logging.getLogger(__name__)


@cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
        # Recent boto3 adds checksum headers to every upload by default, which R2
        # doesn't fully support; only send them when an operation requires it.
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def upload_for_download(path: Path, key: str, expires_seconds: int) -> str | None:
    """Upload `path` to the bucket as `key` and return a link that downloads it.

    The link stops working after `expires_seconds`; the bucket's lifecycle rule
    deletes the object itself. None if R2 isn't configured or the upload failed.
    """

    if not all((R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET)):
        logger.error(f"Not uploading {key} to R2: R2 settings are missing")
        return None

    try:
        client = _client()
        client.upload_file(str(path), R2_BUCKET, key)
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": R2_BUCKET,
                "Key": key,
                # Makes the browser save the file under its own name instead of opening it.
                "ResponseContentDisposition": f'attachment; filename="{path.name}"',
            },
            ExpiresIn=expires_seconds,
        )

    except (Boto3Error, BotoCoreError, ClientError, OSError):
        logger.exception(f"R2 upload failed for {key}")
        return None

    except Exception:
        logger.exception(f"Unexpected R2 upload failure for {key}")
        return None
