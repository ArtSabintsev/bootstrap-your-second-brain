#!/usr/bin/env python3
"""Referee for the Goodreads book-processing loop.

Exits 0 iff every book in .status/goodreads-books-manifest.json has a note at
Library/books/<file> satisfying the note contract in .status/goodreads-books-GOAL.md.
"""
import json
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
BOOKS = VAULT / "Library" / "books"
MANIFEST = VAULT / ".status" / "goodreads-books-manifest.json"

VALID_TAGS = {
    "ai-agents", "agent-payments", "agent-memory", "ai-coding", "ai-enablement",
    "bitcoin", "mining", "privacy", "sovereignty",
    "israel-zionism", "jewish-mythology", "gold-ranger", "ventures", "unsorted",
}
REQUIRED_KEYS = ("title:", "author:", "tags:", "created:", "updated:", "source:", "shelf:", "category:")


def check(entry):
    path = BOOKS / entry["file"]
    if not path.exists():
        return "missing file"
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return "no frontmatter block"
    fm, body = m.groups()
    problems = []
    for key in REQUIRED_KEYS:
        if not re.search(rf"^{key}", fm, re.MULTILINE):
            problems.append(f"frontmatter missing {key}")
    if entry["id"] not in fm:
        problems.append("goodreads id not in frontmatter source")
    fm_tags = set(re.findall(r"[a-z0-9-]+", " ".join(re.findall(r"tags:.*|^\s*-\s*([a-z0-9-]+)", fm, re.MULTILINE))))
    tag_line = re.search(r"^tags:\s*\[(.*?)\]", fm, re.MULTILINE)
    if tag_line:
        tags = {t.strip() for t in tag_line.group(1).split(",") if t.strip()}
        bad = tags - VALID_TAGS
        if bad:
            problems.append(f"invalid tags {sorted(bad)}")
    if len(body.strip()) < 400:
        problems.append(f"body too thin ({len(body.strip())} chars)")
    if not re.search(r"^## ", body, re.MULTILINE):
        problems.append("no ## section")
    if not re.search(r"\[\[[^\]]+\]\]", body):
        problems.append("no wikilink")
    if re.search(r'^title: (?!["\'])\S.*: ', fm, re.MULTILINE):
        problems.append("unquoted colon in title (invalid YAML)")
    if entry.get("review"):
        flat = re.sub(r"\s+", " ", text.replace(">", " "))
        for part in re.split(r"<br\s*/?>", entry["review"]):
            part = part.strip()
            if part and re.sub(r"\s+", " ", part) not in flat:
                problems.append("captured review not quoted in full")
                break
    return "; ".join(problems) if problems else None


def main():
    manifest = json.loads(MANIFEST.read_text())
    failures = {}
    for entry in manifest:
        problem = check(entry)
        if problem:
            failures[entry["file"]] = problem
    if failures:
        print(f"FAIL {len(failures)}/{len(manifest)}")
        for f, p in sorted(failures.items()):
            print(f"  {f}: {p}")
        sys.exit(1)
    print(f"OK {len(manifest)}/{len(manifest)} notes pass")
    sys.exit(0)


if __name__ == "__main__":
    main()
