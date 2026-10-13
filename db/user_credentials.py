"""Third-party credentials (e.g. a Canvas API key), stored once per user and provider
so every service that needs them shares the same key."""

import logging
from calendar import monthrange
from datetime import datetime, timezone

from postgrest import APIError

from config.settings import USER_CREDENTIALS_TABLE
from security.credentials import encrypt_secret

from .client import supabase

logger = logging.getLogger(__name__)

# How long a saved key is treated as valid before the user is asked for a new one.
CREDENTIAL_VALID_MONTHS = 3


def set_credential(telegram_user_id: int, provider: str, secret: str) -> bool:
    """Encrypt and store a verified credential, replacing any previous one."""

    encrypted_secret = encrypt_secret(secret)
    if encrypted_secret is None:
        return False

    now = datetime.now(timezone.utc)
    row = {
        "telegram_user_id": telegram_user_id,
        "provider": provider,
        "encrypted_secret": encrypted_secret,
        "expires_at": _add_months(now, CREDENTIAL_VALID_MONTHS).isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        supabase.table(USER_CREDENTIALS_TABLE).upsert(
            row, on_conflict="telegram_user_id,provider"
        ).execute()
    except APIError:
        logger.error(
            "Error saving %s credential for user %s",
            provider,
            telegram_user_id,
            exc_info=True,
        )
        return False
    except Exception:
        logger.error(
            "Unexpected error saving %s credential for user %s",
            provider,
            telegram_user_id,
            exc_info=True,
        )
        return False

    logger.info("Saved verified %s credential for user %s", provider, telegram_user_id)
    return True


def has_credential(telegram_user_id: int, provider: str) -> bool | None:
    """True if the user has a stored credential for the provider, None if the lookup failed."""

    try:
        response = (
            supabase.table(USER_CREDENTIALS_TABLE)
            .select("provider")
            .eq("telegram_user_id", telegram_user_id)
            .eq("provider", provider)
            .execute()
        )
    except APIError:
        logger.error(
            "Error checking %s credential for user %s",
            provider,
            telegram_user_id,
            exc_info=True,
        )
        return None
    except Exception:
        logger.error(
            "Unexpected error checking %s credential for user %s",
            provider,
            telegram_user_id,
            exc_info=True,
        )
        return None

    return bool(response.data)


def _add_months(moment: datetime, months: int) -> datetime:
    """Same day `months` later, clamped to the end of shorter months."""

    month = moment.month + months
    year = moment.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return moment.replace(
        year=year, month=month, day=min(moment.day, monthrange(year, month)[1])
    )
