import logging
from ats_scrapers.models import Job as ScraperJob
from .models import DbJob
from .client import supabase
from postgrest import APIError
from typing import cast

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


def get_seen_global_ids(table_name: str) -> set[str]:
    try:
        response = supabase.table(table_name=table_name).select("global_id").execute()
    except APIError:
        logger.error(
            f"Error occured trying to get seen global_ids from {table_name}",
            exc_info=True,
        )
        return set()
    except Exception as e:
        logger.error(
            f"Unexpected exception {e} trying to get seen global_ids from {table_name}"
        )
        return set()
    rows = cast(list[dict[str, str]], response.data)
    ids: set[str] = set()
    for row in rows:
        ids.add(row["global_id"])
    logger.info(
        f"Successfully retrieved {len(ids)} seen global id(s) from {table_name}"
    )
    return ids
