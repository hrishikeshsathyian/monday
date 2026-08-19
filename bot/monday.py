import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.logging import setup_logging
from config.settings import MONDAY_BOT_TOKEN

logger = logging.getLogger(__name__)


async def handle_monday(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_user is None or update.message is None:
        return

    telegram_user_id = update.effective_user.id

    logger.info(f"User ID: {telegram_user_id}")

    await update.message.reply_text(
        f"Your Telegram user ID is {telegram_user_id}"
    )

def run_monday() -> None:
    setup_logging()

    app = Application.builder().token(MONDAY_BOT_TOKEN).build()
    app.add_handler(CommandHandler("monday", handle_monday))

    logger.info("MondayBot polling for updates")

    app.run_polling()
