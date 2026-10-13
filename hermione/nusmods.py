"""NUSMods API lookups used by Hermione"""

import functools
import logging
from dataclasses import dataclass

import requests

from .config import ACADEMIC_YEAR, NUSMODS_API_URL, SEMESTER

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Lesson:
    module_code: str
    lesson_type: str
    class_no: str
    day: str
    start_time: str
    end_time: str
    venue: str


@functools.cache
def get_module_lessons(module_code: str) -> tuple[Lesson, ...] | None:
    url = f"{NUSMODS_API_URL}/{ACADEMIC_YEAR}/modules/{module_code}.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        semesters = response.json()["semesterData"]

        timetable = next(
            (data["timetable"] for data in semesters if data["semester"] == SEMESTER),
            [],
        )
        return tuple(
            Lesson(
                module_code=module_code,
                lesson_type=lesson["lessonType"],
                class_no=lesson["classNo"],
                day=lesson["day"],
                start_time=lesson["startTime"],
                end_time=lesson["endTime"],
                venue=lesson["venue"],
            )
            for lesson in timetable
        )

    except (requests.RequestException, KeyError, ValueError):
        logger.exception("Could not fetch NUSMods timetable for %s", module_code)
        return None

    except Exception:
        logger.exception("Unexpected NUSMods timetable failure for %s", module_code)
        return None
