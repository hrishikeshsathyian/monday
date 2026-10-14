"""Scheduled-work runner for Hermione."""

import asyncio
import logging
from datetime import datetime, timedelta

from bot.hermione import send_daily_digest
from config.settings import HERMIONE_DEV_CHAT_ID, IS_DEV
from db.models import HermioneUser
from db.user_services import get_authenticated_hermione_users
from integrations.canvas import get_class_groups
from security.credentials import decrypt_secret

from .assignments import get_digest_assignments
from .config import DISPLAY_TIMEZONE, MAX_CONCURRENT_USERS
from .nusmods import Lesson, get_module_lessons
from .timetable import get_classes_on, is_weekday

logger = logging.getLogger(__name__)


class HermioneRunner:
    """Send the daily digest to every authenticated Hermione user."""

    async def run(self) -> None:
        get_module_lessons.cache_clear()

        users = get_authenticated_hermione_users()
        if users is None:
            logger.error(
                "Error while loading authenticated users, skipping Hermione run.."
            )
            return
        if IS_DEV:
            users = [
                user for user in users if user.telegram_chat_id == HERMIONE_DEV_CHAT_ID
            ]

        # Every user is processed, MAX_CONCURRENT_USERS at a time: each task waits for
        # a free slot, and a finished user frees its slot for the next one.
        slots = asyncio.Semaphore(MAX_CONCURRENT_USERS)

        async def send_when_slot_free(user: HermioneUser) -> bool:
            async with slots:
                return await self._send_digest(user)

        results = await asyncio.gather(
            *(send_when_slot_free(user) for user in users), return_exceptions=True
        )

        for user, result in zip(users, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Unexpected failure sending Hermione digest to chat {user.telegram_chat_id}",
                    exc_info=result,
                )

        sent = sum(result is True for result in results)
        logger.info(f"Sent Hermione reminders to {sent}/{len(users)} users")

    async def _send_digest(self, user: HermioneUser) -> bool:
        """Send one user's digest; True only if Telegram accepted it."""

        api_key = decrypt_secret(user.encrypted_secret)
        if api_key is None:
            logger.error(
                f"Error decrypting API key, skipping Hermione run for {user.telegram_chat_id} ({user.telegram_username})",
            )
            return False

        # canvasapi is blocking; using to_thread keeps the event loop free for other users.
        assignments = await asyncio.to_thread(get_digest_assignments, api_key)
        if assignments is None:
            logger.error(
                f"Skipping Hermione digest for chat {user.telegram_chat_id} (@{user.telegram_username}): Error loading their assignments"
            )
            return False

        classes = await self._get_tomorrows_classes(api_key)
        if classes is None:
            logger.error(
                f"Sending Hermione digest to chat {user.telegram_chat_id} (@{user.telegram_username}) without classes: could not load their classes"
            )

        if not await send_daily_digest(
            user.telegram_chat_id, user.telegram_username, assignments, classes
        ):
            logger.error(
                f"Failed to send Hermione digest to chat {user.telegram_chat_id} (@{user.telegram_username})"
            )
            return False

        logger.info(
            f"Sent Hermione digest to chat {user.telegram_chat_id} (@{user.telegram_username})"
        )
        return True

    async def _get_tomorrows_classes(self, api_key: str) -> list[Lesson] | None:
        # The digest goes out the night before, so it lists the next day's classes.
        tomorrow = datetime.now(DISPLAY_TIMEZONE).date() + timedelta(days=1)

        # early termination for weekend, assume there are no classes
        if not is_weekday(tomorrow):
            return []

        class_groups = await asyncio.to_thread(get_class_groups, api_key)
        if class_groups is None:
            return None

        return await asyncio.to_thread(get_classes_on, tomorrow, class_groups)
