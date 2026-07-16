#!/usr/bin/env python3
"""Build lean monthly world-context digests from an RSS news show.

Does NOT create one note per episode. Groups episodes by YYYY-MM, writes:

  Library/podcasts/<show_key>/YYYY-MM.md

Usage:
  consolidate_world_context.py <show_key> [YYYYMMDD_cutoff]

Default cutoff: config podcasts.cutoff or 20220224 (Ukraine invasion week).
Idempotent rewrite of month notes from the live feed (source of truth is RSS).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent.parent
sys.path.insert(0, str(BRAIN / "scripts"))

_TAG = re.compile(r"<[^>]+>", re.S)
MAX_BULLETS_PER_MONTH = 40  # hard cap — gist, not archive


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.split(r"Learn more about your ad choices", s, flags=re.I)[0].strip()
    return s


def bullets(text: str, limit: int = 6) -> list[str]:
    text = strip_html(text)
    chunks = re.split(r"(?<=[.!?])\s+|\s+Plus,\s+|\s+And\s+(?=[A-Z])", text)
    out: list[str] = []
    for c in chunks:
        c = c.strip(" .;")
        if len(c) < 45:
            continue
        if re.search(r"sign up for|ad choices|newsletter|brought to you", c, re.I):
            continue
        out.append(c if c.endswith(".") else c + ".")
        if len(out) >= limit:
            break
    return out


def load_cutoff(cli: str | None) -> str:
    if cli:
        return cli
    try:
        from config import get as cfg_get

        return str(cfg_get("podcasts.cutoff") or "20220224")
    except Exception:
        return "20220224"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    show_key = sys.argv[1]
    cutoff = load_cutoff(sys.argv[2] if len(sys.argv) > 2 else None)
    shows = json.loads((HERE / "shows.json").read_text())
    if show_key not in shows:
        print(f"unknown show {show_key}", file=sys.stderr)
        return 1
    show = shows[show_key]
    if show.get("role") != "world-context" or show.get("source") != "rss":
        print("show must be source=rss and role=world-context", file=sys.stderr)
        return 1

    with urllib.request.urlopen(show["url"], timeout=90) as r:
        root = ET.fromstring(r.read())

    by_month: dict[str, list[dict]] = defaultdict(list)
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
        month = d.strftime("%Y-%m")
        title = (item.findtext("title") or "").strip()
        desc = item.findtext("description") or ""
        by_month[month].append(
            {
                "ymd": ymd,
                "iso": d.strftime("%Y-%m-%d"),
                "title": title,
                "bullets": bullets(desc, limit=4),
            }
        )

    out_dir = BRAIN / "Library" / "podcasts" / show_key
    out_dir.mkdir(parents=True, exist_ok=True)
    tags = show.get("tags") or ["history"]
    show_title = show.get("title", show_key)
    written = 0

    for month in sorted(by_month.keys()):
        eps = sorted(by_month[month], key=lambda e: e["ymd"])
        # Keep gist: prefer fewer, denser bullets across the month
        lines: list[str] = []
        seen: set[str] = set()
        for ep in eps:
            for b in ep["bullets"]:
                key = b[:80].lower()
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- **{ep['iso']}** — {b}")
                if len(lines) >= MAX_BULLETS_PER_MONTH:
                    break
            if len(lines) >= MAX_BULLETS_PER_MONTH:
                break

        note = out_dir / f"{month}.md"
        md = f"""---
title: "{show_title} — {month}"
tags: {json.dumps(tags)}
created: {month}-01
updated: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}
show: {json.dumps(show_key)}
role: world-context
period: {json.dumps(month)}
episode_count: {len(eps)}
source: {json.dumps(show["url"])}
---

# {show_title} — {month}

World-context **month digest** from {len(eps)} feed episodes (after cutoff).
**Gist only** — no per-episode notes. Depth shows stay in their own folders.

## Gist

{chr(10).join(lines) if lines else "_No dense bullets extracted._"}

## Meta

- Rebuild anytime: `python3 scripts/podcasts/consolidate_world_context.py {show_key}`
- Audio stays on the publisher feed; vault holds the monthly gist only.
"""
        note.write_text(md, encoding="utf-8")
        written += 1
        print(f"wrote {note.relative_to(BRAIN)} ({len(eps)} eps, {len(lines)} gist bullets)")

    # README for the folder
    readme = out_dir / "README.md"
    readme.write_text(
        f"""---
title: "{show_title}"
type: index
tags: {json.dumps(tags)}
updated: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}
---

# {show_title}

**World-context layer** — monthly digests, not one note per episode.

```bash
python3 scripts/podcasts/consolidate_world_context.py {show_key}
```

Cutoff: config `podcasts.cutoff` (Ukraine invasion week `20220224` by default).
""",
        encoding="utf-8",
    )
    print(f"{show_key}: {written} month notes under Library/podcasts/{show_key}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
