---
title: "Secrets layout"
type: guide
updated: 2026-07-14
---

# Secrets (outside the vault)

Secrets never live in this git repo or in `config.json`. They live in the
directory named by `config.json` -> `secrets_dir` (default `~/Developer/helpers`).

## Expected layout

```
$secrets_dir/
  goodreads/
    rss-key          # required if sources.goodreads is true
```

### goodreads/rss-key

1. Open Goodreads in a browser while logged in.
2. Account settings -> find your private RSS feed URL for a shelf or all shelves.
3. The URL looks like:
   `https://www.goodreads.com/review/list_rss/USER_ID?key=THE_KEY&shelf=...`
4. Put `USER_ID` in `config.json` as `identity.goodreads_user_id`.
5. Put only `THE_KEY` (one line, no quotes) in `$secrets_dir/goodreads/rss-key`.

If you do not use Goodreads, set `sources.goodreads` to `false` and skip this file.

## What is not a file here

| Secret | Where it lives |
|--------|----------------|
| X / Twitter session | Browser cookies imported by `xtap auth browser` into `~/.xtap/` |
| GitHub auth | `gh auth login` |
| Claude / Grok API | Whatever the respective CLIs use (not this vault) |

## Rules

- Never commit files from `secrets_dir`.
- Never paste keys into notes under Sources/, Profile/, or Drafts/.
- Reference secrets by path only when documenting setup.

## google-drive/ (only if sources.google_drive_meetings is true)

- `google-drive/client_secret.json` — OAuth client credentials JSON from the
  Google Cloud console (Drive API, desktop app).
- `google-drive/token.json` — refresh token; written by
  `scripts/google_drive_auth.py` after the one-time browser authorization.
