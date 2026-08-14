from .client import bot
from config.settings import TELEGRAM_CHAT_ID
from telegram.constants import ParseMode

MAX_RETRIES = 5

async def send_message():
    return await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Hello World",
        parse_mode=ParseMode.HTML
    )
