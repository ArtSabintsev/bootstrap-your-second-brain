---
title: "Setup"
type: guide
updated: 2026-07-14
---

# Setup: bootstrap your second brain

Checklist for a human **or** an AI agent pointed at this repo. Complete steps
in order. Prefer `scripts/doctor.sh` after bootstrap to verify.

## For agents

You are standing up a personal vault, not answering a query. You **may**:

- write `config.json` from the operator's answers
- create/edit seed notes under `Profile/`
- write secret files only under the configured `secrets_dir` (never in the vault)
- edit `scripts/podcasts/shows.json`
- run `scripts/bootstrap.sh`, `scripts/doctor.sh`, and auth commands
- install launchd after rewriting the vault path

You **must not** commit secrets, push unless the operator says so, or invent
handles/IDs. Interview the operator for missing values.

## Prerequisites

| Tool | Why |
|------|-----|
| Python 3 | venv, ingest scripts, xtap |
| `claude` CLI on PATH | daily filing, podcast/likes synth, ledgers, briefs, ask |
| `grok` CLI (optional) | `ask.sh -m grok` |
| `gh` CLI, authenticated | GitHub source |
| Browser with logged-in X session | xtap bookmarks + YouTube likes cookies |
| macOS (for launchd) or cron | daily job |
| Obsidian (optional) | browse/edit the vault |

## Step 1. Clone and bootstrap

```bash
git clone https://github.com/ArtSabintsev/bootstrap-your-second-brain.git second-brain
cd second-brain
bash scripts/bootstrap.sh
```

This creates `config.json`, folder structure (`Profile/`, `Projects/`, `Log/`,
Sources, …), Python venv, installs `xtap` + deps, seeds Profile stubs, writes
`todos.md` if missing, creates the secrets dir, and rewrites the launchd plist
path to this clone.

## Step 2. Fill `config.json`

Edit every field. See `config.example.json`.

| Field | Notes |
|-------|--------|
| `identity.name` | Display name injected into AI prompts |
| `identity.context` | One line for briefs (role, focus) |
| `identity.interests` | Short tags; also seed Profile |
| `identity.git_emails` | Used to attribute GitHub commits |
| `identity.github_login` | GitHub username |
| `identity.goodreads_user_id` | Numeric id from Goodreads profile URL |
| `identity.substack_feed` | Full RSS URL, or leave placeholder and disable source |
| `browser` | `brave`, `chrome`, `firefox`, … (xtap cookie import) |
| `secrets_dir` | Outside the vault, e.g. `~/Developer/helpers` |
| `podcasts.cutoff` | `YYYYMMDD` backfill floor |
| `sources.*` | `true`/`false` per pipeline |

Disable sources you will not configure (`sources.goodreads: false`, etc.).

## Step 3. Secrets

Never put secrets in the vault or `config.json`. Layout under `secrets_dir`:

```
$secrets_dir/
  goodreads/
    rss-key          # single line: private RSS key from Goodreads
```

How to get the Goodreads key: Goodreads -> Account settings -> RSS (private
"all shelves" or per-shelf feed URL contains `key=`). Put only the key value
in `rss-key`.

X auth uses browser cookies via xtap (step 4), not a file in secrets_dir.

See also `secrets.example/README.md`.

## Step 4. Auth external accounts

```bash
# X / Twitter session for bookmarks
.venv/bin/xtap auth browser --browser "$(python3 scripts/config.py browser)"
.venv/bin/xtap auth whoami

# GitHub (for sources.github)
gh auth status
```

## Step 5. Podcasts and Profile

```bash
$EDITOR scripts/podcasts/shows.json   # keep only shows you follow
```

Fill the seed notes under `Profile/` (at least `00-overview.md` and
`working-with-me.md`). Agents load these before non-trivial answers.

## Step 6. Doctor

```bash
bash scripts/doctor.sh
```

Fix anything red. Yellow items are optional sources you disabled or soft deps.

## Step 7. Daily job (macOS)

```bash
# bootstrap already rewrote the path inside scripts/com.brain.ingest.plist
cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
```

Manual run:

```bash
bash scripts/ingest-daily.sh
```

Env overrides: `BRAIN_PROCESS=0`, `BRAIN_X_DELETE=0`, `BRAIN_PODCASTS=0`,
`BRAIN_LIKES=0`.

## Step 8. Day-zero use

```bash
scripts/log.sh decision "stood up second brain"
scripts/ask.sh "what is in my Profile?"
# after People notes exist:
scripts/intelligence/brief.sh some-person-slug
```

Open the vault folder in Obsidian.

## Success criteria

| Horizon | Expect |
|---------|--------|
| Day 0 | `doctor.sh` clean for enabled sources; Profile stubs filled; ask works |
| Day 1 | `ingest-daily` ran; Sources/ has captures or intentional skips; commit on remote if push path works |
| Week 1 | Library/podcasts or likes notes if those sources on; first brief or ledger |

## Troubleshooting

- **pull/push fails:** scripts use the **current branch** name. Stay on `master`
  or `main` and ensure `origin` tracks it.
- **Goodreads fails:** check `identity.goodreads_user_id` and
  `$secrets_dir/goodreads/rss-key`.
- **X bookmarks empty:** re-run `xtap auth browser` while logged into X.
- **No Claude processing:** install/login `claude` CLI; Sources still archive.
- **launchd silent:** check `/tmp/brain.ingest.out.log` and `.err.log`.
