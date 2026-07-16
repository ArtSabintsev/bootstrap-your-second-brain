#!/usr/bin/env python3
"""Enumerate missing long-form depth-show episodes for the vault cutoff.

Writes .status/ukraine-backfill-gaps.json.

Rules:
  - Index video ids already on disk (source URLs).
  - Flat-list channel (~newest-first).
  - Meta only uncovered ids; require duration >= MIN_DURATION_S (default 20 min)
    so clips/shorts are not treated as podcast gaps.
  - Missing = date >= cutoff, duration ok, no note.
  - Early-stop after STOP_AFTER_OLD consecutive pre-cutoff long-form (or failed) metas
    once we have walked past the modern covered region.

Usage:
  python3 scripts/podcasts/enumerate_depth_gaps.py [show_key ...]
  MIN_DURATION_S=1200 python3 ...   # default 20 minutes
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent.parent
sys.path.insert(0, str(BRAIN / "scripts"))
from config import get as cfg_get, ytdlp_cookie_args  # noqa: E402

YTDLP = str(BRAIN / ".venv" / "bin" / "yt-dlp")
SHOWS = HERE / "shows.json"
POD = BRAIN / "Library" / "podcasts"
GAPS = BRAIN / ".status" / "ukraine-backfill-gaps.json"
STOP_AFTER_OLD = 8
MIN_DURATION_S = int(os.environ.get("MIN_DURATION_S", "1200"))


def cookies() -> list[str]:
    return [*ytdlp_cookie_args(), "--ignore-no-formats-error", "--sleep-requests", "0.4"]


def flat_ids(url: str) -> list[str]:
    out = subprocess.run(
        [YTDLP, *cookies(), "--flat-playlist", "--print", "%(id)s", url],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return [x for x in out.stdout.splitlines() if x.strip()]


def meta(vid: str) -> tuple[str, str, str, int] | None:
    """Return (id, upload_date YYYYMMDD, title, duration_seconds) or None."""
    out = subprocess.run(
        [
            YTDLP,
            *cookies(),
            "--skip-download",
            "--no-write-subs",
            "--print",
            "%(upload_date)s\t%(duration)s\t%(title)s",
            vid,
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    line = out.stdout.strip().splitlines()
    if not line:
        return None
    parts = line[0].split("\t", 2)
    if len(parts) < 3:
        return None
    date, dur_s, title = parts[0], parts[1], parts[2]
    if not date or date == "NA":
        return None
    try:
        duration = int(float(dur_s)) if dur_s and dur_s != "NA" else 0
    except ValueError:
        duration = 0
    return vid, date, title, duration


def existing_vid_index(show: str) -> set[str]:
    d = POD / show
    if not d.is_dir():
        return set()
    found: set[str] = set()
    for p in d.glob("*.md"):
        if p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")[:5000]
        for m in re.finditer(
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})", text
        ):
            found.add(m.group(1))
        m2 = re.search(r"(?m)^video_id:\s*[\"']?([A-Za-z0-9_-]+)", text)
        if m2:
            found.add(m2.group(1))
    return found


def main() -> int:
    args = sys.argv[1:]
    cutoff = str(cfg_get("podcasts.cutoff") or "20220224")
    if args and re.fullmatch(r"\d{8}", args[0]):
        cutoff = args[0]
        args = args[1:]
    shows = json.loads(SHOWS.read_text())
    keys = args or [k for k, v in shows.items() if v.get("role") != "world-context"]

    doc: dict = {
        "cutoff": cutoff,
        "updated": datetime.now(timezone.utc).isoformat(),
        "min_duration_s": MIN_DURATION_S,
        "shows": {},
        "method": "longform_newest_first_early_stop",
    }
    if GAPS.exists():
        try:
            prev = json.loads(GAPS.read_text())
            if prev.get("cutoff") == cutoff and prev.get("min_duration_s") == MIN_DURATION_S:
                doc["shows"] = prev.get("shows") or {}
        except Exception:
            pass

    for key in keys:
        cfg = shows[key]
        if cfg.get("role") == "world-context" or cfg.get("source") == "rss":
            print(f"skip {key}", flush=True)
            continue
        print(f"=== {key} (cutoff {cutoff}, min_dur {MIN_DURATION_S}s)", flush=True)
        have = existing_vid_index(key)
        notes = list((POD / key).glob("????-??-??-*.md")) if (POD / key).is_dir() else []
        print(f"  notes={len(notes)} covered_ids={len(have)}", flush=True)
        ids = flat_ids(cfg["url"])
        print(f"  flat={len(ids)}", flush=True)

        missing: list[dict] = []
        skipped_short = 0
        checked = 0
        consecutive_old_long = 0
        for vid in ids:
            if vid in have:
                consecutive_old_long = 0
                continue
            r = meta(vid)
            checked += 1
            if not r:
                consecutive_old_long += 1
                if consecutive_old_long >= STOP_AFTER_OLD:
                    print(f"  early-stop after {checked} meta (fail streak)", flush=True)
                    break
                continue
            _vid, ymd, title, duration = r
            if duration and duration < MIN_DURATION_S:
                skipped_short += 1
                # shorts don't advance "past history" signal much; don't early-stop on them
                if checked % 25 == 0:
                    print(
                        f"  …checked {checked}, missing {len(missing)}, "
                        f"short_skips {skipped_short}",
                        flush=True,
                    )
                continue
            if ymd >= cutoff:
                missing.append(
                    {
                        "id": vid,
                        "date": ymd,
                        "title": title[:120],
                        "duration_s": duration,
                    }
                )
                consecutive_old_long = 0
                if len(missing) % 5 == 0:
                    print(
                        f"  …checked {checked}, missing {len(missing)}, "
                        f"short_skips {skipped_short}",
                        flush=True,
                    )
            else:
                consecutive_old_long += 1
                if consecutive_old_long >= STOP_AFTER_OLD:
                    print(
                        f"  early-stop past cutoff after {checked} meta "
                        f"(hit long-form {ymd} < {cutoff})",
                        flush=True,
                    )
                    break

        missing.sort(key=lambda m: m["date"])
        entry = {
            "flat_playlist": len(ids),
            "notes_on_disk": len(notes),
            "covered_ids": len(have),
            "meta_checked": checked,
            "skipped_short": skipped_short,
            "missing_ids": [m["id"] for m in missing],
            "missing": missing,
            "status": "ok" if not missing else "gaps",
        }
        doc["shows"][key] = entry
        doc["updated"] = datetime.now(timezone.utc).isoformat()
        print(
            f"  missing_longform_in_range={len(missing)} short_skips={skipped_short}",
            flush=True,
        )
        GAPS.parent.mkdir(parents=True, exist_ok=True)
        GAPS.write_text(json.dumps(doc, indent=2) + "\n")

    total = sum(len(s.get("missing_ids") or []) for s in doc["shows"].values())
    print(f"wrote {GAPS.relative_to(BRAIN)}; TOTAL missing long-form={total}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
