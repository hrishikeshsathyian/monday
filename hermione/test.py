"""Upcoming Canvas deadlines + submission status."""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

from config.settings import CANVAS_API_KEY as API_KEY

CANVAS_URL = "https://canvas.nus.edu.sg"
SGT = ZoneInfo("Asia/Singapore")


def parse(dt: str | None) -> datetime | None:
    return datetime.fromisoformat(dt.replace("Z", "+00:00")) if dt else None


def kind(a) -> str:
    if getattr(a, "is_quiz_assignment", False) or getattr(a, "is_quiz_lti_assignment", False):
        return "quiz"
    return "assignment"


def status(sub: dict) -> str:
    if sub.get("excused"):
        return "excused"
    if sub.get("missing"):
        return "MISSING"
    state = sub.get("workflow_state", "unsubmitted")
    if state == "unsubmitted":
        return "not submitted"
    return f"{state}, late" if sub.get("late") else state


def main() -> None:
    canvas = Canvas(CANVAS_URL, API_KEY)
    now = datetime.now(timezone.utc)
    window_start, window_end = now - timedelta(days=7), now + timedelta(days=14)
    rows = []

    for course in canvas.get_courses(enrollment_state="active"):
        course_name = getattr(course, "name", f"Course {course.id}")
        try:
            for a in course.get_assignments(include=["submission"]):
                due = parse(a.due_at)
                if not due or not (window_start <= due <= window_end):
                    continue
                sub = getattr(a, "submission", None) or {}
                rows.append((due, course_name, a.name, kind(a), status(sub)))
        except CanvasException as e:
            print(f"skip {course_name}: {e}")

    rows.sort()
    for due, course_name, title, k, st in rows:
        print(f"{due.astimezone(SGT):%a %d %b %H:%M}  {k:<10}  [{st:<14}]  {course_name}: {title}")


if __name__ == "__main__":
    main()
