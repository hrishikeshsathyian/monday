import datetime
import asyncio
import logging
import html
import textwrap

from telegram import InlineKeyboardMarkup, Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError, TimedOut
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .client import bot as mcqueen_bot
from ats_scrapers.models import Job

logger = logging.getLogger(__name__)
MAX_RETRIES = 5
MAX_MESSAGE_LENGTH = 4096
BATCH_THRESHOLD = 10


# OVERALL MESSAGE SENDER


async def send_message(
    chat_id: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    bot: Bot = mcqueen_bot,
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


async def send_job(job: Job, chat_id: str, is_intern: bool):
    alert_type = "Internship" if is_intern else "Job"
    text = (
        f"🚨 <b>{alert_type} Alert</b>\n"
        f"💼 {html.escape(job.title)}\n"
        f"🏢 {html.escape(job.company)}\n"
        f"📍 {html.escape(job.location if job.location else "Singapore")}"
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


def _job_line(job: Job) -> str:
    return f'💼 {textwrap.shorten(html.escape(job.title), width=55, placeholder="...")} | 🏢 {html.escape(job.company)} | <a href="{html.escape(str(job.url), quote=True)}">🚀 Apply Now</a> \n'


def _build_batch_messages(jobs: list[Job], alert_type: str) -> list[str]:
    header = f"🚨 <b>{len(jobs)} New {alert_type} Alerts</b>\n\n"
    messages: list[str] = []
    current = header

    for job in jobs:
        line = _job_line(job)
        addition = line if current == header else f"\n{line}"
        if len(current) + len(addition) > MAX_MESSAGE_LENGTH:
            messages.append(current)
            current = header + line
        else:
            current += addition

    if current != header or not messages:
        messages.append(current)

    return messages


async def send_job_batch(jobs: list[Job], chat_id: str, is_intern: bool):
    if not jobs:
        return

    alert_type = "Internship" if is_intern else "Job"
    for text in _build_batch_messages(jobs, alert_type):
        await send_message(chat_id=chat_id, text=text)
