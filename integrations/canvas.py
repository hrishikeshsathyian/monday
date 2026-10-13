"""Canvas API operations shared by every service that uses a student's Canvas key."""

import logging

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException, InvalidAccessToken, Unauthorized

from config.settings import CANVAS_URL

logger = logging.getLogger(__name__)


def canvas_healthcheck(api_key: str) -> bool | None:
    """True if Canvas accepts the key, False if it rejects it, None if Canvas couldn't be checked."""

    try:
        Canvas(CANVAS_URL, api_key).get_current_user()
        return True
    except (InvalidAccessToken, Unauthorized):
        logger.warning("Canvas healthcheck rejected an API key")
        return False
    except CanvasException:
        logger.exception("Canvas healthcheck failed")
        return None
    except Exception:
        logger.exception("Unexpected Canvas healthcheck failure")
        return None
