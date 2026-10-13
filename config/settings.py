"""Settings shared across services (bot, db, security).

Secrets are read from the environment (a local .env file, or GitHub Actions
secrets in production) and fail fast with KeyError if missing. Settings used by
only one service live in that service's own config.py instead.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# "dev" on a laptop, "prod" in deployed environments. Dev runs are restricted so
# they can't reach real users (see hermione/runner.py).
ENV = os.environ["ENV"]
if ENV not in ("dev", "prod"):
    raise ValueError(f"ENV must be 'dev' or 'prod', got {ENV!r}")
IS_DEV = ENV == "dev"

# only user a dev run sends messages to
_hermione_dev_chat_id = os.environ.get("HERMIONE_DEV_CHAT_ID")
HERMIONE_DEV_CHAT_ID = int(_hermione_dev_chat_id) if _hermione_dev_chat_id else None

# TELEGRAM CONFIG
# Token for mcqueen_channel_bot, which posts job listings to the McQueen channel
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# User-facing Monday bot: onboarding, service toggles and direct messages.
MONDAY_BOT_TOKEN = os.environ["MONDAY_BOT_TOKEN"]

# DATABASE CONFIG
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
SERVICE_CREDENTIALS_TABLE = "user_services"
# Third-party credentials (e.g. Canvas API keys), shared by every service that needs them.
USER_CREDENTIALS_TABLE = "user_credentials"

# SECURITY CONFIG
# Fernet key used to encrypt third-party service credentials at rest.
FERNET_KEY = os.environ["FERNET_KEY"]

# CANVAS CONFIG
# NUS Canvas instance that student API keys are issued for.
CANVAS_URL = "https://canvas.nus.edu.sg"
