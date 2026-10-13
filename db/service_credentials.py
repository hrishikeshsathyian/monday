import logging
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any

from postgrest import APIError
from pydantic import ValidationError

from config.settings import SERVICE_CREDENTIALS_TABLE
from security.credentials import encrypt_secret

from .client import supabase
from .models import (
    DbUserService,
    HermioneUser,
    McQueenUser,
)

logger = logging.getLogger(__name__)


def create_service_credential(
    telegram_user_id: int,
    service: str,
    enabled: bool = True,
) -> bool:

    row: dict[str, Any] = {
        "telegram_user_id": telegram_user_id,
        "service": service,
        "enabled": enabled,
    }
    try:
        supabase.table(SERVICE_CREDENTIALS_TABLE).insert(row).execute()
    except APIError:
        logger.error(
            f"Error creating {service} credential for user {telegram_user_id}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected exception {e} creating {service} for user {telegram_user_id}"
        )
        return False

    logger.info(
        f"Created {service} credential for user {telegram_user_id} (enabled={enabled})"
    )
    return True


def get_service_credentials(telegram_user_id: int) -> list[DbUserService] | None:
    try:
        response = (
            supabase.table(SERVICE_CREDENTIALS_TABLE)
            .select("*")
            .eq("telegram_user_id", telegram_user_id)
            .order("service", desc=True)
            .execute()
        )
    except (APIError, ValidationError):
        logger.error(
            f"Error fetching service credentials for user {telegram_user_id}",
            exc_info=True,
        )
        return None
    except Exception:
        logger.error(
            f"Unexpected error fetching service credentials for user {telegram_user_id}",
            exc_info=True,
        )
        return None

    try:
        return [DbUserService.model_validate(row) for row in response.data]
    except ValidationError:
        logger.error(
            f"Invalid service credential data for user {telegram_user_id}",
            exc_info=True,
        )
        return None


def set_service_enabled(
    telegram_user_id: int,
    service: str,
    enabled: bool,
) -> bool:
    try:
        supabase.table(SERVICE_CREDENTIALS_TABLE).update({"enabled": enabled}).eq(
            "telegram_user_id", telegram_user_id
        ).eq("service", service).execute()
    except APIError:
        logger.error(
            f"Error updating {service} for user {telegram_user_id}",
            exc_info=True,
        )
        return False
    except Exception:
        logger.error(
            f"Unexpected error updating {service} for user {telegram_user_id}",
            exc_info=True,
        )
        return False

    logger.info(f"Updated {service} for user {telegram_user_id} (enabled={enabled})")
    return True


def set_service_secret(
    telegram_user_id: int,
    service: str,
    secret: str,
) -> bool:
    """Store a verified service credential, then enable its service."""
    encrypted_secret = encrypt_secret(secret)
    if encrypted_secret is None:
        return False

    now = datetime.now(timezone.utc)
    expiry_month = now.month + 3
    expiry_year = now.year + (expiry_month - 1) // 12
    expiry_month = (expiry_month - 1) % 12 + 1
    expires_at = now.replace(
        year=expiry_year,
        month=expiry_month,
        day=min(now.day, monthrange(expiry_year, expiry_month)[1]),
    )

    try:
        supabase.table(SERVICE_CREDENTIALS_TABLE).update(
            {
                "encrypted_secret": encrypted_secret,
                "enabled": True,
                "expires_at": expires_at.isoformat(),
                "updated_at": now.isoformat(),
            }
        ).eq("telegram_user_id", telegram_user_id).eq("service", service).execute()
    except APIError:
        logger.error(
            "Error saving %s credential for user %s",
            service,
            telegram_user_id,
            exc_info=True,
        )
        return False
    except Exception:
        logger.error(
            "Unexpected error saving %s credential for user %s",
            service,
            telegram_user_id,
            exc_info=True,
        )
        return False

    logger.info("Saved verified %s credential for user %s", service, telegram_user_id)
    return True


def get_mcqueen_users() -> list[McQueenUser] | None:
    """Fetch every user with McQueen enabled."""

    try:
        response = (
            supabase.table(SERVICE_CREDENTIALS_TABLE)
            .select("users!inner(telegram_chat_id, telegram_username)")
            .eq("service", "mcqueen")
            .eq("enabled", True)
            .execute()
        )
        # Each row looks like {"users": {"telegram_chat_id": 123, "telegram_username": "foo"}}
        return [McQueenUser.model_validate(row) for row in response.data]

    except (APIError, ValidationError):
        logger.error("Error fetching users with McQueen enabled", exc_info=True)
        return None
    except Exception:
        logger.error(
            "Unexpected error fetching users with McQueen enabled", exc_info=True
        )
        return None


def get_authenticated_hermione_users() -> list[HermioneUser] | None:
    """Fetch every user with Hermione enabled."""

    try:
        response = (
            supabase.table(SERVICE_CREDENTIALS_TABLE)
            .select(
                "encrypted_secret, users!inner(telegram_chat_id, telegram_username)"
            )
            .eq("service", "hermione")
            .eq("enabled", True)
            .not_.is_("encrypted_secret", "null")
            .execute()
        )
        # Each row looks like
        # {"encrypted_secret": "...", "users": {"telegram_chat_id": 123, "telegram_username": "foo"}}
        return [HermioneUser.model_validate(row) for row in response.data]

    except (APIError, ValidationError):
        logger.error("Error fetching enabled Hermione credentials", exc_info=True)
        return None
    except Exception:
        logger.error(
            "Unexpected error fetching enabled Hermione credentials", exc_info=True
        )
        return None
