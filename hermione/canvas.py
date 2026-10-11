"""Canvas API operations used by Hermione."""

import logging

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

from config.settings import CANVAS_URL

logger = logging.getLogger(__name__)


def canvas_healthcheck(api_key: str) -> bool:
    try:
        Canvas(CANVAS_URL, api_key).get_current_user()
        return True
    except CanvasException:
        logger.warning("Canvas healthcheck rejected an API key")
        return False
    except Exception:
        logger.exception("Unexpected Canvas healthcheck failure")
        return False


def get_active_course_names(api_key: str) -> list[str] | None:

    try:
        courses = Canvas(CANVAS_URL, api_key).get_courses(enrollment_state="active")
        result = [f"{course.name}" for course in courses]
        return result

    except CanvasException:
        logger.warning("Canvas rejected a stored Hermione credential")
        return None

    except Exception:
        logger.exception("Unexpected Canvas course lookup failure")
        return None
