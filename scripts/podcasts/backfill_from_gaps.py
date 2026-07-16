#!/usr/bin/env python3
"""Drive synth_episode.sh only for missing ids in ukraine-backfill-gaps.json.

Safer/faster than re-enumerating whole channels when the gap map already exists.

Usage:
  python3 scripts/podcasts/backfill_from_gaps.py              # all shows with gaps
  python3 scripts/podcasts/backfill_from_gaps.py show-key-a show-key-b
  JOBS=3 python3 scripts/podcasts/backfill_from_gaps.py show-key-a

Env:
  JOBS          parallel synth workers (default 1; 2–3 is usually safe on YT)
  DRY_RUN=1     print queue only
  COOLDOWN      seconds to pause launches after YouTube rate-limit (default 2700)
  LAUNCH_GAP    seconds between starting workers (default 1)

Exit: 0 if every synth exits 0 or 5 (skip exists); 1 if any hard failure.
Exit 8 (RATE_LIMITED) is retried once after cooldown, then counted as fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
GAPS = BRAIN / ".status" / "ukraine-backfill-gaps.json"
SYNTH = HERE / "synth_episode.sh"
LOG = BRAIN / ".status" / "podcasts.log"
JOBS = max(1, int(os.environ.get("JOBS", "1")))
DRY = os.environ.get("DRY_RUN", "") in ("1", "true", "yes")
COOLDOWN = int(os.environ.get("COOLDOWN", "2700"))  # 45 min, matches backfill.sh
LAUNCH_GAP = float(os.environ.get("LAUNCH_GAP", "1"))
# synth_episode.sh: 0 ok, 5 skip (exists / world-context), 8 rate-limited
OK_CODES = {0, 5}
RATE_LIMITED = 8


def main() -> int:
    if not GAPS.exists():
        print("no gaps file; run enumerate_depth_gaps.py first", file=sys.stderr)
        return 1
    doc = json.loads(GAPS.read_text())
    want = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    work: list[tuple[str, str, str, str]] = []
    for show, g in doc.get("shows", {}).items():
        if want is not None and show not in want:
            continue
        for m in g.get("missing") or []:
            work.append((show, m["id"], m["date"], m.get("title") or "episode"))

    work.sort(key=lambda x: (x[0], x[2]))  # show, date
    print(f"queue={len(work)} jobs={JOBS} dry_run={DRY} launch_gap={LAUNCH_GAP}", flush=True)
    if DRY:
        for row in work[:20]:
            print(" ", row)
        if len(work) > 20:
            print(f"  … +{len(work)-20} more")
        return 0
    if not work:
        print("nothing to do", flush=True)
        return 0

    LOG.parent.mkdir(parents=True, exist_ok=True)
    logf = LOG.open("a", encoding="utf-8")
    # (proc, label, item, attempt)
    running: list[tuple[subprocess.Popen, str, tuple[str, str, str, str], int]] = []
    queue = list(work)
    launched = 0
    failures: list[str] = []
    retried: set[str] = set()

    def start_one(item: tuple[str, str, str, str], attempt: int) -> None:
        nonlocal launched
        show, vid, date, title = item
        cmd = ["bash", str(SYNTH), show, vid, date, title]
        label = f"{show} {date} {vid}"
        print(f"synth {label} {title[:50]} (try {attempt})", flush=True)
        p = subprocess.Popen(
            cmd,
            cwd=str(BRAIN),
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
        running.append((p, label, item, attempt))
        launched += 1
        if launched % 5 == 0:
            print(f"  launched {launched} (in flight {len(running)} queue {len(queue)})", flush=True)

    def reap_finished() -> None:
        nonlocal running
        still: list[tuple[subprocess.Popen, str, tuple[str, str, str, str], int]] = []
        for p, label, item, attempt in running:
            rc = p.poll()
            if rc is None:
                still.append((p, label, item, attempt))
                continue
            if rc in OK_CODES:
                print(f"ok {label} exit={rc}", flush=True)
                continue
            if rc == RATE_LIMITED and item[1] not in retried:
                retried.add(item[1])
                print(
                    f"RATE_LIMITED {label}; cooldown {COOLDOWN}s then retry once",
                    flush=True,
                )
                time.sleep(COOLDOWN)
                # put back at front of queue for one retry
                queue.insert(0, item)
                continue
            failures.append(f"{label} exit={rc}")
            print(f"FAIL {label} exit={rc}", flush=True)
        running = still

    try:
        while queue or running:
            reap_finished()
            while queue and len(running) < JOBS:
                item = queue.pop(0)
                start_one(item, 1 if item[1] not in retried else 2)
                if queue and len(running) < JOBS:
                    time.sleep(LAUNCH_GAP)
            if running and (not queue or len(running) >= JOBS):
                time.sleep(1)
    finally:
        logf.flush()
        logf.close()

    print(
        f"done launched={launched} failures={len(failures)}; "
        "re-run enumerate_depth_gaps to refresh gaps",
        flush=True,
    )
    for f in failures[:20]:
        print(f" - {f}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
