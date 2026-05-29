import os


class Config:
    def __init__(self):
        self.vk_token: str = self._get_env('VK_TOKEN', '')
        self.vk_api_version: str = self._get_env('VK_API_VERSION', '5.131')
        self.mongo_uri: str = self._get_env('MONGO_URI', '')
        self.mongo_db: str = self._get_env('MONGO_DB', '')
        self.mongo_collection: str = self._get_env('MONGO_COLLECTION', '')
        self.dgtu_api_token: str = self._get_env('DGTU_API_TOKEN', '')
        self.university_type: str = self._get_env('UNIVERSITY_TYPE', 'T').strip() or 'T'
        self.eios_encryption_key: str = self._get_env('EIOS_ENCRYPTION_KEY', '')
        self.mongo_eios_collection: str = (
            self._get_env('MONGO_EIOS_COLLECTION', '') or 'eios_credentials'
        )

        self.miniapp_enabled: bool = self._get_env('MINIAPP_ENABLED', '1').strip().lower() in (
            '1', 'true', 'yes', 'on',
        )
        self.miniapp_host: str = self._get_env('MINIAPP_HOST', '0.0.0.0')
        # Dokploy и др. часто задают PORT; иначе MINIAPP_PORT (локально по умолчанию 8080)
        _port = (
            self._get_env('MINIAPP_PORT', '').strip()
            or self._get_env('PORT', '').strip()
            or '8080'
        )
        self.miniapp_port: int = int(_port)
        self.vk_app_secret: str = self._get_env('VK_APP_SECRET', '')
        self.vk_app_id: str = self._get_env('VK_APP_ID', '')
        self.miniapp_allow_unsigned: bool = self._get_env(
            'MINIAPP_ALLOW_UNSIGNED', '0'
        ).strip().lower() in ('1', 'true', 'yes', 'on')

        if not self.vk_token:
            raise ValueError("VK_TOKEN обязателен для работы бота")

    @staticmethod
    def _get_env(key: str, default: str = '') -> str:
        return os.getenv(key, default)
