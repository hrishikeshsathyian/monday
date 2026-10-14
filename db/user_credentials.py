"""Third-party credentials (e.g. a Canvas API key), stored once per user and provider
so every service that needs them shares the same key."""

import logging
from calendar import monthrange
from datetime import datetime, timezone

from postgrest import APIError
from pydantic import ValidationError

from config.settings import USER_CREDENTIALS_TABLE
from security.credentials import decrypt_secret, encrypt_secret

from .client import supabase
from .models import DbUserCredential

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
            f"Error saving {provider} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return False
    except Exception:
        logger.error(
            f"Unexpected error saving {provider} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return False

    logger.info(f"Saved verified {provider} credential for user {telegram_user_id}")
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
            f"Error checking {provider} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return None
    except Exception:
        logger.error(
            f"Unexpected error checking {provider} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return None

    return bool(response.data)


def get_credential(telegram_user_id: int, provider: str) -> str | None:
    """The user's decrypted credential, or None if it is missing or couldn't be loaded.

    Callers that need to tell "no credential" apart from a failed lookup check
    has_credential first.
    """

    try:
        response = (
            supabase.table(USER_CREDENTIALS_TABLE)
            .select("*")
            .eq("telegram_user_id", telegram_user_id)
            .eq("provider", provider)
            .execute()
        )
    except APIError:
        logger.error(
            f"Error loading {provider} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return None
    except Exception:
        logger.error(
            f"Unexpected error loading {provider} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return None

    if not response.data:
        logger.error(f"No {provider} credential stored for user {telegram_user_id}")
        return None

    try:
        credential = DbUserCredential.model_validate(response.data[0])
    except ValidationError:
        logger.error(
            f"Invalid {provider} credential data for user {telegram_user_id}",
            exc_info=True,
        )
        return None

    return decrypt_secret(credential.encrypted_secret)


def _add_months(moment: datetime, months: int) -> datetime:
    """Same day `months` later, clamped to the end of shorter months."""

    month = moment.month + months
    year = moment.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return moment.replace(
        year=year, month=month, day=min(moment.day, monthrange(year, month)[1])
    )
