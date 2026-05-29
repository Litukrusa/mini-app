"""Кэш списков преподавателей и аудиторий (ПИ ДГТУ / ДГТУ)."""
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from bot.api.timetable import TimetableAPI
from bot.constants import academic_year_string

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
CACHE_TTL_SEC = 6 * 3600

# ПИ ДГТУ — компактные списки, можно показать сразу. ДГТУ — только поиск (как в VK-боте).
SEARCH_POLICY = {
    "T": {"min_query_len": 0, "default_limit": 100, "list_on_open": True},
    "D": {"min_query_len": 2, "default_limit": 80, "list_on_open": False},
}


def search_policy(university: str) -> Dict[str, Any]:
    return dict(SEARCH_POLICY.get(university, SEARCH_POLICY["D"]))


def _cache_path(kind: str, university: str) -> Path:
    return DATA_DIR / f"{kind}_{university}.json"


def _subtitle_from_keys(item: Dict[str, Any], keys: tuple) -> str:
    parts = []
    for key in keys:
        val = item.get(key)
        if val is not None and str(val).strip():
            parts.append(str(val).strip())
    return " · ".join(parts)


def _normalize_teacher(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(item["id"]),
        "name": str(item.get("name", "")),
        "subtitle": _subtitle_from_keys(
            item, ("kaf", "department", "fac", "faculty", "кафедра", "spec")
        ),
    }


def _normalize_aud(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(item["id"]),
        "name": str(item.get("name", "")),
        "subtitle": _subtitle_from_keys(
            item, ("corpus", "building", "корпус", "facul", "faculty", "kaf")
        ),
    }


class RaspListCatalog:
    """kind: teachers | auditoriums"""

    def __init__(
        self,
        kind: str,
        *,
        fetch_fn: Callable[..., List[Dict[str, Any]]],
        normalize_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        api: Optional[TimetableAPI] = None,
    ) -> None:
        if kind not in ("teachers", "auditoriums"):
            raise ValueError("kind must be teachers or auditoriums")
        self.kind = kind
        self._fetch_fn = fetch_fn
        self._normalize = normalize_fn
        self.api = api or TimetableAPI()
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _read_cache(self, university: str) -> Optional[Dict[str, Any]]:
        path = _cache_path(self.kind, university)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get(self.kind), list):
                return None
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("%s cache read %s: %s", self.kind, path, e)
            return None

    def _write_cache(self, university: str, items: List[Dict[str, Any]], year: str) -> None:
        path = _cache_path(self.kind, university)
        payload = {
            "university": university,
            "year": year,
            "updatedAt": int(time.time()),
            "count": len(items),
            self.kind: items,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")
        logger.info("%s cache saved: %s (%s items)", self.kind, path.name, len(items))

    def _fetch_from_api(
        self, university: str, token: Optional[str], year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        y = year or academic_year_string()
        raw = self._fetch_fn(university, token, y)
        return [self._normalize(x) for x in raw if x.get("id") is not None]

    def refresh(self, university: str, token: Optional[str] = None) -> int:
        if university not in ("T", "D"):
            raise ValueError("university must be T or D")
        year = academic_year_string()
        items = self._fetch_from_api(university, token, year)
        self._write_cache(university, items, year)
        return len(items)

    def get_items(
        self,
        university: str,
        token: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        if university not in ("T", "D"):
            return []

        cached = None if force_refresh else self._read_cache(university)
        if cached:
            age = time.time() - int(cached.get("updatedAt") or 0)
            if age < CACHE_TTL_SEC:
                return list(cached.get(self.kind) or [])

        try:
            items = self._fetch_from_api(university, token)
            if items:
                self._write_cache(university, items, academic_year_string())
                return items
        except Exception as e:
            logger.error("%s API %s: %s", self.kind, university, e)

        if cached:
            logger.warning(
                "%s: API недоступен, используем файл %s",
                self.kind,
                _cache_path(self.kind, university),
            )
            return list(cached.get(self.kind) or [])
        return []

    def search(
        self,
        university: str,
        query: str,
        token: Optional[str] = None,
        *,
        limit: Optional[int] = None,
        min_query_len: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        policy = search_policy(university)
        lim = limit if limit is not None else int(policy["default_limit"])
        min_len = (
            min_query_len if min_query_len is not None else int(policy["min_query_len"])
        )
        items = self.get_items(university, token)
        q = (query or "").casefold().strip()
        if not q:
            if min_len > 0:
                return []
            return items[:lim]
        if len(q) < min_len:
            return []
        matches = [x for x in items if q in (x.get("name") or "").casefold()]
        matches.sort(key=lambda x: (x.get("name") or ""))
        return matches[:lim]


def teachers_catalog(api: Optional[TimetableAPI] = None) -> RaspListCatalog:
    a = api or TimetableAPI()
    return RaspListCatalog(
        "teachers",
        fetch_fn=a.list_teachers,
        normalize_fn=_normalize_teacher,
        api=a,
    )


def auditoriums_catalog(api: Optional[TimetableAPI] = None) -> RaspListCatalog:
    a = api or TimetableAPI()
    return RaspListCatalog(
        "auditoriums",
        fetch_fn=a.list_auditoriums,
        normalize_fn=_normalize_aud,
        api=a,
    )
