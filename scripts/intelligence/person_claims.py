#!/usr/bin/env python3
"""Dump a person's dated claims across all their podcast/video appearances.

Usage: person_claims.py <person-slug> [max_episodes]

Reads _indexes/appearances.json for the person's episodes (newest first), then
for each pulls that episode's date and its "## Core claims & predictions" and
"## Notable segments" sections (where a recurring guest's positions live). Emits
a compact, dated digest for the ledger generator so it never has to load whole
transcripts.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
INDEX = VAULT / "_indexes" / "appearances.json"
POD = VAULT / "Library" / "podcasts"
LIKES = VAULT / "Library" / "youtube-likes"


def section(text: str, header: str) -> str:
    m = re.search(rf"^##\s+{re.escape(header)}.*?$(.*?)(?=^##\s|\Z)", text,
                  re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def find_note(stem: str) -> Path | None:
    for base in (POD, LIKES):
        hits = list(base.rglob(f"{stem}.md"))
        if hits:
            return hits[0]
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    slug = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    idx = json.loads(INDEX.read_text())
    person = idx["people"].get(slug)
    if not person:
        print(f"no appearances indexed for {slug}", file=sys.stderr)
        return 2

    print(f"# Claims digest: {slug}  ({person['count']} appearances)\n")
    for ep in person["episodes"][:cap]:
        note = find_note(ep["note"])
        if not note:
            continue
        text = note.read_text()
        claims = section(text, "Core claims & predictions") or section(text, "Core claims & arguments")
        segs = section(text, "Notable segments")
        body = "\n".join(x for x in (claims, segs) if x)
        if not body:
            continue
        print(f"## {ep['date']} — {ep['show']} — [[{ep['note']}]]")
        print(body[:2500])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
