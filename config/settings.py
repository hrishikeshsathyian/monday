import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# db config
TECH_INTERN_JOBS_TABLE_NAME = "tech_intern_jobs"
TECH_NON_INTERN_JOBS_TABLE_NAME = "tech_non_intern_jobs"
NON_TECH_JOBS_TABLE_NAME = "non_tech_jobs"
