from telegram import Bot
from config.settings import TELEGRAM_BOT_TOKEN, MONDAY_BOT_TOKEN

mcqueen_channel_bot = Bot(token=TELEGRAM_BOT_TOKEN)
monday_bot = Bot(token=MONDAY_BOT_TOKEN)
