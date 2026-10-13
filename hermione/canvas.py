"""Canvas API operations used by Hermione."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from canvasapi import Canvas
from canvasapi.assignment import Assignment
from canvasapi.exceptions import CanvasException

from config.settings import CANVAS_URL

from .config import DIGEST_WINDOW_DAYS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpcomingAssignment:
    course_code: str
    name: str
    url: str
    due_at: datetime
    is_quiz: bool
    is_submitted: bool


def get_upcoming_assignments(api_key: str) -> list[UpcomingAssignment] | None:
    """Assignments and quizzes due within the digest window, soonest first."""

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=DIGEST_WINDOW_DAYS)

    try:
        upcoming = []
        for course in Canvas(CANVAS_URL, api_key).get_courses(
            enrollment_state="active"
        ):
            # The "future" bucket excludes overdue work but still includes undated
            # items, which are filtered out below.
            for assignment in course.get_assignments(
                bucket="future", include=["submission"]
            ):
                due_at = getattr(assignment, "due_at_date", None)
                if due_at is None or not now < due_at <= window_end:
                    continue

                upcoming.append(
                    UpcomingAssignment(
                        course_code=course.course_code,
                        name=assignment.name,
                        url=assignment.html_url,
                        due_at=due_at,
                        is_quiz="online_quiz" in assignment.submission_types,
                        is_submitted=_is_submitted(assignment),
                    )
                )

    except CanvasException:
        logger.exception("Canvas assignment lookup failed")
        return None

    except Exception:
        logger.exception("Unexpected Canvas assignment lookup failure")
        return None

    return sorted(upcoming, key=lambda assignment: assignment.due_at)


def get_class_groups(api_key: str) -> dict[str, list[str]] | None:
    """Course code -> the user's section names, e.g. {"CS3210": ["T02", "L1"]}."""

    try:
        courses = Canvas(CANVAS_URL, api_key).get_courses(
            enrollment_state="active", include=["sections"]
        )
        # Section names look like "T02 (CS3210)"; only the leading group is needed.
        return {
            course.course_code: [
                section["name"].split()[0]
                for section in getattr(course, "sections", [])
                if section.get("name")
            ]
            for course in courses
        }

    except CanvasException:
        logger.exception("Canvas section lookup failed")
        return None

    except Exception:
        logger.exception("Unexpected Canvas section lookup failure")
        return None


def _is_submitted(assignment: Assignment) -> bool:
    # Some courses omit the submission object entirely until the student submits.
    submission = getattr(assignment, "submission", None)
    return submission is not None and submission.get("workflow_state") != "unsubmitted"
