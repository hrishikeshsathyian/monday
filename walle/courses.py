"""Wall-E's course lookups, built on the shared Canvas integration."""

from integrations.canvas import Course, get_active_courses


def get_selectable_courses(api_key: str) -> list[Course] | None:
    """The courses a user can pick in Wall-E: their active Canvas courses.

    Raises InvalidAccessToken if Canvas rejects the key, so the caller can ask
    the user to reconnect Canvas instead of retrying.
    """

    return get_active_courses(api_key)
