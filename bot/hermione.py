"""All bot messaging functionality UNIQUE to Hermione Service"""

import html
from datetime import datetime

from hermione.assignments import UpcomingAssignment
from hermione.config import DIGEST_WINDOW_DAYS, DISPLAY_TIMEZONE
from hermione.nusmods import Lesson

from .client import monday_bot
from .messages import send_message


async def send_daily_digest(
    chat_id: int,
    username: str | None,
    assignments: list[UpcomingAssignment],
    classes: list[Lesson],
) -> bool:
    return await send_message(
        chat_id=str(chat_id),
        text=format_daily_digest(username, assignments, classes),
        bot=monday_bot,
    )


def format_daily_digest(
    username: str | None,
    assignments: list[UpcomingAssignment],
    classes: list[Lesson],
) -> str:
    greeting = (
        f"Rise and shine {html.escape(username)} ☀️🐓!"
        if username
        else "Rise and shine ☀️🐓!"
    )
    lines = [
        "<b>[Hermione] Daily Digest</b>",
        "",
        f"{greeting}",
    ]

    lines += ["", "🗓 <b>Today's classes</b>"]
    if classes:
        lines += [_class_line(lesson) for lesson in classes]
    else:
        lines.append("No classes today.")

    to_do = [assignment for assignment in assignments if not assignment.is_submitted]
    done = [assignment for assignment in assignments if assignment.is_submitted]

    lines += ["", f"⏳ <b>To do (next {DIGEST_WINDOW_DAYS} days)</b>"]
    if to_do:
        lines += [_assignment_line(assignment) for assignment in to_do]
    else:
        lines.append("You're all caught up")

    if done:
        lines += ["", "✅ <b>Done</b>"]
        lines += [_assignment_line(assignment) for assignment in done]

    return "\n".join(lines)


def _assignment_line(assignment: UpcomingAssignment) -> str:
    quiz_label = " (Quiz)" if assignment.is_quiz else ""
    return (
        f"• <b>{html.escape(assignment.course_code)}</b> "
        f'<a href="{html.escape(assignment.url, quote=True)}">{html.escape(assignment.name)}</a>{quiz_label}\n'
        f"   due {_format_due(assignment.due_at)}"
    )


def _class_line(lesson: Lesson) -> str:
    start = f"{lesson.start_time[:2]}:{lesson.start_time[2:]}"
    end = f"{lesson.end_time[:2]}:{lesson.end_time[2:]}"
    return f"• {start}–{end} | <b>{html.escape(lesson.module_code)}</b> {lesson.lesson_type} | {html.escape(lesson.venue)}"


def _format_due(due_at: datetime) -> str:
    local = due_at.astimezone(DISPLAY_TIMEZONE)
    hour = local.hour % 12 or 12
    return f"{local:%a} {local.day} {local:%b}, {hour}:{local:%M %p}"
