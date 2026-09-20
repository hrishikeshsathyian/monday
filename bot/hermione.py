"""Canvas-key authentication messages for Hermione."""

import asyncio

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db.service_credentials import set_service_secret
from hermione.main import canvas_healthcheck

AWAITING_CANVAS_API_KEY = 1

AUTH_PROMPT_TEXT = (
    "🔐 <b>Connect Hermione to Canvas</b>\n\n"
    "Paste your Canvas API key to continue.\n\n"
    "<b>Where to find it? </b> \n Canvas → Account → Settings → Approved Integrations → New Access Token\n\n"
    "<i>Unfortunately, this is the only way 😔 Trust me, I tried.</i>\n\n"
    "Your token is encrypted safely before being stored and is never exposed in plaintext.\n\n"
    "Use /cancel to back out if you'd rather not continue."
)
CHECKING_KEY_TEXT = "Validating your Canvas API key…"
INVALID_KEY_TEXT = (
    "⚠️ <b>That Canvas API key didn't work.</b>\n\n"
    "Please send a valid key, or use /cancel to stop."
)
SERVICE_STATE_FAILED_TEXT = (
    "⚠️ <b>Your Canvas Key was valid but we couldn't save it</b>\n\n"
    "Please try again in a moment."
)
ENABLED_TEXT = "<b>Hermione authenticated.</b> Unless set otherwise, your key will be valid for the next 3 months."
CANCELLED_TEXT = "Hermione setup cancelled."


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
