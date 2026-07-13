"""Cookie / session auth for twscrape + write actions."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .paths import accounts_db, cookies_file, home


def save_cookies(cookie_str: str, path: Path | None = None) -> Path:
    """Save `auth_token=...; ct0=...` cookie string (mode 0600)."""
    path = path or cookies_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = cookie_str.strip().strip('"').strip("'")
    if "auth_token=" not in cleaned or "ct0=" not in cleaned:
        raise ValueError("Cookie string must include auth_token and ct0")
    path.write_text(cleaned + "\n")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


def user_id_from_cookies(cookie_str: str | None = None) -> str | None:
    """Extract numeric user id from twid cookie (u%3D123 / u=123)."""
    from urllib.parse import unquote

    raw = cookie_str or load_cookies()
    d = parse_cookie_dict(raw)
    twid = d.get("twid")
    if not twid:
        return None
    decoded = unquote(twid)
    if "u=" in decoded:
        return decoded.split("u=", 1)[1].split(";")[0].strip()
    if decoded.isdigit():
        return decoded
    return None


def load_cookies(path: Path | None = None) -> str:
    path = path or cookies_file()
    if not path.exists():
        raise FileNotFoundError(
            f"No cookies at {path}. Run: xtap auth cookies 'auth_token=...; ct0=...'\n"
            "Or: xtap auth browser --browser brave"
        )
    return path.read_text().strip()


def parse_cookie_dict(cookie_str: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    if "auth_token" not in out or "ct0" not in out:
        raise ValueError("Need auth_token and ct0 in cookie string")
    return out  # twid optional


BROWSERS = ("brave", "chrome", "chromium", "firefox", "edge", "safari")


def _browser_cookies(browser: str) -> dict[str, str]:
    """Raw x.com cookies from one browser's on-disk store (may raise)."""
    import browser_cookie3

    loaders = {
        "brave": browser_cookie3.brave,
        "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium,
        "firefox": browser_cookie3.firefox,
        "edge": getattr(browser_cookie3, "edge", None),
        "safari": getattr(browser_cookie3, "safari", None),
    }
    loader = loaders.get(browser.lower())
    if loader is None:
        raise ValueError(f"Unsupported browser: {browser}. Choose: {', '.join(loaders)}")
    cj = loader(domain_name=".x.com")
    return {c.name: c.value for c in cj}


def _is_permission_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        isinstance(exc, PermissionError)
        or "operation not permitted" in msg
        or "permission denied" in msg
        or "full disk access" in msg
    )


def scan_all_browsers() -> list[dict[str, str]]:
    """Per-browser cookie status. Never raises.

    Each entry: {browser, status, user_id?, cookie?, error?} where status is
    one of: "session" (logged in), "no-session" (readable, not logged in),
    "locked" (couldn't read — usually macOS Full Disk Access, e.g. Safari),
    "absent" (browser not installed / no profile).
    """
    out: list[dict[str, str]] = []
    for b in BROWSERS:
        try:
            cookies = _browser_cookies(b)
        except Exception as e:  # noqa: BLE001 — classify, don't crash the scan
            if _is_permission_error(e):
                out.append({"browser": b, "status": "locked", "error": str(e).splitlines()[0][:160]})
            else:
                out.append({"browser": b, "status": "absent"})
            continue
        if not cookies.get("auth_token") or not cookies.get("ct0"):
            out.append({"browser": b, "status": "no-session"})
            continue
        parts = [f"auth_token={cookies['auth_token']}", f"ct0={cookies['ct0']}"]
        if cookies.get("twid"):
            parts.append(f"twid={cookies['twid']}")
        cookie_str = "; ".join(parts)
        out.append({
            "browser": b,
            "status": "session",
            "user_id": user_id_from_cookies(cookie_str) or "",
            "cookie": cookie_str,
        })
    return out


def scan_browser_sessions() -> list[dict[str, str]]:
    """Only the browsers with a logged-in X session. See scan_all_browsers."""
    return [s for s in scan_all_browsers() if s["status"] == "session"]


def import_from_any() -> tuple[str, str]:
    """Import the first logged-in X session found in any installed browser.

    Returns (browser_name, cookie_string).
    """
    sessions = scan_browser_sessions()
    if not sessions:
        raise RuntimeError(
            "Log into x.com in your browser first, then run this again. "
            f"No signed-in X session was found in any browser ({', '.join(BROWSERS)})."
        )
    s = sessions[0]
    save_cookies(s["cookie"])
    return s["browser"], s["cookie"]


def import_from_browser(browser: str = "brave") -> str:
    """Pull x.com cookies from a specific local browser."""
    try:
        cookies = _browser_cookies(browser)
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed reading {browser} cookies: {e}") from e

    if not cookies.get("auth_token") or not cookies.get("ct0"):
        raise RuntimeError(
            f"Log into x.com in {browser} first — no signed-in X session found there."
        )
    parts = [f"auth_token={cookies['auth_token']}", f"ct0={cookies['ct0']}"]
    if cookies.get("twid"):
        parts.append(f"twid={cookies['twid']}")
    s = "; ".join(parts)
    save_cookies(s)
    return s


def logout() -> list[str]:
    """Disconnect the imported X session.

    Removes the saved cookies, twscrape account store, and cached profile so
    the tool returns to a signed-out state. Snapshots and reports are kept.
    Returns the list of paths actually removed.
    """
    removed: list[str] = []
    for path in (cookies_file(), accounts_db(), home() / "profile.json"):
        try:
            path.unlink()
            removed.append(str(path))
        except FileNotFoundError:
            pass
    return removed


async def ensure_twscrape_account(username: str = "primary") -> None:
    """Register cookies into twscrape accounts DB."""
    from twscrape import API

    cookie = load_cookies()
    api = API(str(accounts_db()))
    # add_account_cookies is idempotent enough; delete+readd if needed
    try:
        await api.pool.delete_accounts([username])
    except Exception:
        pass
    await api.pool.add_account_cookies(username, cookie)
