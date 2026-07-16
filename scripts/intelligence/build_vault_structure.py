#!/usr/bin/env python3
"""Write _indexes/vault-structure.md — cheap bootstrap counts for agents."""

from __future__ import annotations

from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
OUT = VAULT / "_indexes" / "vault-structure.md"


def count_md(folder: str) -> int:
    p = VAULT / folder
    if not p.is_dir():
        return 0
    return sum(1 for _ in p.rglob("*.md") if _.name != "README.md")


def main() -> int:
    log_days = len(list((VAULT / "Log").glob("????-??-??.md"))) if (VAULT / "Log").is_dir() else 0
    decisions = 0
    dec_path = VAULT / "_indexes" / "decisions.md"
    if dec_path.exists():
        for line in dec_path.read_text().splitlines():
            if line.startswith("| 20") and (
                "| decision |" in line or "| kill |" in line
            ):
                decisions += 1

    theses = sorted((VAULT / "Theses").glob("*.md")) if (VAULT / "Theses").is_dir() else []
    thesis_status: dict[str, int] = {}
    missing_falsifier = 0
    truncated_falsifier = 0
    for t in theses:
        text = t.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("\n---", 3)
            fm = text[3:end] if end > 0 else ""
        else:
            fm = ""
        st = "unknown"
        nf_val = ""
        for line in fm.splitlines():
            if line.startswith("status:"):
                st = line.split(":", 1)[1].strip()
            if line.startswith("next-falsifier:"):
                nf_val = line.split(":", 1)[1].strip().strip('"').strip("'")
        thesis_status[st] = thesis_status.get(st, 0) + 1
        if not nf_val:
            missing_falsifier += 1
        else:
            last = nf_val.rstrip().split()[-1].lower().strip(".,;:") if nf_val.split() else ""
            stub_last = {
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
            if len(nf_val) < 80 or last in stub_last:
                truncated_falsifier += 1

    lines = [
        "---",
        'title: "Vault structure snapshot"',
        "type: index",
        f"updated: {date.today().isoformat()}",
        "---",
        "",
        "# Vault structure snapshot",
        "",
        f"Generated **{date.today().isoformat()}** by "
        "`scripts/intelligence/build_vault_structure.py`.",
        "",
        "## Counts",
        "",
        f"| Surface | Count |",
        f"|---------|------:|",
        f"| People notes | {count_md('People')} |",
        f"| Topics notes | {count_md('Topics')} |",
        f"| Theses | {len(theses)} |",
        f"| Projects | {count_md('Projects')} |",
        f"| Library notes | {count_md('Library')} |",
        f"| Briefs | {count_md('Briefs')} |",
        f"| Log day files | {log_days} |",
        f"| Decision/kill index rows | {decisions} |",
        "",
        "## Theses by status",
        "",
    ]
    for st, n in sorted(thesis_status.items()):
        lines.append(f"- `{st}`: {n}")
    lines.extend(
        [
            "",
            f"Theses missing `next-falsifier` frontmatter: **{missing_falsifier}**.",
            f"Theses with truncated/stub `next-falsifier` (mid-sentence): "
            f"**{truncated_falsifier}**.",
            "",
            "## Load path (agents)",
            "",
            "1. `Profile/00-overview.md` + `Profile/working-with-me.md`",
            "2. `Theses/` for operator hypotheses; `_indexes/decisions.md` for choices",
            "3. Project/person notes as needed — hub first (`Projects/pocket-network.md`)",
            "4. Gap report: `_indexes/second-brain-gap-report.md`",
            "",
            "## Rebuild",
            "",
            "```bash",
            "python3 scripts/intelligence/build_decisions_index.py",
            "python3 scripts/intelligence/build_vault_structure.py",
            "python3 scripts/intelligence/lint.py",
            "```",
            "",
        ]
    )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
