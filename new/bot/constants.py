from datetime import datetime, timedelta
from typing import Optional

import pytz

TPI_DGTY_API_URL = "https://edu-tpi.donstu.ru/api"
DGTY_API_URL = "https://edu.donstu.ru/api"

AUTH_PATH = "/tokenauth"
GET_STUDENT_PATH = "/UserInfo/Student"
GET_TEACHER_PATH = "/UserInfo/user"

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def academic_year_string(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(MOSCOW_TZ)
    y = dt.year
    if dt.month >= 9:
        return f"{y}-{y + 1}"
    return f"{y - 1}-{y}"


def get_week_anchor_date(week_offset: int = 0) -> str:
    d = datetime.now(MOSCOW_TZ).date()
    monday = d - timedelta(days=d.weekday()) + timedelta(weeks=week_offset)
    return monday.strftime("%Y-%m-%d")


def get_current_date(week_offset: int = 0) -> str:
    if week_offset == 0:
        return datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")
    d = datetime.now(MOSCOW_TZ).date() + timedelta(weeks=week_offset)
    return d.strftime("%Y-%m-%d")


def get_tomorrow_date(week_offset: int = 0) -> str:
    if week_offset == 0:
        tomorrow = datetime.now(MOSCOW_TZ) + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    d = datetime.now(MOSCOW_TZ).date() + timedelta(days=1, weeks=week_offset)
    return d.strftime("%Y-%m-%d")


def semester_start_iso() -> str:
    d = datetime.now(MOSCOW_TZ).date()
    if d.month >= 9:
        anchor = datetime(d.year, 9, 1, tzinfo=MOSCOW_TZ).date()
    elif d.month >= 2:
        anchor = datetime(d.year, 2, 1, tzinfo=MOSCOW_TZ).date()
    else:
        anchor = datetime(d.year - 1, 9, 1, tzinfo=MOSCOW_TZ).date()
    monday = anchor - timedelta(days=anchor.weekday())
    return monday.strftime("%Y-%m-%d")
