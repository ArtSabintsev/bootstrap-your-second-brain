#!/usr/bin/env python3
"""Archive the operator's published Substack essays into Sources/substack/.

Fetches the publication feed (from config identity.substack_feed), converts each
post body from HTML to markdown, and writes one file per post
(kebab-case slug). Existing files are never touched: Sources/ is immutable
per AGENTS.md, so a published post is captured once, as published.

Note: the RSS feed covers publication posts only, not Substack Notes and not
posts saved/liked on other publications.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import html2text
import httpx

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get as cfg  # noqa: E402

VAULT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = VAULT / "Sources" / "substack"
FEED = cfg("identity.substack_feed", "")
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def fmt_date(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return datetime.strptime(raw.strip(), "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()
    except ValueError:
        return raw.strip()


def main() -> int:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    r = httpx.get(FEED, timeout=30, follow_redirects=True)
    r.raise_for_status()

    conv = html2text.HTML2Text()
    conv.body_width = 0
    conv.ignore_images = False

    new = 0
    for item in ET.fromstring(r.content).findall(".//item"):
        title = (item.findtext("title") or "").strip()
        out = CAPTURE_DIR / f"{slugify(title)}.md"
        if out.exists():
            continue

        link = (item.findtext("link") or "").strip()
        pub = fmt_date(item.findtext("pubDate"))
        subtitle = (item.findtext("description") or "").strip()
        body_el = item.find(CONTENT_NS)
        body = conv.handle(body_el.text or "") if body_el is not None else ""

        out.write_text(
            "---\n"
            f'title: "{title}"\n'
            "tags: [writing, substack]\n"
            f"created: {pub}\n"
            f"updated: {pub}\n"
            f"source: {link}\n"
            "---\n\n"
            f"# {title}\n\n"
            f"*{subtitle}*\n\n"
            f"{body.strip()}\n"
        )
        new += 1
        print(f"substack: archived '{title}' -> {out.relative_to(VAULT)}")

    if not new:
        print("substack: no new posts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
