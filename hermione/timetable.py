"""Match a user's Canvas class groups to NUSMods lessons."""

import re
from datetime import date

from .config import SECTION_LESSON_TYPES
from .nusmods import Lesson, get_module_lessons


def is_weekday(day: date) -> bool:
    return day.weekday() < 5


def get_classes_on(
    day: date, class_groups: dict[str, list[str]]
) -> list[Lesson] | None:
    """The user's lessons that fall on the given day's weekday, earliest first.

    Returns None if any module's timetable couldn't be loaded, so a partial
    schedule is never shown as the full one.
    """

    weekday = f"{day:%A}"
    classes = []

    # class_groups looks like {"cs3210":[L01,T02]}
    for module_code, sections in class_groups.items():
        groups = {group for section in sections if (group := _parse_section(section))}
        if not groups:
            continue

        lessons = _get_cross_listed_lessons(module_code)
        if lessons is None:
            return None

        classes += [
            lesson
            for lesson in lessons
            if lesson.day == weekday
            and (lesson.lesson_type, _normalise(lesson.class_no)) in groups
        ]

    return sorted(classes, key=lambda lesson: lesson.start_time)


def _get_cross_listed_lessons(module_code: str) -> tuple[Lesson, ...] | None:
    """Lessons for a Canvas course code, which may list several codes like
    "GES1035/GESS1025". Cross-listed codes share a timetable on NUSMods, so the
    first code that loads is used."""

    for code in module_code.split("/"):
        lessons = get_module_lessons(code.strip())
        if lessons is not None:
            return lessons
    return None


def _parse_section(section: str) -> tuple[str, str] | None:
    """Turn a Canvas section name into the (lesson type, class no) NUSMods uses.

    "T02" -> ("Tutorial", "2"), "TD38" -> ("Tutorial", "D38"), "L1" -> ("Lecture", "1").
    Returns None for sections that aren't classes, like "Travel" or "SoC", or whose
    type letter isn't in SECTION_LESSON_TYPES.
    """

    # A Canvas class section name, split into two groups:
    #   1. the lesson type letter, e.g. "T" (Tutorial) or "L" (Lecture)
    #   2. the class number, optionally prefixed by one more letter, e.g. "02" or "D38"
    # So "T02" -> ("T", "02") and "TD38" -> ("T", "D38").
    SECTION_PATTERN = re.compile(r"([A-Z])([A-Z]?\d+)")

    match = SECTION_PATTERN.fullmatch(section)
    if match is None or match[1] not in SECTION_LESSON_TYPES:
        return None
    return SECTION_LESSON_TYPES[match[1]], _normalise(match[2])


def _normalise(class_no: str) -> str:
    # Canvas and NUSMods disagree on zero padding ("L01" vs "1").
    return class_no.lstrip("0") or "0"
