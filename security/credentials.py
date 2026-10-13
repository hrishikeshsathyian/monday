"""Symmetric (Fernet) encryption for secret service credentials stored in the database."""

import logging

from cryptography.fernet import Fernet, InvalidToken
from config.settings import FERNET_KEY

logger = logging.getLogger(__name__)


def encrypt_secret(secret: str) -> str | None:
    """Encrypt a plaintext credential for storage. Returns None on failure."""
    try:
        return Fernet(FERNET_KEY.encode()).encrypt(secret.encode()).decode()
    except (TypeError, ValueError):
        logger.error("Unable to encrypt a service credential")
        return None


def decrypt_secret(encrypted_secret: str) -> str | None:
    """Decrypt a stored credential. Returns None on failure."""
    try:
        return Fernet(FERNET_KEY.encode()).decrypt(encrypted_secret.encode()).decode()
    except (InvalidToken, TypeError, ValueError, UnicodeDecodeError):
        logger.error("Unable to decrypt a stored service credential")
        return None
