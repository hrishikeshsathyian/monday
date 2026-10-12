import logging
from dataclasses import dataclass, field

from ats_scrapers.models import Job
from telegram import Bot

from bot.client import mcqueen_channel_bot, monday_bot
from bot.mcqueen import BATCH_THRESHOLD, send_job, send_job_batch
from config.settings import HERMIONE_DEV_CHAT_ID, IS_DEV
from db.jobs import get_seen_global_ids, upsert_jobs
from db.models import ServiceUser
from db.service_credentials import get_enabled_service_users

from .config import JOB_CHANNELS, NON_TECH, TECH_INTERN, TECH_NON_INTERN, JobChannel
from .scrapers.base import ScraperSource
from .scrapers.source import SOURCES

logger = logging.getLogger(__name__)


@dataclass
class McQueenRunner:
    """Owns the McQueen pipeline end to end: scrape -> upsert -> publish to the channel, and DM internships to subscribers."""

    sources: list[ScraperSource] = field(default_factory=lambda: list(SOURCES))
    channels: dict[str, JobChannel] = field(default_factory=lambda: dict(JOB_CHANNELS))

    @classmethod
    def from_source_names(cls, source_names: list[str] | None) -> "McQueenRunner":
        # None means every configured source.
        if source_names is None:
            return cls()
        return cls(
            sources=[source for source in SOURCES if source.name in source_names]
        )

    def _load_seen_ids(self) -> set[str] | None:
        seen_ids: set[str] = set()
        for channel in self.channels.values():
            channel_ids = get_seen_global_ids(channel.table_name)
            if channel_ids is None:
                return None
            seen_ids |= channel_ids
        return seen_ids

    def _scrape(self, seen_ids: set[str]) -> dict[str, list[Job]]:
        buckets: dict[str, list[Job]] = {
            TECH_INTERN: [],
            TECH_NON_INTERN: [],
            NON_TECH: [],
        }

        for source in self.sources:
            logger.info(f"Scraping source: {source.name}")
            tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs = source.scrape(
                seen_ids
            )
            buckets[TECH_INTERN].extend(tech_intern_jobs)
            buckets[TECH_NON_INTERN].extend(tech_non_intern_jobs)
            buckets[NON_TECH].extend(non_tech_jobs)
            logger.info(f"""
        Found {len(tech_intern_jobs)} NEW TECH INTERN POSTINGS
        Found {len(tech_non_intern_jobs)} NEW TECH NON INTERN POSTINGS
        Found {len(non_tech_jobs)} NEW NON TECH NON INTERN POSTINGS
        """)

        for bucket, jobs in buckets.items():
            unique_jobs: dict[str, Job] = {}
            duplicate_ids: set[str] = set()

            for job in jobs:
                if job.global_id in unique_jobs:
                    duplicate_ids.add(job.global_id)
                    continue
                unique_jobs[job.global_id] = job

            if duplicate_ids:
                logger.warning(
                    "Dropped %d duplicate job(s) from %s: %s",
                    len(jobs) - len(unique_jobs),
                    bucket,
                    ", ".join(sorted(duplicate_ids)),
                )
            buckets[bucket] = list(unique_jobs.values())

        return buckets

    async def _send_jobs(
        self, jobs: list[Job], chat_id: str, is_intern: bool, bot: Bot
    ) -> bool:
        """Send jobs to one chat, batched past BATCH_THRESHOLD; True if every message was sent."""

        if len(jobs) > BATCH_THRESHOLD:
            return await send_job_batch(
                jobs, chat_id=chat_id, is_intern=is_intern, bot=bot
            )

        all_sent = True
        for job in jobs:
            if not await send_job(job, chat_id=chat_id, is_intern=is_intern, bot=bot):
                logger.error(
                    "Failed to send %s (%s at %s) to chat %s",
                    job.global_id,
                    job.title,
                    job.company,
                    chat_id,
                )
                all_sent = False
        return all_sent

    async def _publish_to_channel(self, channel: JobChannel, jobs: list[Job]) -> None:
        # Only tech_intern has a channel; the other buckets are stored but never posted.
        if not channel.telegram_chat_id:
            return

        if await self._send_jobs(
            jobs, channel.telegram_chat_id, channel.is_intern, mcqueen_channel_bot
        ):
            logger.info("Published %d job(s) to %s", len(jobs), channel.table_name)
        else:
            logger.error(
                "Failed to publish some of %d job(s) to %s",
                len(jobs),
                channel.table_name,
            )

    async def _send_internships_to_subscribers(
        self, jobs: list[Job], subscribers: list[ServiceUser]
    ) -> None:
        sent = 0
        for user in subscribers:
            # Subscribers chat with the Monday bot, so it has to be the one that DMs them.
            if await self._send_jobs(
                jobs, str(user.telegram_chat_id), is_intern=True, bot=monday_bot
            ):
                sent += 1
            else:
                logger.error(
                    "Failed to send some of %d internship(s) to chat %s (@%s)",
                    len(jobs),
                    user.telegram_chat_id,
                    user.telegram_username,
                )
        logger.info(
            "Sent %d internship(s) to %d/%d McQueen subscribers",
            len(jobs),
            sent,
            len(subscribers),
        )

    def _load_subscribers(self) -> list[ServiceUser] | None:
        subscribers = get_enabled_service_users("mcqueen")
        if subscribers is None:
            logger.error(
                "Not sending internships to McQueen subscribers this run: could not "
                "load them; internships will still be posted to the channel"
            )
            return None
        if IS_DEV:
            subscribers = [
                user
                for user in subscribers
                if user.telegram_chat_id == HERMIONE_DEV_CHAT_ID
            ]
        return subscribers

    async def run(self) -> None:
        seen_ids = self._load_seen_ids()
        if seen_ids is None:
            # Without the seen IDs every job looks new and would be re-posted.
            logger.error("Skipping McQueen run: could not load already-seen jobs")
            return

        subscribers = self._load_subscribers()

        for bucket, jobs in self._scrape(seen_ids).items():
            if not jobs:
                continue

            channel = self.channels[bucket]
            # Persist before publishing so a failed send can't lose the posting.
            if not upsert_jobs(jobs, channel.table_name):
                # Unsaved jobs still look new next run; publishing now would post them twice.
                logger.error(
                    "Not publishing %d %s job(s): could not save them to %s",
                    len(jobs),
                    bucket,
                    channel.table_name,
                )
                continue
            await self._publish_to_channel(channel, jobs)

            # Subscribers get internships only; the non-intern channel is deprecated for now.
            # None means loading them failed, which _load_subscribers has already logged.
            if bucket == TECH_INTERN and subscribers is not None:
                await self._send_internships_to_subscribers(jobs, subscribers)
