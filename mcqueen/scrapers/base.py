from ats_scrapers.scrapers import BaseScraper
from typing import Callable
from dataclasses import dataclass
from ats_scrapers.models import Job
from concurrent.futures import ThreadPoolExecutor, as_completed
from ats_scrapers.exceptions import ATSScrapersError
from .filters import (
    default_is_intern,
    default_is_senior,
    default_is_singapore,
    default_is_tech,
)
import logging

logger = logging.getLogger(__name__)

JobFilter = Callable[[Job], bool]


@dataclass
class ScraperSource:
    name: str
    scraper_cls: type[BaseScraper]
    slugs: list[str]
    is_singapore: JobFilter = default_is_singapore
    is_intern: JobFilter = default_is_intern
    is_tech: JobFilter = default_is_tech
    is_senior: JobFilter = default_is_senior
    max_workers: int = 8
    include_descriptions: bool = (
        False  # set to false to prevent smartrecruiters from making excesive per listings calls that triggers rate limiting
    )

    # fetch all jobs from one slug; None if the fetch failed
    def _fetch_one(self, slug: str) -> list[Job] | None:
        try:
            return self.scraper_cls(
                slug, include_descriptions=self.include_descriptions
            ).fetch()
        except ATSScrapersError:
            logger.exception(f"[{self.name}] fetch failed for {slug}")
            return None
        except Exception:
            logger.exception(f"[{self.name}] unexpected fetch failure for {slug}")
            return None

    def _fetch_all(self) -> list[Job]:
        # A failed slug is skipped: its jobs are still unseen, so the next run picks them up.
        raw: list[Job] = []
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._fetch_one, slug): slug for slug in self.slugs}
            for i, future in enumerate(as_completed(futures), start=1):
                slug = futures[future]
                jobs = future.result()
                if jobs is None:
                    failed += 1
                    logger.error(f"[{self.name}] ({i}/{len(futures)}) {slug} skipped")
                    continue
                raw.extend(jobs)
                logger.info(f"[{self.name}] ({i}/{len(futures)}) {slug}")

        logger.info(
            f"[{self.name}] fetched {len(self.slugs) - failed}/{len(self.slugs)} slug(s)"
        )
        return raw

    def _filter(
        self, jobs: list[Job], seen_ids: set[str]
    ) -> tuple[list[Job], list[Job], list[Job]]:

        logger.info(f"{len(jobs)} raw jobs found PRE-FILTER")

        tech_intern_jobs: list[Job] = []
        tech_non_intern_jobs: list[Job] = []
        non_tech_jobs: list[Job] = []
        senior_dropped: list[str] = []

        for j in jobs:
            # filter out non singaporean listings
            if j.global_id in seen_ids:
                continue

            if not self.is_singapore(j):
                continue

            if not self.is_tech(j):
                non_tech_jobs.append(j)
                continue

            if not self.is_intern(j):
                # tech_non_intern is the "grad" bucket — senior/managerial
                # postings aren't grad-appropriate, so drop them here.
                if self.is_senior(j):
                    senior_dropped.append(j.title)
                    continue
                tech_non_intern_jobs.append(j)
                continue

            tech_intern_jobs.append(j)

        # if senior_dropped:
        #     logger.info(
        #         f"[{self.name}] dropped {len(senior_dropped)} senior/non-grad postings"
        #     )
        #     for dropped_title in senior_dropped:
        #         logger.info(f"Dropped {dropped_title}")

        return tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs

    def scrape(
        self,
        seen_ids: set[str],
    ) -> tuple[list[Job], list[Job], list[Job]]:
        return self._filter(self._fetch_all(), seen_ids=seen_ids)
