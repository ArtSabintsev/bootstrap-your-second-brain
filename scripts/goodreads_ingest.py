#!/usr/bin/env python3
"""Ingest the operator's Goodreads shelves into Sources/goodreads/.

Pulls the private all-shelves RSS feed (key read from
~/Developer/helpers/goodreads/rss-key, never stored in the vault), dedupes by
(book id, shelf state) against prior captures, and appends new or
shelf-changed books to a dated capture file (goodreads-YYYY-MM-DD.md).

A book moving to-read -> currently-reading -> read appears once per state,
so the archive records the reading lifecycle. Sources/ is immutable per
AGENTS.md: this script only appends.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import httpx

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get as cfg, secrets_dir  # noqa: E402

VAULT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = VAULT / "Sources" / "goodreads"
KEY_FILE = secrets_dir() / "goodreads" / "rss-key"
USER_ID = cfg("identity.goodreads_user_id", "")


def fetch_all_items() -> list[ET.Element]:
    key = KEY_FILE.read_text().strip()
    base = (
        f"https://www.goodreads.com/review/list_rss/{USER_ID}"
        f"?key={key}&shelf=%23ALL%23"
    )
    items: list[ET.Element] = []
    for page in range(1, 30):
        r = httpx.get(f"{base}&page={page}", timeout=30)
        r.raise_for_status()
        page_items = ET.fromstring(r.content).findall(".//item")
        items.extend(page_items)
        if len(page_items) < 100:
            break
    return items


def shelf_of(item: ET.Element) -> str:
    # user_shelves is empty for books on the implicit "read" shelf
    return (item.findtext("user_shelves") or "").strip() or "read"


def known_states() -> set[str]:
    states: set[str] = set()
    for md in CAPTURE_DIR.glob("*.md"):
        states.update(re.findall(r"<!-- gr:(\d+:[a-z0-9-]+) -->", md.read_text()))
    return states


def fmt_date(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return datetime.strptime(raw.strip(), "%a, %d %b %Y %H:%M:%S %z").date().isoformat()
    except ValueError:
        return raw.strip()


def render(item: ET.Element, shelf: str, book_id: str) -> str:
    title = (item.findtext("title") or "").strip()
    author = (item.findtext("author_name") or "").strip()
    rating = (item.findtext("user_rating") or "0").strip()
    read_at = fmt_date(item.findtext("user_read_at"))
    added = fmt_date(item.findtext("user_date_added"))
    review = (item.findtext("user_review") or "").strip()

    lines = [f"\n## [{shelf}] {title} — {author} <!-- gr:{book_id}:{shelf} -->"]
    meta = []
    if rating != "0":
        meta.append(f"rating {rating}/5")
    if read_at:
        meta.append(f"read {read_at}")
    if added:
        meta.append(f"added {added}")
    if meta:
        lines.append(", ".join(meta))
    if review:
        lines.append(f"\n{review}")
    lines.append(f"\nhttps://www.goodreads.com/book/show/{book_id}\n")
    return "\n".join(lines)


def main() -> int:
    if not KEY_FILE.exists():
        print(f"missing RSS key file: {KEY_FILE}", file=sys.stderr)
        return 1

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    seen = known_states()

    fresh = []
    for item in fetch_all_items():
        book_id = (item.findtext("book_id") or "").strip()
        shelf = shelf_of(item)
        if book_id and f"{book_id}:{shelf}" not in seen:
            fresh.append((item, shelf, book_id))

    if not fresh:
        print(f"goodreads: no shelf changes (tracking {len(seen)} book-states)")
        return 0

    today = date.today().isoformat()
    out = CAPTURE_DIR / f"goodreads-{today}.md"
    chunks = []
    if not out.exists():
        chunks.append(
            f"# Goodreads shelves captured {today}\n\n"
            "Automated capture via scripts/goodreads_ingest.py (all-shelves RSS). "
            "Immutable raw source; each entry is one (book, shelf-state).\n"
        )
    chunks.extend(render(item, shelf, book_id) for item, shelf, book_id in fresh)

    with out.open("a") as f:
        f.write("".join(chunks))

    print(f"goodreads: appended {len(fresh)} book-state(s) to {out.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
