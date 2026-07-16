#!/usr/bin/env python3
"""Fetch one RSS episode's text payload for synthesis.

Usage: fetch_rss_episode.py <show_key> <episode_id> <out_text_path>

Writes plain text (title + description + link) to out_text_path.
Prints: YYYYMMDD\\ttitle
Exit 3 if episode not found.
"""

from __future__ import annotations

import html
import re
import sys
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
SHOWS = HERE / "shows.json"

_TAG = re.compile(r"<[^>]+>", re.S)


def _strip_html(s: str) -> str:
    s = html.unescape(s or "")
    s = _TAG.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # drop standard ad footers
    s = re.split(r"Learn more about your ad choices", s, flags=re.I)[0].strip()
    return s


def _episode_id(item: ET.Element) -> str:
    enc = item.find("enclosure")
    if enc is not None and enc.get("url"):
        url = enc.get("url", "")
        # .../WSJ5420672519.mp3
        m = re.search(r"/([A-Za-z0-9_-]+)\.mp3", url)
        if m:
            return m.group(1)
    guid = (item.findtext("guid") or "").strip()
    if guid:
        return re.sub(r"[^A-Za-z0-9_-]+", "-", guid)[:40]
    return re.sub(r"[^A-Za-z0-9]+", "-", (item.findtext("title") or "ep"))[:40]


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 1
    show_key, want_id, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    import json

    shows = json.loads(SHOWS.read_text())
    show = shows[show_key]
    if show.get("source") != "rss":
        print("not an rss show", file=sys.stderr)
        return 1
    with urllib.request.urlopen(show["url"], timeout=60) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    for item in root.findall(".//item"):
        eid = _episode_id(item)
        if eid != want_id and want_id not in (item.findtext("guid") or ""):
            continue
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate") or ""
        d = parsedate_to_datetime(pub)
        ymd = d.strftime("%Y%m%d")
        desc = _strip_html(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        enc = item.find("enclosure")
        audio = enc.get("url") if enc is not None else ""
        body = (
            f"Title: {title}\n"
            f"Published: {d.isoformat()}\n"
            f"Show: {show.get('title', show_key)}\n"
            f"Link: {link}\n"
            f"Audio: {audio}\n\n"
            f"Episode summary / show notes:\n{desc}\n"
        )
        Path(out_path).write_text(body, encoding="utf-8")
        print(f"{ymd}\t{title}")
        return 0
    print(f"episode not found: {want_id}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
