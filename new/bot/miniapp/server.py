import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from aiohttp import web

from bot.config import Config
from bot.miniapp.service import MiniAppService
from bot.miniapp.vk_auth import extract_auth

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "miniapp" / "static"
LAUNCH_HEADER = "X-VK-Launch-Params"


def _json_error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


async def _parse_body(request: web.Request) -> dict:
    if not request.can_read_body:
        return {}
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        text = await request.text()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}


class MiniAppServer:
    def __init__(self, config: Config, service: MiniAppService) -> None:
        self.config = config
        self.service = service
        self._secret = (config.vk_app_secret or "").strip()
        self._allow_unsigned = config.miniapp_allow_unsigned

    def _auth_user(self, request: web.Request) -> Tuple[Optional[str], Optional[web.Response]]:
        raw = request.headers.get(LAUNCH_HEADER, "")
        if not raw:
            raw = request.query.get("vk_params", "")
        user_id, err = extract_auth(
            raw, self._secret, allow_unsigned=self._allow_unsigned
        )
        if err:
            return None, _json_error(err, 401)
        return user_id, None

    async def handle_me(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        return web.json_response({"ok": True, "data": self.service.get_me(user_id)})

    async def handle_schedule(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        period = request.query.get("period", "today")
        date = request.query.get("date", "").strip() or None
        try:
            week_offset = max(0, int(request.query.get("week_offset", "0")))
        except ValueError:
            week_offset = 0
        try:
            data = self.service.get_schedule(
                user_id, period, week_offset=week_offset, date=date
            )
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("schedule error user=%s: %s", user_id, e)
            return _json_error("Ошибка загрузки расписания", 500)
        return web.json_response({"ok": True, "data": data})

    async def handle_university(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        body = await _parse_body(request)
        code = str(body.get("university") or body.get("code") or "").strip().upper()
        try:
            data = self.service.set_university(user_id, code)
        except ValueError as e:
            return _json_error(str(e), 400)
        return web.json_response({"ok": True, "data": data})

    async def handle_bind_group(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        body = await _parse_body(request)
        try:
            gid = int(body.get("groupId") or body.get("id"))
        except (TypeError, ValueError):
            return _json_error("Укажите groupId", 400)
        name = str(body.get("name") or f"id {gid}")
        data = self.service.bind_group(user_id, gid, name)
        return web.json_response({"ok": True, "data": data})

    async def handle_bind_aud(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        body = await _parse_body(request)
        try:
            aid = int(body.get("audId") or body.get("id"))
        except (TypeError, ValueError):
            return _json_error("Укажите audId", 400)
        name = str(body.get("name") or f"id {aid}")
        try:
            data = self.service.bind_auditorium(user_id, aid, name)
        except ValueError as e:
            return _json_error(str(e), 400)
        return web.json_response({"ok": True, "data": data})

    async def handle_schedule_kind(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        body = await _parse_body(request)
        kind = str(body.get("kind") or body.get("scheduleKind") or "").strip().lower()
        try:
            data = self.service.set_schedule_kind(user_id, kind)
        except ValueError as e:
            return _json_error(str(e), 400)
        return web.json_response({"ok": True, "data": data})

    async def handle_bind_teacher(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        body = await _parse_body(request)
        try:
            tid = int(body.get("teacherId") or body.get("id"))
        except (TypeError, ValueError):
            return _json_error("Укажите teacherId", 400)
        name = str(body.get("name") or f"id {tid}")
        data = self.service.bind_teacher(user_id, tid, name)
        return web.json_response({"ok": True, "data": data})

    async def handle_reset(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        data = self.service.reset_profile(user_id)
        return web.json_response({"ok": True, "data": data})

    async def handle_search_groups(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        q = request.query.get("q", "")
        try:
            limit = min(200, max(1, int(request.query.get("limit", "80"))))
        except ValueError:
            limit = 80
        try:
            items = self.service.list_groups(user_id, q, limit=limit)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("search groups: %s", e)
            return _json_error("Ошибка поиска групп", 500)
        return web.json_response({"ok": True, "data": items})

    async def handle_refresh_groups(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        try:
            data = self.service.refresh_groups_cache(user_id)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("refresh groups: %s", e)
            return _json_error("Не удалось обновить список групп", 500)
        return web.json_response({"ok": True, "data": data})

    async def handle_search_teachers(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        q = request.query.get("q", "")
        try:
            limit = min(200, max(1, int(request.query.get("limit", "0")))) if request.query.get("limit") else None
        except ValueError:
            limit = None
        try:
            items = self.service.search_teachers(user_id, q, limit=limit)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("search teachers: %s", e)
            return _json_error("Ошибка поиска преподавателей", 500)
        return web.json_response({"ok": True, "data": items})

    async def handle_refresh_teachers(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        try:
            data = self.service.refresh_teachers_cache(user_id)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("refresh teachers: %s", e)
            return _json_error("Не удалось обновить список преподавателей", 500)
        return web.json_response({"ok": True, "data": data})

    async def handle_search_auditoriums(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        q = request.query.get("q", "")
        try:
            limit = min(200, max(1, int(request.query.get("limit", "0")))) if request.query.get("limit") else None
        except ValueError:
            limit = None
        try:
            items = self.service.search_auditoriums(user_id, q, limit=limit)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("search aud: %s", e)
            return _json_error("Ошибка поиска аудиторий", 500)
        return web.json_response({"ok": True, "data": items})

    async def handle_refresh_auditoriums(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        try:
            data = self.service.refresh_auditoriums_cache(user_id)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("refresh aud: %s", e)
            return _json_error("Не удалось обновить список аудиторий", 500)
        return web.json_response({"ok": True, "data": data})

    async def handle_eios_status(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        meta = self.service.eios_status(user_id)
        return web.json_response(
            {
                "ok": True,
                "data": {
                    "available": meta["eios_available"],
                    "authenticated": meta["eios_authenticated"],
                    "canConfigure": meta["eios_can_configure"],
                    "eiosId": meta["eios_id"],
                },
            }
        )

    async def handle_eios_login(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        body = await _parse_body(request)
        login = str(body.get("login") or body.get("username") or "").strip()
        password = str(body.get("password") or "").strip()
        try:
            data = self.service.eios_login(user_id, login, password)
        except ValueError as e:
            return _json_error(str(e), 400)
        except Exception as e:
            logger.exception("eios login user=%s: %s", user_id, e)
            return _json_error("Ошибка авторизации ЭИОС", 500)
        return web.json_response({"ok": True, "data": data})

    async def handle_eios_logout(self, request: web.Request) -> web.Response:
        user_id, err_resp = self._auth_user(request)
        if err_resp:
            return err_resp
        try:
            data = self.service.eios_logout(user_id)
        except ValueError as e:
            return _json_error(str(e), 400)
        return web.json_response({"ok": True, "data": data})

    async def handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "service": "dgtu-miniapp"})


async def _serve_index(_request: web.Request) -> web.Response:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise web.HTTPNotFound(text="index.html not found — run: cd miniapp/frontend && npm run build")
    return web.FileResponse(index_path)


def create_app(config: Config, handlers) -> web.Application:
    service = MiniAppService(handlers)
    srv = MiniAppServer(config, service)
    app = web.Application()
    app.router.add_get("/api/health", srv.handle_health)
    app.router.add_get("/api/me", srv.handle_me)
    app.router.add_get("/api/schedule", srv.handle_schedule)
    app.router.add_post("/api/university", srv.handle_university)
    app.router.add_post("/api/profile/group", srv.handle_bind_group)
    app.router.add_post("/api/profile/teacher", srv.handle_bind_teacher)
    app.router.add_post("/api/profile/reset", srv.handle_reset)
    app.router.add_get("/api/groups/search", srv.handle_search_groups)
    app.router.add_post("/api/groups/refresh", srv.handle_refresh_groups)
    app.router.add_get("/api/teachers/search", srv.handle_search_teachers)
    app.router.add_post("/api/teachers/refresh", srv.handle_refresh_teachers)
    app.router.add_get("/api/auditoriums/search", srv.handle_search_auditoriums)
    app.router.add_post("/api/auditoriums/refresh", srv.handle_refresh_auditoriums)
    app.router.add_post("/api/profile/aud", srv.handle_bind_aud)
    app.router.add_post("/api/schedule-kind", srv.handle_schedule_kind)
    app.router.add_get("/api/eios/status", srv.handle_eios_status)
    app.router.add_post("/api/eios/login", srv.handle_eios_login)
    app.router.add_post("/api/eios/logout", srv.handle_eios_logout)

    if STATIC_DIR.is_dir():
        app.router.add_get("/", _serve_index)
        app.router.add_get("/index.html", _serve_index)
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.router.add_static("/assets", assets_dir)
        else:
            logger.warning("Mini App assets not found: %s", assets_dir)
    else:
        logger.warning("Mini App static not found: %s", STATIC_DIR)

    return app


async def _warm_rasp_cache(handlers) -> None:
    try:
        from bot.data.groups_catalog import GroupsCatalog
        from bot.data.rasp_catalog import auditoriums_catalog, teachers_catalog

        token = (handlers.bot.config.dgtu_api_token or "").strip() or None
        groups = GroupsCatalog(handlers.api)
        teachers = teachers_catalog(handlers.api)
        auds = auditoriums_catalog(handlers.api)
        for univ in ("T", "D"):
            try:
                ng = len(groups.get_groups(univ, token))
                nt = len(teachers.get_items(univ, token))
                na = len(auds.get_items(univ, token))
                logger.info(
                    "Каталог %s: групп %s, преподавателей %s, аудиторий %s",
                    univ,
                    ng,
                    nt,
                    na,
                )
            except Exception as e:
                logger.warning("Каталог %s: %s", univ, e)
    except Exception as e:
        logger.warning("warm rasp cache: %s", e)


async def start_server(config: Config, handlers) -> None:
    app = create_app(config, handlers)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.miniapp_host, config.miniapp_port)
    await site.start()
    await _warm_rasp_cache(handlers)
    logger.info(
        "VK Mini App: http://%s:%s (static: %s)",
        config.miniapp_host,
        config.miniapp_port,
        STATIC_DIR,
    )
