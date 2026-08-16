"""Bundled, intentionally-broken demo repositories.

Each demo is a real Python project with a genuine bug and a failing test,
so "Run Demo" performs a real investigation with real evidence.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .config import cfg
from . import db

DEMOS = {
    "auth": ("auth_demo", "Null / None handling"),
    "offbyone": ("search_demo", "Off-by-one error"),
    "api": ("api_demo", "Incorrect API response handling"),
    "sql": ("sql_demo", "Incorrect SQL query"),
    "auth2": ("auth2_demo", "Authentication logic bug"),
}

DEMO_DIR = Path(__file__).resolve().parent / "demo_repos"


def create_demo_project(bug: str) -> dict:
    bug = (bug or "auth").lower()
    if bug not in DEMOS:
        bug = "auth"
    src, label = DEMOS[bug]
    dest = cfg.projects_dir / f"demo-{bug}"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(DEMO_DIR / src, dest)
    return db.create_project(f"demo:{label}", "demo", str(dest), source_url="")
