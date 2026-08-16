from mcqueen.scrapers.base import ScraperSource
from ats_scrapers.models import Job
import logging

logger = logging.getLogger(__name__)


def scrape_all_sources(
    seen_ids: set[str],
    sources: list[ScraperSource],
) -> dict[str, list[Job]]:
    buckets: dict[str, list[Job]] = {
        "tech_intern": [],
        "tech_non_intern": [],
        "non_tech": [],
    }

    for source in sources:
        logger.info(f"Scraping source: {source.name}")
        tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs = source.scrape(seen_ids)
        buckets["tech_intern"].extend(tech_intern_jobs)
        buckets["tech_non_intern"].extend(tech_non_intern_jobs)
        buckets["non_tech"].extend(non_tech_jobs)
        logger.info(f"""
        Found {len(tech_intern_jobs)} NEW TECH INTERN POSTINGS
        Found {len(tech_non_intern_jobs)} NEW TECH NON INTERN POSTINGS
        Found {len(non_tech_jobs)} NEW NON TECH NON INTERN POSTINGS
        """)
    return buckets
