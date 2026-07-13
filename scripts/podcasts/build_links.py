#!/usr/bin/env python3
"""Build the appearances index from episode/video notes. Index, not landfill.

Scans every note under Library/podcasts/ and Library/youtube-likes/, reads the
[[wikilinks]] in each note's Guests/Source and Threads sections, and writes a
single machine-readable index to _indexes/appearances.json:

    { "people": { slug: {count, episodes:[{note,show,date}]} },
      "topics": { slug: {count, episodes:[...]} } }

It creates NO markdown. People/Topics notes are curated (canonical ontology,
tiered people, position ledgers) and are never auto-minted, which is what kept
the vault an ever-growing archive instead of an intelligence layer. The brief
generator and cleanup tooling read this index.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
POD_DIR = VAULT / "Library" / "podcasts"
LIKES_DIR = VAULT / "Library" / "youtube-likes"
INDEX = VAULT / "_indexes" / "appearances.json"

_LINK = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]")
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_FM_CREATED = re.compile(r"^created:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def section_links(text: str, header: str) -> set[str]:
    m = re.search(rf"^##\s+{re.escape(header)}\s*$(.*?)(?=^##\s|\Z)", text,
                  re.MULTILINE | re.DOTALL)
    if not m:
        return set()
    out = set()
    for raw in _LINK.findall(m.group(1)):
        slug = re.split(r"[\\/]", raw.strip())[-1].strip().lower()
        slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")
        if slug:
            out.add(slug)
    return out


def note_date(note: Path, text: str) -> str:
    m = _DATE_PREFIX.match(note.stem)
    if m:
        return m.group(1)
    m = _FM_CREATED.search(text)
    return m.group(1) if m else ""


def main() -> int:
    notes = sorted(POD_DIR.rglob("*.md")) + sorted(LIKES_DIR.glob("*.md"))
    episode_slugs = {n.stem.lower() for n in notes}
    people: dict[str, list] = defaultdict(list)
    topics: dict[str, list] = defaultdict(list)

    parsed = []
    for n in notes:
        text = n.read_text()
        guests = section_links(text, "Guests") | section_links(text, "Source")
        threads = section_links(text, "Threads")
        parsed.append((n, guests, threads, note_date(n, text)))
    person_slugs = set().union(*[g for _, g, _, _ in parsed]) if parsed else set()

    for n, guests, threads, date in parsed:
        show = n.parent.name
        entry = {"note": n.stem, "show": show, "date": date}
        for slug in guests:
            people[slug].append(entry)
        for slug in threads:
            if slug in person_slugs:
                continue
            if re.match(r"\d{4}-\d{2}-\d{2}-", slug) or slug in episode_slugs:
                continue  # link to another episode, not a topic
            topics[slug].append(entry)

    def pack(d):
        return {
            slug: {
                "count": len(eps),
                "episodes": sorted(eps, key=lambda e: e["date"], reverse=True),
            }
            for slug, eps in sorted(d.items(), key=lambda kv: len(kv[1]), reverse=True)
        }

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps({"people": pack(people), "topics": pack(topics)}, indent=1))
    print(f"build_links: indexed {len(notes)} notes -> "
          f"{len(people)} people, {len(topics)} topics in {INDEX.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
