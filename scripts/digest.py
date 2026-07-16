#!/usr/bin/env python3
"""Write the morning digest: what got filed, added, and updated on a given day.

Reads .status/filed.log and the day's git history, writes Digests/<date>.md.
Deterministic; no model call. Usage: digest.py [YYYY-MM-DD]
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
DIGESTS = VAULT / "Digests"
FILED_LOG = VAULT / ".status" / "filed.log"

CONTENT_DIRS = ("Library/", "People/", "Topics/", "Theses/", "Meetings/", "Projects/")


def git_files(day: str, diff_filter: str) -> list[str]:
    out = subprocess.run(
        ["git", "log", f"--since={day} 00:00", f"--until={day} 23:59",
         f"--diff-filter={diff_filter}", "--name-only", "--pretty=format:"],
        cwd=VAULT, capture_output=True, text=True,
    ).stdout
    seen: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if line and line.startswith(CONTENT_DIRS) and line.endswith(".md") and line not in seen:
            seen.append(line)
    return seen


def filed_items(day: str) -> list[str]:
    if not FILED_LOG.exists():
        return []
    return [ln[len(day):].strip() for ln in FILED_LOG.read_text().splitlines() if ln.startswith(day)]


def main() -> int:
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    filed = filed_items(day)
    added = git_files(day, "A")
    updated = [f for f in git_files(day, "M") if f.startswith(("People/", "Theses/"))]

    if not (filed or added or updated):
        print(f"{day}: nothing landed; no digest written")
        return 0

    lines = [
        "---",
        f'title: "Digest {day}"',
        "type: digest",
        "tags: [productivity]",
        f"created: {day}",
        f"updated: {day}",
        "---",
        "",
        f"# Digest · {day}",
        "",
    ]
    if filed:
        lines += ["## Filed", ""] + [f"- {item}" for item in filed] + [""]
    if added:
        if len(added) > 40:
            from collections import Counter
            counts = Counter(f.split("/")[0] + ("/" + f.split("/")[1] if f.startswith("Library/") and len(f.split("/")) > 2 else "") for f in added)
            lines += ["## New notes", ""] + [f"- {k}: {v}" for k, v in counts.most_common()] + [""]
            keynotes = [f for f in added if f.startswith(("People/", "Topics/", "Theses/", "Meetings/"))][:30]
            if keynotes:
                lines += ["Key additions:", ""] + [f"- [[{Path(f).stem}]] ({f})" for f in keynotes] + [""]
        else:
            lines += ["## New notes", ""] + [f"- [[{Path(f).stem}]] ({f})" for f in added] + [""]
    if updated:
        if len(updated) > 30:
            lines += ["## Ledgers and theses updated", "", f"- {len(updated)} People/Theses notes touched (bulk pass)", ""]
        else:
            lines += ["## Ledgers and theses updated", ""] + [f"- [[{Path(f).stem}]] ({f})" for f in updated] + [""]

    DIGESTS.mkdir(exist_ok=True)
    out = DIGESTS / f"{day}.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out.relative_to(VAULT)} (filed {len(filed)}, new {len(added)}, updated {len(updated)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
