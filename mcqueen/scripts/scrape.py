from mcqueen.scrapers.source import SOURCES
import logging 

logger = logging.getLogger(__name__)

def scrape_all_sources() -> None:
    for source in SOURCES:
        logger.info(f"Scraping source: {source.name}")
        tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs = source.scrape()
        logger.info(f"Found {len(tech_intern_jobs)} TECH INTERN POSTINGS")
        logger.info(f"Found {len(tech_non_intern_jobs)} TECH NON INTERN POSTINGS")
        logger.info(f"Found {len(non_tech_jobs)} NON TECH NON INTERN POSTINGS")
    return 
