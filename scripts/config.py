#!/usr/bin/env python3
"""Per-user config loader for the brain automation.

Reads config.json at the repo root (falls back to config.example.json). Centralizes
the values that differ per person: identity/handles, browser, secrets dir, models,
podcast cutoff. Secrets never live here; they stay in the secrets_dir.

Python:   from config import get;  get("identity.github_login")
Shell:    BROWSER="$(python3 scripts/config.py browser)"
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load() -> dict:
    for name in ("config.json", "config.example.json"):
        p = ROOT / name
        if p.exists():
            return json.loads(p.read_text())
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


if __name__ == "__main__":
    val = get(sys.argv[1]) if len(sys.argv) > 1 else CFG
    if isinstance(val, (dict, list)):
        print(json.dumps(val))
    elif val is not None:
        print(val)
