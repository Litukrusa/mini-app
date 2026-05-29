import json
from typing import Any, Dict, List

VK_COLOR = "secondary"


def _btn(label: str, color: str = None) -> Dict[str, Any]:
    if color is None:
        color = VK_COLOR

    return {
        "action": {
            "type": "text",
            "label": label[:255],
            "payload": json.dumps({"button": label[:255]}),
        },
        "color": color,
    }


EIOS_AUTH_BTN = "🔐 Дополнительная авторизация"
EIOS_LOGOUT_BTN = "🔓 Отключить доп. авторизацию"


def _eios_auth_row(*, authenticated: bool) -> List[Dict[str, Any]]:
    label = EIOS_LOGOUT_BTN if authenticated else EIOS_AUTH_BTN
    return [_btn(label, "primary")]


def get_main_menu(
    has_focus: bool = False,
    *,
    show_eios_auth: bool = False,
    eios_authenticated: bool = False,
) -> Dict[str, Any]:
    row_schedule = [
        _btn("📖 Сегодня", "positive"),
        _btn("📖 Завтра", "positive"),
        _btn("📖 Неделя", "positive"),
    ]
    row_all = [
        _btn("📖 Следующая неделя", "positive"),
        _btn("📖 Семестр", "positive"),
    ]
    if has_focus:
        buttons: List[List[Dict[str, Any]]] = [row_schedule, row_all, [_btn("🔴 ВЫХОД", "negative")]]
        if show_eios_auth:
            buttons.append(_eios_auth_row(authenticated=eios_authenticated))
        return {"one_time": False, "inline": False, "buttons": buttons}
    buttons = [
        row_schedule,
        row_all,
        [
            _btn("👤 Преподаватель"),
            _btn("🚪 Аудитория"),
            _btn("👥 Группа"),
        ],
    ]
    if show_eios_auth:
        buttons.append(_eios_auth_row(authenticated=eios_authenticated))
    buttons.append(
        [
            _btn("ℹ Помощь"),
            _btn("🔄 Сменить профиль"),
        ]
    )
    return {"one_time": False, "inline": False, "buttons": buttons}


def univ_choice_keyboard() -> Dict[str, Any]:
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                _btn("ПИ ДГТУ", "positive"),
                _btn("ДГТУ", "positive"),
            ],
        ],
    }


def role_choice_keyboard(*, show_eios_auth: bool = False, eios_authenticated: bool = False) -> Dict[str, Any]:
    buttons: List[List[Dict[str, Any]]] = [
        [
            _btn("🎓 Я студент", "positive"),
            _btn("👨‍🏫 Я преподаватель", "positive"),
        ],
    ]
    if show_eios_auth:
        buttons.append(_eios_auth_row(authenticated=eios_authenticated))
    return {"one_time": False, "inline": False, "buttons": buttons}


def cancel_only_keyboard() -> Dict[str, Any]:
    return {"one_time": False, "inline": False, "buttons": [[_btn("❌ Отмена", "negative")]]}


def _short_label(name: str, max_len: int = 28) -> str:
    n = (name or "").strip()
    if len(n) <= max_len:
        return n
    return n[: max_len - 1] + "…"


def teacher_saved_keyboard(saved: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[List[Dict[str, Any]]] = []
    row: List[Dict[str, Any]] = []
    for t in saved[:12]:
        fio = t.get("name", "")
        display_fio = fio[:30] if len(fio) > 30 else fio
        row.append(_btn(display_fio))
        if len(row) >= 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("➕ Другой преподаватель"), _btn("❌ Отмена", "negative")])
    return {"one_time": False, "inline": False, "buttons": rows}


def teacher_pick_keyboard(
    candidates: List[Dict[str, Any]], *, bind: bool = False
) -> Dict[str, Any]:
    prefix = "★" if bind else "▶"
    rows: List[List[Dict[str, Any]]] = []
    for c in candidates[:10]:
        tid = int(c["id"])
        lab = f"{prefix} {tid}|{_short_label(c.get('name', ''), 26)}"
        rows.append([_btn(lab)])
    rows.append([_btn("❌ Отмена", "negative")])
    return {"one_time": False, "inline": False, "buttons": rows}


def aud_pick_keyboard(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[List[Dict[str, Any]]] = []
    for c in candidates[:10]:
        aid = int(c["id"])
        lab = f"◆ {aid}|{_short_label(c.get('name', ''), 26)}"
        rows.append([_btn(lab)])
    rows.append([_btn("❌ Отмена", "negative")])
    return {"one_time": False, "inline": False, "buttons": rows}


def group_pick_keyboard(
    candidates: List[Dict[str, Any]], *, bind: bool = False
) -> Dict[str, Any]:
    prefix = "◎" if bind else "◇"
    rows: List[List[Dict[str, Any]]] = []
    for c in candidates[:10]:
        gid = int(c["id"])
        lab = f"{prefix} {gid}|{_short_label(c.get('name', ''), 26)}"
        rows.append([_btn(lab)])
    rows.append([_btn("❌ Отмена", "negative")])
    return {"one_time": False, "inline": False, "buttons": rows}
