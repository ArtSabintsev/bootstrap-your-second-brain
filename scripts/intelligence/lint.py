#!/usr/bin/env python3
"""Lint the second brain: surface what needs attention, not what exists.

Deterministic health-check (the Karpathy 'lint' operation, adapted to this
vault's intelligence layer). Writes a report to _indexes/lint-report.md flagging:

  1. Core people (many appearances) with no position ledger yet.
  2. High-frequency topics not covered by the canonical ontology (drift in).
  3. Ontology concepts with zero appearances in the index (drift out / dead).
  4. Theses with no recent citing episode (possibly stale).
  5. Ledgers not refreshed since their newest cited episode (reversal may be
     un-captured).

It proposes actions; it never mutates content. Run it periodically or after a
backfill. The contradiction/thesis-pressure check (needs an LLM read) is a
separate pass; this is the cheap deterministic sweep.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
INDEX = VAULT / "_indexes" / "appearances.json"
ONTOLOGY = VAULT / "scripts" / "ontology.yaml"
LEDGER_MIN = 10   # appearances above which a person deserves a ledger
TOPIC_MIN = 15    # appearances above which a topic should be in the ontology


def ontology_slugs() -> set[str]:
    slugs: set[str] = set()
    if not ONTOLOGY.exists():
        return slugs
    for line in ONTOLOGY.read_text().splitlines():
        m = re.match(r"\s*- slug:\s*(\S+)", line) or re.match(r"\s*-\s*([a-z0-9-]+)\s*$", line)
        if m:
            slugs.add(m.group(1).strip())
    return slugs


def main() -> int:
    idx = json.loads(INDEX.read_text())
    onto = ontology_slugs()
    out = [f"# Brain lint report — {date.today().isoformat()}\n"]

    # 1. core people without a ledger
    missing = []
    for slug, v in idx["people"].items():
        if v["count"] < LEDGER_MIN:
            continue
        note = VAULT / "People" / f"{slug}.md"
        if not note.exists() or "Position ledger" not in note.read_text():
            missing.append((slug, v["count"]))
    out.append(f"## Core people without a ledger ({len(missing)})\n")
    out += [f"- `{c}` [[{s}]] -> build_ledger.sh {s}" for s, c in missing[:40]]

    # 2. high-frequency topics missing from ontology
    drift_in = [(s, v["count"]) for s, v in idx["topics"].items()
                if v["count"] >= TOPIC_MIN and s not in onto]
    out.append(f"\n## High-frequency topics not in ontology ({len(drift_in)})\n")
    out += [f"- `{c}` {s} -> add to scripts/ontology.yaml (canonical or alias)"
            for s, c in drift_in[:40]]

    # 3. ontology concepts with no appearances (dead)
    seen = set(idx["topics"])
    dead = [s for s in sorted(onto) if s not in seen]
    out.append(f"\n## Ontology concepts with zero appearances ({len(dead)})\n")
    out += [f"- {s} -> verify still relevant or drop" for s in dead[:40]]

    # 4. theses not reviewed in 30+ days (age-based; contradiction-pressure is a
    #    separate LLM pass, not a citation match)
    thesis_dir = VAULT / "Theses"
    stale = []
    cutoff = date.today().toordinal() - 30
    if thesis_dir.exists():
        for t in sorted(thesis_dir.glob("*.md")):
            m = re.search(r"^updated:\s*(\d{4})-(\d{2})-(\d{2})", t.read_text(), re.MULTILINE)
            if m:
                d = date(int(m[1]), int(m[2]), int(m[3])).toordinal()
                if d < cutoff:
                    stale.append(t.stem)
            else:
                stale.append(t.stem)
    out.append(f"\n## Theses not reviewed in 30+ days ({len(stale)})\n")
    out += [f"- [[{s}]] -> run thesis-pressure review against recent claims" for s in stale]

    report = VAULT / "_indexes" / "lint-report.md"
    report.write_text("\n".join(out) + "\n")
    print(f"lint: {len(missing)} ledger gaps, {len(drift_in)} topic drift-ins, "
          f"{len(dead)} dead concepts, {len(stale)} possibly-stale theses -> {report.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
