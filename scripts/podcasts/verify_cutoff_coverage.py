#!/usr/bin/env python3
"""Referee for Ukraine-era (or any) podcast cutoff coverage.

Exit 0 only if:
  1. config podcasts.cutoff is set and parses as YYYYMMDD
  2. every world-context RSS show has monthly digests covering from
     max(cutoff_month, first_feed_month) through the latest feed month
  3. unless --depth-gaps-ok: every depth show has gaps.json entry with missing==0
     (run with --write-gaps to refresh .status/ukraine-backfill-gaps.json first)

Usage:
  python3 scripts/podcasts/verify_cutoff_coverage.py
  python3 scripts/podcasts/verify_cutoff_coverage.py --write-gaps
  python3 scripts/podcasts/verify_cutoff_coverage.py --depth-gaps-ok   # config+WSJ only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

BRAIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BRAIN / "scripts"))
from config import get as cfg_get  # noqa: E402

SHOWS = BRAIN / "scripts" / "podcasts" / "shows.json"
GAPS = BRAIN / ".status" / "ukraine-backfill-gaps.json"
POD = BRAIN / "Library" / "podcasts"


def ymd_to_month(ymd: str) -> str:
    return f"{ymd[0:4]}-{ymd[4:6]}"


def months_between(start: str, end: str) -> list[str]:
    """Inclusive YYYY-MM range."""
    y, m = int(start[:4]), int(start[5:7])
    ye, me = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) <= (ye, me):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def rss_month_span(url: str, cutoff: str) -> tuple[str, str, int]:
    with urllib.request.urlopen(url, timeout=90) as r:
        root = ET.fromstring(r.read())
    months: set[str] = set()
    n = 0
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
        n += 1
        months.add(d.strftime("%Y-%m"))
    if not months:
        return "", "", 0
    return min(months), max(months), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-gaps", action="store_true")
    ap.add_argument(
        "--depth-gaps-ok",
        action="store_true",
        help="Do not fail on missing depth-show gap map (milestone A/B)",
    )
    args = ap.parse_args()

    cutoff = str(cfg_get("podcasts.cutoff") or "")
    errors: list[str] = []
    if not re.fullmatch(r"\d{8}", cutoff):
        errors.append(f"config podcasts.cutoff invalid: {cutoff!r}")
        print("FAIL:", errors)
        return 1

    shows = json.loads(SHOWS.read_text())
    print(f"cutoff={cutoff} ({ymd_to_month(cutoff)}+)")

    # World-context months
    for key, show in shows.items():
        if show.get("role") != "world-context":
            continue
        if show.get("source") != "rss":
            errors.append(f"{key}: world-context must be source=rss")
            continue
        first, last, n = rss_month_span(show["url"], cutoff)
        print(f"  {key}: feed months {first}..{last} ({n} eps in range)")
        if not first:
            errors.append(f"{key}: no feed items on/after cutoff")
            continue
        need = months_between(first, last)
        have = {
            p.stem
            for p in (POD / key).glob("????-??.md")
            if re.fullmatch(r"\d{4}-\d{2}", p.stem)
        }
        missing = [m for m in need if m not in have]
        if missing:
            errors.append(f"{key}: missing month digests: {missing[:8]}{'…' if len(missing)>8 else ''}")
        else:
            print(f"  {key}: OK {len(need)} month digests on disk")

    # Depth gaps (optional hard fail)
    depth = {k: v for k, v in shows.items() if v.get("role") != "world-context"}
    if args.write_gaps:
        # Full YT enumerate — slow; prefer: python3 scripts/podcasts/enumerate_depth_gaps.py
        enum = BRAIN / "scripts" / "podcasts" / "enumerate_depth_gaps.py"
        import subprocess

        print("running enumerate_depth_gaps.py (YouTube metadata; can take a while)...")
        r = subprocess.run([sys.executable, str(enum)], cwd=str(BRAIN))
        if r.returncode != 0:
            errors.append("enumerate_depth_gaps.py failed")

    if not args.depth_gaps_ok:
        if not GAPS.exists():
            errors.append(
                "gaps file missing — run enumerate_depth_gaps.py "
                "or verify --depth-gaps-ok for early milestones"
            )
        else:
            gap_doc = json.loads(GAPS.read_text())
            gap_shows = gap_doc.get("shows") or {}
            for key in depth:
                if key not in gap_shows:
                    errors.append(f"{key}: not in gaps file (run enumerate_depth_gaps.py)")
                    continue
                g = gap_shows[key]
                missing = g.get("missing_ids")
                if g.get("status") == "map_pending" and not missing:
                    errors.append(
                        f"{key}: depth gap map still pending (run enumerate_depth_gaps)"
                    )
                elif missing:
                    errors.append(f"{key}: {len(missing)} missing in-range episodes")
                elif g.get("status") not in (None, "ok", "gaps"):
                    # gaps + empty missing_ids is ok after clear
                    pass

    if errors:
        print("FAIL:")
        for e in errors:
            print(" -", e)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
