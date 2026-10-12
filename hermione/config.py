"""Hermione-only settings."""

from zoneinfo import ZoneInfo

# NUS Canvas instance that student API keys are issued for.
CANVAS_URL = "https://canvas.nus.edu.sg"

# Users processed at once; each user's Canvas requests stay sequential to respect
# Canvas's per-token rate limit.
MAX_CONCURRENT_USERS = 10

# How far ahead the daily digest looks for upcoming deadlines.
DIGEST_WINDOW_DAYS = 10

# Due dates and class days are shown to users in NUS local time.
DISPLAY_TIMEZONE = ZoneInfo("Asia/Singapore")

NUSMODS_API_URL = "https://api.nusmods.com/v2"

# Update at the start of each semester.
ACADEMIC_YEAR = "2026-2027"
SEMESTER = 1

# Leading letter of a Canvas section name ("T02", "L1") -> NUSMods lesson type.
SECTION_LESSON_TYPES = {"L": "Lecture", "T": "Tutorial"}
