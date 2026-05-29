import hashlib
import hmac
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl, unquote


def parse_launch_params(raw: str) -> Dict[str, str]:
    """Разбор строки launch-параметров VK Mini Apps (query string)."""
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("?"):
        text = text[1:]
    pairs = parse_qsl(text, keep_blank_values=True)
    return {k: unquote(v) if isinstance(v, str) else str(v) for k, v in pairs}


def verify_launch_params(params: Dict[str, str], secret: str) -> bool:
    """
    Проверка подписи launch-параметров (алгоритм VK Mini Apps).
    https://dev.vk.com/ru/mini-apps/development/launch-params-sign
    """
    if not secret:
        return False
    sign = params.get("sign")
    if not sign:
        return False
    pairs = sorted((k, v) for k, v in params.items() if k != "sign")
    base = "&".join(f"{k}={v}" for k, v in pairs)
    digest = hashlib.md5((base + secret).encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, sign)


def vk_user_id_from_params(params: Dict[str, str]) -> Optional[str]:
    uid = params.get("vk_user_id") or params.get("user_id")
    if uid is None:
        return None
    return str(uid).strip() or None


def extract_auth(
    params_raw: str, secret: str, *, allow_unsigned: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """
    Возвращает (user_id, error_message).
    error_message — текст для клиента при ошибке авторизации.
    """
    params = parse_launch_params(params_raw)
    if not params:
        return None, "Нет параметров авторизации VK"

    if secret:
        if not verify_launch_params(params, secret):
            return None, "Неверная подпись launch-параметров"
    elif not allow_unsigned:
        return None, "Сервер не настроен: задайте VK_APP_SECRET"

    user_id = vk_user_id_from_params(params)
    if not user_id:
        return None, "Не удалось определить vk_user_id"
    return user_id, None
