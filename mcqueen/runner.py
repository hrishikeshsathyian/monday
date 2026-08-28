import logging
from dataclasses import dataclass, field

from ats_scrapers.models import Job

from bot.messages import BATCH_THRESHOLD, send_job, send_job_batch
from config.settings import JOB_CHANNELS, JobChannel
from db.jobs import get_seen_global_ids, upsert_jobs

from .scrapers.base import ScraperSource
from .scrapers.source import SOURCES

logger = logging.getLogger(__name__)

# Bucket keys are fixed by the tuple order ScraperSource.scrape() returns, and
# must stay in sync with the keys of JOB_CHANNELS.
TECH_INTERN = "tech_intern"
TECH_NON_INTERN = "tech_non_intern"
NON_TECH = "non_tech"


@dataclass
class McQueenRunner:
    """Owns the McQueen pipeline end to end: scrape -> upsert -> publish."""

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

    def _load_seen_ids(self) -> set[str]:
        seen_ids: set[str] = set()
        for channel in self.channels.values():
            seen_ids |= get_seen_global_ids(channel.table_name)
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

        return buckets

    async def _publish(self, channel: JobChannel, jobs: list[Job]) -> None:
        # non_tech has no channel today, so it is stored but never broadcast.
        if not channel.telegram_chat_id:
            return

        if len(jobs) > BATCH_THRESHOLD:
            await send_job_batch(
                jobs, chat_id=channel.telegram_chat_id, is_intern=channel.is_intern
            )
            return

        for job in jobs:
            await send_job(
                job, chat_id=channel.telegram_chat_id, is_intern=channel.is_intern
            )

    async def run(self) -> None:
        seen_ids = self._load_seen_ids()

        for bucket, jobs in self._scrape(seen_ids).items():
            if not jobs:
                continue

            channel = self.channels[bucket]
            # Persist before publishing so a failed send can't lose the posting.
            upsert_jobs(jobs, channel.table_name)
            await self._publish(channel, jobs)
