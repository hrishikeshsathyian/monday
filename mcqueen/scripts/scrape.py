from mcqueen.scrapers.source import SOURCES
from ats_scrapers.models import Job
import logging

logger = logging.getLogger(__name__)


def scrape_all_sources() -> tuple[list[Job], list[Job], list[Job]]:
    all_tech_intern_jobs: list[Job] = []
    all_tech_non_intern_jobs: list[Job] = []
    all_non_tech_jobs: list[Job] = []

    for source in SOURCES:
        logger.info(f"Scraping source: {source.name}")
        tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs = source.scrape()
        all_tech_intern_jobs.extend(tech_intern_jobs)
        all_tech_non_intern_jobs.extend(tech_non_intern_jobs)
        all_non_tech_jobs.extend(non_tech_jobs)
        logger.info(f"""
        Found {len(tech_intern_jobs)} TECH INTERN POSTINGS
        Found {len(tech_non_intern_jobs)} TECH NON INTERN POSTINGS
        Found {len(non_tech_jobs)} NON TECH NON INTERN POSTINGS
        """)
    return all_tech_intern_jobs, all_tech_non_intern_jobs, all_non_tech_jobs
