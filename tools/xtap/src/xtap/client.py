"""Read path via twscrape; write path via X web API + cookies."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from .auth import ensure_twscrape_account, load_cookies, parse_cookie_dict
from .paths import accounts_db, home

# Public web bearer used by x.com (not a secret)
WEB_BEARER = (
    "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

GQL = "https://x.com/i/api/graphql"

# GraphQL query IDs rotate. These are last-known-good defaults; when one goes
# stale the client re-discovers current IDs from x.com's public JS bundle and
# caches them in $XTAP_HOME/gql-ops.json.
DEFAULT_OPS = {
    "Likes": "tl9f_I0xyREhFd5KMzuO7w/Likes",
    "DeleteTweet": "nxpZCY2K-I6QoFHAHeojFQ/DeleteTweet",
    "DeleteRetweet": "ZyZigVsNiFO6v1dEks1eWg/DeleteRetweet",
    "UnfavoriteTweet": "ZYKSe-w7KEslx3JhSIk5LA/UnfavoriteTweet",
    "DeleteBookmark": "Wlmlj2-xzyS1GN3a6cj-mQ/DeleteBookmark",
}

_BUNDLE_RE = r"https://abs\.twimg\.com/responsive-web/client-web(?:-legacy)?/main\.[\w.]+\.js"
_QUERY_ID_RE = r'queryId:"([^"]{10,40})"\s*,\s*operationName:"(\w+)"'
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _ops_cache_file():
    return home() / "gql-ops.json"


async def discover_ops() -> dict[str, str]:
    """Scrape current GraphQL query IDs from x.com's public JS bundle."""
    import re

    import httpx

    async with httpx.AsyncClient(
        headers={"user-agent": _UA}, follow_redirects=True, timeout=30.0
    ) as c:
        html = (await c.get("https://x.com/")).text
        found: dict[str, str] = {}
        for url in dict.fromkeys(re.findall(_BUNDLE_RE, html)):
            js = (await c.get(url)).text
            for qid, name in re.findall(_QUERY_ID_RE, js):
                if name in DEFAULT_OPS:
                    found[name] = f"{qid}/{name}"
        return found


async def fresh_ops(max_age_hours: float = 24.0) -> dict[str, str]:
    """Current query IDs: file cache if recent, else re-discover, else defaults.

    Discovery is proactive because a stale ID does not fail fast — twscrape
    treats the 404 as a bad account and parks the session for 15 minutes.
    """
    ops = dict(DEFAULT_OPS)
    cache = _ops_cache_file()
    try:
        data = json.loads(cache.read_text())
        fetched = datetime.fromisoformat(data.get("fetched", ""))
        cached_ops = {
            k: v for k, v in data.get("ops", {}).items()
            if k in DEFAULT_OPS and isinstance(v, str) and "/" in v
        }
        age_h = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        if cached_ops and age_h < max_age_hours:
            ops.update(cached_ops)
            return ops
    except (OSError, ValueError):
        pass
    try:
        found = await discover_ops()
    except Exception:
        found = {}
    if found:
        ops.update(found)
        cache.write_text(json.dumps(
            {"fetched": datetime.now(timezone.utc).isoformat(), "ops": found},
            indent=2,
        ) + "\n")
    return ops


@dataclass
class UserRow:
    id: str
    username: str
    name: str
    followers: int
    following: int
    tweets: int
    description: str
    created: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "followers": self.followers,
            "following": self.following,
            "tweets": self.tweets,
            "description": self.description,
            "created": self.created,
            "url": f"https://x.com/{self.username}",
        }


@dataclass
class TweetRow:
    id: str
    created_at: str
    text: str
    likes: int
    retweets: int
    replies: int
    is_retweet: bool
    is_reply: bool
    lang: str | None = None
    author: str | None = None
    is_quote: bool = False
    quotes: int = 0
    views: int = 0
    media_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "text": self.text,
            "author": self.author,
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "quotes": self.quotes,
            "views": self.views,
            "is_retweet": self.is_retweet,
            "is_reply": self.is_reply,
            "is_quote": self.is_quote,
            "media_count": self.media_count,
            "lang": self.lang,
            "url": f"https://x.com/i/web/status/{self.id}",
        }


class XClient:
    """Async client: reads via twscrape, writes via cookie-authenticated HTTP."""

    def __init__(self, account: str = "primary"):
        self.account = account
        self._api = None
        self._http = None
        self._me: UserRow | None = None

    async def __aenter__(self) -> "XClient":
        await self.open()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def open(self) -> None:
        from twscrape import API

        await ensure_twscrape_account(self.account)
        self._api = API(str(accounts_db()))
        import httpx  # cookie-authenticated client for write actions

        cookies = parse_cookie_dict(load_cookies())
        self._http = httpx.AsyncClient(
            headers={
                "authorization": WEB_BEARER,
                "x-csrf-token": cookies["ct0"],
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-active-user": "yes",
                "x-twitter-client-language": "en",
                "user-agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ),
                "content-type": "application/x-www-form-urlencoded",
                "referer": "https://x.com/",
                "origin": "https://x.com",
            },
            cookies={
                "auth_token": cookies["auth_token"],
                "ct0": cookies["ct0"],
            },
            timeout=60.0,
            follow_redirects=True,
        )

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def api(self):
        if self._api is None:
            raise RuntimeError("Client not open")
        return self._api

    async def me(self) -> UserRow:
        if self._me:
            return self._me
        from .auth import user_id_from_cookies

        uid = user_id_from_cookies()
        if not uid:
            # last resort: re-pull twid from browser cookies via env
            raise RuntimeError(
                "No twid cookie — re-run: xtap auth browser --browser brave"
            )
        # Resolve profile via GraphQL UserByScreenName after username from tweets/following
        # Prefer UserByRestId through twscrape internals
        from twscrape.api import OP_UserByRestId
        from twscrape.models import parse_user
        from twscrape.queue_client import QueueClient
        from twscrape.utils import encode_params

        op = OP_UserByRestId
        kv = {
            "userId": str(uid),
            "withSafetyModeUserFields": True,
        }
        # Use public user_by_login path if we know handle; else rest id query
        try:
            from twscrape.api import GQL_FEATURES, GQL_URL

            async with QueueClient(self.api.pool, "UserByRestId", False) as client:
                params = {"variables": kv, "features": {**GQL_FEATURES}}
                rep = await client.get(f"{GQL_URL}/{op}", params=encode_params(params))
            if rep is None:
                raise RuntimeError("UserByRestId empty response")
            u = parse_user(rep)
            if u is None:
                raise RuntimeError("Could not parse user from UserByRestId")
            self._me = self._user_row(u)
            return self._me
        except Exception:
            # Fallback: sample following is not needed — hardcode lookup via tweets author
            # Use a known own tweet from user_tweets
            async for t in self.api.user_tweets(int(uid), limit=1):
                author = getattr(t, "user", None)
                if author is not None:
                    self._me = self._user_row(author)
                    return self._me
                break
            # Minimal stub so following(id) still works
            self._me = UserRow(
                id=str(uid),
                username="me",
                name="",
                followers=0,
                following=0,
                tweets=0,
                description="",
            )
            return self._me

    def _user_row(self, u) -> UserRow:
        desc = getattr(u, "rawDescription", None) or getattr(u, "description", "") or ""
        if not isinstance(desc, str):
            desc = str(desc)
        created = getattr(u, "created", None)
        return UserRow(
            id=str(u.id),
            username=u.username,
            name=u.displayname or "",
            followers=int(u.followersCount or 0),
            following=int(u.friendsCount or 0),
            tweets=int(u.statusesCount or 0),
            description=desc[:500],
            created=str(created) if created else None,
        )

    def _tweet_row(self, t) -> TweetRow:
        text = getattr(t, "rawContent", None) or getattr(t, "content", None) or ""
        is_rt = getattr(t, "retweetedTweet", None) is not None or str(text).startswith("RT @")
        is_reply = bool(
            getattr(t, "inReplyToTweetId", None) or getattr(t, "inReplyToUser", None)
        )
        created = getattr(t, "date", None)
        if created is not None and getattr(created, "tzinfo", None) is None:
            created = created.replace(tzinfo=timezone.utc)
        author = getattr(getattr(t, "user", None), "username", None)
        media = getattr(t, "media", None)
        media_count = (
            len(getattr(media, "photos", []) or [])
            + len(getattr(media, "videos", []) or [])
            + len(getattr(media, "animated", []) or [])
            if media
            else 0
        )
        return TweetRow(
            id=str(t.id),
            created_at=created.isoformat() if created else "",
            text=str(text),
            likes=int(getattr(t, "likeCount", 0) or 0),
            retweets=int(getattr(t, "retweetCount", 0) or 0),
            replies=int(getattr(t, "replyCount", 0) or 0),
            is_retweet=is_rt,
            is_reply=is_reply,
            lang=getattr(t, "lang", None),
            author=author,
            is_quote=getattr(t, "quotedTweet", None) is not None,
            quotes=int(getattr(t, "quoteCount", 0) or 0),
            views=int(getattr(t, "viewCount", 0) or 0),
            media_count=media_count,
        )

    def _collect_tweets(self, items) -> list[TweetRow]:
        """Map to rows, deduped by id, order preserved.

        X repeats a pinned tweet on every timeline page, so raw pagination
        yields it once per page — dedup by id or it appears dozens of times.
        """
        seen: set[str] = set()
        out: list[TweetRow] = []
        for t in items:
            row = self._tweet_row(t)
            if row.id in seen:
                continue
            seen.add(row.id)
            out.append(row)
        return out

    async def _collect_tweets_async(self, gen) -> list[TweetRow]:
        seen: set[str] = set()
        out: list[TweetRow] = []
        async for t in gen:
            row = self._tweet_row(t)
            if row.id in seen:
                continue
            seen.add(row.id)
            out.append(row)
        return out

    async def following(self, limit: int | None = None) -> list[UserRow]:
        me = await self.me()
        seen: set[str] = set()
        out: list[UserRow] = []
        lim = limit or 10_000
        async for u in self.api.following(int(me.id), limit=lim):
            row = self._user_row(u)
            if row.id in seen:
                continue
            seen.add(row.id)
            out.append(row)
        return out

    async def followers(self, limit: int | None = None) -> list[UserRow]:
        me = await self.me()
        seen: set[str] = set()
        out: list[UserRow] = []
        lim = limit or 10_000
        async for u in self.api.followers(int(me.id), limit=lim):
            row = self._user_row(u)
            if row.id in seen:
                continue
            seen.add(row.id)
            out.append(row)
        return out

    async def user_tweets(self, user_id: int | str, limit: int = 40) -> list[TweetRow]:
        return await self._collect_tweets_async(self.api.user_tweets(int(user_id), limit=limit))

    async def my_tweets(self, limit: int = 200) -> list[TweetRow]:
        me = await self.me()
        return await self.user_tweets(me.id, limit=limit)

    async def my_tweets_and_replies(self, limit: int = 200) -> list[TweetRow]:
        me = await self.me()
        return await self._collect_tweets_async(
            self.api.user_tweets_and_replies(int(me.id), limit=limit)
        )

    async def my_media(self, limit: int = 200) -> list[TweetRow]:
        """Own tweets that carry photos / videos / GIFs."""
        me = await self.me()
        return await self._collect_tweets_async(self.api.user_media(int(me.id), limit=limit))

    async def my_bookmarks(self, limit: int = 200) -> list[TweetRow]:
        """Own bookmarks (cookie session only sees its own)."""
        return await self._collect_tweets_async(self.api.bookmarks(limit=limit))

    async def my_likes(self, limit: int = 200) -> list[TweetRow]:
        """Own liked tweets. Likes are private on X; only the session owner
        can read them, via the Likes GraphQL op (id rotates → auto-discover)."""
        me = await self.me()
        kv = {
            "userId": str(me.id),
            "count": 20,
            "includePromotedContent": False,
            "withClientEventToken": False,
            "withBirdwatchNotes": False,
            "withVoice": True,
            "withV2Timeline": True,
        }
        from contextlib import aclosing

        from twscrape.models import parse_tweets

        op = (await fresh_ops())["Likes"]
        seen: set[str] = set()
        out: list[TweetRow] = []
        async with aclosing(self.api._gql_items(op, kv, limit=limit)) as gen:
            async for rep in gen:
                for t in parse_tweets(rep.json(), limit):
                    row = self._tweet_row(t)
                    if row.id in seen:
                        continue
                    seen.add(row.id)
                    out.append(row)
        return out[:limit] if limit and limit > 0 else out

    # --- writes (cookie session) -------------------------------------------------

    async def unfollow(self, user_id: str | int) -> dict[str, Any]:
        """Unfollow by user id. Uses v1.1 friendships/destroy."""
        assert self._http is not None
        r = await self._http.post(
            "https://x.com/i/api/1.1/friendships/destroy.json",
            content=urlencode({"user_id": str(user_id)}),
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"unfollow failed {r.status_code}: {r.text[:300]}")
        return r.json()

    async def unfollow_username(self, username: str) -> dict[str, Any]:
        u = await self.api.user_by_login(username.lstrip("@"))
        return await self.unfollow(u.id)

    async def delete_tweet(self, tweet_id: str | int) -> dict[str, Any]:
        """Delete own tweet or undo RT via statuses/destroy."""
        assert self._http is not None
        tid = str(tweet_id)
        r = await self._http.post(
            f"https://x.com/i/api/1.1/statuses/destroy/{tid}.json",
            content=urlencode({"id": tid}),
        )
        if r.status_code not in (200, 201):
            # try GraphQL DeleteTweet
            r2 = await self._gql_delete_tweet(tid)
            return r2
        return r.json()

    async def _gql_post(self, op_name: str, variables: dict[str, Any]) -> dict[str, Any]:
        assert self._http is not None
        op = (await fresh_ops())[op_name]
        r = await self._http.post(
            f"{GQL}/{op}",
            json={"variables": variables, "queryId": op.split("/")[0]},
            headers={"content-type": "application/json"},
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"{op_name} failed {r.status_code}: {r.text[:300]}")
        return r.json()

    async def _gql_delete_tweet(self, tweet_id: str) -> dict[str, Any]:
        return await self._gql_post(
            "DeleteTweet", {"tweet_id": tweet_id, "dark_request": False}
        )

    async def unlike(self, tweet_id: str | int) -> dict[str, Any]:
        """Remove your like from a tweet."""
        return await self._gql_post("UnfavoriteTweet", {"tweet_id": str(tweet_id)})

    async def unbookmark(self, tweet_id: str | int) -> dict[str, Any]:
        """Remove a tweet from your bookmarks."""
        return await self._gql_post("DeleteBookmark", {"tweet_id": str(tweet_id)})
    async def sleep_pace(self, seconds: float = 0.4) -> None:
        await asyncio.sleep(seconds)
