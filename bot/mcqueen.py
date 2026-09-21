"""Telegram messages used exclusively by the McQueen job-posting service."""

import html
import textwrap

from ats_scrapers.models import Job
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .messages import MAX_MESSAGE_LENGTH, send_message

BATCH_THRESHOLD = 10


async def send_job(job: Job, chat_id: str, is_intern: bool) -> None:
    """Publish one McQueen job alert with an application link."""

    alert_type = "Internship" if is_intern else "Job"
    text = (
        f"🚨 <b>{alert_type} Alert</b>\n"
        f"💼 {html.escape(job.title)}\n"
        f"🏢 {html.escape(job.company)}\n"
        f"📍 {html.escape(job.location or 'Singapore')}"
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Apply Now 🚀", url=str(job.url))]]
    )
    await send_message(chat_id=chat_id, text=text, reply_markup=keyboard)


def _job_line(job: Job) -> str:
    title = textwrap.shorten(html.escape(job.title), width=55, placeholder="...")
    url = html.escape(str(job.url), quote=True)
    return (
        f"💼 {title} | 🏢 {html.escape(job.company)} | "
        f'<a href="{url}">🚀 Apply Now</a>\n'
    )


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


async def send_job_batch(jobs: list[Job], chat_id: str, is_intern: bool) -> None:
    """Publish McQueen job alerts in Telegram-sized batches."""

    if not jobs:
        return

    alert_type = "Internship" if is_intern else "Job"
    for text in _build_batch_messages(jobs, alert_type):
        await send_message(chat_id=chat_id, text=text)
