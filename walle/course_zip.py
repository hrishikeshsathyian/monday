"""Download a course's Canvas files and zip them, keeping their folder layout."""

import re
import zipfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from integrations.canvas import CourseFile, download_course_file, get_course_files

from .config import MAX_COURSE_DOWNLOAD_BYTES


class CourseZipStatus(Enum):
    READY = auto()
    NO_FILES = auto()
    TOO_BIG = auto()


class FetchPhase(Enum):
    LISTING = auto()
    DOWNLOADING = auto()
    ZIPPING = auto()


@dataclass
class FetchProgress:
    """How far a fetch has got; written by the build thread, read by the bot."""

    phase: FetchPhase = FetchPhase.LISTING
    done_bytes: int = 0
    total_bytes: int = 0

    def add_downloaded(self, size: int) -> None:
        self.done_bytes += size


@dataclass(frozen=True)
class CourseZip:
    status: CourseZipStatus
    path: Path | None = None
    file_count: int = 0
    size_bytes: int = 0


def build_course_zip(
    api_key: str,
    course_id: int,
    course_code: str,
    workdir: Path,
    progress: FetchProgress,
) -> CourseZip | None:
    """Download every file in the course into `workdir` and zip them, updating `progress`.

    Returns None if any file couldn't be listed or downloaded, so a partial zip is
    never sent as the whole course. Raises InvalidAccessToken if Canvas rejects
    the key. The caller owns `workdir` and deletes it afterwards.
    """

    files = get_course_files(api_key, course_id)
    if files is None:
        return None
    if not files:
        return CourseZip(CourseZipStatus.NO_FILES)
    total_bytes = sum(file.size for file in files)
    if total_bytes > MAX_COURSE_DOWNLOAD_BYTES:
        return CourseZip(CourseZipStatus.TOO_BIG)

    # Files are saved under their Canvas ID, so odd names can't affect the disk;
    # names only matter inside the zip.
    downloads = workdir / "files"
    downloads.mkdir()
    progress.total_bytes = total_bytes
    progress.phase = FetchPhase.DOWNLOADING
    for file in files:
        if not download_course_file(
            api_key, file, downloads / str(file.id), progress.add_downloaded
        ):
            return None

    progress.phase = FetchPhase.ZIPPING

    zip_path = workdir / f"{_safe_name(course_code)}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file, entry_name in zip(files, _zip_entry_names(files)):
            archive.write(downloads / str(file.id), entry_name)

    return CourseZip(
        CourseZipStatus.READY, zip_path, len(files), zip_path.stat().st_size
    )


def _zip_entry_names(files: list[CourseFile]) -> list[str]:
    """Each file's path inside the zip, e.g. "Lecture Notes/L01.pdf", made unique."""

    taken: set[str] = set()
    names = []
    for file in files:
        folder = "/".join(_safe_name(part) for part in file.folder.split("/") if part)
        name = _safe_name(file.name)
        entry = f"{folder}/{name}" if folder else name

        # Two files with the same name in one folder become "notes.pdf", "notes (2).pdf".
        stem, dot, suffix = name.rpartition(".")
        if not dot:
            stem, suffix = name, ""
        copy = 2
        while entry.lower() in taken:
            numbered = f"{stem} ({copy}).{suffix}" if suffix else f"{stem} ({copy})"
            entry = f"{folder}/{numbered}" if folder else numbered
            copy += 1

        taken.add(entry.lower())
        names.append(entry)
    return names


def _safe_name(name: str) -> str:
    # Keeps a Canvas-provided name to one harmless path segment: no slashes, no
    # characters Windows rejects, and no "." or ".." that could climb out of the zip.
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "unnamed"
