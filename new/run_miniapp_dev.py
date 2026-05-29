#!/usr/bin/env python3
"""Локальный запуск только VK Mini App (без VK LongPoll)."""
import asyncio
import logging
import os

os.environ.setdefault("VK_TOKEN", "dev-placeholder")
os.environ.setdefault("MINIAPP_ALLOW_UNSIGNED", "1")
os.environ.setdefault("MINIAPP_ENABLED", "1")
os.environ.setdefault("MINIAPP_HOST", "127.0.0.1")
os.environ.setdefault("MINIAPP_PORT", "8080")
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017/")
os.environ.setdefault("MONGO_DB", "ras")
os.environ.setdefault("MONGO_COLLECTION", "sessions")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def _port_in_use(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return False
        except OSError:
            return True


def _free_port_hint(port: int) -> str:
    return (
        f"Порт {port} уже занят (часто — предыдущий запуск Mini App).\n"
        f"Остановите процесс: lsof -ti :{port} | xargs kill\n"
        f"Или укажите другой порт: MINIAPP_PORT=8081 python3 run_miniapp_dev.py"
    )


def _use_in_memory_mongo() -> None:
    """Если MongoDB недоступен — подмена на mongomock (только для локального теста)."""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=800)
        client.admin.command("ping")
        client.close()
        return
    except Exception:
        pass

    try:
        import mongomock  # type: ignore
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "mongomock"])
        import mongomock  # type: ignore

    import pymongo

    pymongo.MongoClient = mongomock.MongoClient  # type: ignore[misc, assignment]
    logger.warning("MongoDB недоступен — используется in-memory mongomock (данные не сохранятся после перезапуска)")


async def main() -> None:
    _use_in_memory_mongo()

    from bot.config import Config
    from bot.miniapp.server import start_server
    from bot.vk_bot import VKBot

    config = Config()
    if _port_in_use(config.miniapp_host, config.miniapp_port):
        raise SystemExit(_free_port_hint(config.miniapp_port))

    bot = VKBot(config)
    await start_server(config, bot.handlers)
    url = f"http://{config.miniapp_host}:{config.miniapp_port}/"
    logger.info("Mini App доступен: %s", url)
    logger.info("API: %sapi/health", url)
    logger.info("Режим dev: MINIAPP_ALLOW_UNSIGNED=1 (без подписи VK)")
    print(f"\n→ Откройте в браузере: {url}\n")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except OSError as e:
        if getattr(e, "errno", None) == 48:
            port = os.environ.get("MINIAPP_PORT", "8080")
            raise SystemExit(_free_port_hint(int(port))) from e
        raise
