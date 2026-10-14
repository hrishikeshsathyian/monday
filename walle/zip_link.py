"""Download links for zips too big to send through Telegram, built on the shared R2 integration."""

import uuid
from pathlib import Path

from integrations.r2 import upload_for_download

from .config import ZIP_LINK_EXPIRY_SECONDS, ZIP_LINK_KEY_PREFIX


def get_zip_download_link(zip_path: Path) -> str | None:
    """Upload a course zip to R2 and return a link that downloads it. None on failure."""

    key = f"{ZIP_LINK_KEY_PREFIX}{uuid.uuid4().hex}/{zip_path.name}"
    return upload_for_download(zip_path, key, ZIP_LINK_EXPIRY_SECONDS)
