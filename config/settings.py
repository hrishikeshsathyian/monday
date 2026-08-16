import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


@dataclass(frozen=True)
class JobChannel:
    table_name: str
    telegram_chat_id: str | None = None


JOB_CHANNELS: dict[str, JobChannel] = {
    "tech_intern": JobChannel(
        table_name="tech_intern_jobs",
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
    ),
    "tech_non_intern": JobChannel(
        table_name="tech_non_intern_jobs",
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID_NON_INTERN"]
    ),
    "non_tech": JobChannel(table_name="non_tech_jobs"),
}
