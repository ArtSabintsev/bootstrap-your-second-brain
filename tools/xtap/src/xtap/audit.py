"""Scoring: dead / infrequent / low-quality follows; own tweet cleanup candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .client import TweetRow, UserRow

SPAM = re.compile(
    r"(?i)(giveaway|airdrop|claim your|dm for promo|follow me and|like and rt|"
    r"100x gem|to the moon|join my telegram|free nft|crypto signal|vip signal|"
    r"click here)"
)
BAIT = re.compile(
    r"(?i)(^\s*(this|wow|lol|lmao|based|true|facts|so true|exactly|huge)\s*[.!?]*\s*$|"
    r"ratioed|unpopular opinion:|hot take:|agree\?|rt if you)"
)
EMPTY = re.compile(r"(?i)^(gm|gn|wagmi|ngmi|lfg|🔥+|🚀+|👍+|❤️+|💯+)+\s*$")


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@dataclass
class FollowScore:
    user: UserRow
    posts_30d: int
    posts_per_week: float
    quality_score: float
    days_since_last: int | None
    last_post: str | None
    quality_reasons: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    truncated: bool = False

    # flags
    dead_90d: bool = False
    infrequent: bool = False  # < max_ppw
    zero_30d: bool = False
    low_quality: bool = False
    recommend: bool = False
    priority: int = 0
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.user.as_dict(),
            "posts_30d": self.posts_30d,
            "posts_per_week": self.posts_per_week,
            "quality_score": self.quality_score,
            "days_since_last": self.days_since_last,
            "last_post": self.last_post,
            "quality_reasons": self.quality_reasons,
            "samples": self.samples,
            "truncated": self.truncated,
            "dead_90d": self.dead_90d,
            "infrequent": self.infrequent,
            "zero_30d": self.zero_30d,
            "low_quality": self.low_quality,
            "recommend": self.recommend,
            "priority": self.priority,
            "reasons": self.reasons,
        }


def score_tweets_quality(tweets: list[TweetRow]) -> tuple[float, list[str], list[str]]:
    if not tweets:
        return 0.0, ["no posts in window"], []
    n = len(tweets)
    rts = sum(1 for t in tweets if t.is_retweet)
    replies = sum(1 for t in tweets if t.is_reply and not t.is_retweet)
    spam_hits = bait_hits = empty_hits = 0
    total_likes = 0
    samples: list[str] = []
    for t in tweets:
        samples.append(t.text[:120])
        if SPAM.search(t.text):
            spam_hits += 1
        if BAIT.search(t.text) or EMPTY.search(t.text.strip()):
            bait_hits += 1
        if len(t.text.strip()) < 8 and not t.is_retweet:
            empty_hits += 1
        total_likes += t.likes
    avg = total_likes / n
    rt_ratio = rts / n
    reply_ratio = replies / n
    score = 70.0
    reasons: list[str] = []
    if rt_ratio >= 0.85:
        score -= 35
        reasons.append(f"almost only RTs ({rt_ratio:.0%})")
    elif rt_ratio >= 0.65:
        score -= 18
        reasons.append(f"heavy RT feed ({rt_ratio:.0%})")
    if reply_ratio >= 0.8:
        score -= 25
        reasons.append(f"almost only replies ({reply_ratio:.0%})")
    elif reply_ratio >= 0.6:
        score -= 12
        reasons.append(f"mostly replies ({reply_ratio:.0%})")
    if spam_hits / n >= 0.15:
        score -= 40
        reasons.append(f"spam/giveaway ({spam_hits}/{n})")
    elif spam_hits:
        score -= 15
        reasons.append(f"some spam ({spam_hits}/{n})")
    if bait_hits / n >= 0.4:
        score -= 25
        reasons.append(f"bait/empty ({bait_hits}/{n})")
    elif bait_hits / n >= 0.2:
        score -= 12
        reasons.append(f"low-effort ({bait_hits}/{n})")
    if empty_hits / n >= 0.3:
        score -= 15
        reasons.append(f"near-empty ({empty_hits}/{n})")
    if n >= 15 and avg < 3:
        score -= 12
        reasons.append(f"weak engagement (~{avg:.1f} likes)")
    if not reasons:
        reasons.append("ok-ish mix")
    return max(0.0, min(100.0, score)), reasons, samples[:3]


def score_follow(
    user: UserRow,
    tweets: list[TweetRow],
    *,
    window_days: int = 30,
    max_ppw: float = 5.0,
    dead_days: int = 90,
    quality_cutoff: float = 45.0,
    tweet_limit: int = 20,
) -> FollowScore:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    in_window: list[TweetRow] = []
    last_dt: datetime | None = None
    for t in tweets:
        dt = _parse_iso(t.created_at)
        if dt and (last_dt is None or dt > last_dt):
            last_dt = dt
        if dt and dt >= cutoff:
            in_window.append(t)

    n30 = len(in_window)
    truncated = len(tweets) >= tweet_limit and n30 == len(tweets) and len(tweets) > 0
    ppw = n30 / (window_days / 7.0)
    if truncated:
        ppw = max(ppw, tweet_limit / (window_days / 7.0))

    qscore, qreasons, samples = score_tweets_quality(in_window)
    days = (now - last_dt).days if last_dt else None

    fs = FollowScore(
        user=user,
        posts_30d=n30,
        posts_per_week=round(ppw, 2),
        quality_score=round(qscore, 1),
        days_since_last=days,
        last_post=last_dt.isoformat() if last_dt else None,
        quality_reasons=qreasons,
        samples=samples,
        truncated=truncated,
    )

    reasons: list[str] = []
    priority = 0
    if days is not None and days >= dead_days:
        fs.dead_90d = True
        reasons.append(f"DEAD: last post ~{days}d ago (≥{dead_days}d)")
        priority += 5
    if n30 == 0:
        fs.zero_30d = True
        fs.infrequent = True
        if not fs.dead_90d:
            reasons.append(
                f"INACTIVE: 0 posts in last {window_days}d"
                + (f"; last ~{days}d ago" if days is not None else "")
            )
            priority += 4
    elif ppw < max_ppw:
        fs.infrequent = True
        reasons.append(
            f"INFREQUENT: {ppw:.1f}/wk over {window_days}d (threshold ≥{max_ppw}/wk)"
        )
        priority += 3 if ppw < 1 else (2 if ppw < 2 else 1)

    if qscore < quality_cutoff and n30 >= 3:
        fs.low_quality = True
        reasons.append(f"LOW QUALITY ({qscore:.0f}/100): " + "; ".join(qreasons[:3]))
        priority += 3 if qscore < 30 else 2

    fs.recommend = fs.dead_90d or fs.infrequent or fs.low_quality
    fs.priority = priority
    fs.reasons = reasons
    return fs


@dataclass
class TweetCleanup:
    tweet: TweetRow
    age_days: int
    reasons: list[str]
    priority: int

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.tweet.as_dict(),
            "age_days": self.age_days,
            "reasons": self.reasons,
            "priority": self.priority,
        }


def score_own_tweets_for_cleanup(
    tweets: list[TweetRow],
    *,
    min_age_days: int = 90,
    only_rts: bool = False,
    only_replies: bool = False,
    low_engagement_max_likes: int | None = 2,
) -> list[TweetCleanup]:
    """Flag own posts/RTs for deletion review."""
    now = datetime.now(timezone.utc)
    out: list[TweetCleanup] = []
    for t in tweets:
        dt = _parse_iso(t.created_at)
        if not dt:
            continue
        age = (now - dt).days
        if age < min_age_days:
            continue
        reasons: list[str] = []
        priority = 0
        if only_rts and not t.is_retweet:
            continue
        if only_replies and not t.is_reply:
            continue
        if t.is_retweet:
            reasons.append("retweet")
            priority += 2
        if t.is_reply:
            reasons.append("reply")
            priority += 1
        if low_engagement_max_likes is not None and t.likes <= low_engagement_max_likes:
            reasons.append(f"low engagement ({t.likes} likes)")
            priority += 1
        if SPAM.search(t.text):
            reasons.append("spam-like text")
            priority += 3
        if not reasons:
            reasons.append(f"older than {min_age_days}d")
            priority += 1
        out.append(TweetCleanup(tweet=t, age_days=age, reasons=reasons, priority=priority))
    out.sort(key=lambda x: (-x.priority, -x.age_days))
    return out
