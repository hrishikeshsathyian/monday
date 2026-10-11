"""Settings shared across services (bot, db, security).

Secrets are read from the environment (a local .env file, or GitHub Actions
secrets in production) and fail fast with KeyError if missing. Settings used by
only one service live in that service's own config.py instead.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# TELEGRAM CONFIG
# Bot that posts job listings to the public McQueen channels.
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# User-facing Monday bot: onboarding, service toggles and direct messages.
MONDAY_BOT_TOKEN = os.environ["MONDAY_BOT_TOKEN"]

# DATABASE CONFIG
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
SERVICE_CREDENTIALS_TABLE = "user_services"

# SECURITY CONFIG
# Fernet key used to encrypt third-party service credentials at rest.
FERNET_KEY = os.environ["FERNET_KEY"]
