"""Scheduled-work runner for Hermione."""

import asyncio
import logging

from bot.hermione import send_todo_digest
from db.service_credentials import (
    HermioneCredential,
    get_enabled_hermione_credentials,
)
from security.credentials import decrypt_secret

from .canvas import get_todo_digest

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
            await self._send_todo_digest(credential)

    async def _send_todo_digest(self, credential: HermioneCredential) -> None:
        api_key = decrypt_secret(credential.encrypted_secret)
        if api_key is None:
            return

        digest = await asyncio.to_thread(get_todo_digest, api_key)
        if digest is None:
            return

        await send_todo_digest(
            chat_id=str(credential.telegram_chat_id),
            digest=digest,
        )
