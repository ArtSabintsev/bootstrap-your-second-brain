"""Local data directory layout (gitignored)."""

from __future__ import annotations

import os
from pathlib import Path


# Data directory: $XTAP_HOME if set, otherwise ~/.xtap
def home() -> Path:
    env = os.environ.get("XTAP_HOME")
    if env:
        p = Path(env).expanduser().resolve()
    else:
        p = Path.home() / ".xtap"
    p.mkdir(parents=True, exist_ok=True)
    (p / "auth").mkdir(exist_ok=True)
    (p / "reports").mkdir(exist_ok=True)
    (p / "snapshots").mkdir(exist_ok=True)
    return p


def auth_dir() -> Path:
    return home() / "auth"


def accounts_db() -> Path:
    return home() / "accounts.db"


def cookies_file() -> Path:
    return auth_dir() / "cookies.txt"


def snapshots_dir() -> Path:
    return home() / "snapshots"


def reports_dir() -> Path:
    return home() / "reports"
