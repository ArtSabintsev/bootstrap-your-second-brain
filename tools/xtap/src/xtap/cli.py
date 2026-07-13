"""xtap — archive, audit, and trim your X account."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# re-export for typer runtime
from . import __version__, store
from .audit import score_follow, score_own_tweets_for_cleanup
from .auth import import_from_browser, save_cookies
from .client import XClient
from .paths import home

app = typer.Typer(
    name="xtap",
    help="Archive, audit, and trim your X account from the CLI or a local dashboard.",
    no_args_is_help=True,
    add_completion=False,
)
auth_app = typer.Typer(help="Connect or disconnect your X session")
sync_app = typer.Typer(help="Save snapshots of your tweets, likes, follows, and more")
audit_app = typer.Typer(help="Score follows and posts for cleanup")
act_app = typer.Typer(help="Unfollow or delete (dry-run by default)")
app.add_typer(auth_app, name="auth")
app.add_typer(sync_app, name="sync")
app.add_typer(audit_app, name="audit")
app.add_typer(act_app, name="act")

console = Console()


def _run(coro):
    return asyncio.run(coro)


@app.callback()
def main_callback(
    ctx: typer.Context,
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Less chatter"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet


@app.command("version")
def version_cmd() -> None:
    """Print version."""
    console.print(f"xtap {__version__}")
    console.print(f"data: {home()}")


# --- auth ----------------------------------------------------------------------

@auth_app.command("cookies")
def auth_cookies(
    cookie: str = typer.Argument(..., help="auth_token=...; ct0=..."),
) -> None:
    """Save cookies manually (from browser DevTools)."""
    path = save_cookies(cookie)
    console.print(f"[green]Saved cookies → {path}[/green]")


@auth_app.command("browser")
def auth_browser(
    browser: str = typer.Option(
        "auto", "--browser", "-b", help="auto|brave|chrome|chromium|firefox|edge|safari"
    ),
) -> None:
    """Import X cookies from a local browser (must be logged in).

    Default 'auto' tries every installed browser until one has a session.
    """
    from .auth import import_from_any, scan_browser_sessions

    try:
        if browser == "auto":
            sessions = scan_browser_sessions()
            unique = {s["user_id"] or s["cookie"][:48]: s for s in reversed(sessions)}
            if len(unique) > 1:
                choices = list(unique.values())
                console.print("[bold]Multiple X sessions found:[/bold]")
                for i, s in enumerate(choices, 1):
                    console.print(f"  {i}. {s['browser']}  (user id {s['user_id'] or '?'})")
                n = typer.prompt("Which one?", default=1, type=int)
                browser = choices[min(max(n, 1), len(choices)) - 1]["browser"]
                import_from_browser(browser)
            else:
                browser, _ = import_from_any()
        else:
            import_from_browser(browser)
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Imported cookies from {browser} → {home() / 'auth' / 'cookies.txt'}[/green]")


@auth_app.command("logout")
def auth_logout(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Disconnect the imported X session (clears cookies + cached profile).

    Snapshots and reports are kept. Re-run `xtap auth browser` to reconnect.
    """
    from .auth import logout

    if not yes and not typer.confirm("Disconnect the imported X session?"):
        raise typer.Abort()
    removed = logout()
    if removed:
        console.print(f"[green]Disconnected.[/green] Removed {len(removed)} file(s).")
    else:
        console.print("[yellow]Nothing to disconnect. No session was imported.[/yellow]")


@auth_app.command("whoami")
def auth_whoami() -> None:
    """Verify session and print @handle."""

    async def _go():
        async with XClient() as xc:
            me = await xc.me()
            store.save_profile(me.as_dict())
            console.print(
                f"[bold]@{me.username}[/bold]  followers={me.followers:,}  "
                f"following={me.following:,}  tweets={me.tweets:,}"
            )

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


# --- sync ----------------------------------------------------------------------

@sync_app.command("following")
def sync_following(
    limit: Optional[int] = typer.Option(None, "--limit", help="Max accounts (default: all)"),
) -> None:
    """Snapshot accounts you follow."""

    async def _go():
        async with XClient() as xc:
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                p.add_task("Fetching following…", total=None)
                rows = await xc.following(limit=limit)
            path = store.snapshot_following([r.as_dict() for r in rows])
            me = await xc.me()
            console.print(
                f"[green]Saved {len(rows)} following[/green] (profile says {me.following}) → {path}"
            )

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


async def _fetch_kind(xc: XClient, kind: str, limit: int, replies: bool = False):
    if kind == "tweets":
        if replies:
            return await xc.my_tweets_and_replies(limit=limit)
        return await xc.my_tweets(limit=limit)
    if kind == "likes":
        return await xc.my_likes(limit=limit)
    if kind == "bookmarks":
        return await xc.my_bookmarks(limit=limit)
    if kind == "media":
        return await xc.my_media(limit=limit)
    raise ValueError(kind)


def _save_tweet_snapshot(kind: str, rows, extra_meta: dict | None = None) -> None:
    dicts = [r.as_dict() for r in rows]
    path = store.snapshot_tweets(kind, dicts, meta=extra_meta)
    rts = sum(1 for r in rows if r.is_retweet)
    quotes = sum(1 for r in rows if r.is_quote)
    repl = sum(1 for r in rows if r.is_reply)
    console.print(
        f"[green]Saved {len(rows)} {kind}[/green] "
        f"(RTs={rts}, quotes={quotes}, replies={repl}) → {path}"
    )


def _sync_tweet_kind(kind: str, limit: int, replies: bool = False, label: str | None = None) -> None:
    async def _go():
        async with XClient() as xc:
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                p.add_task(label or f"Fetching your {kind}…", total=None)
                rows = await _fetch_kind(xc, kind, limit, replies=replies)
            _save_tweet_snapshot(kind, rows, {"limit": limit, "replies": replies})

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@sync_app.command("tweets")
def sync_tweets(
    limit: int = typer.Option(200, "--limit", "-n", help="Max posts to pull (-1 = everything X serves, ~3200)"),
    replies: bool = typer.Option(True, "--replies/--no-replies", help="Include replies timeline"),
) -> None:
    """Snapshot your tweets, retweets, and quote tweets (replies included by default)."""
    _sync_tweet_kind("tweets", limit, replies=replies)


@sync_app.command("likes")
def sync_likes(
    limit: int = typer.Option(200, "--limit", "-n", help="Max likes to pull (-1 = all available)"),
) -> None:
    """Snapshot tweets you've liked (only your own session can see these)."""
    _sync_tweet_kind("likes", limit)


@sync_app.command("bookmarks")
def sync_bookmarks(
    limit: int = typer.Option(200, "--limit", "-n", help="Max bookmarks to pull (-1 = all)"),
) -> None:
    """Snapshot your bookmarks."""
    _sync_tweet_kind("bookmarks", limit)


@sync_app.command("media")
def sync_media(
    limit: int = typer.Option(200, "--limit", "-n", help="Max media posts to pull (-1 = all)"),
) -> None:
    """Snapshot your posts that carry photos / videos / GIFs."""
    _sync_tweet_kind("media", limit)


@sync_app.command("all")
def sync_all(
    limit: int = typer.Option(500, "--limit", "-n", help="Max items per timeline (-1 = all available)"),
    skip: Optional[list[str]] = typer.Option(
        None, "--skip", help="Timelines to skip (following, tweets, likes, bookmarks, media)"
    ),
) -> None:
    """Snapshot everything: following, tweets+replies, likes, bookmarks, media."""
    skipped = set(skip or [])

    async def _go():
        async with XClient() as xc:
            me = await xc.me()
            store.save_profile(me.as_dict())
            console.print(f"Syncing everything for [bold]@{me.username}[/bold]")
            if "following" not in skipped:
                with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                    p.add_task("Fetching following…", total=None)
                    users = await xc.following()
                path = store.snapshot_following([u.as_dict() for u in users])
                console.print(f"[green]Saved {len(users)} following[/green] → {path}")
            for kind in ("tweets", "likes", "bookmarks", "media"):
                if kind in skipped:
                    continue
                with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                    p.add_task(f"Fetching {kind}…", total=None)
                    rows = await _fetch_kind(xc, kind, limit, replies=True)
                _save_tweet_snapshot(kind, rows, {"limit": limit})

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


# --- audit ---------------------------------------------------------------------

@audit_app.command("following")
def audit_following(
    max_ppw: float = typer.Option(5.0, "--max-ppw", help="Infrequent if posts/week below this"),
    dead_days: int = typer.Option(90, "--dead-days", help="Dead if last post older than this"),
    window: int = typer.Option(30, "--window", help="Activity window in days"),
    tweet_limit: int = typer.Option(20, "--tweet-limit", help="Recent tweets sampled per user"),
    quality_cutoff: float = typer.Option(45.0, "--quality-cutoff", help="Low quality if score below"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Only audit first N follows (debug)"),
    pace: float = typer.Option(0.4, "--pace", help="Seconds between user timeline fetches"),
) -> None:
    """Score follows for dead / infrequent / low-quality timelines.

    Rate limits: ~20 UserTweets per 15 minutes per session. Full 700+ may take hours.
    """

    async def _go():
        async with XClient() as xc:
            me = await xc.me()
            console.print(f"Auditing [bold]@{me.username}[/bold] following={me.following:,}")
            following = await xc.following(limit=limit)
            if limit:
                following = following[:limit]
            console.print(f"Loaded {len(following)} accounts. Sampling ≤{tweet_limit} tweets each…")

            recs = []
            scores = []
            with Progress(console=console) as progress:
                task = progress.add_task("Scoring…", total=len(following))
                for i, u in enumerate(following, 1):
                    try:
                        tweets = await xc.user_tweets(u.id, limit=tweet_limit)
                        fs = score_follow(
                            u,
                            tweets,
                            window_days=window,
                            max_ppw=max_ppw,
                            dead_days=dead_days,
                            quality_cutoff=quality_cutoff,
                            tweet_limit=tweet_limit,
                        )
                        scores.append(fs)
                        if fs.recommend:
                            recs.append(fs.as_dict())
                    except Exception as e:
                        console.print(f"  [yellow]skip @{u.username}: {e}[/yellow]")
                    progress.update(task, advance=1)
                    if i % 10 == 0:
                        progress.console.print(
                            f"  {i}/{len(following)}  flagged={len(recs)}"
                        )
                    await xc.sleep_pace(pace)

            recs.sort(
                key=lambda r: (
                    -r.get("priority", 0),
                    r.get("posts_per_week") or 0,
                    r.get("quality_score") or 100,
                )
            )
            meta = {
                "total_following": len(following),
                "recommend": len(recs),
                "dead_90d": sum(1 for r in recs if r.get("dead_90d")),
                "infrequent": sum(1 for r in recs if r.get("infrequent")),
                "low_quality": sum(1 for r in recs if r.get("low_quality")),
                "max_ppw": max_ppw,
                "dead_days": dead_days,
                "window_days": window,
            }
            j, c, md = store.save_follow_audit(recs, meta)
            console.print(
                f"\n[bold green]Recommend unfollow: {len(recs)}[/bold green] "
                f"(dead≥{dead_days}d={meta['dead_90d']}, "
                f"<{max_ppw}/wk={meta['infrequent']}, lowq={meta['low_quality']})"
            )
            console.print(f"Report: {md}")
            console.print(f"CSV:    {c}")
            console.print(f"JSON:   {j}")
            console.print(
                "\nApply (dry-run): [cyan]xtap act unfollow --from "
                f"{c}[/cyan]"
            )
            console.print(
                "Apply for real:  [cyan]xtap act unfollow --from "
                f"{c} --apply[/cyan]"
            )

            # preview table
            table = Table(title="Top 25 unfollow candidates")
            table.add_column("@handle")
            table.add_column("days", justify="right")
            table.add_column("ppw", justify="right")
            table.add_column("q", justify="right")
            table.add_column("why")
            for r in recs[:25]:
                why = (r.get("reasons") or [""])[0][:60]
                table.add_row(
                    f"@{r.get('username')}",
                    str(r.get("days_since_last") if r.get("days_since_last") is not None else "—"),
                    str(r.get("posts_per_week")),
                    str(r.get("quality_score")),
                    why,
                )
            console.print(table)

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@audit_app.command("tweets")
def audit_tweets(
    limit: int = typer.Option(300, "--limit", "-n"),
    min_age: int = typer.Option(90, "--min-age", help="Only tweets older than N days"),
    only_rts: bool = typer.Option(False, "--only-rts", help="Only retweets"),
    only_replies: bool = typer.Option(False, "--only-replies"),
    max_likes: Optional[int] = typer.Option(2, "--max-likes", help="Low engagement threshold"),
) -> None:
    """Score your own tweets/RTs for cleanup."""

    async def _go():
        async with XClient() as xc:
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                p.add_task("Fetching your tweets…", total=None)
                tweets = await xc.my_tweets_and_replies(limit=limit)
            recs = score_own_tweets_for_cleanup(
                tweets,
                min_age_days=min_age,
                only_rts=only_rts,
                only_replies=only_replies,
                low_engagement_max_likes=max_likes,
            )
            rows = [r.as_dict() for r in recs]
            meta = {
                "pulled": len(tweets),
                "flagged": len(rows),
                "min_age_days": min_age,
                "only_rts": only_rts,
                "only_replies": only_replies,
            }
            j, c = store.save_tweet_audit(rows, meta)
            console.print(f"[green]Flagged {len(rows)}/{len(tweets)} tweets[/green]")
            console.print(f"CSV:  {c}")
            console.print(f"JSON: {j}")
            console.print(
                f"\nDry-run delete: [cyan]xtap act delete --from {c}[/cyan]"
            )
            console.print(
                f"Apply delete:   [cyan]xtap act delete --from {c} --apply[/cyan]"
            )

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


# --- act -----------------------------------------------------------------------

def _load_ids_from_report(path: Path, id_key: str = "id", user_key: str = "username") -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        rows = data.get("recs") if isinstance(data, dict) and "recs" in data else data
        if not isinstance(rows, list):
            raise ValueError("JSON must be a list or {recs: [...]}")
        return rows
    if path.suffix == ".csv":
        import csv

        with path.open() as f:
            return list(csv.DictReader(f))
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    raise ValueError(f"Unsupported report type: {path.suffix}")


@act_app.command("unfollow")
def act_unfollow(
    from_report: Optional[Path] = typer.Option(None, "--from", help="CSV/JSON audit report"),
    username: Optional[list[str]] = typer.Option(None, "--user", "-u", help="Explicit @handles"),
    apply: bool = typer.Option(False, "--apply", help="Actually unfollow (default: dry-run)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation when --apply"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max unfollows this run"),
    pace: float = typer.Option(1.0, "--pace", help="Seconds between unfollows"),
    only_dead: bool = typer.Option(False, "--only-dead", help="Only rows with dead_90d=true"),
    only_lowq: bool = typer.Option(False, "--only-lowq", help="Only low_quality rows"),
    max_ppw: Optional[float] = typer.Option(None, "--max-ppw", help="Only if posts_per_week < N"),
) -> None:
    """Unfollow accounts from an audit report or explicit handles.

    Default is dry-run. Pass --apply to mutate.
    """
    targets: list[dict] = []
    if from_report:
        rows = _load_ids_from_report(from_report)
        for r in rows:
            if only_dead and str(r.get("dead_90d", "")).lower() not in ("true", "1", "yes"):
                continue
            if only_lowq and str(r.get("low_quality", "")).lower() not in ("true", "1", "yes"):
                continue
            if max_ppw is not None:
                try:
                    if float(r.get("posts_per_week") or 999) >= max_ppw:
                        continue
                except ValueError:
                    pass
            targets.append(r)
    if username:
        for u in username:
            targets.append({"username": u.lstrip("@")})
    if not targets:
        console.print("[red]No targets. Pass --from report.csv or --user handle[/red]")
        raise typer.Exit(1)
    if limit:
        targets = targets[:limit]

    console.print(f"{'APPLY' if apply else 'DRY-RUN'}: {len(targets)} unfollows")
    for t in targets[:20]:
        console.print(f"  @{t.get('username') or t.get('id')}")
    if len(targets) > 20:
        console.print(f"  … +{len(targets) - 20} more")

    if apply and not yes:
        if not typer.confirm("Unfollow these accounts for real?"):
            raise typer.Abort()

    if not apply:
        console.print("[yellow]Dry-run only. Re-run with --apply to execute.[/yellow]")
        return

    async def _go():
        async with XClient() as xc:
            ok = fail = 0
            for t in targets:
                handle = (t.get("username") or "").lstrip("@")
                uid = t.get("id")
                try:
                    if uid and str(uid).isdigit():
                        await xc.unfollow(uid)
                    elif handle:
                        await xc.unfollow_username(handle)
                    else:
                        raise ValueError("no id/username")
                    ok += 1
                    console.print(f"  [green]unfollowed[/green] @{handle or uid}")
                except Exception as e:
                    fail += 1
                    console.print(f"  [red]fail[/red] @{handle or uid}: {e}")
                await xc.sleep_pace(pace)
            console.print(f"Done. ok={ok} fail={fail}")

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@act_app.command("delete")
def act_delete(
    from_report: Optional[Path] = typer.Option(None, "--from", help="CSV/JSON tweet audit"),
    tweet_id: Optional[list[str]] = typer.Option(None, "--id", help="Explicit tweet ids"),
    apply: bool = typer.Option(False, "--apply", help="Actually delete"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    pace: float = typer.Option(1.0, "--pace"),
    only_rts: bool = typer.Option(False, "--only-rts"),
) -> None:
    """Delete own tweets / undo RTs. Default dry-run."""
    targets: list[dict] = []
    if from_report:
        rows = _load_ids_from_report(from_report)
        for r in rows:
            if only_rts and str(r.get("is_retweet", "")).lower() not in ("true", "1", "yes"):
                continue
            targets.append(r)
    if tweet_id:
        for i in tweet_id:
            targets.append({"id": i})
    if not targets:
        console.print("[red]No targets. Pass --from report.csv or --id TWEET_ID[/red]")
        raise typer.Exit(1)
    if limit:
        targets = targets[:limit]

    console.print(f"{'APPLY' if apply else 'DRY-RUN'}: {len(targets)} deletes")
    for t in targets[:15]:
        console.print(f"  {t.get('id')}  {(t.get('text') or '')[:50]}")
    if len(targets) > 15:
        console.print(f"  … +{len(targets) - 15} more")

    if apply and not yes:
        if not typer.confirm("Delete these tweets for real?"):
            raise typer.Abort()
    if not apply:
        console.print("[yellow]Dry-run only. Re-run with --apply to execute.[/yellow]")
        return

    async def _go():
        async with XClient() as xc:
            ok = fail = 0
            for t in targets:
                tid = t.get("id")
                try:
                    await xc.delete_tweet(tid)
                    ok += 1
                    console.print(f"  [green]deleted[/green] {tid}")
                except Exception as e:
                    fail += 1
                    console.print(f"  [red]fail[/red] {tid}: {e}")
                await xc.sleep_pace(pace)
            console.print(f"Done. ok={ok} fail={fail}")

    try:
        _run(_go())
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


# --- web -----------------------------------------------------------------------

@app.command("web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (keep it local)"),
    port: int = typer.Option(8787, "--port", "-p"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open dashboard in browser"),
) -> None:
    """Serve the local dashboard: browse snapshots, run syncs, act on single items."""
    try:
        import uvicorn

        from .web import create_app
    except ImportError:
        console.print(
            "[red]Web extras not installed.[/red] Run: pip install -e '.[web]'"
        )
        raise typer.Exit(1)

    if host not in ("127.0.0.1", "localhost", "::1"):
        console.print(
            f"[yellow]Warning:[/yellow] binding to {host} exposes the dashboard beyond "
            "this machine. It has no password — anyone who can reach the port can "
            "delete and unfollow as you. Use 127.0.0.1 unless you know what you're doing."
        )
        if not typer.confirm("Bind to a non-local address anyway?"):
            raise typer.Abort()

    url = f"http://{host}:{port}"
    console.print(f"[bold]xtap dashboard[/bold] → {url}  (Ctrl-C to stop)")
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    app()
