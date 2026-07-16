#!/usr/bin/env python3
"""Smoke test: rebuild decisions index from Log and assert real entries."""
from __future__ import annotations

import re
import subprocess

import pytest
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[3]
SCRIPT = VAULT / "scripts" / "intelligence" / "build_decisions_index.py"
OUT = VAULT / "_indexes" / "decisions.md"


def test_rebuild_contains_log_decisions():
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(VAULT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "wrote" in r.stdout
    text = OUT.read_text(encoding="utf-8")
    assert "Decisions index" in text
    # no parallel Decisions/ tree; Log/ is the journal
    assert not (VAULT / "Decisions").exists()
    assert not (VAULT / "Hypotheses").exists()
    # decision rows only exist once the operator has logged decisions
    logs = [f for f in (VAULT / "Log").glob("*.md") if f.name != "README.md"]
    if not logs:
        pytest.skip("fresh vault: no Log entries yet")
    rows = [
        line
        for line in text.splitlines()
        if line.startswith("| 20") and "| decision |" in line
    ]
    assert rows, f"expected decision rows from Log, got:\n{text}"


if __name__ == "__main__":
    test_rebuild_contains_log_decisions()
    print("ok")
