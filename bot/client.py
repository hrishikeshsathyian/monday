from telegram import Bot
from config.settings import TELEGRAM_BOT_TOKEN, MONDAY_BOT_TOKEN

# Posts job alerts to the public McQueen channel, which is live in prod.
mcqueen_channel_bot = Bot(token=TELEGRAM_BOT_TOKEN)
# The user-facing Monday bot: onboarding, service toggles and Hermione digests.
monday_bot = Bot(token=MONDAY_BOT_TOKEN)
