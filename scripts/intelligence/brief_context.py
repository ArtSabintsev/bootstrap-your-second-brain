#!/usr/bin/env python3
"""Assemble the context for a pre-engagement brief on a person/company/theme.

Usage: brief_context.py <target-slug>

Pulls, from the graph and notes:
  - the target's position ledger (People/<slug>.md) if it exists, else a raw
    dated claims digest,
  - graph neighbors: the people they most co-appear with (traversal, not lookup),
  - the operator's active theses (Theses/*.md, current-view lines),
so the brief generator can answer "what did they claim over time, where did they
reverse, and how does it collide with the operator's theses" in one pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
INDEX = VAULT / "_indexes" / "appearances.json"
HERE = Path(__file__).resolve().parent


def neighbors(idx: dict, slug: str, top: int = 8) -> list[tuple[str, int]]:
    eps = {e["note"] for e in idx["people"].get(slug, {}).get("episodes", [])}
    if not eps:
        return []
    co: Counter = Counter()
    for other, v in idx["people"].items():
        if other == slug:
            continue
        shared = sum(1 for e in v["episodes"] if e["note"] in eps)
        if shared:
            co[other] = shared
    return co.most_common(top)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    slug = sys.argv[1]
    idx = json.loads(INDEX.read_text())

    print(f"# Brief context: {slug}\n")

    ledger = VAULT / "People" / f"{slug}.md"
    if ledger.exists() and "Position ledger" in ledger.read_text():
        print("## Existing position ledger\n")
        print(ledger.read_text())
    else:
        print("## Dated claims digest (no ledger yet)\n")
        out = subprocess.run(
            [str(VAULT / ".venv/bin/python3"), str(HERE / "person_claims.py"), slug, "40"],
            capture_output=True, text=True,
        )
        print(out.stdout or f"(no indexed appearances for {slug})")

    nb = neighbors(idx, slug)
    if nb:
        print("\n## Graph neighbors (most co-appearances)\n")
        for other, n in nb:
            print(f"- [[{other}]] ({n} shared episodes)")

    theses = sorted((VAULT / "Theses").glob("*.md"))
    if theses:
        print("\n## The operator's active theses (collide-check against these)\n")
        for t in theses:
            lines = t.read_text().splitlines()
            title = next((l[2:] for l in lines if l.startswith("# ")), t.stem)
            cur = ""
            body = t.read_text()
            if "## Current view" in body:
                cur = body.split("## Current view", 1)[1].split("##", 1)[0].strip()[:240]
            print(f"- **[[{t.stem}]]** — {title}\n  {cur}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
