#!/usr/bin/env python3
"""Скачать группы, преподавателей и аудитории в bot/data/*.json."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("VK_TOKEN", "dev")

from bot.data.groups_catalog import GroupsCatalog
from bot.data.rasp_catalog import auditoriums_catalog, teachers_catalog


def main() -> None:
    token = os.environ.get("DGTU_API_TOKEN") or None
    groups = GroupsCatalog()
    teachers = teachers_catalog()
    auds = auditoriums_catalog()
    for univ, label in (("T", "ПИ ДГТУ"), ("D", "ДГТУ")):
        ng = groups.refresh(univ, token)
        nt = teachers.refresh(univ, token)
        na = auds.refresh(univ, token)
        print(f"{label}: групп {ng}, преподавателей {nt}, аудиторий {na}")


if __name__ == "__main__":
    main()
