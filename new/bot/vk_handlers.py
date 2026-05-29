import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient, UpdateOne

from bot.api.timetable import TimetableAPI, parse_storage
from bot.eios_store import EiosCredentialsStore
from bot.constants import (
    academic_year_string,
    get_current_date,
    get_tomorrow_date,
    get_week_anchor_date,
)
from bot.localizer import localize
from bot.vk_menu import (
    EIOS_AUTH_BTN,
    EIOS_LOGOUT_BTN,
    aud_pick_keyboard,
    cancel_only_keyboard,
    get_main_menu,
    group_pick_keyboard,
    role_choice_keyboard,
    teacher_pick_keyboard,
    teacher_saved_keyboard,
    univ_choice_keyboard,
)

logger = logging.getLogger(__name__)

RE_TEACHER_BTN = re.compile(r"^▶\s*(\d+)\|")
RE_AUD_BTN = re.compile(r"^◆\s*(\d+)\|")
RE_GROUP_BTN = re.compile(r"^◇\s*(\d+)\|")
RE_BIND_GROUP_BTN = re.compile(r"^◎\s*(\d+)\|")
RE_BIND_TEACHER_BTN = re.compile(r"^★\s*(\d+)\|")

MAX_SAVED_TEACHERS = 12
EIOS_TOKEN_CACHE_TTL_SEC = 45 * 60
UNIV_PI_LABEL = "ПИ ДГТУ"
UNIV_D_LABEL = "ДГТУ"


class VKHandlers:
    def __init__(self, bot):
        self.bot = bot
        try:
            config = bot.config
            self.client = MongoClient(config.mongo_uri)
            self.client.admin.command("ping")
            self.collection = self.client[config.mongo_db][config.mongo_collection]
        except ImportError as e:
            raise ImportError("pip install pymongo") from e
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к MongoDB: {e}") from e

        self.api = TimetableAPI()
        self._univ = (config.university_type or "T")[0]
        eios_col = self.client[config.mongo_db][config.mongo_eios_collection]
        self._eios_store = EiosCredentialsStore(eios_col, config.eios_encryption_key or "")
        self._eios_token_cache: Dict[str, Tuple[str, float]] = {}

    def _show_eios_auth(self, user_id: str) -> bool:
        return self._university(user_id) == "D"

    def _eios_authenticated(self, user_id: str) -> bool:
        if not self._show_eios_auth(user_id):
            return False
        return self._eios_store.has_credentials(user_id)

    def _invalidate_eios_token_cache(self, user_id: str) -> None:
        self._eios_token_cache.pop(str(user_id), None)

    def _get_user_eios_token(self, user_id: str) -> Optional[str]:
        if not self._eios_authenticated(user_id):
            return None
        now = time.time()
        cached = self._eios_token_cache.get(user_id)
        if cached and cached[1] > now:
            return cached[0]
        creds = self._eios_store.load_login_password(user_id)
        if not creds:
            return None
        login, password = creds
        try:
            payload = self.api.auth_user("D", login, password)
        except Exception as e:
            logger.error("eios re-auth user=%s: %s", user_id, e)
            return None
        token, _, err = TimetableAPI.parse_auth_response(payload)
        if not token:
            logger.warning("eios re-auth failed user=%s: %s", user_id, err)
            return None
        self._eios_token_cache[user_id] = (token, now + EIOS_TOKEN_CACHE_TTL_SEC)
        return token

    def _api_token(self, user_id: str) -> Optional[str]:
        if self._show_eios_auth(user_id):
            user_tok = self._get_user_eios_token(user_id)
            if user_tok:
                return user_tok
        t = (self.bot.config.dgtu_api_token or "").strip()
        return t or None

    def _role_choice_keyboard(self, user_id: str) -> Dict[str, Any]:
        show_eios = self._show_eios_auth(user_id)
        return role_choice_keyboard(
            show_eios_auth=show_eios,
            eios_authenticated=self._eios_authenticated(user_id) if show_eios else False,
        )

    def eios_login(self, user_id: str, login: str, password: str) -> Dict[str, Any]:
        login = (login or "").strip()
        password = (password or "").strip()
        if not login or not password:
            raise ValueError("Введите логин и пароль")
        if not self._show_eios_auth(user_id):
            raise ValueError("Дополнительная авторизация доступна только для ДГТУ")
        if not (self.bot.config.eios_encryption_key or "").strip():
            raise ValueError(
                "Сохранение учётных данных недоступно: не задан EIOS_ENCRYPTION_KEY на сервере"
            )
        try:
            payload = self.api.auth_user("D", login, password)
        except Exception as e:
            logger.error("eios auth user=%s: %s", user_id, e, exc_info=True)
            raise ValueError("Ошибка связи с ЭИОС, попробуйте позже") from e

        token, eios_id, err = TimetableAPI.parse_auth_response(payload)
        if not token:
            raise ValueError(err or "Неверный логин или пароль")

        eios_id = eios_id or user_id
        self._eios_store.save(user_id, eios_id, login, password)
        self._eios_token_cache[user_id] = (token, time.time() + EIOS_TOKEN_CACHE_TTL_SEC)
        return {"eiosId": str(eios_id)}

    def eios_logout(self, user_id: str) -> None:
        if not self._show_eios_auth(user_id):
            raise ValueError("Дополнительная авторизация доступна только для ДГТУ")
        self._eios_store.delete(user_id)
        self._invalidate_eios_token_cache(user_id)

    def _university(self, user_id: str) -> str:
        stored = self._get(self._k(user_id, "university"))
        if stored in ("T", "D"):
            return stored
        return self._univ

    def _has_user_university(self, user_id: str) -> bool:
        return self._get(self._k(user_id, "university")) in ("T", "D")

    @staticmethod
    def _parse_univ_from_text(text: str) -> Optional[str]:
        t = (text or "").strip().casefold()
        if t in (UNIV_PI_LABEL.casefold(), "пи", "t", "tpi"):
            return "T"
        if t in (UNIV_D_LABEL.casefold(), "дгту", "d"):
            return "D"
        if "пи" in t and "дгту" in t:
            return "T"
        if t == "дгту" or (t.startswith("дгту") and "пи" not in t):
            return "D"
        return None

    @staticmethod
    def _univ_display_name(code: str) -> str:
        return UNIV_PI_LABEL if code == "T" else UNIV_D_LABEL

    def _schedule_keyboard(self, user_id: str) -> Dict[str, Any]:
        show_eios = self._show_eios_auth(user_id)
        eios_ok = self._eios_authenticated(user_id) if show_eios else False
        if not self._has_profile(user_id):
            if not self._has_user_university(user_id):
                return univ_choice_keyboard()
            return self._role_choice_keyboard(user_id)
        return get_main_menu(
            has_focus=bool(self._get_focus(user_id)),
            show_eios_auth=show_eios,
            eios_authenticated=eios_ok,
        )

    @staticmethod
    def _split_message_chunks(text: str, limit: int = 3800) -> List[str]:
        if len(text) <= limit:
            return [text]
        parts: List[str] = []
        rest = text
        while rest:
            if len(rest) <= limit:
                parts.append(rest)
                break
            cut = rest.rfind("\n", 0, limit)
            if cut == -1 or cut < max(80, limit // 4):
                cut = limit
            parts.append(rest[:cut].rstrip("\n"))
            rest = rest[cut:].lstrip("\n")
        return parts

    def _send_plain_chunks(self, peer_id: int, body: str, keyboard: Optional[dict] = None) -> None:
        parts = self._split_message_chunks(body, 3800)
        for i, part in enumerate(parts):
            self.bot._send_message(peer_id, part, keyboard if i == len(parts) - 1 else None)

    @staticmethod
    def _get_user_id(peer_id: int) -> str:
        return str(peer_id)

    def _k(self, user_id: str, suffix: str = "") -> str:
        return f"{user_id}:{suffix}" if suffix else user_id

    def _get(self, key: str) -> Optional[str]:
        doc = self.collection.find_one({"_id": key})
        return doc.get("value") if doc else None

    def _set(self, key: str, value: str) -> None:
        self.collection.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

    def _set_many(self, data: Dict[str, str]) -> None:
        operations = [
            UpdateOne({"_id": key}, {"$set": {"value": value}}, upsert=True)
            for key, value in data.items()
        ]
        if operations:
            self.collection.bulk_write(operations)

    def _delete(self, key: str) -> None:
        self.collection.delete_one({"_id": key})

    def _delete_many(self, keys: List[str]) -> None:
        if keys:
            self.collection.delete_many({"_id": {"$in": keys}})

    def _load_json(self, user_id: str, suffix: str) -> Any:
        raw = self._get(self._k(user_id, suffix))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _save_json(self, user_id: str, suffix: str, obj: Any) -> None:
        self._set(self._k(user_id, suffix), json.dumps(obj, ensure_ascii=False))

    def _delete_json(self, user_id: str, suffix: str) -> None:
        self._delete(self._k(user_id, suffix))

    def _clear_flow(self, user_id: str) -> None:
        self._delete_many(
            [
                self._k(user_id, "flow"),
                self._k(user_id, "teacher_pick"),
                self._k(user_id, "aud_pick"),
                self._k(user_id, "group_pick"),
                self._k(user_id, "bind_group_pick"),
                self._k(user_id, "bind_teacher_pick"),
            ]
        )

    def _has_profile(self, user_id: str) -> bool:
        return bool(self._get(user_id))

    def _require_profile(self, user_id: str) -> Optional[str]:
        return self._get(user_id)

    def _get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_json(user_id, "my_profile")
        if isinstance(data, dict):
            return data
        legacy = self._load_json(user_id, "my_group")
        if isinstance(legacy, dict) and legacy.get("name"):
            return {"role": "student", "id": legacy.get("id"), "name": legacy.get("name")}
        return None

    def _profile_role(self, user_id: str) -> Optional[str]:
        p = self._get_profile(user_id)
        return str(p.get("role", "")) if p else None

    def _profile_label(self, user_id: str) -> str:
        p = self._get_profile(user_id)
        if not p:
            return ""
        role = p.get("role")
        name = p.get("name", "")
        if role == "teacher":
            return f"преподаватель {name}"
        if role == "student":
            return f"группа {name}"
        return str(name)

    def _focus_exit_message(self, user_id: str) -> str:
        if self._profile_role(user_id) == "teacher":
            return localize("FocusModeExitTeacher", {})
        return localize("FocusModeExitStudent", {})

    def _saved_teachers(self, user_id: str) -> List[Dict[str, Any]]:
        data = self._load_json(user_id, "saved_teachers")
        if isinstance(data, list):
            return data
        return []

    def _upsert_saved_teacher(self, user_id: str, tid: int, name: str) -> None:
        saved = self._saved_teachers(user_id)
        saved = [x for x in saved if int(x.get("id", -1)) != int(tid)]
        saved.insert(0, {"id": int(tid), "name": name})
        saved = saved[:MAX_SAVED_TEACHERS]
        self._save_json(user_id, "saved_teachers", saved)

    def _set_focus(self, user_id: str, kind: str, eid: int, name: str) -> None:
        self._save_json(user_id, "focus", {"kind": kind, "id": int(eid), "name": name})

    def _clear_focus(self, user_id: str) -> None:
        self._delete(self._k(user_id, "focus"))

    def _get_focus(self, user_id: str) -> Optional[Dict[str, Any]]:
        f = self._load_json(user_id, "focus")
        return f if isinstance(f, dict) else None

    def _format_focus_hint(self, focus: Optional[Dict[str, Any]]) -> str:
        if not focus:
            return ""
        k = focus.get("kind")
        nm = focus.get("name", "")
        if k == "teacher":
            return localize("FocusTeacherHint", {"name": nm})
        if k == "aud":
            return localize("FocusAudHint", {"name": nm})
        if k == "group":
            return localize("FocusGroupHint", {"name": nm})
        return ""

    async def start_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if self._has_profile(user_id):
            self.bot._send_message(
                peer_id,
                localize(
                    "StartHandlerReturning",
                    {"profile": self._profile_label(user_id)},
                ),
                self._schedule_keyboard(user_id),
            )
            return
        self._begin_univ_choice(
            peer_id, user_id, localize("StartHandlerWelcome", {})
        )

    def _begin_univ_choice(self, peer_id: int, user_id: str, intro: str) -> None:
        self._clear_flow(user_id)
        self._clear_focus(user_id)
        self._set(self._k(user_id, "flow"), "univ_choice")
        msg = intro.strip()
        if localize("UnivChoicePrompt", {}) not in msg:
            msg = f"{msg}\n\n{localize('UnivChoicePrompt', {})}"
        self.bot._send_message(peer_id, msg, univ_choice_keyboard())

    def _begin_role_choice(self, peer_id: int, user_id: str, intro: str) -> None:
        self._clear_flow(user_id)
        self.bot._send_message(peer_id, intro, self._role_choice_keyboard(user_id))

    def _apply_univ_choice(self, peer_id: int, user_id: str, code: str) -> None:
        self._set(self._k(user_id, "university"), code)
        self._clear_flow(user_id)
        name = self._univ_display_name(code)
        intro = (
            f"{localize('UnivSelected', {'name': name})}\n\n"
            f"{localize('RoleChoicePrompt', {})}"
        )
        self._begin_role_choice(peer_id, user_id, intro)

    def _begin_bind_group(self, peer_id: int, user_id: str, intro: str) -> None:
        self._clear_flow(user_id)
        self._clear_focus(user_id)
        self._set(self._k(user_id, "flow"), "bind_group_query")
        self.bot._send_message(peer_id, intro, cancel_only_keyboard())

    def _begin_bind_teacher(self, peer_id: int, user_id: str, intro: str) -> None:
        self._clear_flow(user_id)
        self._clear_focus(user_id)
        self._set(self._k(user_id, "flow"), "bind_teacher_query")
        self.bot._send_message(peer_id, intro, cancel_only_keyboard())

    async def student_role_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_user_university(user_id):
            self._begin_univ_choice(peer_id, user_id, localize("UnivChoicePrompt", {}))
            return
        self._begin_bind_group(peer_id, user_id, localize("BindGroupWelcome", {}))

    async def teacher_role_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_user_university(user_id):
            self._begin_univ_choice(peer_id, user_id, localize("UnivChoicePrompt", {}))
            return
        self._begin_bind_teacher(peer_id, user_id, localize("BindTeacherWelcome", {}))

    async def pi_univ_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._apply_univ_choice(peer_id, user_id, "T")

    async def dgtu_univ_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._apply_univ_choice(peer_id, user_id, "D")

    async def change_profile_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._purge_user_data(user_id)
        self._begin_univ_choice(peer_id, user_id, localize("ChangeProfilePrompt", {}))

    def _purge_user_data(self, user_id: str) -> None:
        keys = [
            user_id,
            self._k(user_id, "my_profile"),
            self._k(user_id, "my_group"),
            self._k(user_id, "focus"),
            self._k(user_id, "flow"),
            self._k(user_id, "teacher_pick"),
            self._k(user_id, "aud_pick"),
            self._k(user_id, "group_pick"),
            self._k(user_id, "bind_group_pick"),
            self._k(user_id, "bind_teacher_pick"),
            self._k(user_id, "university"),
            self._k(user_id, "saved_teachers"),
            self._k(user_id, "week_offset"),
            self._k(user_id, "last_period"),
        ]
        self._delete_many(keys)
        self._eios_store.delete(user_id)
        self._invalidate_eios_token_cache(user_id)

    async def eios_auth_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._show_eios_auth(user_id):
            self.bot._send_message(
                peer_id,
                localize("EiosAuthOnlyDgtu", {}),
                self._schedule_keyboard(user_id),
            )
            return
        if self._eios_authenticated(user_id):
            self.bot._send_message(
                peer_id,
                localize("EiosAuthAlready", {}),
                self._schedule_keyboard(user_id),
            )
            return
        if not (self.bot.config.eios_encryption_key or "").strip():
            self.bot._send_message(
                peer_id,
                localize("EiosAuthNoKey", {}),
                self._schedule_keyboard(user_id),
            )
            return
        self._clear_flow(user_id)
        self._set(self._k(user_id, "flow"), "eios_auth_login")
        self.bot._send_message(
            peer_id,
            localize("EiosAuthIntro", {}) + "\n\n" + localize("EiosAuthEnterLogin", {}),
            cancel_only_keyboard(),
        )

    async def eios_logout_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._show_eios_auth(user_id):
            self.bot._send_message(
                peer_id,
                localize("EiosAuthOnlyDgtu", {}),
                self._schedule_keyboard(user_id),
            )
            return
        self._clear_flow(user_id)
        self.eios_logout(user_id)
        self.bot._send_message(
            peer_id,
            localize("EiosAuthLoggedOut", {}),
            self._schedule_keyboard(user_id),
        )

    def _bind_my_group(self, peer_id: int, user_id: str, gid: int, name: str) -> None:
        univ = self._university(user_id)
        self._set(user_id, f"{univ}{gid}")
        self._save_json(
            user_id, "my_profile", {"role": "student", "id": int(gid), "name": name}
        )
        self._clear_flow(user_id)
        self._clear_focus(user_id)
        self.bot._send_message(
            peer_id,
            localize("BindGroupDone", {"name": name}),
            self._schedule_keyboard(user_id),
        )

    def _bind_my_teacher(self, peer_id: int, user_id: str, tid: int, name: str) -> None:
        univ = self._university(user_id)
        self._set(user_id, f"{univ}{tid}T")
        self._save_json(
            user_id, "my_profile", {"role": "teacher", "id": int(tid), "name": name}
        )
        self._clear_flow(user_id)
        self._clear_focus(user_id)
        self.bot._send_message(
            peer_id,
            localize("BindTeacherDone", {"name": name}),
            self._schedule_keyboard(user_id),
        )

    async def legacy_menu_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_user_university(user_id):
            self._begin_univ_choice(peer_id, user_id, localize("UnivChoicePrompt", {}))
            return
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("RoleChoicePrompt", {}))
            return
        self.bot._send_message(
            peer_id,
            localize("StartHandlerReturning", {"profile": self._profile_label(user_id)}),
            self._schedule_keyboard(user_id),
        )

    def _ensure_profile_or_choose(self, peer_id: int, user_id: str) -> bool:
        if self._has_profile(user_id):
            return True
        if not self._has_user_university(user_id):
            self._begin_univ_choice(peer_id, user_id, localize("UnivChoicePrompt", {}))
        else:
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
        return False

    async def help_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        text = localize(
            "HelpHandler",
            {
                "BtnToday": "📖 Сегодня",
                "BtnTomorrow": "📖 Завтра",
                "BtnWeek": "📖 Неделя",
            },
        )
        self.bot._send_message(peer_id, text, self._schedule_keyboard(user_id))

    def _get_week_offset(self, user_id: str) -> int:
        raw = self._get(self._k(user_id, "week_offset"))
        if not raw:
            return 0
        try:
            return max(0, int(raw))
        except ValueError:
            return 0

    def _set_week_offset(self, user_id: str, offset: int) -> None:
        self._set(self._k(user_id, "week_offset"), str(max(0, offset)))

    def _clear_week_offset(self, user_id: str) -> None:
        self._delete(self._k(user_id, "week_offset"))

    def _get_last_period(self, user_id: str) -> str:
        p = self._get(self._k(user_id, "last_period"))
        return p if p in ("today", "tomorrow", "week", "all") else "week"

    def _set_last_period(self, user_id: str, period: str) -> None:
        if period in ("today", "tomorrow", "week", "all"):
            self._set(self._k(user_id, "last_period"), period)

    async def today_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._clear_week_offset(user_id)
        self._set_last_period(user_id, "today")
        await self._send_timetable(peer_id, "today")

    async def tomorrow_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._clear_week_offset(user_id)
        self._set_last_period(user_id, "tomorrow")
        await self._send_timetable(peer_id, "tomorrow")

    async def week_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._clear_week_offset(user_id)
        self._set_last_period(user_id, "week")
        await self._send_timetable(peer_id, "week")

    async def all_schedule_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._clear_week_offset(user_id)
        self._set_last_period(user_id, "all")
        await self._send_timetable(peer_id, "all")

    async def next_week_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._ensure_profile_or_choose(peer_id, user_id):
            return
        offset = self._get_week_offset(user_id) + 1
        self._set_week_offset(user_id, offset)
        await self._send_timetable(peer_id, self._get_last_period(user_id), week_offset=offset)

    async def focus_exit_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
            return
        if not self._get_focus(user_id):
            self.bot._send_message(
                peer_id,
                localize("FocusExitNoMode", {}),
                self._schedule_keyboard(user_id),
            )
            return
        self._clear_focus(user_id)
        self._clear_flow(user_id)
        self.bot._send_message(
            peer_id,
            self._focus_exit_message(user_id),
            self._schedule_keyboard(user_id),
        )

    async def teacher_menu_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
            return
        saved = self._saved_teachers(user_id)
        self._clear_flow(user_id)
        if saved:
            self.bot._send_message(
                peer_id,
                localize("TeacherMenuSaved", {}),
                teacher_saved_keyboard(saved),
            )
        else:
            self._set(self._k(user_id, "flow"), "teacher_surname")
            self.bot._send_message(
                peer_id, localize("TeacherEnterSurname", {}), cancel_only_keyboard()
            )

    async def teacher_other_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
            return
        self._set(self._k(user_id, "flow"), "teacher_surname")
        self.bot._send_message(
            peer_id, localize("TeacherEnterSurname", {}), cancel_only_keyboard()
        )

    async def cancel_flow_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        self._clear_flow(user_id)
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("RoleChoicePrompt", {}))
            return
        self.bot._send_message(
            peer_id,
            localize("FlowCancelled", {}),
            self._schedule_keyboard(user_id),
        )

    async def aud_menu_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
            return
        self._clear_flow(user_id)
        self._set(self._k(user_id, "flow"), "aud_query")
        self.bot._send_message(peer_id, localize("AudEnterQuery", {}), cancel_only_keyboard())

    async def group_menu_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        if not self._has_profile(user_id):
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
            return
        self._clear_flow(user_id)
        self._set(self._k(user_id, "flow"), "group_query")
        self.bot._send_message(peer_id, localize("GroupEnterQuery", {}), cancel_only_keyboard())

    async def text_message_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        text = context["text"].strip()

        handled = await self._try_handle_special_buttons(peer_id, user_id, text)
        if handled:
            return

        if self._has_profile(user_id):
            saved = self._saved_teachers(user_id)
            for teacher in saved:
                if teacher.get("name", "") == text:
                    await self._select_teacher_named(
                        peer_id, user_id, int(teacher["id"]), teacher["name"]
                    )
                    return

        await self._handle_free_text(peer_id, user_id, text)

    async def _try_handle_special_buttons(
        self, peer_id: int, user_id: str, text: str
    ) -> bool:
        m = RE_BIND_GROUP_BTN.match(text)
        if m:
            gid = int(m.group(1))
            await self._select_bind_group_by_id(peer_id, user_id, gid)
            return True

        m = RE_BIND_TEACHER_BTN.match(text)
        if m:
            tid = int(m.group(1))
            await self._select_bind_teacher_by_id(peer_id, user_id, tid)
            return True

        if not self._has_profile(user_id):
            return False

        m = RE_TEACHER_BTN.match(text)
        if m:
            tid = int(m.group(1))
            await self._select_teacher_by_id(peer_id, user_id, tid)
            return True

        m = RE_AUD_BTN.match(text)
        if m:
            aid = int(m.group(1))
            await self._select_aud_by_id(peer_id, user_id, aid)
            return True

        m = RE_GROUP_BTN.match(text)
        if m:
            gid = int(m.group(1))
            await self._select_group_by_id(peer_id, user_id, gid)
            return True

        return False

    async def _handle_free_text(self, peer_id: int, user_id: str, text: str):
        flow = self._get(self._k(user_id, "flow"))

        if flow == "eios_auth_login":
            await self._flow_eios_login(peer_id, user_id, text)
            return
        if flow == "eios_auth_password":
            await self._flow_eios_password(peer_id, user_id, text)
            return

        if flow == "bind_group_query":
            await self._flow_bind_group_query(peer_id, user_id, text)
            return
        if flow == "bind_group_pick":
            await self._flow_bind_group_pick(peer_id, user_id, text)
            return
        if flow == "bind_teacher_query":
            await self._flow_bind_teacher_query(peer_id, user_id, text)
            return
        if flow == "bind_teacher_pick":
            await self._flow_bind_teacher_pick(peer_id, user_id, text)
            return
        if flow == "univ_choice":
            code = self._parse_univ_from_text(text)
            if not code:
                self.bot._send_message(
                    peer_id,
                    localize("UnivChoiceInvalid", {}),
                    univ_choice_keyboard(),
                )
                return
            self._apply_univ_choice(peer_id, user_id, code)
            return

        if not self._has_profile(user_id):
            code = self._parse_univ_from_text(text)
            if code:
                self._apply_univ_choice(peer_id, user_id, code)
                return
            if not self._has_user_university(user_id):
                self._begin_univ_choice(peer_id, user_id, localize("UnivChoicePrompt", {}))
            else:
                self._begin_role_choice(peer_id, user_id, localize("RoleChoicePrompt", {}))
            return

        storage = self._require_profile(user_id)
        if flow == "teacher_surname":
            await self._flow_teacher_surname(peer_id, user_id, text, storage)
        elif flow == "teacher_pick":
            await self._flow_teacher_pick(peer_id, user_id, text)
        elif flow == "aud_query":
            await self._flow_aud_query(peer_id, user_id, text, storage)
        elif flow == "aud_pick":
            await self._flow_aud_pick(peer_id, user_id, text)
        elif flow == "group_query":
            await self._flow_group_query(peer_id, user_id, text, storage)
        elif flow == "group_pick":
            await self._flow_group_pick(peer_id, user_id, text)
        else:
            self.bot._send_message(
                peer_id,
                localize("UseMenuHint", {}),
                self._schedule_keyboard(user_id),
            )

    async def _flow_eios_login(self, peer_id: int, user_id: str, login: str):
        login = login.strip()
        if not login:
            self.bot._send_message(peer_id, localize("EiosAuthEnterLogin", {}), cancel_only_keyboard())
            return
        self._set(self._k(user_id, "eios_pending_login"), login)
        self._set(self._k(user_id, "flow"), "eios_auth_password")
        self.bot._send_message(peer_id, localize("EiosAuthEnterPassword", {}), cancel_only_keyboard())

    async def _flow_eios_password(self, peer_id: int, user_id: str, password: str):
        login = (self._get(self._k(user_id, "eios_pending_login")) or "").strip()
        if not login:
            self._clear_flow(user_id)
            self.bot._send_message(peer_id, localize("TryLaterError", {}), self._schedule_keyboard(user_id))
            return
        try:
            result = self.eios_login(user_id, login, password)
        except ValueError as e:
            self.bot._send_message(
                peer_id,
                localize("EiosAuthFailed", {"reason": str(e)}),
                cancel_only_keyboard(),
            )
            return
        self._clear_flow(user_id)
        self.bot._send_message(
            peer_id,
            localize("EiosAuthSuccess", {"eios_id": result["eiosId"]}),
            self._schedule_keyboard(user_id),
        )

    async def _flow_bind_group_query(self, peer_id: int, user_id: str, query: str):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            groups = self.api.list_groups(univ, token, year)
        except Exception as e:
            logger.error("list_groups: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return

        q = query.casefold().strip()
        matches = [g for g in groups if q in (g.get("name") or "").casefold()]
        if not matches:
            self.bot._send_message(peer_id, localize("GroupNotFound", {}), cancel_only_keyboard())
            return
        if len(matches) == 1:
            g = matches[0]
            self._bind_my_group(peer_id, user_id, int(g["id"]), str(g.get("name", "")))
            return

        matches.sort(key=lambda x: (x.get("name") or ""))
        self._save_json(user_id, "bind_group_pick", matches[:15])
        self._set(self._k(user_id, "flow"), "bind_group_pick")
        self.bot._send_message(
            peer_id,
            localize("GroupPickMany", {"n": len(matches)}),
            group_pick_keyboard(matches[:10], bind=True),
        )

    async def _flow_bind_group_pick(self, peer_id: int, user_id: str, text: str):
        candidates = self._load_json(user_id, "bind_group_pick")
        if not isinstance(candidates, list):
            self._clear_flow(user_id)
            return
        tnorm = text.casefold().strip()
        chosen = None
        for c in candidates:
            if (c.get("name") or "").strip().casefold() == tnorm:
                chosen = c
                break
        if not chosen:
            self.bot._send_message(peer_id, localize("GroupPickInvalid", {}))
            return
        self._bind_my_group(peer_id, user_id, int(chosen["id"]), str(chosen.get("name", "")))

    async def _select_bind_group_by_id(self, peer_id: int, user_id: str, gid: int):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            groups = self.api.list_groups(univ, token, year)
        except Exception as e:
            logger.error("list_groups: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return
        name = ""
        for g in groups:
            if int(g.get("id", -1)) == int(gid):
                name = str(g.get("name", ""))
                break
        if not name:
            name = f"id {gid}"
        self._bind_my_group(peer_id, user_id, gid, name)

    async def _flow_bind_teacher_query(self, peer_id: int, user_id: str, query: str):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            teachers = self.api.list_teachers(univ, token, year)
        except Exception as e:
            logger.error("list_teachers: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return

        q = query.casefold().strip()
        matches = [t for t in teachers if q in (t.get("name") or "").casefold()]
        if not matches:
            self.bot._send_message(
                peer_id, localize("TeacherNotFound", {}), cancel_only_keyboard()
            )
            return
        if len(matches) == 1:
            t = matches[0]
            self._bind_my_teacher(
                peer_id, user_id, int(t["id"]), str(t.get("name", ""))
            )
            return

        matches.sort(key=lambda x: (x.get("name") or ""))
        self._save_json(user_id, "bind_teacher_pick", matches[:15])
        self._set(self._k(user_id, "flow"), "bind_teacher_pick")
        self.bot._send_message(
            peer_id,
            localize("TeacherPickMany", {"n": len(matches)}),
            teacher_pick_keyboard(matches[:10], bind=True),
        )

    async def _flow_bind_teacher_pick(self, peer_id: int, user_id: str, text: str):
        candidates = self._load_json(user_id, "bind_teacher_pick")
        if not isinstance(candidates, list):
            self._clear_flow(user_id)
            return
        tnorm = text.casefold().strip()
        chosen = None
        for c in candidates:
            if (c.get("name") or "").strip().casefold() == tnorm:
                chosen = c
                break
        if not chosen:
            self.bot._send_message(peer_id, localize("TeacherPickInvalid", {}))
            return
        self._bind_my_teacher(
            peer_id, user_id, int(chosen["id"]), str(chosen.get("name", ""))
        )

    async def _select_bind_teacher_by_id(self, peer_id: int, user_id: str, tid: int):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            teachers = self.api.list_teachers(univ, token, year)
        except Exception as e:
            logger.error("list_teachers: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return
        name = ""
        for t in teachers:
            if int(t.get("id", -1)) == int(tid):
                name = str(t.get("name", ""))
                break
        if not name:
            name = f"id {tid}"
        self._bind_my_teacher(peer_id, user_id, tid, name)

    async def _flow_teacher_surname(
        self, peer_id: int, user_id: str, query: str, storage: str
    ):
        univ = storage[0]
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            teachers = self.api.list_teachers(univ, token, year)
        except Exception as e:
            logger.error("list_teachers: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return

        q = query.casefold().strip()
        matches = [t for t in teachers if q in (t.get("name") or "").casefold()]
        if not matches:
            self.bot._send_message(
                peer_id,
                localize("TeacherNotFound", {}),
                self._schedule_keyboard(user_id),
            )
            return

        if len(matches) == 1:
            t = matches[0]
            await self._select_teacher_named(
                peer_id, user_id, int(t["id"]), str(t.get("name", ""))
            )
            return

        matches.sort(key=lambda x: (x.get("name") or ""))
        self._save_json(user_id, "teacher_pick", matches[:15])
        self._set(self._k(user_id, "flow"), "teacher_pick")
        self.bot._send_message(
            peer_id,
            localize("TeacherPickMany", {"n": len(matches)}),
            teacher_pick_keyboard(matches[:10]),
        )

    async def _flow_teacher_pick(self, peer_id: int, user_id: str, text: str):
        candidates = self._load_json(user_id, "teacher_pick")
        if not isinstance(candidates, list):
            self._clear_flow(user_id)
            return

        tnorm = text.casefold().strip()
        chosen = None
        for c in candidates:
            if (c.get("name") or "").strip().casefold() == tnorm:
                chosen = c
                break

        if not chosen:
            self.bot._send_message(peer_id, localize("TeacherPickInvalid", {}))
            return

        if not self._has_profile(user_id):
            return

        await self._select_teacher_named(
            peer_id, user_id, int(chosen["id"]), str(chosen.get("name", ""))
        )

    async def _select_teacher_by_id(self, peer_id: int, user_id: str, tid: int):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            teachers = self.api.list_teachers(univ, token, year)
        except Exception as e:
            logger.error("list_teachers: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return

        name = ""
        for t in teachers:
            if int(t.get("id", -1)) == int(tid):
                name = str(t.get("name", ""))
                break
        if not name:
            name = f"id {tid}"

        await self._select_teacher_named(peer_id, user_id, tid, name)

    async def _select_teacher_named(
        self,
        peer_id: int,
        user_id: str,
        tid: int,
        name: str,
    ):
        self._upsert_saved_teacher(user_id, tid, name)
        self._set_focus(user_id, "teacher", tid, name)
        self._clear_flow(user_id)
        msg = localize("TeacherSelected", {"name": name}) + "\n\n" + self._format_focus_hint(
            self._get_focus(user_id)
        )
        self.bot._send_message(peer_id, msg, self._schedule_keyboard(user_id))

    async def _flow_aud_query(self, peer_id: int, user_id: str, query: str, storage: str):
        univ = storage[0]
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            auds = self.api.list_auditoriums(univ, token, year)
        except Exception as e:
            logger.error("list_auditoriums: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return

        q = query.casefold().strip()
        matches = [a for a in auds if q in (a.get("name") or "").casefold()]
        if not matches:
            self.bot._send_message(
                peer_id,
                localize("AudNotFound", {}),
                self._schedule_keyboard(user_id),
            )
            return
        if len(matches) == 1:
            a = matches[0]
            await self._select_aud_named(
                peer_id, user_id, int(a["id"]), str(a.get("name", ""))
            )
            return

        matches.sort(key=lambda x: (x.get("name") or ""))
        self._save_json(user_id, "aud_pick", matches[:15])
        self._set(self._k(user_id, "flow"), "aud_pick")
        self.bot._send_message(
            peer_id,
            localize("AudPickMany", {"n": len(matches)}),
            aud_pick_keyboard(matches[:10]),
        )

    async def _flow_aud_pick(self, peer_id: int, user_id: str, text: str):
        candidates = self._load_json(user_id, "aud_pick")
        if not isinstance(candidates, list):
            self._clear_flow(user_id)
            return
        tnorm = text.casefold().strip()
        chosen = None
        for c in candidates:
            if (c.get("name") or "").strip().casefold() == tnorm:
                chosen = c
                break
        if not chosen:
            self.bot._send_message(peer_id, localize("AudPickInvalid", {}))
            return
        if not self._has_profile(user_id):
            return
        await self._select_aud_named(
            peer_id, user_id, int(chosen["id"]), str(chosen.get("name", ""))
        )

    async def _select_aud_by_id(self, peer_id: int, user_id: str, aid: int):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            auds = self.api.list_auditoriums(univ, token, year)
        except Exception as e:
            logger.error("list_auditoriums: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return
        name = ""
        for a in auds:
            if int(a.get("id", -1)) == int(aid):
                name = str(a.get("name", ""))
                break
        if not name:
            name = f"id {aid}"
        await self._select_aud_named(peer_id, user_id, aid, name)

    async def _select_aud_named(self, peer_id: int, user_id: str, aid: int, name: str):
        self._set_focus(user_id, "aud", aid, name)
        self._clear_flow(user_id)
        msg = localize("AudSelected", {"name": name}) + "\n\n" + self._format_focus_hint(
            self._get_focus(user_id)
        )
        self.bot._send_message(peer_id, msg, self._schedule_keyboard(user_id))

    async def _flow_group_query(self, peer_id: int, user_id: str, query: str, storage: str):
        univ = storage[0]
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            groups = self.api.list_groups(univ, token, year)
        except Exception as e:
            logger.error("list_groups: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return

        q = query.casefold().strip()
        matches = [g for g in groups if q in (g.get("name") or "").casefold()]
        if not matches:
            self.bot._send_message(
                peer_id,
                localize("GroupNotFound", {}),
                self._schedule_keyboard(user_id),
            )
            return
        if len(matches) == 1:
            g = matches[0]
            await self._select_group_named(
                peer_id, user_id, int(g["id"]), str(g.get("name", ""))
            )
            return

        matches.sort(key=lambda x: (x.get("name") or ""))
        self._save_json(user_id, "group_pick", matches[:15])
        self._set(self._k(user_id, "flow"), "group_pick")
        self.bot._send_message(
            peer_id,
            localize("GroupPickMany", {"n": len(matches)}),
            group_pick_keyboard(matches[:10]),
        )

    async def _flow_group_pick(self, peer_id: int, user_id: str, text: str):
        candidates = self._load_json(user_id, "group_pick")
        if not isinstance(candidates, list):
            self._clear_flow(user_id)
            return
        tnorm = text.casefold().strip()
        chosen = None
        for c in candidates:
            if (c.get("name") or "").strip().casefold() == tnorm:
                chosen = c
                break
        if not chosen:
            self.bot._send_message(peer_id, localize("GroupPickInvalid", {}))
            return
        if not self._has_profile(user_id):
            return
        await self._select_group_named(
            peer_id, user_id, int(chosen["id"]), str(chosen.get("name", ""))
        )

    async def _select_group_by_id(self, peer_id: int, user_id: str, gid: int):
        univ = self._university(user_id)
        token = self._api_token(user_id)
        year = academic_year_string()
        try:
            groups = self.api.list_groups(univ, token, year)
        except Exception as e:
            logger.error("list_groups: %s", e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))
            return
        name = ""
        for g in groups:
            if int(g.get("id", -1)) == int(gid):
                name = str(g.get("name", ""))
                break
        if not name:
            name = f"id {gid}"
        await self._select_group_named(peer_id, user_id, gid, name)

    async def _select_group_named(self, peer_id: int, user_id: str, gid: int, name: str):
        self._set_focus(user_id, "group", gid, name)
        self._clear_flow(user_id)
        msg = localize("GroupSelected", {"name": name}) + "\n\n" + self._format_focus_hint(
            self._get_focus(user_id)
        )
        self.bot._send_message(peer_id, msg, self._schedule_keyboard(user_id))

    async def _send_timetable(self, peer_id: int, period: str, *, week_offset: int = 0):
        user_id = self._get_user_id(peer_id)
        storage = self._require_profile(user_id)

        if not storage:
            self._begin_role_choice(peer_id, user_id, localize("ProfileNotBoundError", {}))
            return

        if week_offset == 0:
            self._set_last_period(user_id, period)

        token = self._api_token(user_id)
        focus = self._get_focus(user_id)
        id_teacher = id_aud = id_group = None
        if isinstance(focus, dict):
            k = focus.get("kind")
            if k == "teacher":
                id_teacher = int(focus["id"])
            elif k == "aud":
                id_aud = int(focus["id"])
            elif k == "group":
                id_group = int(focus["id"])

        try:
            timetable = self.api.get_timetable_for_period(
                storage,
                period,
                token,
                week_offset=week_offset,
                id_teacher=id_teacher,
                id_aud_line=id_aud,
                id_group=id_group,
            )

            _, role, _, _ = parse_storage(storage)
            if id_teacher is not None:
                is_teacher_view = True
            elif id_group is not None or id_aud is not None:
                is_teacher_view = False
            else:
                is_teacher_view = role == "teacher"

            text, _parse_mode = self._format_timetable(
                timetable, is_teacher_view, period, week_offset=week_offset
            )
            hint = self._format_focus_hint(focus) if focus else ""

            if not text or not text.strip():
                body = localize("TimetableEmpty", {})
            else:
                body = self._html_to_plain(text)

            if week_offset > 0:
                anchor = get_week_anchor_date(week_offset)
                offset_hint = localize(
                    "TimetableWeekOffsetHint",
                    {"n": week_offset, "date": anchor},
                )
                body = offset_hint + "\n\n" + body

            if hint:
                body = hint + "\n\n" + body

            kb = self._schedule_keyboard(user_id)
            self._send_plain_chunks(peer_id, body, kb)
        except Exception as e:
            logger.error("Ошибка расписания user=%s: %s", user_id, e, exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))

    def _html_to_plain(self, text: str) -> str:
        text = re.sub(r"<b>(.*?)</b>", r"\1", text)
        text = re.sub(r"<i>(.*?)</i>", r"\1", text)
        text = re.sub(r"<code>(.*?)</code>", r"\1", text)
        text = re.sub(r"<.*?>", "", text)
        return text

    @staticmethod
    def _rasp_item_dd_mm(item: dict) -> str:
        raw = (item.get("дата") or "").strip()
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return f"{raw[8:10]}.{raw[5:7]}"
        return ""

    async def _format_week_timetable(self, group_id: int, week_offset: int) -> str:
        from datetime import timedelta

        anchor = get_week_anchor_date(week_offset)
        lines: List[str] = []
        for day_i in range(7):
            day_date = (anchor + timedelta(days=day_i)).strftime("%Y-%m-%d")
            try:
                tt = await self._get_timetable_for_period(group_id, day_date)
                day_items = (tt.get("data") or {}).get("rasp") or []
            except Exception:
                lines.append(f"{day_date}: ошибка загрузки")
                continue
            if not day_items:
                continue
            day_name = day_items[0].get("день_недели") or day_i + 1
            lines.append(f"**{day_name}** ({day_date})")
            for item in day_items:
                lines.append(self._rasp_item_dd_mm(item))
        return "\n".join(lines) if lines else "Нет занятий на неделе."

    async def _format_week_timetable_teacher(self, teacher_id: int, week_offset: int) -> str:
        from datetime import timedelta

        anchor = get_week_anchor_date(week_offset)
        lines: List[str] = []
        for day_i in range(7):
            day_date = (anchor + timedelta(days=day_i)).strftime("%Y-%m-%d")
            try:
                tt = await self._get_timetable_for_period(teacher_id, day_date, id_teacher=teacher_id)
                day_items = (tt.get("data") or {}).get("rasp") or []
            except Exception:
                lines.append(f"{day_date}: ошибка загрузки")
                continue
            if not day_items:
                continue
            day_name = day_items[0].get("день_недели") or day_i + 1
            lines.append(f"**{day_name}** ({day_date})")
            for item in day_items:
                lines.append(self._rasp_item_dd_mm(item))
        return "\n".join(lines) if lines else "Нет занятий на неделе."

    def _format_timetable(
        self, timetable: dict, is_teacher: bool, period: str, *, week_offset: int = 0
    ):
        if not timetable or "data" not in timetable or "rasp" not in timetable["data"]:
            return "", None

        items = timetable["data"]["rasp"]

        if period == "week":
            filtered_items = items
        elif period == "today":
            current_date = get_current_date(week_offset)
            filtered_items = [item for item in items if item.get("дата", "").startswith(current_date)]
        elif period == "tomorrow":
            tomorrow_date = get_tomorrow_date(week_offset)
            filtered_items = [item for item in items if item.get("дата", "").startswith(tomorrow_date)]
        else:
            filtered_items = items

        if not filtered_items:
            return "", None

        lines = []
        if period == "week":
            by_day: Dict[int, List[dict]] = defaultdict(list)
            for item in filtered_items:
                day_num = item.get("деньНедели", 0)
                if 1 <= day_num <= 7:
                    by_day[day_num].append(item)

            for day_num in sorted(by_day.keys()):
                day_items = by_day[day_num]
                if day_items:
                    day_name = day_items[0].get("день_недели", "")
                    if day_name.startswith("📅 "):
                        day_name = day_name[2:]
                    day_name = re.sub(r"\s+\d+$", "", day_name).strip()
                    dd_mm = self._rasp_item_dd_mm(day_items[0])
                    if dd_mm:
                        day_name = f"{day_name} · {dd_mm}" if day_name else dd_mm
                    lines.append(f"\n{day_name}\n")
                    for idx, item in enumerate(day_items):
                        lines.append(self._format_item(item, is_teacher, idx + 1))
                        if idx < len(day_items) - 1:
                            lines.append("\n\n")
        elif period == "all":
            by_date: Dict[str, List[dict]] = defaultdict(list)
            for item in filtered_items:
                raw = item.get("дата") or ""
                dk = raw[:10] if len(raw) >= 10 else raw.strip() or "?"
                by_date[dk].append(item)
            for dkey in sorted(by_date.keys()):
                day_items = by_date[dkey]
                if not day_items:
                    continue
                day_label = day_items[0].get("день_недели", "")
                if day_label.startswith("📅 "):
                    day_label = day_label[2:]
                day_label = re.sub(r"\s+\d+$", "", day_label).strip()
                title = f"📅 {dkey}" + (f" · {day_label}" if day_label else "")
                lines.append(f"\n{title}\n")
                for idx, item in enumerate(day_items):
                    lines.append(self._format_item(item, is_teacher, idx + 1))
                    if idx < len(day_items) - 1:
                        lines.append("\n\n")
        else:
            period_titles = {"today": "Сегодня", "tomorrow": "Завтра"}
            if period in period_titles:
                lines.append(f"{period_titles[period]}")

            for idx, item in enumerate(filtered_items):
                lines.append(self._format_item(item, is_teacher, idx + 1))
                if idx < len(filtered_items) - 1:
                    lines.append("\n\n")

        return "\n".join(lines), "text"

    def _get_lesson_type_emoji(self, discipline: str) -> str:
        discipline_lower = discipline.lower()
        if discipline_lower.startswith("лек"):
            return "🟢"
        if discipline_lower.startswith("лаб"):
            return "🔵"
        if discipline_lower.startswith("пр"):
            return "🟠"
        return "🔴"

    def _format_item(self, item: dict, is_teacher: bool, number: int = 0) -> str:
        discipline = item.get("дисциплина", "")

        if is_teacher:
            teacher_part = f"{item.get('группа', '')}"
        else:
            teacher_part = f"{item.get('преподаватель', '')}"

        start = item.get("начало", "")
        end = item.get("конец", "")
        audience = item.get("аудитория", "")

        number_prefix = f"{number}. " if number > 0 else ""
        type_emoji = self._get_lesson_type_emoji(discipline)

        line1 = f"{number_prefix}{type_emoji} {discipline}"
        time_part = f"{start}–{end}" if start and end else (start or end)
        line2 = f"{teacher_part}  🕒 {time_part}"

        lines = [line1, line2]
        if audience:
            lines.append(f"📍 {audience}")

        return "\n".join(lines)
