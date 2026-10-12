import asyncio
import html
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db.service_credentials import set_service_secret
from hermione.canvas import UpcomingAssignment, canvas_healthcheck
from hermione.config import DIGEST_WINDOW_DAYS, DISPLAY_TIMEZONE
from hermione.nusmods import Lesson

from .client import monday_bot
from .messages import send_message

logger = logging.getLogger(__name__)

AWAITING_CANVAS_API_KEY = 1

AUTH_PROMPT_TEXT = (
    "🔐 <b>Connect Hermione to Canvas</b>\n\n"
    "Paste your Canvas API key to continue.\n\n"
    "<b>Where to find it? </b> \n Canvas → Account → Settings → Approved Integrations → New Access Token\n\n"
    "Your token is encrypted safely before being stored and is never exposed in plaintext.\n\n"
    "Use /cancel to cancel authentication flow."
)
CHECKING_KEY_TEXT = "Validating your Canvas API key…"
INVALID_KEY_TEXT = (
    "⚠️ <b>That Canvas API key didn't work.</b>\n\n"
    "Please try again with another key, or use /cancel to stop the authentication process."
)
CANVAS_UNAVAILABLE_TEXT = (
    "⚠️ <b>Couldn't reach Canvas to check your key.</b>\n\n"
    "Please send it again in a moment, or use /cancel to stop the authentication process."
)
SERVICE_STATE_FAILED_TEXT = (
    "⚠️ <b>Your Canvas Key was valid but we couldn't save it</b>\n\n"
    "Please try again in a moment."
)
ENABLED_TEXT = (
    "<b>Hermione authenticated.</b> Your key will be valid for the next 3 months."
)
CANCELLED_TEXT = "Hermione authentication flow cancelled."


async def prompt_canvas_auth(update: Update) -> None:
    if update.message is not None:
        await update.message.reply_text(AUTH_PROMPT_TEXT, parse_mode="HTML")


async def receive_canvas_api_key(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    del context

    if update.message is None or update.effective_user is None:
        return ConversationHandler.END

    api_key = (update.message.text or "").strip()
    if not api_key:
        await update.message.reply_text(INVALID_KEY_TEXT, parse_mode="HTML")
        return AWAITING_CANVAS_API_KEY

    await update.message.reply_text(CHECKING_KEY_TEXT)
    is_valid = await asyncio.to_thread(canvas_healthcheck, api_key)
    if is_valid is None:
        logger.error(
            "Could not verify Canvas key for user %s; asked them to retry",
            update.effective_user.id,
        )
        await update.message.reply_text(CANVAS_UNAVAILABLE_TEXT, parse_mode="HTML")
        return AWAITING_CANVAS_API_KEY

    if not is_valid:
        await update.message.reply_text(INVALID_KEY_TEXT, parse_mode="HTML")
        return AWAITING_CANVAS_API_KEY

    if not set_service_secret(update.effective_user.id, "hermione", api_key):
        await update.message.reply_text(SERVICE_STATE_FAILED_TEXT, parse_mode="HTML")
        return ConversationHandler.END

    await update.message.reply_text(ENABLED_TEXT, parse_mode="HTML")
    return ConversationHandler.END


async def cancel_hermione_auth(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    del context
    if update.message is not None:
        await update.message.reply_text(CANCELLED_TEXT)
    return ConversationHandler.END


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
        f"Rise and shine {html.escape(username)} ☀️!"
        if username
        else "Rise and shine ☀️!"
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
