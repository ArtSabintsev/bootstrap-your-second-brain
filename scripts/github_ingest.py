#!/usr/bin/env python3
"""Ingest the operator's recent GitHub commits into Sources/github/.

Lists their repos, finds those pushed within the lookback window, pulls their own
commits since then via the gh CLI, dedupes by SHA against prior captures, and
appends new commits (grouped by repo) to a dated capture file. The daily Claude
pass folds this into the relevant Projects/ notes, so the vault tracks what they
are actually building.

Usage: github_ingest.py [--days N]   (default 3)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = VAULT / "Sources" / "github"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get as cfg  # noqa: E402

LOGIN = cfg("identity.github_login", "")
# git commits aren't linked to the GitHub login (author.login is null), so
# filter locally by the commit author's email/name instead of the API author=.
EMAILS = set(cfg("identity.git_emails", []))
NAME = cfg("identity.name", "")


def gh_json(args: list[str]):
    out = subprocess.run(["gh", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip())
    return json.loads(out.stdout) if out.stdout.strip() else []


def known_shas() -> set[str]:
    shas: set[str] = set()
    for md in CAPTURE_DIR.glob("*.md"):
        shas.update(re.findall(r"\b([0-9a-f]{7})\b", md.read_text()))
    return shas


def main() -> int:
    days = 3
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    seen = known_shas()

    repos = gh_json([
        "repo", "list", "--limit", "300",
        "--json", "nameWithOwner,pushedAt,isPrivate",
    ])
    active = [r for r in repos if r.get("pushedAt", "") >= since]

    blocks = []
    total = 0
    for r in sorted(active, key=lambda r: r["pushedAt"], reverse=True):
        repo = r["nameWithOwner"]
        try:
            commits = gh_json([
                "api", f"repos/{repo}/commits?since={since}&per_page=100",
            ])
        except RuntimeError:
            continue
        rows = []
        for c in commits:
            author = c["commit"]["author"]
            if author.get("email") not in EMAILS and author.get("name") != NAME:
                continue
            sha = c["sha"][:7]
            if sha in seen:
                continue
            msg = (c["commit"]["message"].splitlines() or [""])[0].strip()
            when = author["date"][:10]
            rows.append(f"- `{sha}` {when} {msg}")
            seen.add(sha)
        if rows:
            vis = "private" if r.get("isPrivate") else "public"
            blocks.append(f"\n## {repo} ({vis})\n" + "\n".join(rows) + "\n")
            total += len(rows)

    if not total:
        print(f"github: no new commits in the last {days} day(s)")
        return 0

    today = date.today().isoformat()
    out = CAPTURE_DIR / f"github-{today}.md"
    header = (
        f"# GitHub commits captured {today}\n\n"
        f"Automated capture via scripts/github_ingest.py (gh CLI, author {LOGIN}, "
        f"last {days} days). Immutable raw source; the daily pass folds these into Projects/.\n"
        if not out.exists() else ""
    )
    with out.open("a") as f:
        f.write(header + "".join(blocks))
    print(f"github: appended {total} commit(s) across {len(blocks)} repo(s) to {out.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
