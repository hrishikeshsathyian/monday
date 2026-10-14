"""Conversation for connecting a user's Canvas account, shared by every Canvas service.

This flow only verifies and saves the key; the caller decides which service to
enable once Canvas is connected.
"""

import asyncio
import logging
from enum import Enum, auto

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.text_presets import (
    CANVAS_AUTH_CANCELLED_TEXT,
    CANVAS_AUTH_PROMPT_TEXT,
    CANVAS_CHECKING_KEY_TEXT,
    CANVAS_CONNECTED_TEXT,
    CANVAS_INVALID_KEY_TEXT,
    CANVAS_KEY_CHECK_UNAVAILABLE_TEXT,
    CANVAS_KEY_SAVE_FAILED_TEXT,
)
from db.user_credentials import set_credential
from integrations.canvas import canvas_healthcheck

logger = logging.getLogger(__name__)

AWAITING_CANVAS_API_KEY = 1

# user_data key remembering which service started the flow, so it can continue
# once Canvas is connected.
PENDING_SERVICE = "canvas_auth_pending_service"


class CanvasAuthResult(Enum):
    CONNECTED = auto()  # key verified and saved
    RETRY = auto()  # key rejected or couldn't be checked; wait for another
    FAILED = auto()  # flow ends without a saved key


async def prompt_canvas_auth(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    service: str,
) -> int:
    """Ask for a Canvas key on behalf of <service> and wait for the reply."""

    if context.user_data is not None:
        context.user_data[PENDING_SERVICE] = service
    if update.message is not None:
        await update.message.reply_text(CANVAS_AUTH_PROMPT_TEXT, parse_mode="HTML")
    return AWAITING_CANVAS_API_KEY


def pop_pending_service(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """The service that started the flow, cleared so it can't be reused."""

    if context.user_data is None:
        return None
    return context.user_data.pop(PENDING_SERVICE, None)


async def receive_canvas_api_key(update: Update) -> CanvasAuthResult:
    if update.message is None or update.effective_user is None:
        return CanvasAuthResult.FAILED

    api_key = (update.message.text or "").strip()
    if not api_key:
        await update.message.reply_text(CANVAS_INVALID_KEY_TEXT, parse_mode="HTML")
        return CanvasAuthResult.RETRY

    await update.message.reply_text(CANVAS_CHECKING_KEY_TEXT)
    is_valid = await asyncio.to_thread(canvas_healthcheck, api_key)
    if is_valid is None:
        logger.error(
            f"Could not verify Canvas key for user {update.effective_user.id} (@{update.effective_user.username}); asked them to retry"
        )
        await update.message.reply_text(
            CANVAS_KEY_CHECK_UNAVAILABLE_TEXT, parse_mode="HTML"
        )
        return CanvasAuthResult.RETRY

    if not is_valid:
        await update.message.reply_text(CANVAS_INVALID_KEY_TEXT, parse_mode="HTML")
        return CanvasAuthResult.RETRY

    if not set_credential(update.effective_user.id, "canvas", api_key):
        logger.error(
            f"Ending Canvas auth for user {update.effective_user.id} (@{update.effective_user.username}): could not save their verified key"
        )
        await update.message.reply_text(CANVAS_KEY_SAVE_FAILED_TEXT, parse_mode="HTML")
        return CanvasAuthResult.FAILED

    await update.message.reply_text(CANVAS_CONNECTED_TEXT, parse_mode="HTML")
    return CanvasAuthResult.CONNECTED


async def cancel_canvas_auth(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    pop_pending_service(context)
    if update.message is not None:
        await update.message.reply_text(CANVAS_AUTH_CANCELLED_TEXT)
    return ConversationHandler.END
