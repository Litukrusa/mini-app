#!/usr/bin/env python3
"""Совместимость: то же, что fetch_rasp_cache.py."""
import os
import runpy
import sys

if __name__ == "__main__":
    path = os.path.join(os.path.dirname(__file__), "fetch_rasp_cache.py")
    runpy.run_path(path, run_name="__main__")
