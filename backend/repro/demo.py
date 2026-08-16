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


def _force_rmtree(path: Path) -> None:
    """Remove a directory tree even on Windows, where read-only files (e.g.
    inside .git/objects) make shutil.rmtree silently skip them."""
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        try:
            p.chmod(0o777)  # clear the read-only attribute so rmtree can delete
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def create_demo_project(bug: str) -> dict:
    bug = (bug or "auth").lower()
    if bug not in DEMOS:
        bug = "auth"
    src, label = DEMOS[bug]
    dest = cfg.projects_dir / f"demo-{bug}"
    # Clear any stale copy (e.g. a leftover .git with read-only files that
    # rmtree silently skips) then overwrite in place.
    if dest.exists():
        _force_rmtree(dest)
    shutil.copytree(DEMO_DIR / src, dest, dirs_exist_ok=True)
    # A previous run may have git-initialized the demo (apply_patch does git
    # init). Rmtree can skip read-only .git objects on Windows, so drop any
    # leftover git state explicitly so each demo starts clean.
    _force_rmtree(dest / ".git")
    return db.create_project(f"demo:{label}", "demo", str(dest), source_url="")
