import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _fernet(key: str) -> Fernet:
    raw = (key or "").strip()
    if not raw:
        raise ValueError("EIOS_ENCRYPTION_KEY не задан")
    try:
        return Fernet(raw.encode("ascii") if isinstance(raw, str) else raw)
    except Exception as e:
        raise ValueError("EIOS_ENCRYPTION_KEY должен быть ключом Fernet (base64)") from e


def encrypt_secret(plain: str, key: str) -> str:
    token = _fernet(key).encrypt(plain.encode("utf-8"))
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt_secret(cipher_b64: str, key: str) -> Optional[str]:
    if not cipher_b64:
        return None
    try:
        token = base64.urlsafe_b64decode(cipher_b64.encode("ascii"))
        return _fernet(key).decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        logger.error("Не удалось расшифровать учётные данные: %s", e)
        return None
