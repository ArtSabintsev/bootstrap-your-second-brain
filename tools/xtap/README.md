# xtap (vendored CLI)

`xtap` taps X for the brain: it archives your account (bookmarks, tweets, likes,
following), searches X via your logged-in session, and serves as a RAG source.

`xtap` began as `xtrim` (github.com/ArtSabintsev/xtrim). That repo is retired and
no longer maintained; `xtap` here is the canonical, maintained version. The web
dashboard from the old tool is excluded (`xtap web` is a no-op stub).

Data and secrets stay in `~/.xtap/` (cookies, session store, snapshots). Nothing
sensitive lives in the vault. See `scripts/sources/x-bookmarks.sh` for the daily
bookmark ingest.

Install into the vault venv:

```bash
cd ~/Developer/second-brain
python3 -m venv .venv
.venv/bin/pip install -e tools/xtap
```
