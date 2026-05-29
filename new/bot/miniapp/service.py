import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bot.api.timetable import TimetableAPI
from bot.constants import academic_year_string, get_week_anchor_date
from bot.data.groups_catalog import GroupsCatalog
from bot.data.rasp_catalog import auditoriums_catalog, search_policy, teachers_catalog
from bot.miniapp.schedule_format import (
    profile_payload,
    timetable_for_date,
    timetable_to_lessons,
)

logger = logging.getLogger(__name__)

SCHEDULE_KINDS = ("group", "teacher", "aud")


class MiniAppService:
    """Слой данных Mini App — та же MongoDB, что и у бота."""

    def __init__(self, handlers) -> None:
        self._h = handlers
        self.api: TimetableAPI = handlers.api
        self.groups_catalog = GroupsCatalog(self.api)
        self.teachers_catalog = teachers_catalog(self.api)
        self.auditoriums_catalog = auditoriums_catalog(self.api)

    def _uid(self, user_id: str) -> str:
        return str(user_id)

    def _load_miniapp(self, user_id: str) -> Dict[str, Any]:
        data = self._h._load_json(self._uid(user_id), "miniapp")
        if not isinstance(data, dict):
            data = {}
        if "scheduleKind" not in data:
            data["scheduleKind"] = "group"
        if "selections" not in data or not isinstance(data["selections"], dict):
            data["selections"] = {}
        return data

    def _save_miniapp(self, user_id: str, data: Dict[str, Any]) -> None:
        self._h._save_json(self._uid(user_id), "miniapp", data)

    def _eios_meta(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        h = self._h
        available = h._show_eios_auth(uid)
        authenticated = h._eios_authenticated(uid) if available else False
        can_configure = bool((h.bot.config.eios_encryption_key or "").strip())
        eios_id = h._eios_store.get_eios_id(uid) if authenticated else None
        return {
            "eios_available": available,
            "eios_authenticated": authenticated,
            "eios_can_configure": can_configure,
            "eios_id": eios_id,
        }

    def get_me(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        h = self._h
        profile = h._get_profile(uid)
        focus = h._get_focus(uid)
        mini = self._load_miniapp(uid)
        univ = h._get(h._k(uid, "university"))
        if univ not in ("T", "D"):
            univ = h._univ(uid) if h._has_user_university(uid) else None
        eios = self._eios_meta(user_id)
        return profile_payload(
            has_profile=h._has_profile(uid),
            university=univ,
            profile=profile,
            focus=focus,
            schedule_kind=mini.get("scheduleKind", "group"),
            selections=mini.get("selections"),
            eios_available=eios["eios_available"],
            eios_authenticated=eios["eios_authenticated"],
            eios_can_configure=eios["eios_can_configure"],
            eios_id=eios["eios_id"],
        )

    def eios_status(self, user_id: str) -> Dict[str, Any]:
        return self._eios_meta(user_id)

    def eios_login(self, user_id: str, login: str, password: str) -> Dict[str, Any]:
        result = self._h.eios_login(self._uid(user_id), login, password)
        return {"me": self.get_me(user_id), **result}

    def eios_logout(self, user_id: str) -> Dict[str, Any]:
        self._h.eios_logout(self._uid(user_id))
        return self.get_me(user_id)

    def set_university(self, user_id: str, code: str) -> Dict[str, Any]:
        if code not in ("T", "D"):
            raise ValueError("university must be T or D")
        uid = self._uid(user_id)
        self._h._set(self._h._k(uid, "university"), code)
        return self.get_me(user_id)

    def set_schedule_kind(self, user_id: str, kind: str) -> Dict[str, Any]:
        if kind not in SCHEDULE_KINDS:
            raise ValueError("kind must be group, teacher or aud")
        mini = self._load_miniapp(user_id)
        mini["scheduleKind"] = kind
        self._save_miniapp(user_id, mini)
        return self.get_me(user_id)

    def set_selection(self, user_id: str, kind: str, entity_id: int, name: str) -> Dict[str, Any]:
        if kind not in SCHEDULE_KINDS:
            raise ValueError("kind must be group, teacher or aud")
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз в настройках")

        mini = self._load_miniapp(uid)
        mini.setdefault("selections", {})[kind] = {
            "id": int(entity_id),
            "name": str(name),
        }
        mini["scheduleKind"] = kind
        self._save_miniapp(uid, mini)

        self._h._set_focus(uid, kind, int(entity_id), str(name))

        univ = self._h._university(uid)
        if kind == "group" and not self._h._has_profile(uid):
            self._h._set(uid, f"{univ}{int(entity_id)}")
            self._h._save_json(
                uid,
                "my_profile",
                {"role": "student", "id": int(entity_id), "name": name},
            )
        elif kind == "teacher" and not self._h._has_profile(uid):
            self._h._set(uid, f"{univ}{int(entity_id)}T")
            self._h._save_json(
                uid,
                "my_profile",
                {"role": "teacher", "id": int(entity_id), "name": name},
            )
        elif not self._h._has_profile(uid):
            self._h._set(uid, f"{univ}1")

        return self.get_me(user_id)

    def bind_group(self, user_id: str, group_id: int, name: str) -> Dict[str, Any]:
        return self.set_selection(user_id, "group", group_id, name)

    def bind_teacher(self, user_id: str, teacher_id: int, name: str) -> Dict[str, Any]:
        return self.set_selection(user_id, "teacher", teacher_id, name)

    def bind_auditorium(self, user_id: str, aud_id: int, name: str) -> Dict[str, Any]:
        return self.set_selection(user_id, "aud", aud_id, name)

    def reset_profile(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        self._h._purge_user_data(uid)
        self._h._delete(self._h._k(uid, "miniapp"))
        return self.get_me(user_id)

    def _token(self, user_id: str) -> Optional[str]:
        return self._h._api_token(self._uid(user_id))

    def list_groups(
        self, user_id: str, query: str = "", *, limit: int = 80
    ) -> List[Dict[str, Any]]:
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")
        univ = self._h._university(uid)
        token = self._token(user_id)
        return self.groups_catalog.search(univ, query, token, limit=limit)

    def search_groups(self, user_id: str, query: str, *, limit: int = 40) -> List[Dict[str, Any]]:
        return self.list_groups(user_id, query, limit=limit)

    def refresh_groups_cache(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")
        univ = self._h._university(uid)
        token = self._token(user_id)
        count = self.groups_catalog.refresh(univ, token)
        return {"university": univ, "count": count}

    def search_teachers(
        self, user_id: str, query: str = "", *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")
        univ = self._h._university(uid)
        token = self._token(user_id)
        return self.teachers_catalog.search(univ, query, token, limit=limit)

    def search_auditoriums(
        self, user_id: str, query: str = "", *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")
        univ = self._h._university(uid)
        token = self._token(user_id)
        return self.auditoriums_catalog.search(univ, query, token, limit=limit)

    def refresh_teachers_cache(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")
        univ = self._h._university(uid)
        count = self.teachers_catalog.refresh(univ, self._token(user_id))
        return {"university": univ, "count": count}

    def refresh_auditoriums_cache(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        if not self._h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")
        univ = self._h._university(uid)
        count = self.auditoriums_catalog.refresh(univ, self._token(user_id))
        return {"university": univ, "count": count}

    def search_meta(self, user_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        univ = self._h._university(uid) if self._h._has_user_university(uid) else "D"
        policy = search_policy(univ)
        return {
            "university": univ,
            "minQueryLen": policy["min_query_len"],
            "listOnOpen": policy["list_on_open"],
        }

    def _resolve_schedule_target(self, user_id: str) -> Tuple[str, Optional[int], Optional[int], Optional[int], bool]:
        uid = self._uid(user_id)
        h = self._h
        mini = self._load_miniapp(uid)
        kind = mini.get("scheduleKind", "group")
        sel = (mini.get("selections") or {}).get(kind)

        if not sel or "id" not in sel:
            focus = h._get_focus(uid)
            if isinstance(focus, dict) and focus.get("kind") == kind:
                sel = focus
            else:
                raise ValueError("Выберите группу, преподавателя или аудиторию в профиле")

        if not h._has_user_university(uid):
            raise ValueError("Сначала выберите вуз")

        univ = h._university(uid)
        eid = int(sel["id"])
        id_teacher = id_aud = id_group = None
        is_teacher_view = False

        if kind == "teacher":
            id_teacher = eid
            is_teacher_view = True
        elif kind == "aud":
            id_aud = eid
        else:
            id_group = eid

        return univ, id_teacher, id_aud, id_group, is_teacher_view

    def _dummy_storage(self, univ: str) -> str:
        return f"{univ}1"

    def get_schedule(
        self,
        user_id: str,
        period: str = "today",
        *,
        week_offset: int = 0,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = self._uid(user_id)
        h = self._h

        univ, id_teacher, id_aud, id_group, is_teacher_view = self._resolve_schedule_target(
            user_id
        )
        storage = h._require_profile(uid) or self._dummy_storage(univ)
        token = h._api_token(uid)

        if date:
            try:
                d = datetime.strptime(date[:10], "%Y-%m-%d").date()
                monday = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
            except ValueError:
                monday = get_week_anchor_date(0)

            timetable = self.api.get_timetable_for_period(
                storage,
                "week",
                token,
                anchor_sdate=monday,
                id_teacher=id_teacher,
                id_aud_line=id_aud,
                id_group=id_group,
            )
            lessons = timetable_for_date(timetable, date[:10], is_teacher=is_teacher_view)
            meta = {"date": date[:10], "empty": len(lessons) == 0}
        else:
            if period not in ("today", "tomorrow", "week"):
                raise ValueError("period must be today, tomorrow or week")
            timetable = self.api.get_timetable_for_period(
                storage,
                period,
                token,
                week_offset=week_offset,
                id_teacher=id_teacher,
                id_aud_line=id_aud,
                id_group=id_group,
            )
            lessons = timetable_to_lessons(
                timetable, period, is_teacher=is_teacher_view, week_offset=week_offset
            )
            meta = {
                "period": period,
                "weekOffset": week_offset,
                "empty": len(lessons) == 0,
            }
            if week_offset > 0:
                meta["anchorDate"] = get_week_anchor_date(week_offset)

        mini = self._load_miniapp(uid)
        return {
            "meta": meta,
            "scheduleKind": mini.get("scheduleKind", "group"),
            "selection": (mini.get("selections") or {}).get(mini.get("scheduleKind", "group")),
            "lessons": lessons,
        }
