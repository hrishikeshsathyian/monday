"""Telegram side of Wall-E: pick a Canvas course, then receive its files."""

import asyncio
import html
import logging
from enum import Enum, auto

from canvasapi.exceptions import InvalidAccessToken
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.text_presets import (
    WALLE_CANVAS_UNAVAILABLE_TEXT,
    WALLE_KEY_LOAD_FAILED_TEXT,
    WALLE_KEY_REJECTED_TEXT,
    WALLE_NO_COURSES_TEXT,
    WALLE_PICKER_TEXT,
)
from db.user_credentials import get_credential
from walle.courses import Course, get_selectable_courses

logger = logging.getLogger(__name__)

# Course buttons carry "walle:<course id>:<course code>" so a tap needs no extra lookup.
COURSE_CALLBACK_PREFIX = "walle:"
COURSE_CALLBACK_PATTERN = rf"^{COURSE_CALLBACK_PREFIX}\d+:"
COURSE_BUTTONS_PER_ROW = 2


class CoursePickerResult(Enum):
    SHOWN = auto()  # the user got the course list (or was told they have none)
    FAILED = auto()  # the user was told something went wrong
    KEY_REJECTED = auto()  # Canvas rejected the stored key; the user must reconnect


async def send_course_picker(update: Update) -> CoursePickerResult:
    message, user = update.message, update.effective_user
    if message is None or user is None:
        return CoursePickerResult.FAILED

    api_key = get_credential(user.id, "canvas")
    if api_key is None:
        logger.error(
            f"Not showing Wall-E courses to user {user.id} (@{user.username}): could not load their Canvas key"
        )
        await message.reply_text(WALLE_KEY_LOAD_FAILED_TEXT, parse_mode="HTML")
        return CoursePickerResult.FAILED

    try:
        courses = await asyncio.to_thread(get_selectable_courses, api_key)
    except InvalidAccessToken:
        logger.warning(
            f"Canvas rejected the key for user {user.id} (@{user.username}); asking them to reconnect"
        )
        await message.reply_text(WALLE_KEY_REJECTED_TEXT, parse_mode="HTML")
        return CoursePickerResult.KEY_REJECTED

    if courses is None:
        logger.error(
            f"Not showing Wall-E courses to user {user.id} (@{user.username}): could not load their courses"
        )
        await message.reply_text(WALLE_CANVAS_UNAVAILABLE_TEXT, parse_mode="HTML")
        return CoursePickerResult.FAILED

    if not courses:
        await message.reply_text(WALLE_NO_COURSES_TEXT, parse_mode="HTML")
        return CoursePickerResult.SHOWN

    await message.reply_text(
        WALLE_PICKER_TEXT, parse_mode="HTML", reply_markup=_course_keyboard(courses)
    )
    return CoursePickerResult.SHOWN


async def handle_course_selected(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle a tap on one of the course buttons."""

    query = update.callback_query
    if query is None or query.data is None:
        return

    # Stops the button's loading spinner.
    await query.answer()

    course_id, course_code = query.data.removeprefix(COURSE_CALLBACK_PREFIX).split(
        ":", 1
    )
    logger.info(
        f"User {query.from_user.id} picked course {course_code} ({course_id}) in Wall-E"
    )

    # Downloading and zipping the course's files comes in the next step.
    await query.edit_message_text(
        f"📦 <b>{html.escape(course_code)}</b> selected.", parse_mode="HTML"
    )


def _course_keyboard(courses: list[Course]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(course.code, callback_data=_course_callback_data(course))
        for course in courses
    ]
    return InlineKeyboardMarkup(
        [
            buttons[i : i + COURSE_BUTTONS_PER_ROW]
            for i in range(0, len(buttons), COURSE_BUTTONS_PER_ROW)
        ]
    )


def _course_callback_data(course: Course) -> str:
    # Telegram rejects callback data over 64 bytes, so long course codes are cut short.
    data = f"{COURSE_CALLBACK_PREFIX}{course.id}:{course.code}".encode()
    return data[:64].decode(errors="ignore")
