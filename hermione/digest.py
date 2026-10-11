"""Pure bucketing for Hermione's todo digest. No network, no Telegram."""

from datetime import datetime, timedelta

from .models import TodoDigest, TodoItem

WEEK = timedelta(days=7)


def build_digest(items: list[TodoItem], now: datetime) -> TodoDigest:
    """Split items into this week's todos, overdue ones, and undated unsubmitted work.

    Overdue follows Canvas's own `missing` flag, which is what the dashboard shows.
    Undated work has no deadline to place, so it gets its own list.
    """

    due_this_week: list[TodoItem] = []
    overdue: list[TodoItem] = []
    no_due_date: list[TodoItem] = []

    for item in items:
        if item.excused:
            continue

        if item.due_at is None:
            if not item.submitted:
                no_due_date.append(item)
        elif now <= item.due_at < now + WEEK:
            due_this_week.append(item)
        elif item.due_at < now and item.missing and not item.submitted:
            overdue.append(item)

    due_this_week.sort(key=lambda item: item.due_at)
    overdue.sort(key=lambda item: item.due_at, reverse=True)
    no_due_date.sort(key=lambda item: (item.course_name, item.title))
    return TodoDigest(
        due_this_week=due_this_week,
        overdue=overdue,
        no_due_date=no_due_date,
    )
