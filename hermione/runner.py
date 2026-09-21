"""Scheduled-work runner for Hermione."""

import logging

logger = logging.getLogger(__name__)


class HermioneRunner:
    """Own the eventual Canvas check-and-notify workflow for all enabled users."""

    async def run(self) -> None:
        """Run one Hermione cycle.

        The user-credential query and pending-assignment notification workflow have
        not been implemented yet, so this is intentionally a safe no-op.
        """

        logger.info("Hermione runner has no assignment workflow configured yet")
