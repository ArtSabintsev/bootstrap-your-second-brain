#!/usr/bin/env python3
"""Per-user config loader for the brain automation.

Reads config.json at the repo root (falls back to config.example.json).
Keys starting with underscore are documentation-only and ignored by get().

Python:   from config import get, source_enabled;  get("identity.github_login")
Shell:    BROWSER="$(python3 scripts/config.py browser)"
          python3 scripts/config.py --source-enabled goodreads
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Built-in source keys the daily orchestrator understands.
SOURCE_KEYS = (
    "x_bookmarks",
    "goodreads",
    "substack",
    "github",
    "podcasts",
    "youtube_likes",
)


def _strip_docs(obj):
    """Drop keys starting with _ (agent/human documentation fields)."""
    if isinstance(obj, dict):
        return {
            k: _strip_docs(v)
            for k, v in obj.items()
            if not str(k).startswith("_")
        }
    if isinstance(obj, list):
        return [_strip_docs(x) for x in obj]
    return obj


def _load() -> dict:
    for name in ("config.json", "config.example.json"):
        p = ROOT / name
        if p.exists():
            raw = json.loads(p.read_text())
            return _strip_docs(raw) if isinstance(raw, dict) else {}
    return {}


CFG = _load()


def get(dotted: str, default=None):
    cur = CFG
    for key in dotted.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur


def secrets_dir() -> Path:
    return Path(os.path.expanduser(get("secrets_dir", "~/Developer/helpers")))


def browser(default: str = "brave") -> str:
    """Browser name for xtap and yt-dlp --cookies-from-browser."""
    val = get("browser", default)
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip().lower()


def ytdlp_cookie_args() -> list[str]:
    """Args so yt-dlp uses the same browser session as config.browser."""
    return ["--cookies-from-browser", browser()]


def source_enabled(key: str, default: bool = True) -> bool:
    """Whether config.sources.<key> is on. Missing key => default (True)."""
    val = get(f"sources.{key}", default)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off", "null", ""):
        return False
    return default


def is_placeholder_identity() -> bool:
    name = (get("identity.name") or "").strip()
    return not name or name in ("Your Name", "your name")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--source-enabled":
        key = args[1] if len(args) > 1 else ""
        print("true" if source_enabled(key) else "false")
        sys.exit(0)
    if args and args[0] == "--source-keys":
        print(json.dumps(list(SOURCE_KEYS)))
        sys.exit(0)
    if args and args[0] == "--is-placeholder":
        print("true" if is_placeholder_identity() else "false")
        sys.exit(0)
    if args and args[0] == "--ytdlp-cookies":
        # Space-separated flags for shell scripts if needed
        print(" ".join(ytdlp_cookie_args()))
        sys.exit(0)
    val = get(args[0]) if args else CFG
    if isinstance(val, (dict, list)):
        print(json.dumps(val))
    elif val is not None:
        print(val)
