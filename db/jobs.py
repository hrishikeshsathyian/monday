import logging
from ats_scrapers.models import Job as ScraperJob
from .models import DbJob
from .client import supabase
from postgrest import APIError

logger = logging.getLogger(__name__)


def upsert_jobs(jobs: list[ScraperJob], table_name: str) -> None:
    if len(jobs) == 0: 
        logger.warning(f"Attempted to insert empty jobs list to {table_name}")
        return
    
    rows = [DbJob.from_scraper_job(job).model_dump(mode="json") for job in jobs]
    logger.info(len(rows))
    try:
        # ON CONFLICT (global_id) REPLACE WITH NEW ROW
        supabase.table(table_name).upsert(rows, on_conflict="global_id").execute()
        logger.info(f"Upserted {len(rows)} job(s) into {table_name} successfully")
    except APIError:
        logger.error(
            f"Error occured trying to insert jobs into {table_name}", exc_info=True
        )
    except Exception as e:
        logger.error(
            f"Unexpected exception {e} trying to insert jobs into {table_name}"
        )
