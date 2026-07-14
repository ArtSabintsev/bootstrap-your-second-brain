#!/usr/bin/env python3
"""List a show's in-range episodes as TSV: vid, upload_date, title.

Usage: enumerate_inrange.py <show_key> [YYYYMMDD_cutoff]

Flat-lists the channel (fast), then fetches each video's date+title in parallel
(metadata only, no transcript) and keeps those on or after the cutoff. Output is
newest-first. Default cutoff is the ChatGPT launch week, 20221128.
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent.parent
sys.path.insert(0, str(BRAIN / "scripts"))
from config import ytdlp_cookie_args  # noqa: E402

YTDLP = str(BRAIN / ".venv" / "bin" / "yt-dlp")


# YouTube throttles unauthenticated bulk access (HTTP 429 + bot check), so
# authenticate with the browser session (config.browser) and tolerate
# format-unavailable errors (we only want metadata, not media).
def _cookies() -> list[str]:
    return [*ytdlp_cookie_args(), "--ignore-no-formats-error", "--sleep-requests", "1"]


def flat_ids(url: str) -> list[str]:
    out = subprocess.run(
        [YTDLP, *_cookies(), "--flat-playlist", "--print", "%(id)s", url],
        capture_output=True, text=True,
    )
    return [x for x in out.stdout.splitlines() if x.strip()]


def meta(vid: str) -> tuple[str, str, str] | None:
    out = subprocess.run(
        [YTDLP, *_cookies(), "--skip-download", "--no-write-subs",
         "--print", "%(upload_date)s\t%(title)s", vid],
        capture_output=True, text=True,
    )
    line = out.stdout.strip().splitlines()
    if not line:
        return None
    date, _, title = line[0].partition("\t")
    if not date or date == "NA":
        return None
    return vid, date, title


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    show = sys.argv[1]
    cutoff = sys.argv[2] if len(sys.argv) > 2 else "20221128"
    shows = json.loads((HERE / "shows.json").read_text())
    if show not in shows:
        print(f"unknown show '{show}'", file=sys.stderr)
        return 1

    ids = flat_ids(shows[show]["url"])
    print(f"{show}: {len(ids)} videos in feed, fetching dates...", file=sys.stderr)

    # Channel/playlist feed order is NOT reliably newest-first (playlists
    # especially), so fetch every video's date and filter. Parallel to stay fast.
    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(meta, ids):
            if r and r[1] >= cutoff:
                rows.append(r)

    rows.sort(key=lambda r: r[1], reverse=True)
    for vid, date, title in rows:
        print(f"{vid}\t{date}\t{title}")
    print(f"{show}: {len(rows)} episodes on/after {cutoff}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
