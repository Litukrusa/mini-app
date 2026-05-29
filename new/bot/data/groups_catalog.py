"""Каталог групп: загрузка из API ДГТУ и кэш в JSON-файлы."""
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot.api.timetable import TimetableAPI
from bot.constants import academic_year_string

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
CACHE_TTL_SEC = 6 * 3600  # 6 часов


def _cache_path(university: str) -> Path:
    return DATA_DIR / f"groups_{university}.json"


def _group_subtitle(item: Dict[str, Any]) -> str:
    parts = []
    facul = (item.get("facul") or item.get("faculty") or "").strip()
    if facul:
        parts.append(facul)
    kurs = item.get("kurs")
    if kurs is not None and str(kurs).strip():
        parts.append(f"{kurs} курс")
    year = (item.get("yearName") or "").strip()
    if year:
        parts.append(year)
    return " · ".join(parts)


def _normalize_group(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(item["id"]),
        "name": str(item.get("name", "")),
        "facul": str(item.get("facul") or ""),
        "kurs": item.get("kurs"),
        "yearName": str(item.get("yearName") or ""),
        "subtitle": _group_subtitle(item),
    }


class GroupsCatalog:
    def __init__(self, api: Optional[TimetableAPI] = None) -> None:
        self.api = api or TimetableAPI()
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _read_cache(self, university: str) -> Optional[Dict[str, Any]]:
        path = _cache_path(university)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
                return None
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("groups cache read %s: %s", path, e)
            return None

    def _write_cache(self, university: str, groups: List[Dict[str, Any]], year: str) -> None:
        path = _cache_path(university)
        payload = {
            "university": university,
            "year": year,
            "updatedAt": int(time.time()),
            "count": len(groups),
            "groups": groups,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")
        logger.info("groups cache saved: %s (%s items)", path.name, len(groups))

    def _fetch_from_api(
        self, university: str, token: Optional[str], year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        y = year or academic_year_string()
        raw = self.api.list_groups(university, token, y)
        return [_normalize_group(g) for g in raw if g.get("id") is not None]

    def refresh(self, university: str, token: Optional[str] = None) -> int:
        if university not in ("T", "D"):
            raise ValueError("university must be T or D")
        year = academic_year_string()
        groups = self._fetch_from_api(university, token, year)
        self._write_cache(university, groups, year)
        return len(groups)

    def get_groups(
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
                return list(cached.get("groups") or [])

        try:
            groups = self._fetch_from_api(university, token)
            if groups:
                self._write_cache(university, groups, academic_year_string())
                return groups
        except Exception as e:
            logger.error("groups API %s: %s", university, e)

        if cached:
            logger.warning("groups: API недоступен, используем файл %s", _cache_path(university))
            return list(cached.get("groups") or [])
        return []

    def search(
        self,
        university: str,
        query: str,
        token: Optional[str] = None,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        groups = self.get_groups(university, token)
        q = (query or "").casefold().strip()
        if not q:
            return groups[:limit]
        matches = [g for g in groups if q in (g.get("name") or "").casefold()]
        matches.sort(key=lambda x: (x.get("name") or ""))
        return matches[:limit]
