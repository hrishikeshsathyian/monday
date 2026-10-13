"""Hermione's assignment lookups, built on the shared Canvas integration."""

from integrations.canvas import UpcomingAssignment, get_upcoming_assignments

from .config import DIGEST_WINDOW_DAYS


def get_digest_assignments(api_key: str) -> list[UpcomingAssignment] | None:
    """Assignments and quizzes due within the digest window, soonest first."""

    return get_upcoming_assignments(api_key, DIGEST_WINDOW_DAYS)
