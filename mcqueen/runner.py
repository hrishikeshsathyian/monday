import logging
from dataclasses import dataclass

from ats_scrapers.models import Job
from telegram import Bot

from bot.client import mcqueen_channel_bot, monday_bot
from bot.mcqueen import BATCH_THRESHOLD, send_job, send_job_batch
from config.settings import HERMIONE_DEV_CHAT_ID, IS_DEV
from db.jobs import get_seen_global_ids, upsert_jobs
from db.models import McQueenUser
from db.user_services import get_mcqueen_users

from .config import JOB_CHANNELS, NON_TECH, TECH_INTERN, TECH_NON_INTERN, JobChannel
from .scrapers.base import ScraperSource
from .scrapers.source import SOURCES

logger = logging.getLogger(__name__)


@dataclass
class McQueenRunner:
    """Owns the McQueen pipeline end to end: scrape -> upsert -> publish to the channel, and DM internships to users with McQueen service toggled on."""

    sources: list[ScraperSource]

    @classmethod
    def from_source_names(cls, selected_sources: list[str]):
        return cls(
            sources=[source for source in SOURCES if source.name in selected_sources]
        )

    def _load_seen_ids(self) -> set[str] | None:
        """Get all unique ids of listings already seen."""
        seen_ids: set[str] = set()
        for channel in JOB_CHANNELS.values():
            channel_ids = get_seen_global_ids(channel.table_name)
            if channel_ids is None:
                return None
            seen_ids |= channel_ids
        return seen_ids

    def _scrape(self, seen_ids: set[str]) -> dict[str, list[Job]]:
        """Returns 3 deduplicated buckets of NEW listings for TECH_INTERN, TECH_NON_INTERN and NON_TECH respectively"""
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
        Found {len(tech_intern_jobs)} NEW TECH INTERN POSTINGS in {source.name}
        Found {len(tech_non_intern_jobs)} NEW TECH NON INTERN POSTINGS in {source.name}
        Found {len(non_tech_jobs)} NEW NON TECH NON INTERN POSTINGS in {source.name}
        """)

        # deduplicate in-case an ATL lists the same entry twice, prevents DB upsertion error
        for bucket, jobs in buckets.items():
            unique_jobs: dict[str, Job] = {}
            duplicate_ids: set[str] = set()

            for job in jobs:
                if job.global_id in unique_jobs:
                    duplicate_ids.add(job.global_id)
                    continue
                unique_jobs[job.global_id] = job

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
                    f"Failed to send {job.global_id} ({job.title} at {job.company}) to chat {chat_id}"
                )
                all_sent = False
        return all_sent

    async def _publish_to_channel(self, channel: JobChannel, jobs: list[Job]) -> None:
        # Defensive fall back, we should already be calling this for TECH_INTERN channel which is the only one with a telegram_chat_id
        if not channel.telegram_chat_id:
            return

        if await self._send_jobs(
            jobs, channel.telegram_chat_id, channel.is_intern, mcqueen_channel_bot
        ):
            logger.info(f"Published {len(jobs)} job(s) to {channel.table_name}")
        else:
            logger.error(
                f"Failed to publish some of {len(jobs)} job(s) to {channel.table_name}"
            )

    async def _publish_to_monday(
        self, jobs: list[Job], mcqueen_users: list[McQueenUser]
    ) -> None:

        sent = 0
        for user in mcqueen_users:
            # Subscribers chat with the Monday bot, so it has to be the one that DMs them.
            if await self._send_jobs(
                jobs, str(user.telegram_chat_id), is_intern=True, bot=monday_bot
            ):
                sent += 1
            else:
                logger.error(
                    f"Failed to send some of {len(jobs)} internship(s) to chat {user.telegram_chat_id} (@{user.telegram_username})"
                )
        logger.info(
            f"Sent {len(jobs)} internship(s) to {sent}/{len(mcqueen_users)} McQueen subscribers"
        )

    def _load_subscribers(self) -> list[McQueenUser] | None:
        subscribers = get_mcqueen_users()
        if subscribers is None:
            logger.error("Error loading McQueen Subscribers...")
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
            logger.error("Error loading seen_ids, skipping McQueen run...")
            return

        subscribers = self._load_subscribers()

        for bucket, jobs in self._scrape(seen_ids).items():
            if not jobs:
                continue

            channel = JOB_CHANNELS[bucket]
            # Persist before publishing so a failed send can't lose the posting.
            if not upsert_jobs(jobs, channel.table_name):
                logger.error(
                    f"Error upserting jobs to {channel.table_name}, skipping publishing.",
                )
                continue

            if bucket == TECH_INTERN:
                await self._publish_to_channel(channel, jobs)
            else:
                logger.info(
                    f"Skipping publishing to {bucket} channel since it is not live.."
                )

            # Subscribers get internships only;
            if bucket == TECH_INTERN and subscribers is not None:
                await self._publish_to_monday(jobs, subscribers)
            elif not subscribers:
                logger.error(
                    f"Error loading subscribers... skipping publishing {bucket} to monday.."
                )
