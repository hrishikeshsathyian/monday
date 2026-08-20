import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.logging import setup_logging
from config.settings import MCQUEEN_SERVICE, MONDAY_BOT_TOKEN
from db.service_credentials import create_service_credential
from db.users import try_create_user, get_user

logger = logging.getLogger(__name__)

ALREADY_REGISTERED_TEXT = (
    "✅ You're already set up.\n\nMonday will keep sending you updates -- "
    "nothing else to do."
)
WELCOME_TEXT = (
    "👋 <b>Welcome to Monday</b>\n\n"
    "You're all set. Internship job alerts are <b>on</b>, so new postings will "
    "land here as they're found.\n\n"
    "No commands needed from here."
)
SIGNUP_FAILED_TEXT = (
    "⚠️ Something went wrong setting up your account. Please try again in a moment."
)


async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Edited messages and channel posts arrive with no .message, so guard it.
    if update.message is None:
        return

    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        logger.warning("Ignoring command with no effective user or chat")
        return

    if get_user(user.id) is not None:
        logger.info(f"User {user.id} (@{user.username}) is already registered")
        await update.message.reply_text(ALREADY_REGISTERED_TEXT)
        return

    logger.info(f"Onboarding new user {user.id} (@{user.username})...")

    if not try_create_user(
        telegram_user_id=user.id,
        telegram_chat_id=chat.id,
        telegram_username=user.username,
    ):
        await update.message.reply_text(SIGNUP_FAILED_TEXT)
        return

    # Service rows are written once, here. Nothing re-checks them on later commands.
    if not create_service_credential(user.id, MCQUEEN_SERVICE, enabled=True):
        await update.message.reply_text(SIGNUP_FAILED_TEXT)
        return

    logger.info(f"Registered user {user.id} (@{user.username}) with {MCQUEEN_SERVICE}")
    await update.message.reply_text(WELCOME_TEXT, parse_mode="HTML")


def run_monday() -> None:
    setup_logging()

    app = Application.builder().token(MONDAY_BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "monday"], handle_register))

    logger.info("MondayBot polling for updates")
    # run_polling manages its own event loop, so never call this inside asyncio.run().
    app.run_polling()
