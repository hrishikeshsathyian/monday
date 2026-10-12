from ats_scrapers.models import Job as ScraperJob
from ats_scrapers.models import EmploymentType
from pydantic import AliasPath, BaseModel, ConfigDict, Field, HttpUrl
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo

"""
    Anything prefixed with Db in this file should ALWAYS mirror exactly what exists in the database schema
"""


class DbJob(BaseModel):
    global_id: str
    ats_type: str
    ats_id: Optional[str]

    url: HttpUrl
    company: str
    title: str
    employment_type: Optional[EmploymentType]
    location: Optional[str]
    department: Optional[str]

    posted_at: Optional[datetime]
    fetched_at: datetime

    @classmethod
    def from_scraper_job(cls, job: ScraperJob) -> "DbJob":
        return cls(
            global_id=f"{job.ats_type.value}:{job.ats_id}",
            ats_type=job.ats_type.value,
            ats_id=job.ats_id,
            url=job.apply_url or job.url,
            company=job.company,
            title=job.title,
            location=job.location,
            employment_type=job.employment_type,
            department=job.department,
            posted_at=job.posted_at,
            fetched_at=datetime.now(ZoneInfo("Asia/Singapore")),
        )


class DbUser(BaseModel):
    telegram_user_id: int
    telegram_chat_id: int
    telegram_username: str

    created_at: datetime


class DbUserService(BaseModel):
    telegram_user_id: int
    service: str
    enabled: bool
    encrypted_secret: Optional[str] = None
    expires_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime


# Query results of user_services joined with users, not mirrors of a table.
# Supabase nests the joined columns under "users"; AliasPath reads them from there.
class McQueenUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    telegram_chat_id: int = Field(
        validation_alias=AliasPath("users", "telegram_chat_id")
    )
    telegram_username: str | None = Field(
        validation_alias=AliasPath("users", "telegram_username")
    )


class HermioneUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    telegram_chat_id: int = Field(
        validation_alias=AliasPath("users", "telegram_chat_id")
    )
    telegram_username: str | None = Field(
        validation_alias=AliasPath("users", "telegram_username")
    )
    encrypted_secret: str
