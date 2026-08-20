import logging

from postgrest import APIError

from .client import supabase
from typing import Any

logger = logging.getLogger(__name__)

SERVICE_CREDENTIALS_TABLE = "service_credentials"


def create_service_credential(
    telegram_user_id: int,
    service: str,
    enabled: bool = True,
) -> bool:

    row: dict[str, Any] = {
        "user_id": telegram_user_id,
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
