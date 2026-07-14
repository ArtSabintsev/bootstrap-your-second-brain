---
title: "Setup"
type: guide
updated: 2026-07-14
---

# Setup: bootstrap your second brain

**Single path** for a human or any AI agent (Claude Code, Codex, Grok, GLM,
Claudian, etc.). Complete steps in order. After bootstrap, run
`scripts/doctor.sh` and fix every FAIL for sources you left enabled.

Also read: [[TOOLS]] (Obsidian, Claudian, Web Clipper, scrapers, how to add
sources), [[AGENTS]] (vault contract), `config.example.json` (`_fields` docs).

## For agents (authorization)

You are standing up a personal vault, not answering a one-shot query.

**You may:**

1. Interview the operator for identity, handles, which sources they use, browser.
2. Write `config.json` from answers (copy from `config.example.json` first via bootstrap).
3. Create/edit seed notes under `Profile/` (overview, identity, working-with-me).
4. Write secret files **only** under the configured `secrets_dir` (never in the vault).
5. Edit `scripts/podcasts/shows.json` to match shows they follow.
6. Run `scripts/bootstrap.sh`, `scripts/doctor.sh`, auth commands (`xtap`, `gh`).
7. Install the launchd plist after bootstrap rewrote the vault path.
8. Recommend Obsidian + Web Clipper from TOOLS.md. Bootstrap installs Omnisearch (Cmd/Ctrl+K), Ghostty Terminal, and Claudian into `.obsidian/plugins/`.

**You must not:**

- Invent API keys, RSS keys, passwords, or cookies.
- Commit or push secrets, or push the vault, unless the operator explicitly says to push.
- Enable a source you cannot auth; set `sources.<key>` to `false` instead.
- Skip doctor when finishing a setup session.

If a value is missing, **ask**. Placeholders in `config.example.json` are not real identity.

## Prerequisites

| Tool | Why |
|------|-----|
| Python 3 | venv, ingest scripts, xtap |
| `claude` CLI on PATH | daily filing, podcast/likes synth, ledgers, briefs, ask |
| `grok` CLI (optional) | `ask.sh -m grok` |
| `gh` CLI, authenticated | GitHub source (if enabled) |
| Browser with logged-in X session | xtap bookmarks (+ YouTube for likes) |
| macOS (for launchd) or cron | daily job |
| **Obsidian** | browse/edit the vault (recommended) |
| **Claudian** (Obsidian plugin id `realclaudian`) | in-vault Claude agent (recommended); https://github.com/YishenTu/claudian |
| **Omnisearch** (plugin id `omnisearch`) | vault search; **bootstrap installs**; **Cmd/Ctrl+K** |
| **Ghostty Terminal** (plugin id `ghostty-terminal`) | embedded terminal; **bootstrap installs** |
| **Obsidian Web Clipper** | capture pages into `Clippings/` (recommended) |

Details and install notes: [[TOOLS]].

## Step 1. Clone and bootstrap

```bash
git clone https://github.com/ArtSabintsev/bootstrap-your-second-brain.git second-brain
cd second-brain
bash scripts/bootstrap.sh
```

Creates `config.json`, folders (`Profile/`, `Projects/`, `Log/`, Sources, …),
venv, installs xtap + deps, seeds Profile stubs, `todos.md`, secrets dir,
**downloads Obsidian plugins** (Omnisearch, Ghostty Terminal, Claudian), and
rewrites `scripts/com.brain.ingest.plist` to this clone path.

## Step 2. Fill `config.json`

Edit every live field. **Documentation for each field** lives in
`config.example.json` under `_fields` (agents: read `_fields` then write real
keys). Underscore keys are ignored by `scripts/config.py`.

| Field | Notes |
|-------|--------|
| `identity.name` | Display name in AI prompts. Required. |
| `identity.context` | One line for briefs (role, focus). |
| `identity.interests` | Short tags; expand in Profile. |
| `identity.git_emails` | Own commits for github source. |
| `identity.github_login` | GitHub username. |
| `identity.goodreads_user_id` | Numeric id; only if Goodreads on. |
| `identity.substack_feed` | Full RSS URL; only if Substack on. |
| `browser` | `brave`, `chrome`, `firefox`, … for xtap. |
| `secrets_dir` | Outside vault, e.g. `~/Developer/helpers`. |
| `podcasts.cutoff` | `YYYYMMDD` backfill floor. |
| `sources.*` | `true`/`false` per pipeline (see TOOLS.md). |

Disable sources you will not configure. Every `sources.*` key is honored by
`scripts/ingest-daily.sh`.

## Step 3. Secrets

Never put secrets in the vault or `config.json`. Layout under `secrets_dir`:

```
$secrets_dir/
  goodreads/
    rss-key          # single line; only if sources.goodreads is true
```

How to get the Goodreads key: account settings → RSS URL contains `key=`.
Put only the key value in `rss-key`. X auth uses browser cookies via xtap
(step 4), not a file here. See `secrets.example/README.md`.

## Step 4. Auth external accounts

```bash
# X / Twitter session for bookmarks (and often YouTube cookie jar ecosystem)
.venv/bin/xtap auth browser --browser "$(.venv/bin/python3 scripts/config.py browser)"
.venv/bin/xtap auth whoami

# GitHub (only if sources.github is true)
gh auth status   # or: gh auth login
```

## Step 5. Podcasts, Profile, recommended apps

```bash
$EDITOR scripts/podcasts/shows.json   # keep only shows you follow
```

Fill `Profile/00-overview.md` and `Profile/working-with-me.md` (agents load
these first).

Recommend the operator install (from TOOLS.md):

1. **Obsidian** → Open vault = this repo folder. After `bootstrap.sh`, Omnisearch / Ghostty Terminal / Claudian are in `.obsidian/plugins/` (vault search: **Cmd+K** / **Ctrl+K**). Turn off Restricted mode and enable community plugins if prompted.
2. **Obsidian Web Clipper** → save targets to `Clippings/`.

## Step 6. Doctor

```bash
bash scripts/doctor.sh
```

Critical FAILs for enabled sources must be fixed before relying on daily ingest.
WARN is acceptable for optional CLIs or disabled sources.

## Step 7. Daily job (macOS)

```bash
cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
```

Manual run: `bash scripts/ingest-daily.sh`

Env overrides: `BRAIN_PROCESS=0`, `BRAIN_X_DELETE=0`, `BRAIN_PODCASTS=0`,
`BRAIN_LIKES=0`.

## Step 8. Day-zero use

```bash
scripts/log.sh decision "stood up second brain"
scripts/ask.sh "what is in my Profile?"
# after People notes exist:
scripts/intelligence/brief.sh some-person-slug
```

Open the vault in Obsidian.

## Success criteria

| Horizon | Expect |
|---------|--------|
| Day 0 | doctor clean for enabled sources; Profile filled; ask works; Obsidian opens vault |
| Day 1 | ingest ran; Sources has captures or intentional skips |
| Week 1 | Library notes if podcasts/likes on; first brief or ledger |

## Troubleshooting

- **pull/push fails:** scripts use the **current branch**. Track `origin` for it.
- **Goodreads fails:** `identity.goodreads_user_id` + `$secrets_dir/goodreads/rss-key`.
- **X bookmarks empty:** re-run `xtap auth browser` while logged into X.
- **No Claude processing:** install/login `claude`; Sources still archive.
- **launchd silent:** `/tmp/brain.ingest.out.log` and `.err.log`.
- **Adding a source:** TOOLS.md → "How to add a new ingestor".
