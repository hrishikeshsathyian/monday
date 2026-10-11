"""Canvas API operations used by Hermione."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from canvasapi import Canvas
from canvasapi.assignment import Assignment
from canvasapi.exceptions import CanvasException

from config.settings import CANVAS_URL

from .digest import build_digest
from .models import TodoDigest, TodoItem

logger = logging.getLogger(__name__)

SGT = ZoneInfo("Asia/Singapore")
NON_WORK_SUBMISSION_TYPES = {"none", "not_graded", "on_paper"}


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


def get_todo_digest(api_key: str) -> TodoDigest | None:
    """Collect assignments and quizzes from every active course into a digest."""

    try:
        courses = list(
            Canvas(CANVAS_URL, api_key).get_courses(enrollment_state="active")
        )
    except CanvasException:
        logger.warning("Canvas rejected a stored Hermione credential")
        return None
    except Exception:
        logger.exception("Unexpected Canvas course lookup failure")
        return None

    items: list[TodoItem] = []
    for course in courses:
        try:
            assignments = list(
                course.get_assignments(include=["submission"], order_by="due_at")
            )
        except Exception:
            # One broken course should not hide the rest of the digest.
            logger.exception("Could not load assignments for course %s", course.id)
            continue

        for assignment in assignments:
            item = _to_todo_item(course.name, assignment)
            if item is not None:
                items.append(item)

    return build_digest(items, datetime.now(SGT))


def _to_todo_item(course_name: str, assignment: Assignment) -> TodoItem | None:
    """Map one Canvas assignment to a TodoItem, or None if students can't see it or it needs no work."""

    if getattr(assignment, "published", True) is False:
        return None

    submission_types = set(getattr(assignment, "submission_types", None) or [])
    if submission_types <= NON_WORK_SUBMISSION_TYPES:
        return None

    is_quiz = (
        "online_quiz" in submission_types
        or bool(getattr(assignment, "is_quiz_assignment", False))
        or bool(getattr(assignment, "is_quiz_lti_assignment", False))
    )

    due_raw = getattr(assignment, "due_at", None)
    submission = getattr(assignment, "submission", None) or {}

    return TodoItem(
        kind="quiz" if is_quiz else "assignment",
        title=assignment.name,
        course_name=course_name,
        due_at=datetime.fromisoformat(due_raw).astimezone(SGT) if due_raw else None,
        url=getattr(assignment, "html_url", ""),
        points=getattr(assignment, "points_possible", None),
        submitted=submission.get("submitted_at") is not None,
        missing=bool(submission.get("missing")),
        late=bool(submission.get("late")),
        excused=bool(submission.get("excused")),
    )
