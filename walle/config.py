"""Wall-E-only settings."""

# Largest file a bot can send through Telegram's hosted Bot API.
MAX_ZIP_BYTES = 50 * 1000 * 1000

# Courses whose files add up to more than this aren't downloaded at all: even
# compressed, the zip wouldn't fit under MAX_ZIP_BYTES.
MAX_COURSE_DOWNLOAD_BYTES = 100 * 1000 * 1000

# Seconds between progress updates while a course downloads; editing much more
# often risks Telegram's rate limits.
PROGRESS_UPDATE_SECONDS = 3

# Seconds allowed for uploading a zip to Telegram; the library default is far too
# short for files of tens of MB.
ZIP_UPLOAD_TIMEOUT_SECONDS = 300
