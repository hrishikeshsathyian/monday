"""Telegram side of Wall-E: pick a Canvas course, then receive its files as a zip."""

import asyncio
import contextlib
import html
import logging
import tempfile
from enum import Enum, auto
from pathlib import Path

from canvasapi.exceptions import InvalidAccessToken
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.text_presets import (
    WALLE_CANVAS_UNAVAILABLE_TEXT,
    WALLE_DOWNLOADING_TEXT,
    WALLE_FETCH_BUSY_TEXT,
    WALLE_FETCH_FAILED_TEXT,
    WALLE_FETCH_KEY_REJECTED_TEXT,
    WALLE_FETCHING_TEXT,
    WALLE_KEY_LOAD_FAILED_TEXT,
    WALLE_KEY_REJECTED_TEXT,
    WALLE_LINK_BUTTON_TEXT,
    WALLE_LINK_READY_TEXT,
    WALLE_LINKING_TEXT,
    WALLE_NO_COURSES_TEXT,
    WALLE_NO_FILES_TEXT,
    WALLE_PICKER_TEXT,
    WALLE_SENT_TEXT,
    WALLE_TOO_BIG_TEXT,
    WALLE_UPLOADING_TEXT,
    WALLE_ZIP_CAPTION_TEXT,
    WALLE_ZIPPING_TEXT,
)
from db.user_credentials import get_credential
from walle.config import (
    MAX_COURSE_DOWNLOAD_BYTES,
    MAX_TELEGRAM_ZIP_BYTES,
    PROGRESS_UPDATE_SECONDS,
    ZIP_LINK_EXPIRY_SECONDS,
    ZIP_UPLOAD_TIMEOUT_SECONDS,
)
from walle.course_zip import (
    CourseZip,
    CourseZipStatus,
    FetchPhase,
    FetchProgress,
    build_course_zip,
)
from walle.courses import Course, get_selectable_courses
from walle.zip_link import get_zip_download_link

logger = logging.getLogger(__name__)

# Course buttons carry "walle:<course id>:<course code>" so a tap needs no extra lookup.
COURSE_CALLBACK_PREFIX = "walle:"
COURSE_CALLBACK_PATTERN = rf"^{COURSE_CALLBACK_PREFIX}\d+:"
COURSE_BUTTONS_PER_ROW = 2
PROGRESS_BAR_WIDTH = 10

# user_data key set while one of the user's courses is being fetched, so a second
# tap doesn't start another download.
FETCH_IN_PROGRESS = "walle_fetch_in_progress"


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
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle a tap on a course button: send the course's files as one zip."""

    query = update.callback_query
    chat = update.effective_chat
    if query is None or query.data is None or chat is None or context.user_data is None:
        return

    # Checked and set with no await in between, so two quick taps can't both pass.
    if context.user_data.get(FETCH_IN_PROGRESS):
        await query.answer(WALLE_FETCH_BUSY_TEXT, show_alert=True)
        return
    context.user_data[FETCH_IN_PROGRESS] = True

    try:
        # Stops the button's loading spinner.
        await query.answer()

        course_id, course_code = query.data.removeprefix(COURSE_CALLBACK_PREFIX).split(
            ":", 1
        )
        logger.info(
            f"User {query.from_user.id} (@{query.from_user.username}) picked course {course_code} ({course_id}) in Wall-E"
        )
        await _send_course_zip(
            query, context, chat.id, query.from_user, int(course_id), course_code
        )
    finally:
        context.user_data.pop(FETCH_IN_PROGRESS, None)


async def _send_course_zip(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user: User,
    course_id: int,
    course_code: str,
) -> None:
    """Download, zip and send one course, keeping the user posted in the picker message."""

    code = html.escape(course_code)
    await query.edit_message_text(
        WALLE_FETCHING_TEXT.format(course_code=code), parse_mode="HTML"
    )

    api_key = get_credential(user.id, "canvas")
    if api_key is None:
        logger.error(
            f"Not fetching {course_code} for user {user.id} (@{user.username}): could not load their Canvas key"
        )
        await query.edit_message_text(WALLE_KEY_LOAD_FAILED_TEXT, parse_mode="HTML")
        return

    # The downloads and the zip are deleted as soon as the zip has been sent.
    with tempfile.TemporaryDirectory(prefix="walle-") as workdir:
        progress = FetchProgress()
        reporter = asyncio.create_task(_report_progress(query, code, progress))
        try:
            # canvasapi and the downloads are blocking; to_thread keeps the bot responsive.
            course_zip = await asyncio.to_thread(
                build_course_zip,
                api_key,
                course_id,
                course_code,
                Path(workdir),
                progress,
            )
        except InvalidAccessToken:
            logger.warning(
                f"Canvas rejected the key for user {user.id} (@{user.username}) while fetching {course_code}; asked them to reconnect with /walle"
            )
            await query.edit_message_text(
                WALLE_FETCH_KEY_REJECTED_TEXT, parse_mode="HTML"
            )
            return
        finally:
            # Waited on so a late progress edit can't overwrite the messages below.
            reporter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reporter

        if course_zip is None:
            logger.error(
                f"Not sending {course_code} to user {user.id} (@{user.username}): could not download all of its files"
            )
            await query.edit_message_text(
                WALLE_FETCH_FAILED_TEXT.format(course_code=code), parse_mode="HTML"
            )
            return

        if course_zip.status is CourseZipStatus.NO_FILES:
            await query.edit_message_text(
                WALLE_NO_FILES_TEXT.format(course_code=code), parse_mode="HTML"
            )
            return

        if course_zip.status is CourseZipStatus.TOO_BIG:
            logger.info(
                f"Not fetching {course_code} for user {user.id} (@{user.username}): its files add up to more than {MAX_COURSE_DOWNLOAD_BYTES / 1_000_000:.0f} MB"
            )
            await query.edit_message_text(
                WALLE_TOO_BIG_TEXT.format(
                    course_code=code, limit_mb=MAX_COURSE_DOWNLOAD_BYTES / 1_000_000
                ),
                parse_mode="HTML",
            )
            return

        size_mb = course_zip.size_bytes / 1_000_000
        if course_zip.size_bytes > MAX_TELEGRAM_ZIP_BYTES:
            logger.info(
                f"Built {course_code} zip ({course_zip.file_count} files, {size_mb:.1f} MB) for user {user.id} (@{user.username}); sending it as an R2 link"
            )
            await _send_zip_link(query, user, course_code, course_zip)
            return

        logger.info(
            f"Built {course_code} zip ({course_zip.file_count} files, {size_mb:.1f} MB) for user {user.id} (@{user.username}); sending it through Telegram"
        )
        await query.edit_message_text(
            WALLE_UPLOADING_TEXT.format(course_code=code), parse_mode="HTML"
        )
        if not await _upload_zip(context, chat_id, user, course_code, course_zip):
            await query.edit_message_text(
                WALLE_FETCH_FAILED_TEXT.format(course_code=code), parse_mode="HTML"
            )
            return

    await query.edit_message_text(
        WALLE_SENT_TEXT.format(course_code=code, file_count=course_zip.file_count),
        parse_mode="HTML",
    )


async def _send_zip_link(
    query: CallbackQuery,
    user: User,
    course_code: str,
    course_zip: CourseZip,
) -> None:
    """Upload the zip to R2 and replace the status message with a download button."""

    code = html.escape(course_code)
    size_mb = course_zip.size_bytes / 1_000_000
    if course_zip.path is None:
        return

    await query.edit_message_text(
        WALLE_LINKING_TEXT.format(course_code=code, size_mb=size_mb), parse_mode="HTML"
    )
    # boto3 is blocking; to_thread keeps the bot responsive.
    url = await asyncio.to_thread(get_zip_download_link, course_zip.path)
    if url is None:
        logger.error(
            f"Not sending {course_code} link to user {user.id} (@{user.username}): could not upload the zip to R2"
        )
        await query.edit_message_text(
            WALLE_FETCH_FAILED_TEXT.format(course_code=code), parse_mode="HTML"
        )
        return

    await query.edit_message_text(
        WALLE_LINK_READY_TEXT.format(
            course_code=code,
            file_count=course_zip.file_count,
            size_mb=size_mb,
            hours=ZIP_LINK_EXPIRY_SECONDS // 3600,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        WALLE_LINK_BUTTON_TEXT.format(filename=course_zip.path.name),
                        url=url,
                    )
                ]
            ]
        ),
    )
    logger.info(
        f"Sent {course_code} zip link ({course_zip.file_count} files, {size_mb:.1f} MB) to user {user.id} (@{user.username})"
    )


async def _upload_zip(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user: User,
    course_code: str,
    course_zip: CourseZip,
) -> bool:
    """Send the zip as a document. False if Telegram didn't accept it."""

    if course_zip.path is None:
        return False

    try:
        with course_zip.path.open("rb") as document:
            await context.bot.send_document(
                chat_id=chat_id,
                document=document,
                filename=course_zip.path.name,
                caption=WALLE_ZIP_CAPTION_TEXT.format(
                    course_code=html.escape(course_code),
                    file_count=course_zip.file_count,
                ),
                parse_mode="HTML",
                write_timeout=ZIP_UPLOAD_TIMEOUT_SECONDS,
                read_timeout=ZIP_UPLOAD_TIMEOUT_SECONDS,
            )
    except TelegramError:
        logger.error(
            f"Failed to send {course_code} zip to user {user.id} (@{user.username})",
            exc_info=True,
        )
        return False

    logger.info(
        f"Sent {course_code} zip ({course_zip.file_count} files) to user {user.id} (@{user.username})"
    )
    return True


async def _report_progress(
    query: CallbackQuery, course_code: str, progress: FetchProgress
) -> None:
    """Keep the status message showing how far the fetch has got, until cancelled."""

    shown = None
    while True:
        await asyncio.sleep(PROGRESS_UPDATE_SECONDS)
        text = _progress_text(course_code, progress)
        # Telegram rejects an edit that doesn't change the text.
        if text is None or text == shown:
            continue
        try:
            await query.edit_message_text(text, parse_mode="HTML")
            shown = text
        except TelegramError:
            # A missed update is harmless; the next one catches up.
            pass


def _progress_text(course_code: str, progress: FetchProgress) -> str | None:
    """The status message for the fetch's current phase; None while still listing files."""

    if progress.phase is FetchPhase.ZIPPING:
        return WALLE_ZIPPING_TEXT.format(course_code=course_code)
    if progress.phase is not FetchPhase.DOWNLOADING or not progress.total_bytes:
        return None

    # Canvas's listed sizes can be slightly off, so never show more than 100%.
    fraction = min(progress.done_bytes / progress.total_bytes, 1)
    filled = int(fraction * PROGRESS_BAR_WIDTH)
    return WALLE_DOWNLOADING_TEXT.format(
        course_code=course_code,
        bar="▓" * filled + "░" * (PROGRESS_BAR_WIDTH - filled),
        percent=round(fraction * 100),
        done_mb=progress.done_bytes / 1_000_000,
        total_mb=progress.total_bytes / 1_000_000,
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
