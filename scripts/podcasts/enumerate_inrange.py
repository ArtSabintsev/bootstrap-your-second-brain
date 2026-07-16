#!/usr/bin/env python3
"""List a show's in-range episodes as TSV: id, upload_date, title.

Usage: enumerate_inrange.py <show_key> [YYYYMMDD_cutoff]

YouTube shows: flat-list channel/playlist, fetch dates, filter.
RSS shows (shows.json source=rss): parse feed, filter by pubDate.

Default cutoff is config podcasts.cutoff, else 20220224 (Ukraine week). Output newest-first.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent.parent
sys.path.insert(0, str(BRAIN / "scripts"))
from config import ytdlp_cookie_args  # noqa: E402

YTDLP = str(BRAIN / ".venv" / "bin" / "yt-dlp")


def _cookies() -> list[str]:
    return [*ytdlp_cookie_args(), "--ignore-no-formats-error", "--sleep-requests", "1"]


def flat_ids(url: str) -> list[str]:
    out = subprocess.run(
        [YTDLP, *_cookies(), "--flat-playlist", "--print", "%(id)s", url],
        capture_output=True,
        text=True,
    )
    return [x for x in out.stdout.splitlines() if x.strip()]


def meta(vid: str) -> tuple[str, str, str] | None:
    out = subprocess.run(
        [
            YTDLP,
            *_cookies(),
            "--skip-download",
            "--no-write-subs",
            "--print",
            "%(upload_date)s\t%(title)s",
            vid,
        ],
        capture_output=True,
        text=True,
    )
    line = out.stdout.strip().splitlines()
    if not line:
        return None
    date, _, title = line[0].partition("\t")
    if not date or date == "NA":
        return None
    return vid, date, title


def _rss_episode_id(item: ET.Element) -> str:
    enc = item.find("enclosure")
    if enc is not None and enc.get("url"):
        m = re.search(r"/([A-Za-z0-9_-]+)\.mp3", enc.get("url", ""))
        if m:
            return m.group(1)
    guid = (item.findtext("guid") or "").strip()
    if guid:
        return re.sub(r"[^A-Za-z0-9_-]+", "-", guid)[:40]
    return re.sub(r"[^A-Za-z0-9]+", "-", (item.findtext("title") or "ep"))[:40]


def enumerate_rss(url: str, cutoff: str) -> list[tuple[str, str, str]]:
    with urllib.request.urlopen(url, timeout=90) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    rows: list[tuple[str, str, str]] = []
    for item in root.findall(".//item"):
        pub = item.findtext("pubDate") or ""
        try:
            d = parsedate_to_datetime(pub)
        except (TypeError, ValueError):
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        else:
            d = d.astimezone(timezone.utc)
        ymd = d.strftime("%Y%m%d")
        if ymd < cutoff:
            continue
        title = (item.findtext("title") or "").strip()
        rows.append((_rss_episode_id(item), ymd, title))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def enumerate_youtube(url: str, cutoff: str) -> list[tuple[str, str, str]]:
    ids = flat_ids(url)
    print(f"youtube: {len(ids)} videos in feed, fetching dates...", file=sys.stderr)
    rows: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(meta, ids):
            if r and r[1] >= cutoff:
                rows.append(r)
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    show = sys.argv[1]
    if len(sys.argv) > 2:
        cutoff = sys.argv[2]
    else:
        try:
            from config import get as cfg_get

            cutoff = str(cfg_get("podcasts.cutoff") or "20220224")
        except Exception:
            cutoff = "20220224"
    shows = json.loads((HERE / "shows.json").read_text())
    if show not in shows:
        print(f"unknown show '{show}'", file=sys.stderr)
        return 1
    cfg = shows[show]
    source = cfg.get("source", "youtube")
    if source == "rss":
        rows = enumerate_rss(cfg["url"], cutoff)
    else:
        rows = enumerate_youtube(cfg["url"], cutoff)
    for vid, date, title in rows:
        print(f"{vid}\t{date}\t{title}")
    print(f"{show}: {len(rows)} episodes on/after {cutoff}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
