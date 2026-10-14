"""Every Canvas API call Monday makes.

Services call these functions with the user's API key. This module never imports
from a service, so anything service-specific (e.g. how far ahead to look) is
passed in as an argument.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from canvasapi import Canvas
from canvasapi.assignment import Assignment
from canvasapi.course import Course as CanvasCourse
from canvasapi.exceptions import (
    CanvasException,
    Forbidden,
    InvalidAccessToken,
    Unauthorized,
)

from config.settings import CANVAS_URL

logger = logging.getLogger(__name__)

# Seconds to wait for Canvas to start sending (or keep sending) a file download.
FILE_DOWNLOAD_TIMEOUT_SECONDS = 60


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


@dataclass(frozen=True)
class CourseFile:
    id: int
    name: str
    folder: str
    size: int
    download_url: str


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _client(api_key: str) -> Canvas:
    """A Canvas API client authenticated with the user's key."""

    return Canvas(CANVAS_URL, api_key)


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
    """The user's active courses, sorted by course code; None if the lookup failed.

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
    """Course code -> the user's section names, e.g. {"CS3210": ["T02", "L1"]}.

    None if the lookup failed.
    """

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
    """Assignments and quizzes due in the next `within_days` days, soonest first.

    None if the lookup failed.
    """

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
    """Whether the student has submitted the assignment."""

    # Some courses omit the submission object entirely until the student submits.
    submission = getattr(assignment, "submission", None)
    return submission is not None and submission.get("workflow_state") != "unsubmitted"


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def get_course_files(api_key: str, course_id: int) -> list[CourseFile] | None:
    """Every file the user can download from the course; None if the lookup failed.

    Reads the course's Files section, or its Modules when the course hides Files.
    Raises InvalidAccessToken if Canvas rejects the key, so the caller can ask
    the user to reconnect Canvas instead of retrying.
    """

    try:
        course = _client(api_key).get_course(course_id)
        try:
            files = _files_from_files_section(course)
        except (Forbidden, Unauthorized):
            # Many courses hide the Files section but still share files in Modules.
            try:
                files = _files_from_modules(course)
            except (Forbidden, Unauthorized):
                # Canvas refusing both is a definite "nothing shared", not a failed lookup.
                files = []

    except InvalidAccessToken:
        raise

    except CanvasException:
        logger.exception(f"Canvas file lookup failed for course {course_id}")
        return None

    except Exception:
        logger.exception(
            f"Unexpected Canvas file lookup failure for course {course_id}"
        )
        return None

    return files


def download_course_file(
    api_key: str,
    file: CourseFile,
    destination: Path,
    on_bytes: Callable[[int], None] | None = None,
) -> bool:
    """Stream one file to `destination` without holding it in memory.

    `on_bytes` is called with the size of each chunk written, for progress.
    False if the download failed.
    """

    try:
        with requests.get(
            file.download_url,
            headers={"Authorization": f"Bearer {api_key}"},
            stream=True,
            timeout=FILE_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    out.write(chunk)
                    if on_bytes is not None:
                        on_bytes(len(chunk))

    except (requests.RequestException, OSError):
        logger.exception(f"Canvas download failed for file {file.id} ({file.name})")
        return False

    except Exception:
        logger.exception(
            f"Unexpected Canvas download failure for file {file.id} ({file.name})"
        )
        return False

    return True


def _files_from_files_section(course: CanvasCourse) -> list[CourseFile]:
    """Flat List Files in the course's Files section, each with its full folder path.

    a file's nesting is just its folder path,
    e.g. "Lecture Notes/Lecture One" this is just how we name the files' folders for now to recreate the nesting later.
    """

    # full_name looks like "course files/Lecture Notes/Lecture One"; only the root
    # "course files/" prefix is dropped, every deeper level is kept.
    folders = {
        folder.id: folder.full_name.partition("/")[2] for folder in course.get_folders()
    }
    return [
        _course_file(file, folders.get(file.folder_id, ""))
        for file in course.get_files()
        if _is_downloadable(file)
    ]


def _files_from_modules(course: CanvasCourse) -> list[CourseFile]:
    """Files linked from the course's Modules, foldered by module name.

    Modules don't nest, so each path is one level deep. A file linked from
    several modules is kept once.
    """

    files: dict[int, CourseFile] = {}
    for module in course.get_modules():
        for item in module.get_module_items():
            if item.type != "File" or item.content_id in files:
                continue
            file = course.get_file(item.content_id)
            if _is_downloadable(file):
                files[file.id] = _course_file(file, module.name)
    return list(files.values())


def _is_downloadable(file) -> bool:
    """Whether the user can download the file; locked or hidden files have no usable URL."""

    return bool(getattr(file, "url", "")) and not getattr(
        file, "locked_for_user", False
    )


def _course_file(file, folder: str) -> CourseFile:
    """A canvasapi File as a CourseFile stored under `folder`."""

    return CourseFile(
        id=file.id,
        name=file.display_name,
        folder=folder,
        size=file.size,
        download_url=file.url,
    )
