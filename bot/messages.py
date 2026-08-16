import datetime
import asyncio
import logging
import html

from telegram import InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError, TimedOut
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .client import bot
from ats_scrapers.models import Job

logger = logging.getLogger(__name__)
MAX_RETRIES = 5


# OVERALL MESSAGE SENDER


async def send_message(
    chat_id: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    for _ in range(MAX_RETRIES):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            logger.info(f"Successfully sent message {text[:10]}... to telegram")
            return

        except RetryAfter as e:
            retry_after = e.retry_after
            if isinstance(retry_after, datetime.timedelta):
                retry_after = retry_after.total_seconds()
            logger.warning(f"Telegram flood control hit. Retrying in {retry_after}s...")
            await asyncio.sleep(retry_after + 0.5)

        except TimedOut:
            logger.warning("Telegram timeout occurred. Retrying...")
            await asyncio.sleep(1.0)

        except TelegramError as e:
            logger.error(f"Telegram error occurred: {e}.")
            # do not retry if it is a telegram error just exit
            return

    logger.error(f"Giving up sending message after {MAX_RETRIES} retries.")
    return


async def send_job(job: Job, chat_id: str):
    text = (
        "🚨 <b>Internship Alert</b>\n"
        f"💼 {html.escape(job.title)}\n"
        f"🏢 {html.escape(job.company)}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Apply Now 🚀",
                    url=str(job.url),
                )
            ]
        ]
    )

    return await send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
    )
