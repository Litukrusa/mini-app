import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from bot.constants import get_current_date, get_tomorrow_date


def lesson_type_emoji(discipline: str) -> str:
    d = (discipline or "").lower()
    if d.startswith("лек"):
        return "🟢"
    if d.startswith("лаб"):
        return "🔵"
    if d.startswith("пр"):
        return "🟠"
    return "🔴"


def lesson_to_dict(item: dict, *, is_teacher: bool) -> Dict[str, Any]:
    discipline = item.get("дисциплина", "")
    if is_teacher:
        counterpart = item.get("группа", "")
        counterpart_label = "group"
    else:
        counterpart = item.get("преподаватель", "")
        counterpart_label = "teacher"

    raw_date = (item.get("дата") or "").strip()
    date_iso = raw_date[:10] if len(raw_date) >= 10 else raw_date

    return {
        "date": date_iso,
        "dayName": item.get("день_недели", ""),
        "dayNumber": item.get("деньНедели"),
        "start": item.get("начало", ""),
        "end": item.get("конец", ""),
        "discipline": discipline,
        "typeEmoji": lesson_type_emoji(discipline),
        counterpart_label: counterpart,
        "auditorium": item.get("аудитория", ""),
    }


def timetable_to_lessons(
    timetable: dict,
    period: str,
    *,
    is_teacher: bool,
    week_offset: int = 0,
) -> List[Dict[str, Any]]:
    if not timetable or "data" not in timetable or "rasp" not in timetable.get("data", {}):
        return []

    items = timetable["data"]["rasp"]
    if period == "week":
        filtered = items
    elif period == "today":
        day = get_current_date(week_offset)
        filtered = [i for i in items if (i.get("дата") or "").startswith(day)]
    elif period == "tomorrow":
        day = get_tomorrow_date(week_offset)
        filtered = [i for i in items if (i.get("дата") or "").startswith(day)]
    else:
        filtered = items

    if not filtered:
        return []

    out: List[Dict[str, Any]] = []

    if period == "week":
        by_day: Dict[int, List[dict]] = defaultdict(list)
        for item in filtered:
            day_num = item.get("деньНедели", 0)
            if 1 <= day_num <= 7:
                by_day[day_num].append(item)
        for day_num in sorted(by_day.keys()):
            for item in by_day[day_num]:
                out.append(lesson_to_dict(item, is_teacher=is_teacher))
    else:
        for item in filtered:
            out.append(lesson_to_dict(item, is_teacher=is_teacher))

    return out


def timetable_for_date(
    timetable: dict, date_iso: str, *, is_teacher: bool
) -> List[Dict[str, Any]]:
    if not timetable or "data" not in timetable:
        return []
    items = timetable["data"].get("rasp") or []
    filtered = [i for i in items if (i.get("дата") or "").startswith(date_iso)]
    return [lesson_to_dict(i, is_teacher=is_teacher) for i in filtered]


def profile_payload(
    *,
    has_profile: bool,
    university: Optional[str],
    profile: Optional[Dict[str, Any]],
    focus: Optional[Dict[str, Any]],
    schedule_kind: str = "group",
    selections: Optional[Dict[str, Any]] = None,
    eios_available: bool = False,
    eios_authenticated: bool = False,
    eios_can_configure: bool = False,
    eios_id: Optional[str] = None,
) -> Dict[str, Any]:
    univ_name = None
    if university == "T":
        univ_name = "ПИ ДГТУ"
    elif university == "D":
        univ_name = "ДГТУ"

    sel = selections or {}
    active = sel.get(schedule_kind) if schedule_kind in ("group", "teacher", "aud") else None
    if not active or active.get("id") is None:
        for k in ("group", "teacher", "aud"):
            candidate = sel.get(k)
            if isinstance(candidate, dict) and candidate.get("id") is not None:
                active = candidate
                break

    return {
        "hasProfile": has_profile,
        "university": university,
        "universityName": univ_name,
        "profile": profile,
        "focus": focus,
        "scheduleKind": schedule_kind,
        "selections": sel,
        "activeSelection": active,
        "eiosAvailable": eios_available,
        "eiosAuthenticated": eios_authenticated,
        "eiosCanConfigure": eios_can_configure,
        "eiosId": eios_id,
    }
