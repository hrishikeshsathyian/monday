import logging
from dataclasses import dataclass, field

from ats_scrapers.models import Job

from bot.mcqueen import BATCH_THRESHOLD, send_job, send_job_batch
from db.jobs import get_seen_global_ids, upsert_jobs

from .config import JOB_CHANNELS, NON_TECH, TECH_INTERN, TECH_NON_INTERN, JobChannel
from .scrapers.base import ScraperSource
from .scrapers.source import SOURCES

logger = logging.getLogger(__name__)


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

    async def _publish_to_channel(self, channel: JobChannel, jobs: list[Job]) -> None:
        # non_tech has no channel today, so it is stored but never broadcast.
        if not channel.telegram_chat_id:
            return

        if len(jobs) > BATCH_THRESHOLD:
            if not await send_job_batch(
                jobs, chat_id=channel.telegram_chat_id, is_intern=channel.is_intern
            ):
                logger.error(
                    "Failed to publish part of a %d-job batch to %s",
                    len(jobs),
                    channel.table_name,
                )
                return
            logger.info("Published %d job(s) to %s as a batch", len(jobs), channel.table_name)
            return

        sent = 0
        for job in jobs:
            if await send_job(
                job, chat_id=channel.telegram_chat_id, is_intern=channel.is_intern
            ):
                sent += 1
            else:
                logger.error(
                    "Failed to publish %s (%s at %s) to %s",
                    job.global_id,
                    job.title,
                    job.company,
                    channel.table_name,
                )
        logger.info("Published %d/%d job(s) to %s", sent, len(jobs), channel.table_name)

    async def run(self) -> None:
        seen_ids = self._load_seen_ids()
        if seen_ids is None:
            # Without the seen IDs every job looks new and would be re-posted.
            logger.error("Skipping McQueen run: could not load already-seen jobs")
            return

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
