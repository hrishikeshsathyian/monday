"""Wall-E-only settings."""

# Courses whose files add up to more than this aren't downloaded at all, to keep
# the server's disk use and the fetch time reasonable.
MAX_COURSE_DOWNLOAD_BYTES = 500 * 1000 * 1000

# Zips up to this size are sent straight into the chat; bigger ones go to R2 and
# the user gets a download link. Uploads from the server to Telegram are slow
# (about 300 KB/s, versus about 30 MB/s to R2), so only small zips go through Telegram.
MAX_TELEGRAM_ZIP_BYTES = 10 * 1000 * 1000

# Seconds between progress updates while a course downloads; editing much more
# often risks Telegram's rate limits.
PROGRESS_UPDATE_SECONDS = 3

# Seconds allowed for uploading a zip to Telegram. python-telegram-bot sends the
# whole file as one write, so this caps the entire upload.
ZIP_UPLOAD_TIMEOUT_SECONDS = 300

# How long a zip's R2 download link works. The bucket's lifecycle rule deletes
# the zip itself after a day.
ZIP_LINK_EXPIRY_SECONDS = 24 * 60 * 60

# R2 keys are "<prefix><random id>/<course>.zip", so links can't be guessed.
ZIP_LINK_KEY_PREFIX = "walle/"
