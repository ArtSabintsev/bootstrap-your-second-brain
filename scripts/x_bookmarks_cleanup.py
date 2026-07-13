#!/usr/bin/env python3
"""Remove bookmarks from X once they are safely archived in the vault.

For every tweet in the newest bookmarks snapshot, verify its status ID appears
in a capture under Sources/x-bookmarks/, then call DeleteBookmark for it.
Anything not yet archived is left untouched. This only removes bookmarks; it
never deletes tweets, likes, or follows.

Usage: x_bookmarks_cleanup.py [--dry-run]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "xtap" / "src"))

from xtap.client import XClient  # noqa: E402
from xtap.paths import home  # noqa: E402

VAULT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = VAULT / "Sources" / "x-bookmarks"


def archived_ids() -> set[str]:
    import re

    ids: set[str] = set()
    for md in CAPTURE_DIR.glob("*.md"):
        ids.update(re.findall(r"(?:x|twitter)\.com/[^/\s]+/(?:web/)?status/(\d+)", md.read_text()))
    return ids


def snapshot_ids() -> list[str]:
    snaps = sorted(home().glob("snapshots/bookmarks-*.jsonl"))
    if not snaps:
        return []
    return [json.loads(line)["id"] for line in snaps[-1].read_text().splitlines()]


async def cleanup(dry_run: bool) -> None:
    archived = archived_ids()
    current = snapshot_ids()
    deletable = [i for i in current if i in archived]
    skipped = len(current) - len(deletable)

    if skipped:
        print(f"skipping {skipped} bookmark(s) not yet archived")
    if not deletable:
        print("nothing to delete")
        return
    if dry_run:
        print(f"dry-run: would unbookmark {len(deletable)} archived bookmark(s)")
        return

    async with XClient() as xc:
        done = 0
        for tid in deletable:
            try:
                await xc.unbookmark(tid)
                done += 1
            except Exception as e:  # noqa: BLE001 — keep going; retry tomorrow
                print(f"WARN: unbookmark {tid} failed: {e}")
            await xc.sleep_pace()
    print(f"unbookmarked {done}/{len(deletable)} archived bookmark(s) on X")


if __name__ == "__main__":
    asyncio.run(cleanup(dry_run="--dry-run" in sys.argv))
