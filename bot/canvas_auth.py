"""Conversation for connecting a user's Canvas account, shared by every Canvas service.

This flow only verifies and saves the key; the caller decides which service to
enable once Canvas is connected.
"""

import asyncio
import logging
from enum import Enum, auto

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db.user_credentials import set_credential
from integrations.canvas import canvas_healthcheck

logger = logging.getLogger(__name__)

AWAITING_CANVAS_API_KEY = 1


class CanvasAuthResult(Enum):
    CONNECTED = auto()  # key verified and saved
    RETRY = auto()  # key rejected or couldn't be checked; wait for another
    FAILED = auto()  # flow ends without a saved key


AUTH_PROMPT_TEXT = (
    "🔐 <b>Connect Monday to Canvas</b>\n\n"
    "Paste your Canvas API key to continue. Monday's Canvas services all share this key.\n\n"
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
SAVE_FAILED_TEXT = (
    "⚠️ <b>Your Canvas Key was valid but we couldn't save it</b>\n\n"
    "Please try again in a moment."
)
CONNECTED_TEXT = (
    "✅ <b>Canvas connected.</b> Your Canvas key will be valid for the next 3 months."
)
CANCELLED_TEXT = "Canvas authentication flow cancelled."


async def prompt_canvas_auth(update: Update) -> None:
    if update.message is not None:
        await update.message.reply_text(AUTH_PROMPT_TEXT, parse_mode="HTML")


async def receive_canvas_api_key(update: Update) -> CanvasAuthResult:
    if update.message is None or update.effective_user is None:
        return CanvasAuthResult.FAILED

    api_key = (update.message.text or "").strip()
    if not api_key:
        await update.message.reply_text(INVALID_KEY_TEXT, parse_mode="HTML")
        return CanvasAuthResult.RETRY

    await update.message.reply_text(CHECKING_KEY_TEXT)
    is_valid = await asyncio.to_thread(canvas_healthcheck, api_key)
    if is_valid is None:
        logger.error(
            "Could not verify Canvas key for user %s (@%s); asked them to retry",
            update.effective_user.id,
            update.effective_user.username,
        )
        await update.message.reply_text(CANVAS_UNAVAILABLE_TEXT, parse_mode="HTML")
        return CanvasAuthResult.RETRY

    if not is_valid:
        await update.message.reply_text(INVALID_KEY_TEXT, parse_mode="HTML")
        return CanvasAuthResult.RETRY

    if not set_credential(update.effective_user.id, "canvas", api_key):
        logger.error(
            "Ending Canvas auth for user %s (@%s): could not save their verified key",
            update.effective_user.id,
            update.effective_user.username,
        )
        await update.message.reply_text(SAVE_FAILED_TEXT, parse_mode="HTML")
        return CanvasAuthResult.FAILED

    await update.message.reply_text(CONNECTED_TEXT, parse_mode="HTML")
    return CanvasAuthResult.CONNECTED


async def cancel_canvas_auth(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    del context
    if update.message is not None:
        await update.message.reply_text(CANCELLED_TEXT)
    return ConversationHandler.END
