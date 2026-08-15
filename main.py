from bot.messages import send_message
from mcqueen.scripts.scrape import scrape_all_sources
from config.logging import setup_logging
from config.settings import TECH_INTERN_JOBS_TABLE_NAME, NON_TECH_JOBS_TABLE_NAME, TECH_NON_INTERN_JOBS_TABLE_NAME
from db.jobs import upsert_jobs
import asyncio


async def main():
    setup_logging()

    tech_intern_jobs, non_tech_intern_jobs, non_tech_jobs = scrape_all_sources()

    # insert into db
    if len(tech_intern_jobs) > 0: 
        upsert_jobs(tech_intern_jobs, TECH_INTERN_JOBS_TABLE_NAME)
    if len(non_tech_intern_jobs) > 0:
        upsert_jobs(non_tech_intern_jobs, TECH_NON_INTERN_JOBS_TABLE_NAME)
    if len(non_tech_jobs) > 0:
        upsert_jobs(non_tech_jobs, NON_TECH_JOBS_TABLE_NAME)

    await send_message("End of Intermediate Testing...")


if __name__ == "__main__":
    asyncio.run(main())
