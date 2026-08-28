import logging

from postgrest import APIError
from pydantic import ValidationError
from typing import Any

from .client import supabase
from .models import DbUser

logger = logging.getLogger(__name__)

USERS_TABLE = "users"


def get_user(telegram_user_id: int) -> DbUser | None:
    try:
        response = (
            supabase.table(USERS_TABLE)
            .select("*")
            .eq("telegram_user_id", telegram_user_id)
            .execute()
        )

    except ValidationError as e:
        logger.error(f"ValidationError occurred while retrieving user : {e}")
        return None
    except APIError:
        logger.error(f"Error fetching user {telegram_user_id}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected exception {e} fetching user {telegram_user_id}")
        return None

    if not response.data:
        return None

    return DbUser.model_validate(response.data[0])


def try_create_user(
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str | None,
) -> bool:
    row: dict[str, Any] = {
        "telegram_user_id": telegram_user_id,
        "telegram_chat_id": telegram_chat_id,
        "telegram_username": telegram_username,
    }
    try:
        supabase.table(USERS_TABLE).insert(row).execute()
    except APIError:
        logger.error(f"Error creating user {telegram_user_id}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected exception {e} creating user {telegram_user_id}")
        return False

    logger.info(f"Created user {telegram_user_id} (@{telegram_username})")
    return True
