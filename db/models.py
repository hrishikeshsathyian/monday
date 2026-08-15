from ats_scrapers.models import Job as ScraperJob
from ats_scrapers.models import EmploymentType
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo


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
