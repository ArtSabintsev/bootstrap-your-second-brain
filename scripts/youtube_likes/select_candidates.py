#!/usr/bin/env python3
"""Emit NEW long-form YouTube-like candidates for synthesis as TSV.

Pulls the Liked-videos playlist (LL) live with the browser session, keeps videos
at or above the duration threshold (default 1200s = 20 min), and drops any that
are already handled: a note already exists for them, or they are in the skip-log
(judged not-substantive / no transcript). No stored catalog is kept; the vault's
own notes plus the skip-log are the watermark, so re-runs only surface new likes.

Usage: select_candidates.py [min_seconds]   -> vid \t dur \t channel \t title
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
YTDLP = str(VAULT / ".venv" / "bin" / "yt-dlp")
NOTES_DIR = VAULT / "Library" / "youtube-likes"
SKIP_LOG = VAULT / ".status" / "youtube-likes-skip.log"
LL = "https://www.youtube.com/playlist?list=LL"


def processed_ids() -> set[str]:
    ids: set[str] = set()
    if SKIP_LOG.exists():
        ids.update(ln.split()[0] for ln in SKIP_LOG.read_text().splitlines() if ln.strip())
    for md in NOTES_DIR.glob("*.md"):
        ids.update(re.findall(r"[?&]v=([A-Za-z0-9_-]{11})", md.read_text()))
    return ids


def main() -> int:
    threshold = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    out = subprocess.run(
        [YTDLP, "--cookies-from-browser", "brave", "--flat-playlist",
         "--print", "%(id)s\t%(duration)s\t%(channel)s\t%(title)s", LL],
        capture_output=True, text=True,
    )
    done = processed_ids()
    n = 0
    for ln in out.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) < 4:
            continue
        vid, dur = parts[0], parts[1]
        if not dur.isdigit() or int(dur) < threshold or vid in done:
            continue
        print(ln)
        n += 1
    print(f"select: {n} new candidate(s) >= {threshold}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
