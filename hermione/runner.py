"""Scheduled-work runner for Hermione."""

import asyncio
import html
import logging

from bot.client import mondaybot
from bot.messages import send_message
from db.service_credentials import (
    HermioneCredential,
    get_enabled_hermione_credentials,
)
from security.credentials import decrypt_secret

from .canvas import get_active_course_names

logger = logging.getLogger(__name__)


class HermioneRunner:
    """Send Canvas updates to every user who has enabled Hermione."""

    async def run(self) -> None:
        """Fetch and send one current-course overview for every enabled user."""

        credentials = get_enabled_hermione_credentials()
        if credentials is None:
            return

        logger.info("Running Hermione for %d enabled user(s)", len(credentials))
        for credential in credentials:
            await self._send_course_overview(credential)

    async def _send_course_overview(self, credential: HermioneCredential) -> None:
        api_key = decrypt_secret(credential.encrypted_secret)
        if api_key is None:
            return

        course_names = await asyncio.to_thread(get_active_course_names, api_key)
        if course_names is None:
            return

        await send_message(
            chat_id=str(credential.telegram_chat_id),
            text=_format_course_overview(course_names),
            bot=mondaybot,
        )


def _format_course_overview(course_names: list[str]) -> str:
    """Build the private Telegram message listing a user's active Canvas courses."""

    if not course_names:
        return "📚 <b>Your current Canvas courses</b>\n\nNo active courses found."

    courses = "\n".join(f"• {html.escape(course_name)}" for course_name in course_names)
    return f"📚 <b>Your current Canvas courses</b>\n\n{courses}"
