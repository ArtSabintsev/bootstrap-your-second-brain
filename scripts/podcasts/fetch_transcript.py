#!/usr/bin/env python3
"""Fetch one YouTube episode's date, title, and cleaned transcript.

Usage: fetch_transcript.py <video_id_or_url> <out_transcript_path>

Single yt-dlp extraction: writes the English auto-caption file, prints the
episode's upload_date and title. Cleans the rolling-window VTT into deduped
plain text at out_transcript_path. Prints one line to stdout:

    <YYYYMMDD>\t<title>

Exit 2 if the video has no English captions.
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BRAIN / "scripts"))
from config import ytdlp_cookie_args  # noqa: E402

YTDLP = str(BRAIN / ".venv" / "bin" / "yt-dlp")

_TS = re.compile(r"-->")
_TAG = re.compile(r"<[^>]+>")
_INLINE_TS = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")


def clean_vtt(vtt: str) -> str:
    out: list[str] = []
    last = None
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:")):
            continue
        if _TS.search(line):
            continue
        line = html.unescape(_INLINE_TS.sub("", _TAG.sub("", line))).strip()
        if not line or line == last:
            continue
        if last and (last.endswith(line) or line in last):
            continue
        out.append(line)
        last = line
    return "\n".join(out)


def fetch(video: str, out_path: str) -> tuple[str, str] | None:
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            [
                YTDLP, *ytdlp_cookie_args(), "--ignore-no-formats-error",
                "--sleep-requests", "1.5", "--extractor-retries", "2",
                "--js-runtimes", "node", "--skip-download",
                "--write-auto-subs", "--sub-lang", "en", "--sub-format", "vtt",
                "--print", "%(upload_date)s\t%(title)s", "--no-simulate",
                "--paths", td, "-o", "%(id)s.%(ext)s", video,
            ],
            capture_output=True, text=True,
        )
        meta = proc.stdout.strip().splitlines()
        date_title = meta[0] if meta else "\t"
        vtts = list(Path(td).glob("*.vtt"))
        if not vtts:
            # distinguish an account rate-limit from a genuinely caption-less video
            if re.search(r"rate.?limit|try again later|too many request", proc.stderr, re.I):
                return "RATE_LIMITED"
            return None
        Path(out_path).write_text(clean_vtt(vtts[0].read_text()))
        date, _, title = date_title.partition("\t")
        return date, title


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    res = fetch(sys.argv[1], sys.argv[2])
    if res == "RATE_LIMITED":
        print("rate-limited", file=sys.stderr)
        sys.exit(42)
    if res is None:
        print("no captions available", file=sys.stderr)
        sys.exit(2)
    date, title = res
    print(f"{date}\t{title}")
