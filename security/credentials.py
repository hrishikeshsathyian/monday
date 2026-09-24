"""Encryption helpers for service credentials."""

import logging

from cryptography.fernet import Fernet, InvalidToken

from config.settings import FERNET_KEY

logger = logging.getLogger(__name__)


def encrypt_secret(secret: str) -> str | None:
    """Encrypt a service secret for storage without logging its value."""

    try:
        res = Fernet(FERNET_KEY.encode()).encrypt(secret.encode()).decode()
        logger.info("Successfully encrypted service secret")
        return res
    
    except (TypeError, ValueError):
        logger.error("Unable to encrypt a service credential")
        return None


def decrypt_secret(encrypted_secret: str) -> str | None:
    """Decrypt a stored service secret without logging its value."""

    try:
        res = Fernet(FERNET_KEY.encode()).decrypt(encrypted_secret.encode()).decode()
        logger.info("Successfully decrypted service secret")
        return res
    except (InvalidToken, TypeError, ValueError, UnicodeDecodeError):
        logger.error("Unable to decrypt a stored service credential")
        return None
