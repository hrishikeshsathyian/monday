from mcqueen.scripts.scrape import scrape_all_sources

from config.logging import setup_logging
from config.settings import (
    TECH_INTERN_JOBS_TABLE_NAME,
    NON_TECH_JOBS_TABLE_NAME,
    TECH_NON_INTERN_JOBS_TABLE_NAME,
)

from db.jobs import upsert_jobs, get_seen_global_ids

from bot.messages import send_job

import asyncio


async def run():
    setup_logging()
    # get seen_ids for all tables
    tech_intern_jobs_seen_ids = get_seen_global_ids(TECH_INTERN_JOBS_TABLE_NAME)
    tech_non_intern_jobs_seen_ids = get_seen_global_ids(TECH_NON_INTERN_JOBS_TABLE_NAME)
    non_tech_jobs_seen_ids = get_seen_global_ids(NON_TECH_JOBS_TABLE_NAME)
    seen_ids = tech_intern_jobs_seen_ids.union(
        tech_non_intern_jobs_seen_ids, non_tech_jobs_seen_ids
    )

    tech_intern_jobs, tech_non_intern_jobs, non_tech_jobs = scrape_all_sources(
        seen_ids,
    )

    # insert into db
    if len(tech_intern_jobs) > 0:
        upsert_jobs(tech_intern_jobs, TECH_INTERN_JOBS_TABLE_NAME)
    if len(tech_non_intern_jobs) > 0:
        upsert_jobs(tech_non_intern_jobs, TECH_NON_INTERN_JOBS_TABLE_NAME)
    if len(non_tech_jobs) > 0:
        upsert_jobs(non_tech_jobs, NON_TECH_JOBS_TABLE_NAME)

    for job in tech_intern_jobs:
        await send_job(job)


if __name__ == "__main__":
    asyncio.run(run())
