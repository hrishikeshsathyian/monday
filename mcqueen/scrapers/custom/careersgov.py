from config.settings import (
    CAREERS_GOV_INDUSTRY_FIELD_CODE_IT,
    CAREERS_GOV_URL,
    CAREERS_GOV_INTERNSHIP_EMPLOYMENT_TYPE_CODE,
)
from ats_scrapers.scrapers import BaseScraper
from ats_scrapers.models import Job, ATSType
from typing import Any
import logging
import requests
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


class CareersGovScraper(BaseScraper):

    async def afetch(self) -> list[Job]:
        fetched: list[Job] = []
        response = requests.get(CAREERS_GOV_URL)
        response.raise_for_status()
        data: list[Any] = response.json()
        filtered = [
            posting
            for posting in data
            if (posting["fieldCode"] == CAREERS_GOV_INDUSTRY_FIELD_CODE_IT)
        ]
        for row in filtered:
            res: Job = self.parse(row)
            fetched.append(res)
        return fetched

    def parse(self, posting: Any) -> Job:
        employment_type: str | None = (
            "INTERN"
            if posting["employmentTypeCode"]
            == CAREERS_GOV_INTERNSHIP_EMPLOYMENT_TYPE_CODE
            else None
        )
        return Job(
            url=HttpUrl(self._build_listing_url(posting)),
            title=posting["jobTitle"],
            company=posting["agency"],
            ats_type=ATSType.CUSTOM,
            ats_id=posting["postingNo"],
            location="Singapore",
            employment_type=employment_type,
            description=posting["jobDescription"],
            department="CAREERSGOV_TECH",
        )

    def _build_listing_url(self, posting: Any) -> str:
        platform = posting.get("platform", "").lower()
        job_id = posting.get("jobId", "")
        posting_no = posting.get("postingNo", "")

        if platform == "workable":
            return f"https://apply.workable.com/j/{posting_no}"

        if platform == "greenhouse":
            return (
                f"https://jobs.careers.gov.sg/jobs/{platform}/{job_id}?gh_jid={job_id}"
            )

        return f"https://jobs.careers.gov.sg/jobs/{platform}/{job_id}/{posting_no}"
