import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from bot.constants import (
    AUTH_PATH,
    DGTY_API_URL,
    GET_STUDENT_PATH,
    GET_TEACHER_PATH,
    TPI_DGTY_API_URL,
    academic_year_string,
    get_current_date,
    get_tomorrow_date,
    get_week_anchor_date,
    semester_start_iso,
)

logger = logging.getLogger(__name__)


class TimetableAPI:
    TIMEOUT = 15

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "DGTY-Timetable-Bot/1.0",
            }
        )

    def _get_university_url(self, university_type: str) -> str:
        if university_type.startswith("T"):
            return TPI_DGTY_API_URL
        if university_type.startswith("D"):
            return DGTY_API_URL
        return ""

    def _bearer_headers(self, access_token: Optional[str]) -> Dict[str, str]:
        h = {}
        if access_token:
            h["Authorization"] = f"Bearer {access_token}"
        return h

    def _make_request(
        self,
        method: str,
        url: str,
        error_msg: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        merged = dict(self.session.headers)
        if headers:
            merged.update(headers)
        try:
            response = self.session.request(
                method, url, timeout=self.TIMEOUT, headers=merged, **kwargs
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error("%s: %s", error_msg, e)
            raise

    def auth_user(
        self, university_type: str, username: str, password: str
    ) -> Dict[str, Any]:
        url = self._get_university_url(university_type) + AUTH_PATH
        payload = {"username": username, "password": password}
        response = self._make_request("POST", url, "Ошибка авторизации", json=payload)
        return response.json()

    @staticmethod
    def parse_auth_response(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
        """Возвращает (access_token, eios_id, сообщение об ошибке)."""
        if not isinstance(payload, dict):
            return None, None, "Некорректный ответ сервера"

        outer = payload.get("data")
        if isinstance(outer, dict):
            inner = outer.get("data")
            if isinstance(inner, dict):
                token = inner.get("accessToken") or outer.get("accessToken")
                eios_id = inner.get("id") or inner.get("userID") or inner.get("studentID")
                if token:
                    return str(token), str(eios_id) if eios_id is not None else None, ""
            token = outer.get("accessToken")
            eios_id = outer.get("id")
            if token:
                return str(token), str(eios_id) if eios_id is not None else None, ""

        if payload.get("state") not in (1, None) and not payload.get("accessToken"):
            msg = payload.get("msg") or payload.get("message") or "Неверный логин или пароль"
            return None, None, str(msg)

        return None, None, "Неверный логин или пароль"

    def get_student_group_id(
        self, university_type: str, access_token: str, student_id: str
    ) -> int:
        url = self._get_university_url(university_type) + GET_STUDENT_PATH
        cookies = {"authToken": access_token}
        params = {"studentID": student_id}
        response = self._make_request(
            "GET",
            url,
            "Ошибка получения ID группы",
            cookies=cookies,
            params=params,
        )
        data = response.json()
        return data["data"]["group"]["item2"]

    def get_teacher_id(
        self, university_type: str, access_token: str, user_id: str
    ) -> int:
        url = self._get_university_url(university_type) + GET_TEACHER_PATH
        cookies = {"authToken": access_token}
        params = {"userID": user_id}
        response = self._make_request(
            "GET",
            url,
            "Ошибка получения ID преподавателя",
            cookies=cookies,
            params=params,
        )
        data = response.json()
        return data["data"]["teacherID"]

    def list_teachers(
        self, university_type: str, access_token: str, year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        base = self._get_university_url(university_type)
        y = year or academic_year_string()
        url = f"{base}/raspTeacherList"
        response = self._make_request(
            "GET",
            url,
            "Ошибка списка преподавателей",
            headers=self._bearer_headers(access_token),
            params={"year": y},
        )
        data = response.json()
        if data.get("state") != 1 or not isinstance(data.get("data"), list):
            return []
        return data["data"]

    def list_auditoriums(
        self, university_type: str, access_token: str, year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        base = self._get_university_url(university_type)
        y = year or academic_year_string()
        url = f"{base}/raspAudList"
        response = self._make_request(
            "GET",
            url,
            "Ошибка списка аудиторий",
            headers=self._bearer_headers(access_token),
            params={"year": y},
        )
        data = response.json()
        if data.get("state") != 1 or not isinstance(data.get("data"), list):
            return []
        return data["data"]

    def list_groups(
        self, university_type: str, access_token: str, year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        base = self._get_university_url(university_type)
        y = year or academic_year_string()
        last_err: Optional[Exception] = None
        for path in ("/raspGrouplist", "/raspGroupList"):
            try:
                url = f"{base}{path}"
                response = self._make_request(
                    "GET",
                    url,
                    "Ошибка списка групп",
                    headers=self._bearer_headers(access_token),
                    params={"year": y},
                )
                data = response.json()
                if data.get("state") != 1 or not isinstance(data.get("data"), list):
                    return []
                items = data["data"]
                return [g for g in items if (g.get("name") or "").strip().lower() != "нет"]
            except Exception as e:
                last_err = e
                logger.warning("list_groups %s: %s", path, e)
        if last_err:
            logger.error("list_groups: все пути не сработали: %s", last_err)
        return []

    def get_rasp_dates(
        self,
        university_type: str,
        access_token: str,
        *,
        id_teacher: Optional[int] = None,
        id_aud_line: Optional[int] = None,
        id_group: Optional[int] = None,
    ) -> Dict[str, Any]:
        base = self._get_university_url(university_type)
        url = f"{base}/GetRaspDates"
        params: Dict[str, Any] = {}
        if id_teacher is not None:
            params["idTeacher"] = id_teacher
        elif id_aud_line is not None:
            params["idAudLine"] = id_aud_line
        elif id_group is not None:
            params["idGroup"] = id_group
        response = self._make_request(
            "GET",
            url,
            "Ошибка GetRaspDates",
            headers=self._bearer_headers(access_token),
            params=params,
        )
        return response.json()

    def fetch_rasp(
        self,
        university_type: str,
        access_token: Optional[str],
        sdate: Optional[str],
        *,
        id_teacher: Optional[int] = None,
        id_aud_line: Optional[int] = None,
        id_group: Optional[int] = None,
    ) -> Dict[str, Any]:
        base = self._get_university_url(university_type)
        url = f"{base}/Rasp"
        params: Dict[str, Any] = {}
        if sdate:
            params["sdate"] = sdate
        if id_teacher is not None:
            params["idTeacher"] = id_teacher
        elif id_aud_line is not None:
            params["idAudLine"] = id_aud_line
        elif id_group is not None:
            params["idGroup"] = id_group
        try:
            response = self._make_request(
                "GET",
                url,
                "Ошибка получения расписания",
                headers=self._bearer_headers(access_token),
                params=params,
            )
            return response.json()
        except Exception as e:
            logger.error("Ошибка получения расписания: %s", e)
            return {"data": {"rasp": []}, "state": -1, "msg": str(e)}

    @staticmethod
    def _lesson_merge_key(item: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            item.get("дата"),
            item.get("начало"),
            item.get("конец"),
            item.get("дисциплина"),
            item.get("группа"),
            item.get("аудитория"),
            item.get("преподаватель"),
        )

    def _merge_rasp_payloads(self, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        seen = set()
        all_items: List[dict] = []
        for p in payloads:
            for item in (p or {}).get("data", {}).get("rasp") or []:
                if not isinstance(item, dict):
                    continue
                k = self._lesson_merge_key(item)
                if k in seen:
                    continue
                seen.add(k)
                all_items.append(item)
        all_items.sort(key=lambda x: (str(x.get("дата", "")), str(x.get("начало", ""))))
        return {"state": 1, "data": {"rasp": all_items}}

    @staticmethod
    def _monday_iso(yyyy_mm_dd: str) -> str:
        d = datetime.strptime(yyyy_mm_dd[:10], "%Y-%m-%d").date()
        mon = d - timedelta(days=d.weekday())
        return mon.strftime("%Y-%m-%d")

    def _dates_from_get_rasp_dates(self, dr: Dict[str, Any]) -> List[str]:
        blob = json.dumps(dr.get("data", dr), ensure_ascii=False)
        found = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", blob)
        start = semester_start_iso()
        return sorted({d for d in set(found) if d >= start})

    @staticmethod
    def _filter_rasp_from_date(payload: Dict[str, Any], min_date: str) -> Dict[str, Any]:
        items = (payload.get("data") or {}).get("rasp") or []
        kept = [
            item
            for item in items
            if isinstance(item, dict) and str(item.get("дата", ""))[:10] >= min_date
        ]
        return {"state": payload.get("state", 1), "data": {"rasp": kept}, "msg": payload.get("msg")}

    def _unique_week_starts(self, dates: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for d in dates:
            m = self._monday_iso(d)
            if m not in seen:
                seen.add(m)
                out.append(m)
        return sorted(out)

    def _resolve_rasp_target(
        self,
        storage_value: str,
        id_teacher: Optional[int],
        id_aud_line: Optional[int],
        id_group: Optional[int],
    ) -> Tuple[str, Optional[int], Optional[int], Optional[int]]:
        university_type = storage_value[0]
        if id_teacher is not None:
            return university_type, id_teacher, None, None
        if id_aud_line is not None:
            return university_type, None, id_aud_line, None
        if id_group is not None:
            return university_type, None, None, id_group

        if storage_value.endswith("T") and len(storage_value) > 2:
            value = storage_value[1:-1]
        else:
            value = storage_value[1:]

        if value.startswith("T") or value.startswith("D"):
            value = value[1:]

        try:
            iv = int(value)
        except ValueError:
            return university_type, None, None, None

        if storage_value.endswith("T") and len(storage_value) > 2:
            return university_type, iv, None, None
        return university_type, None, None, iv

    def _fetch_rasp_for_target(
        self,
        university_type: str,
        access_token: Optional[str],
        sdate: Optional[str],
        tid: Optional[int],
        aid: Optional[int],
        gid: Optional[int],
    ) -> Dict[str, Any]:
        if tid is not None:
            return self.fetch_rasp(university_type, access_token, sdate, id_teacher=tid)
        if aid is not None:
            return self.fetch_rasp(university_type, access_token, sdate, id_aud_line=aid)
        return self.fetch_rasp(university_type, access_token, sdate, id_group=gid)

    def _get_full_timetable_merged(
        self,
        university_type: str,
        access_token: Optional[str],
        tid: Optional[int],
        aid: Optional[int],
        gid: Optional[int],
    ) -> Dict[str, Any]:
        if tid is None and aid is None and gid is None:
            return {"data": {"rasp": []}, "state": -1, "msg": "no target"}

        no_date = self._fetch_rasp_for_target(university_type, access_token, None, tid, aid, gid)
        n0 = len((no_date.get("data") or {}).get("rasp") or [])

        dates: List[str] = []
        if access_token:
            try:
                if tid is not None:
                    dr = self.get_rasp_dates(university_type, access_token, id_teacher=tid)
                elif aid is not None:
                    dr = self.get_rasp_dates(university_type, access_token, id_aud_line=aid)
                else:
                    dr = self.get_rasp_dates(university_type, access_token, id_group=gid)
                dates = self._dates_from_get_rasp_dates(dr)
            except Exception as e:
                logger.warning("GetRaspDates: %s", e)

        mondays = self._unique_week_starts(dates)
        if not mondays:
            mondays = sorted(
                {semester_start_iso(), get_week_anchor_date(), get_current_date()}
            )

        payloads: List[Dict[str, Any]] = []
        if n0:
            payloads.append(no_date)
        for m in mondays[:40]:
            payloads.append(
                self._fetch_rasp_for_target(university_type, access_token, m, tid, aid, gid)
            )
        merged = self._merge_rasp_payloads(payloads)
        if not (merged.get("data") or {}).get("rasp"):
            merged = no_date if n0 else merged
        return self._filter_rasp_from_date(merged, semester_start_iso())

    def get_timetable(self, storage_value: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        anchor = get_current_date()
        return self.get_timetable_for_period(storage_value, "today", access_token, anchor_sdate=anchor)

    def get_timetable_for_period(
        self,
        storage_value: str,
        period: str,
        access_token: Optional[str] = None,
        *,
        anchor_sdate: Optional[str] = None,
        week_offset: int = 0,
        id_teacher: Optional[int] = None,
        id_aud_line: Optional[int] = None,
        id_group: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not storage_value:
            return {"data": {"rasp": []}, "state": -1, "msg": "empty storage"}

        univ, tid, aid, gid = self._resolve_rasp_target(
            storage_value, id_teacher, id_aud_line, id_group
        )
        if tid is None and aid is None and gid is None:
            return {"data": {"rasp": []}, "state": -1, "msg": "bad id"}

        if period == "all":
            full = self._get_full_timetable_merged(univ, access_token, tid, aid, gid)
            if week_offset > 0:
                min_date = get_week_anchor_date(week_offset)
                return self._filter_rasp_from_date(full, min_date)
            return full

        sdate = anchor_sdate or self._anchor_for_period(period, week_offset)
        return self._fetch_rasp_for_target(univ, access_token, sdate, tid, aid, gid)

    def _anchor_for_period(self, period: str, week_offset: int = 0) -> str:
        if period == "tomorrow":
            return get_tomorrow_date(week_offset)
        if period == "week":
            return get_week_anchor_date(week_offset)
        return get_current_date(week_offset)


def parse_storage(storage_value: str) -> Tuple[str, str, Optional[int], Optional[int]]:
    if not storage_value:
        return "T", "student", None, None
    u = storage_value[0]
    if storage_value.endswith("T") and len(storage_value) > 2:
        tid = int(storage_value[1:-1])
        return u, "teacher_account", tid, None
    gid = int(storage_value[1:])
    return u, "student", None, gid
