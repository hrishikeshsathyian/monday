"""Every Canvas API call Monday makes.

Services call these functions with the user's API key. This module never imports
from a service, so anything service-specific (e.g. how far ahead to look) is
passed in as an argument.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from canvasapi import Canvas
from canvasapi.assignment import Assignment
from canvasapi.exceptions import CanvasException, InvalidAccessToken, Unauthorized

from config.settings import CANVAS_URL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Course:
    id: int
    code: str
    name: str


@dataclass(frozen=True)
class UpcomingAssignment:
    course_code: str
    name: str
    url: str
    due_at: datetime
    is_quiz: bool
    is_submitted: bool


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def canvas_healthcheck(api_key: str) -> bool | None:
    """True if Canvas accepts the key, False if it rejects it, None if Canvas couldn't be checked."""

    try:
        _client(api_key).get_current_user()
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


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


def get_active_courses(api_key: str) -> list[Course] | None:
    """The user's active courses, sorted by course code.

    Raises InvalidAccessToken if Canvas rejects the key, so the caller can ask
    the user to reconnect Canvas instead of retrying.
    """

    try:
        courses = [
            Course(id=course.id, code=course.course_code, name=course.name)
            for course in _client(api_key).get_courses(enrollment_state="active")
            # Courses that haven't opened yet come back without a code or name.
            if not getattr(course, "access_restricted_by_date", False)
        ]

    except InvalidAccessToken:
        raise

    except CanvasException:
        logger.exception("Canvas course lookup failed")
        return None

    except Exception:
        logger.exception("Unexpected Canvas course lookup failure")
        return None

    return sorted(courses, key=lambda course: course.code)


def get_class_groups(api_key: str) -> dict[str, list[str]] | None:
    """Course code -> the user's section names, e.g. {"CS3210": ["T02", "L1"]}."""

    try:
        courses = _client(api_key).get_courses(
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


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


def get_upcoming_assignments(
    api_key: str, within_days: int
) -> list[UpcomingAssignment] | None:
    """Assignments and quizzes due in the next `within_days` days, soonest first."""

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=within_days)

    try:
        upcoming = []
        for course in _client(api_key).get_courses(enrollment_state="active"):
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


def _is_submitted(assignment: Assignment) -> bool:
    # Some courses omit the submission object entirely until the student submits.
    submission = getattr(assignment, "submission", None)
    return submission is not None and submission.get("workflow_state") != "unsubmitted"


def _client(api_key: str) -> Canvas:
    return Canvas(CANVAS_URL, api_key)
