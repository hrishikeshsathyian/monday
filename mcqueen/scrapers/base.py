from ats_scrapers.scrapers import BaseScraper
from typing import Callable
from dataclasses import dataclass
from ats_scrapers.models import Job
from concurrent.futures import ThreadPoolExecutor, as_completed
from ats_scrapers.exceptions import ATSScrapersError
from .filters import default_is_intern, default_is_singapore, default_is_tech
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
    max_workers: int = 8
    include_descriptions: bool = (
        False  # set to false to prevent smartrecruiters from making excesive per listings calls that triggers rate limiting
    )

    # fetch all jobs from one slug
    def _fetch_one(self, slug: str) -> list[Job]:
        return self.scraper_cls(
            slug, include_descriptions=self.include_descriptions
        ).fetch()

    def _fetch_all(self) -> list[Job]:

        if len(self.slugs) == 1:
            return self._fetch_one(self.slugs[0])

        raw: list[Job] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._fetch_one, slug): slug for slug in self.slugs}
            for i, future in enumerate(as_completed(futures), start=1):
                slug = futures[future]
                try:
                    result = future.result()
                except ATSScrapersError as exc:
                    logger.error(f"{exc} for {slug}")
                    continue
                except Exception as exc:
                    logger.error(f"{exc} for {slug}")
                    continue
                raw.extend(result)
                logger.info(f"[{self.name}] ({i}/{len(futures)}) {slug}")

        return raw

    def _filter(self, jobs: list[Job]) -> tuple[list[Job], list[Job], list[Job]]:
        tech_intern_jobs: list[Job] = []
        tech_non_intern_jobs: list[Job] = []
        non_tech_jobs: list[Job] = []

        for j in jobs:
            logger.info(j.experience)
            # filter out non singaporean listings
            if not self.is_singapore(j):
                continue

            if not self.is_tech(j):
                non_tech_jobs.append(j)
                continue

            if not self.is_intern(j):
                tech_non_intern_jobs.append(j)
                continue

            tech_intern_jobs.append(j)

        return tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs
    
    def scrape(self) -> tuple[list[Job], list[Job], list[Job]]:
        return self._filter(self._fetch_all())
