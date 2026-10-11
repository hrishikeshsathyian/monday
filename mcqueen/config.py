"""McQueen-only settings: job sources and the channels postings are sorted into."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Public Telegram channel that tech internship listings are posted to.
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# CAREERS.GOV SCRAPER
CAREERS_GOV_URL = "https://raw.githubusercontent.com/opengovsg/careersgovsg-jobs-data/main/data/job-listings.json"
CAREERS_GOV_INTERNSHIP_EMPLOYMENT_TYPE_CODE = "0005"
CAREERS_GOV_INDUSTRY_FIELD_CODE_IT = "0017"

# JOB CHANNELS
# Bucket keys, in the tuple order ScraperSource.scrape() returns them.
TECH_INTERN = "tech_intern"
TECH_NON_INTERN = "tech_non_intern"
NON_TECH = "non_tech"


@dataclass(frozen=True)
class JobChannel:
    """A category of scraped jobs: where it is stored and where it is posted."""

    table_name: str
    is_intern: bool
    # Telegram channel to post new jobs to; None means store only, don't post.
    telegram_chat_id: str | None = None


JOB_CHANNELS: dict[str, JobChannel] = {
    TECH_INTERN: JobChannel(
        table_name="tech_intern_jobs",
        telegram_chat_id=TELEGRAM_CHAT_ID,
        is_intern=True,
    ),
    TECH_NON_INTERN: JobChannel(
        table_name="tech_non_intern_jobs",
        is_intern=False,
    ),
    NON_TECH: JobChannel(table_name="non_tech_jobs", is_intern=False),
}
