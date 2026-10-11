"""Plain data types for Hermione's Canvas todo digest."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class TodoItem:
    kind: Literal["assignment", "quiz"]
    title: str
    course_name: str
    due_at: datetime | None
    url: str
    points: float | None
    submitted: bool
    missing: bool
    late: bool
    excused: bool


@dataclass(frozen=True)
class TodoDigest:
    due_this_week: list[TodoItem]
    overdue: list[TodoItem]
    no_due_date: list[TodoItem]
