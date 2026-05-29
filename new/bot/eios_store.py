import logging
from typing import Any, Dict, Optional, Tuple

from pymongo.collection import Collection

from bot.crypto_credentials import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)


class EiosCredentialsStore:
    def __init__(self, collection: Collection, encryption_key: str):
        self._col = collection
        self._key = encryption_key

    def has_credentials(self, vk_id: str) -> bool:
        doc = self._col.find_one({"_id": str(vk_id)}, projection={"eios_id": 1})
        return bool(doc and doc.get("eios_id"))

    def get_eios_id(self, vk_id: str) -> Optional[str]:
        doc = self._col.find_one({"_id": str(vk_id)}, projection={"eios_id": 1})
        if not doc:
            return None
        eid = doc.get("eios_id")
        return str(eid) if eid is not None else None

    def save(
        self,
        vk_id: str,
        eios_id: str,
        username: str,
        password: str,
    ) -> None:
        self._col.update_one(
            {"_id": str(vk_id)},
            {
                "$set": {
                    "vk_id": str(vk_id),
                    "eios_id": str(eios_id),
                    "username_enc": encrypt_secret(username, self._key),
                    "password_enc": encrypt_secret(password, self._key),
                }
            },
            upsert=True,
        )

    def load_login_password(self, vk_id: str) -> Optional[Tuple[str, str]]:
        doc = self._col.find_one({"_id": str(vk_id)})
        if not doc:
            return None
        user = decrypt_secret(doc.get("username_enc", ""), self._key)
        pwd = decrypt_secret(doc.get("password_enc", ""), self._key)
        if not user or not pwd:
            return None
        return user, pwd

    def delete(self, vk_id: str) -> None:
        self._col.delete_one({"_id": str(vk_id)})
