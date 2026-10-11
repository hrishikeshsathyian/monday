import asyncio
import html
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.client import mondaybot
from bot.messages import MAX_MESSAGE_LENGTH, send_message
from db.service_credentials import set_service_secret
from hermione.canvas import canvas_healthcheck
from hermione.models import TodoDigest, TodoItem

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
    if not await asyncio.to_thread(canvas_healthcheck, api_key):
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


async def send_todo_digest(chat_id: str, digest: TodoDigest) -> None:
    """Send a user's Canvas todo digest privately through the Monday bot."""

    for text in _format_todo_digest(digest):
        await send_message(chat_id=chat_id, text=text, bot=mondaybot)


def _format_todo_digest(digest: TodoDigest) -> list[str]:
    """Build digest lines, then pack them into messages under Telegram's length limit."""

    if not (digest.due_this_week or digest.overdue or digest.no_due_date):
        return ["📚 <b>Your Canvas todos</b>\n\nNothing due this week 🎉"]

    lines = ["📚 <b>Your Canvas todos</b>"]

    if digest.overdue:
        lines += ["", "⚠️ <b>Overdue</b>"]
        lines += [
            _format_item(item, f"{item.due_at:%a %d %b %H:%M}")
            for item in digest.overdue
        ]

    if digest.due_this_week:
        lines += ["", "📅 <b>Due this week</b>"]
        current_day: date | None = None
        for item in digest.due_this_week:
            if item.due_at is None:
                continue
            if item.due_at.date() != current_day:
                current_day = item.due_at.date()
                lines.append(f"\n<b>{current_day:%a %d %b}</b>")
            lines.append(_format_item(item, f"{item.due_at:%H:%M}"))

    if digest.no_due_date:
        lines += ["", "🗓 <b>No due date</b>"]
        lines += [_format_item(item) for item in digest.no_due_date]

    return _pack_lines(lines, MAX_MESSAGE_LENGTH)


def _format_item(item: TodoItem, when: str | None = None) -> str:
    status = "✅" if item.submitted else "⬜"
    kind = "🧪" if item.kind == "quiz" else "📝"
    late = " 🕒 late" if item.late else ""
    detail = f" · {when}" if when else ""
    title = html.escape(item.title)
    if item.url:
        title = f'<a href="{html.escape(item.url)}">{title}</a>'
    course = html.escape(item.course_name)
    return f"{status} {kind} {title} · {course}{detail}{late}"


def _pack_lines(lines: list[str], limit: int) -> list[str]:
    messages: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            messages.append(current)
            current = line
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages
