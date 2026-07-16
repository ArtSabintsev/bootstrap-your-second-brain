---
title: "Tools, scrapers, and extensibility"
type: guide
updated: 2026-07-14
---

# Tools, scrapers, and extensibility

This vault is plain Markdown for humans in Obsidian and a contract for agents
under AGENTS.md. The operator stack and the built-in scrapers are documented
here so a setup agent can recommend the right apps and so a developer agent can
add a new source without inventing architecture.

## Recommended operator stack

| Tool | Role | Where it fits |
|------|------|----------------|
| **[Obsidian](https://obsidian.md)** | Primary vault UI: graph, search, wikilinks, mobile | Open this repo folder as the vault. Title Case folders (`Profile/`, `Topics/`, …) are meant to be browsed as notes, not as a hidden database. |
| **[Claudian](https://github.com/YishenTu/claudian)** (community id: `realclaudian`) | Claude agent chat *inside* Obsidian, same filesystem as the vault | **Installed by** `scripts/bootstrap.sh` (or Community Plugins: id `realclaudian`, Yishen Tu). Point it at this vault. Complements terminal `claude` / `ask.sh`; does not replace daily ingest. |
| **[Omnisearch](https://github.com/scambier/obsidian-omnisearch)** (community id: `omnisearch`) | Fast vault search (full text + fuzzy) | **Installed by** `scripts/bootstrap.sh` (build not in git). Enabled in `community-plugins.json`. Hotkey: **Cmd+K** / **Ctrl+K** → vault search (`hotkeys.json`). |
| **[Ghostty Terminal](https://github.com/lavs9/obsidian-ghostty-terminal)** (community id: `ghostty-terminal`) | Embedded terminal in Obsidian | **Installed by** `scripts/bootstrap.sh`. Needs Python 3 for PTY helper. Desktop only. |
| **[Obsidian Web Clipper](https://obsidian.md/clipper)** | Capture web pages into the inbox | Configure the clipper to write into `Clippings/`. Agents file from Clippings only when asked (rule 4). Raw clips stay in Clippings until filed; archive originals under `Sources/` when filing. |
| **Claude Code / Grok CLI / Codex** | Terminal agents that load CLAUDE.md → AGENTS.md | Primary automation harnesses for setup, ask, synth, briefs. Any agent that reads `AGENTS.md` + `SETUP.md` is supported. |
| **`gh` CLI** | Authenticated GitHub API for the github source | Required only if `sources.github` is true. |
| **Browser (Brave/Chrome/Firefox)** | Cookie source for xtap (X) and yt-dlp (podcasts + YouTube likes) | Set `browser` in config.json. Same value drives `xtap auth browser` and `yt-dlp --cookies-from-browser`. Must be logged into X and YouTube. |

### How the pieces relate

```
Browser (logged into X / YouTube)
    | cookies via xtap auth
    v
Daily scrapers  -->  Sources/ (immutable)  -->  Claude filing  -->  wiki notes
Web Clipper     -->  Clippings/ (inbox)     -->  human/agent file on request
Obsidian        -->  browse/edit all folders (Omnisearch: Cmd/Ctrl+K)
Claudian / CLIs -->  ask, log, brief, setup (same files)
```

Nothing about this requires a proprietary host. If you leave the tools, you keep
the Markdown git repo.

### Obsidian plugins (bootstrap installs builds)

`.obsidian/community-plugins.json` and `.obsidian/hotkeys.json` are tracked.
Plugin **builds** under `.obsidian/plugins/` are **not** in git — `scripts/bootstrap.sh`
downloads them (Omnisearch, Ghostty Terminal, Claudian). Re-run bootstrap or the
install step after clone; enable Restricted-mode-off in Obsidian once.


## Built-in scrapers (sources)

Each source is toggled in `config.json` under `sources.<key>`. The daily
orchestrator is `scripts/ingest-daily.sh`. Disabled sources are skipped cleanly.

### 1. X bookmarks (`sources.x_bookmarks`)

| | |
|--|--|
| **Script** | `scripts/sources/x-bookmarks.sh` → `x_bookmarks_ingest.py` |
| **Tool** | Vendored `tools/xtap` (install: `pip install -e tools/xtap` in `.venv`) |
| **Auth** | `.venv/bin/xtap auth browser --browser <config.browser>` → session in `~/.xtap/` |
| **Input** | Your X bookmarks via logged-in session (not the paid X API) |
| **Output** | `Sources/x-bookmarks/x-bookmarks-YYYY-MM-DD.md` (append-only) |
| **Cleanup** | After successful Claude filing, `x_bookmarks_cleanup.py` may remove archived bookmarks from X (`BRAIN_X_DELETE=0` to disable) |
| **Deps** | Python venv, browser with X login, xtap |

### 2. Goodreads (`sources.goodreads`)

| | |
|--|--|
| **Script** | `scripts/goodreads_ingest.py` |
| **Auth** | `$secrets_dir/goodreads/rss-key` + `identity.goodreads_user_id` |
| **Input** | Private all-shelves RSS |
| **Output** | `Sources/goodreads/goodreads-YYYY-MM-DD.md`, one entry per (book, shelf state) |
| **Deps** | httpx, secrets file, numeric user id |

### 3. Substack (`sources.substack`)

| | |
|--|--|
| **Script** | `scripts/substack_ingest.py` |
| **Auth** | Public feed URL only (`identity.substack_feed`) |
| **Input** | Publication RSS |
| **Output** | One archival note per essay under `Sources/substack/` |
| **Deps** | httpx, html2text |

### 4. GitHub (`sources.github`)

| | |
|--|--|
| **Script** | `scripts/github_ingest.py` |
| **Auth** | `gh auth login` |
| **Input** | Recent commits by `identity.git_emails` / name on repos for `identity.github_login` |
| **Output** | `Sources/github/…`; daily Claude pass folds into `Projects/` notes |
| **Deps** | `gh` CLI |

### 5. Podcasts (`sources.podcasts`)

| | |
|--|--|
| **Scripts** | `scripts/podcasts/backfill.sh`, `fetch_transcript.py`, `synth_episode.sh`, `build_links.py` |
| **Config** | `scripts/podcasts/shows.json` (show keys, YouTube or RSS URLs, tags, optional `source`/`role`) |
| **Auth** | YouTube access via yt-dlp (rate-limited; shares lock with likes) |
| **Input** | Episode list + auto-captions |
| **Output** | Deep notes under `Library/podcasts/<show>/` for interest shows; **world-context** shows write monthly digests only (`consolidate_world_context.py`), not one note per episode |
| **Deps** | yt-dlp (cookies via `config.browser`) for YouTube shows; RSS fetch for `source:rss` shows; claude CLI for deep synth |

### 6. YouTube likes (`sources.youtube_likes`)

| | |
|--|--|
| **Scripts** | `scripts/youtube_likes/run.sh`, `select_candidates.py`, `synth_like.sh` |
| **Auth** | Browser/YouTube session (same ecosystem as podcasts; shared lock) |
| **Input** | Liked-videos playlist, live each run (no stored full catalog) |
| **Output** | Substantive long-form notes under `Library/youtube-likes/`; skip log in `.status/` |
| **Deps** | yt-dlp (cookies via `config.browser`), claude CLI (judges music/gameplay out) |

### 7. Google Drive meetings (`sources.google_drive_meetings`)

| | |
|--|--|
| **Scripts** | `scripts/google_drive_meetings_ingest.py`; one-time OAuth via `scripts/google_drive_auth.py` |
| **Auth** | Google OAuth token in the `secrets_dir` (never in the vault) |
| **Input** | Google Meet "Notes by Gemini" docs from Drive |
| **Output** | `Sources/meeting-notes/…`; daily pass files into `Meetings/<project>.md` |
| **Deps** | google-api-python-client, google-auth-oauthlib (installed by bootstrap) |

### After capture: filing and intelligence

| Step | Script | Notes |
|------|--------|-------|
| Wiki filing | Claude pass inside `ingest-daily.sh` | Only for new `Sources/` captures; skip with `BRAIN_PROCESS=0` |
| Graph index | `scripts/podcasts/build_links.py` | People/topics → episodes JSON under `_indexes/` |
| Position ledger | `scripts/intelligence/build_ledger.sh <slug>` | On demand for core people |
| Brief | `scripts/intelligence/brief.sh <slug>` | Pre-engagement read |
| Morning digest | `scripts/digest.py` | Writes `Digests/<date>.md`: what got filed, added, updated |
| Ask | `scripts/ask.sh` | Query with citations |
| Log | `scripts/log.sh` | Operator journal |

## How to add a new ingestor

Design rule: **plumbing in code, judgment in the model.** New sources should
only append under `Sources/` (or synthesize under `Library/` with a clear
watermark). Never rewrite prior Sources notes.

### Checklist

1. **Config toggle**  
   Add `"my_source": false` under `sources` in `config.example.json` and document
   it in SETUP.md / this file.

2. **Ingest script**  
   - Prefer `scripts/my_source_ingest.py` or `scripts/sources/my-source.sh`.  
   - Read identity via `from config import get` / `scripts/config.py`.  
   - Secrets only from `secrets_dir()`, never from the vault.  
   - Write only under `Sources/<name>/` (immutable append).  
   - Exit non-zero on hard failure; the daily job continues other sources.

3. **Wire the daily job**  
   In `scripts/ingest-daily.sh`:

   ```bash
   if brain_source_enabled my_source; then
     run_source my-source brain_py "$ROOT/scripts/my_source_ingest.py"
   else
     log "source: my-source skipped (config.sources.my_source=false)"
   fi
   ```

   Reuse `scripts/lib.sh` (`brain_source_enabled`, `brain_py`, git helpers).

4. **Doctor**  
   In `scripts/doctor.sh`, if the source is on, check its secret file / CLI.

5. **Docs**  
   Add a row to this file and mention the toggle in SETUP.md.

6. **Optional Claude filing**  
   If captures need enrichment, extend the daily Claude prompt to mention the
   new Sources path. Keep Sources immutable.

### Vendoring a tool like xtap

Heavy CLIs that talk to external platforms live under `tools/<name>/` and install
into the vault venv:

```bash
# layout
tools/mytool/
  pyproject.toml   # or package.json, Cargo.toml, …
  README.md        # auth, data dir, what never enters the vault
  src/…

# bootstrap / install
.venv/bin/pip install -e tools/mytool
```

Conventions (match xtap):

- **State and secrets outside the vault** (e.g. `~/.mytool/`), not in git.
- **Thin shell wrapper** under `scripts/sources/` calls the tool, then a Python
  normalizer writes Markdown under `Sources/`.
- **Document auth** in `tools/mytool/README.md` and link from this file.
- **Add to `scripts/bootstrap.sh`** install line only if every fork needs it.

xtap reference implementation: `tools/xtap/` + `scripts/sources/x-bookmarks.sh`.

## Agent harnesses

| Entry file | Consumers |
|------------|-----------|
| `CLAUDE.md` | Claude Code, Claudian, anything that loads CLAUDE.md |
| `GROK.md` | symlink → CLAUDE.md (Grok CLI) |
| `CODEX.md` | symlink → CLAUDE.md (Codex) |
| `AGENTS.md` | Universal contract (also loaded via @AGENTS.md) |
| `SETUP.md` | Setup intent: interview → config → secrets → auth → doctor → schedule |
| `TOOLS.md` | This file: apps, scrapers, extension |

When the operator says "set up my second brain", follow SETUP.md first; use this
file to recommend Obsidian/Claudian/Web Clipper and to explain sources.
