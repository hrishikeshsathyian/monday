from telegram import Bot
from config.settings import TELEGRAM_BOT_TOKEN, MONDAY_BOT_TOKEN

bot = Bot(token=TELEGRAM_BOT_TOKEN)
mondaybot = Bot(token=MONDAY_BOT_TOKEN)
