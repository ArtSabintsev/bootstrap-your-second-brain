#!/usr/bin/env python3
"""Write a lightweight world-context note from RSS show-notes (no LLM).

Usage: write_world_context_note.py <show_key> <episode_id> <YYYYMMDD> <title> <text_path> <note_path>

For daily news digests (e.g. WSJ What's News): captures what the world was
doing that day from publisher show notes. Idempotent if note_path exists.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60]


def bullets_from_summary(text: str) -> list[str]:
    # Prefer content after "show notes" header if present
    if "Episode summary / show notes:" in text:
        text = text.split("Episode summary / show notes:", 1)[1]
    text = text.strip()
    # Split on sentence-ish boundaries and Plus, / And patterns WSJ uses
    chunks = re.split(r"(?<=[.!?])\s+|\s+Plus,\s+|\s+And\s+(?=[A-Z])", text)
    out: list[str] = []
    for c in chunks:
        c = c.strip(" .;")
        if len(c) < 40:
            continue
        if re.search(r"sign up for|ad choices|newsletter", c, re.I):
            continue
        out.append(c if c.endswith(".") else c + ".")
        if len(out) >= 8:
            break
    return out


def main() -> int:
    if len(sys.argv) < 7:
        print(__doc__, file=sys.stderr)
        return 1
    show_key, eid, ymd, title, text_path, note_path = (
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
    )
    note = Path(note_path)
    if note.exists():
        print(f"skip (exists): {note}")
        return 5
    shows = json.loads((HERE / "shows.json").read_text())
    show = shows[show_key]
    tags = show.get("tags") or ["history"]
    text = Path(text_path).read_text(encoding="utf-8")
    # parse link/audio from payload
    link = ""
    audio = ""
    for line in text.splitlines():
        if line.startswith("Link: "):
            link = line[6:].strip()
        if line.startswith("Audio: "):
            audio = line[7:].strip()
    bullets = bullets_from_summary(text)
    iso = f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
    show_title = show.get("title", show_key)
    tag_yaml = json.dumps(tags)
    source = link or audio or show.get("url", "")
    body_bullets = "\n".join(f"- {b}" for b in bullets) or "- (see show notes in Sources field; sparse summary)"
    md = f"""---
title: {json.dumps(title)}
tags: {tag_yaml}
created: {iso}
updated: {iso}
source: {json.dumps(source)}
episode_id: {json.dumps(eid)}
show: {json.dumps(show_key)}
role: world-context
---

# {title}

**{show_title}** · {iso} · world-context digest (publisher show notes; not a full transcript synthesis).

## What the world was doing

{body_bullets}

## Meta

This show is tracked as a **timeline layer**: what markets/politics/tech headlines
looked like while interest-depth shows (All-In, Lex, Dwarkesh, etc.) go deep.
Use for "what else was happening when X was claimed."

- Audio: {audio or "—"}
- Episode id: `{eid}`
"""
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(md, encoding="utf-8")
    print(f"done: {show_key} {eid} {iso}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
