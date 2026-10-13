"""McQueen-only settings: job sources and the channels postings are sorted into."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# McQueen Telegram Channel
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Careers.Gov Config
CAREERS_GOV_URL = "https://raw.githubusercontent.com/opengovsg/careersgovsg-jobs-data/main/data/job-listings.json"
CAREERS_GOV_INTERNSHIP_EMPLOYMENT_TYPE_CODE = "0005"
CAREERS_GOV_INDUSTRY_FIELD_CODE_IT = "0017"

# Job Channels
TECH_INTERN = "tech_intern"
TECH_NON_INTERN = "tech_non_intern"
NON_TECH = "non_tech"


@dataclass(frozen=True)
class JobChannel:
    """A category of scraped jobs: where it is stored and where it is posted."""

    table_name: str
    is_intern: bool
    telegram_chat_id: str | None = None


# only tech_intern has a live telegram channel, rest deprecated
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
