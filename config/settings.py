import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# TELEGRAM CONFIG
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
MONDAY_BOT_TOKEN = os.environ["MONDAY_BOT_TOKEN"]

# SCRAPER CONFIG
CAREERS_GOV_URL = "https://raw.githubusercontent.com/opengovsg/careersgovsg-jobs-data/main/data/job-listings.json"
CAREERS_GOV_INTERNSHIP_EMPLOYMENT_TYPE = "Internship"
CAREERS_GOV_INTERNSHIP_EMPLOYMENT_TYPE_CODE = "0005"
CAREERS_GOV_INDUSTRY_FIELD_CODE_OTHERS = "0025"
CAREERS_GOV_INDUSTRY_FIELD_CODE_IT = "0017"


# MISC CONFIG
@dataclass(frozen=True)
class JobChannel:
    table_name: str
    is_intern: bool
    telegram_chat_id: str | None = None


JOB_CHANNELS: dict[str, JobChannel] = {
    "tech_intern": JobChannel(
        table_name="tech_intern_jobs",
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        is_intern=True,
    ),
    "tech_non_intern": JobChannel(
        table_name="tech_non_intern_jobs",
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID_NON_INTERN"],
        is_intern=False,
    ),
    "non_tech": JobChannel(table_name="non_tech_jobs", is_intern=False),
}
