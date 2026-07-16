#!/usr/bin/env python3
"""Assert every thesis next-falsifier is a usable full sentence, not a stub."""

from __future__ import annotations

import re
import sys

import pytest
from pathlib import Path

VAULT = Path(__file__).resolve().parents[3]
THESES = VAULT / "Theses"

STUB_LAST = {
    "no",
    "a",
    "the",
    "and",
    "or",
    "of",
    "to",
    "for",
    "with",
    "actual",
    "burn",
}


def extract_nf(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    fm = text[3:end] if end > 0 else ""
    for line in fm.splitlines():
        if line.startswith("next-falsifier:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def test_all_next_falsifiers_complete():
    files = sorted(THESES.glob("*.md"))
    if not files:
        pytest.skip("fresh vault: no theses yet")
    bad: list[str] = []
    for p in files:
        nf = extract_nf(p.read_text(encoding="utf-8"))
        if not nf:
            bad.append(f"{p.name}: missing")
            continue
        if len(nf) < 80:
            bad.append(f"{p.name}: too short ({len(nf)}): {nf!r}")
            continue
        last = nf.rstrip().split()[-1].lower().strip(".,;:")
        if last in STUB_LAST:
            bad.append(f"{p.name}: ends mid-phrase: {nf!r}")
            continue
        # must look like a sentence-ish claim (space + letter)
        if not re.search(r"[A-Za-z].+\s+[A-Za-z]", nf):
            bad.append(f"{p.name}: not sentence-like: {nf!r}")
    assert not bad, "truncated or missing next-falsifier:\n" + "\n".join(bad)


if __name__ == "__main__":
    test_all_next_falsifiers_complete()
    print("ok")
