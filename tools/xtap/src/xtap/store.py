"""Snapshot + report persistence."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import home, reports_dir, snapshots_dir


def load_profile() -> dict[str, Any] | None:
    try:
        return json.loads((home() / "profile.json").read_text())
    except (OSError, ValueError):
        return None


def save_profile(profile: dict[str, Any]) -> None:
    (home() / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")
    return path


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return path
    fields = fieldnames or list(rows[0].keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


TWEET_KINDS = ("tweets", "likes", "bookmarks", "media")
TWEET_FIELDS = [
    "id", "created_at", "author", "text", "likes", "retweets", "replies", "quotes",
    "views", "is_retweet", "is_reply", "is_quote", "media_count", "lang", "url",
]


def snapshot_tweets(kind: str, rows: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> Path:
    """Snapshot a tweet-shaped timeline (tweets / likes / bookmarks / media)."""
    if kind not in TWEET_KINDS:
        raise ValueError(f"Unknown snapshot kind: {kind}")
    stamp = _stamp()
    base = snapshots_dir() / f"{kind}-{stamp}"
    write_jsonl(Path(str(base) + ".jsonl"), rows)
    write_csv(Path(str(base) + ".csv"), rows, TWEET_FIELDS)
    write_json(
        Path(str(base) + ".meta.json"),
        {"kind": kind, "count": len(rows), "stamp": stamp, **(meta or {})},
    )
    clear_tombstones(kind)
    return Path(str(base) + ".jsonl")


def latest_snapshot(kind: str) -> Path | None:
    """Most recent .jsonl snapshot for a kind (tweets, likes, following, …)."""
    files = sorted(snapshots_dir().glob(f"{kind}-*.jsonl"))
    return files[-1] if files else None


def list_snapshots() -> list[dict[str, Any]]:
    """All snapshots, newest first: kind, stamp, count, path."""
    out = []
    for f in sorted(snapshots_dir().glob("*.jsonl"), reverse=True):
        kind, stamp = f.stem.split("-", 1) if "-" in f.stem else (f.stem, "")
        meta_path = Path(str(f)[: -len(".jsonl")] + ".meta.json")
        count = None
        if meta_path.exists():
            try:
                count = json.loads(meta_path.read_text()).get("count")
            except ValueError:
                pass
        if count is None:
            count = sum(1 for line in f.read_text().splitlines() if line.strip())
        out.append({"kind": kind, "stamp": stamp, "count": count, "path": str(f)})
    return out


def load_jsonl(path: Path, dedup: bool = False) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if dedup:
        seen: set[str] = set()
        out = []
        for r in rows:
            rid = str(r.get("id"))
            if rid in seen:
                continue
            seen.add(rid)
            out.append(r)
        return out
    return rows


# Snapshot files are immutable records; items removed via the dashboard are
# tracked as tombstones and filtered out at read time until the next sync.
def load_tombstones() -> dict[str, list[str]]:
    try:
        data = json.loads((home() / "tombstones.json").read_text())
        return {k: list(v) for k, v in data.items() if isinstance(v, list)}
    except (OSError, ValueError):
        return {}


def add_tombstone(kind: str, item_id: str) -> None:
    stones = load_tombstones()
    ids = stones.setdefault(kind, [])
    if str(item_id) not in ids:
        ids.append(str(item_id))
    (home() / "tombstones.json").write_text(json.dumps(stones, indent=2) + "\n")


def clear_tombstones(kind: str) -> None:
    """A fresh snapshot reflects reality — drop that kind's tombstones."""
    stones = load_tombstones()
    if stones.pop(kind, None) is not None:
        (home() / "tombstones.json").write_text(json.dumps(stones, indent=2) + "\n")


def snapshot_following(rows: list[dict[str, Any]], label: str | None = None) -> Path:
    stamp = label or _stamp()
    base = snapshots_dir() / f"following-{stamp}"
    write_jsonl(Path(str(base) + ".jsonl"), rows)
    write_csv(
        Path(str(base) + ".csv"),
        rows,
        ["username", "name", "followers", "following", "tweets", "description", "url", "id"],
    )
    write_json(Path(str(base) + ".meta.json"), {"count": len(rows), "stamp": stamp})
    clear_tombstones("following")
    return Path(str(base) + ".jsonl")


def save_follow_audit(recs: list[dict[str, Any]], meta: dict[str, Any]) -> tuple[Path, Path, Path]:
    stamp = _stamp()
    base = reports_dir() / f"follow-audit-{stamp}"
    j = write_json(Path(str(base) + ".json"), {**meta, "recs": recs})
    c = write_csv(
        Path(str(base) + ".csv"),
        recs,
        [
            "username",
            "name",
            "priority",
            "days_since_last",
            "posts_per_week",
            "posts_30d",
            "quality_score",
            "dead_90d",
            "infrequent",
            "low_quality",
            "reasons",
            "url",
            "followers",
            "id",
        ],
    )
    # flatten reasons for csv
    flat = []
    for r in recs:
        row = dict(r)
        if isinstance(row.get("reasons"), list):
            row["reasons"] = " | ".join(row["reasons"])
        flat.append(row)
    c = write_csv(Path(str(base) + ".csv"), flat, [
        "username", "name", "priority", "days_since_last", "posts_per_week", "posts_30d",
        "quality_score", "dead_90d", "infrequent", "low_quality", "reasons", "url", "followers", "id",
    ])
    md_lines = [
        f"# Follow audit {stamp}",
        "",
        f"Following: **{meta.get('total_following')}** · Recommend: **{meta.get('recommend')}**",
        "",
        f"- Dead ≥{meta.get('dead_days')}d: {meta.get('dead_90d')}",
        f"- Infrequent <{meta.get('max_ppw')}/wk: {meta.get('infrequent')}",
        f"- Low quality: {meta.get('low_quality')}",
        "",
        "| Handle | Days | ppw | q | Why |",
        "|--------|-----:|----:|--:|-----|",
    ]
    for r in recs:
        why = " | ".join(r.get("reasons") or [])[:100].replace("|", "/")
        md_lines.append(
            f"| [@{r.get('username')}](https://x.com/{r.get('username')}) | "
            f"{r.get('days_since_last') if r.get('days_since_last') is not None else '—'} | "
            f"{r.get('posts_per_week')} | {r.get('quality_score')} | {why} |"
        )
    md = Path(str(base) + ".md")
    md.write_text("\n".join(md_lines) + "\n")
    return j, c, md


def save_tweet_audit(recs: list[dict[str, Any]], meta: dict[str, Any]) -> tuple[Path, Path]:
    stamp = _stamp()
    base = reports_dir() / f"tweet-audit-{stamp}"
    j = write_json(Path(str(base) + ".json"), {**meta, "recs": recs})
    flat = []
    for r in recs:
        row = dict(r)
        if isinstance(row.get("reasons"), list):
            row["reasons"] = " | ".join(row["reasons"])
        flat.append(row)
    c = write_csv(
        Path(str(base) + ".csv"),
        flat,
        ["id", "age_days", "is_retweet", "is_reply", "likes", "text", "reasons", "url", "priority"],
    )
    return j, c


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())
