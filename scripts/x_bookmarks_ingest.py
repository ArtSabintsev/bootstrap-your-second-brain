#!/usr/bin/env python3
"""Ingest the newest xtap bookmarks snapshot into Sources/x-bookmarks/.

Reads the latest bookmarks-*.jsonl from $XTAP_HOME/snapshots (default
~/.xtap/snapshots), drops every tweet whose status URL already appears in a
prior capture under Sources/x-bookmarks/, and appends the rest to a dated
capture file (x-bookmarks-YYYY-MM-DD.md), creating it if needed.

Sources/ is immutable per AGENTS.md: this script only ever appends new
entries; it never rewrites existing ones.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = VAULT / "Sources" / "x-bookmarks"
XTAP_HOME = Path(os.environ.get("XTAP_HOME", Path.home() / ".xtap"))


def latest_snapshot() -> Path | None:
    files = sorted(XTAP_HOME.glob("snapshots/bookmarks-*.jsonl"))
    return files[-1] if files else None


def known_status_ids() -> set[str]:
    ids: set[str] = set()
    for md in CAPTURE_DIR.glob("*.md"):
        ids.update(re.findall(r"(?:x|twitter)\.com/[^/\s]+/(?:web/)?status/(\d+)", md.read_text()))
    return ids


def main() -> int:
    snap = latest_snapshot()
    if snap is None:
        print(f"no bookmarks snapshot found under {XTAP_HOME}/snapshots", file=sys.stderr)
        return 1

    seen = known_status_ids()
    fresh = []
    for line in snap.read_text().splitlines():
        t = json.loads(line)
        if t["id"] not in seen:
            fresh.append(t)

    if not fresh:
        print(f"{snap.name}: no new bookmarks (all {len(seen)} already captured)")
        return 0

    fresh.sort(key=lambda t: t.get("created_at", ""))
    today = date.today().isoformat()
    out = CAPTURE_DIR / f"x-bookmarks-{today}.md"

    chunks = []
    if not out.exists():
        chunks.append(
            f"# X bookmarks captured {today}\n\n"
            "Automated capture via scripts/x_bookmarks_ingest.py (xtap snapshot). "
            "Immutable raw source; filter into the wiki on ingest.\n"
        )
    for t in fresh:
        chunks.append(f"\n## [{t.get('created_at', '')}] @{t.get('author', 'unknown')}\n{t.get('text', '').strip()}\n\n{t.get('url', '')}\n")

    with out.open("a") as f:
        f.write("".join(chunks))

    print(f"{snap.name}: appended {len(fresh)} new bookmark(s) to {out.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
