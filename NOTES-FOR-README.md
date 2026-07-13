# Notes for the README (raw material, not the README itself)

This file is scaffolding for whoever writes `README.md`. It inventories every
component that was extracted, the data flow, and exactly where AI is invoked.
Turn it into the README; do not ship it as-is.

## What this repo is

A config-driven "second brain": an Obsidian vault plus the automation that keeps
it fed and useful. Clone it, fill in `config.json`, run `bootstrap.sh`, and a
daily job pulls from your accounts, synthesizes what matters with an LLM, and
files it into an interlinked knowledge graph you can query in plain language.
Nothing about the operator is hardcoded; identity comes from `config.json`.

## Components (every file copied, with its one-line purpose)

### Root
- `config.example.json` - the template config. Copy to `config.json` (gitignored)
  and fill in identity, browser, secrets dir, models, podcast cutoff, and which
  sources are enabled.
- `.gitignore` - ignores `config.json`, `.venv/`, `.status/`, `__pycache__/`,
  `_indexes/*` (keeps `.gitkeep`), and `.obsidian/`.
- `AGENTS.md` - the vault contract: schema, intelligence layer, automation,
  rules, conventions. Single source of truth for agents.
- `CLAUDE.md` / `GROK.md` - thin entry points that forward to `AGENTS.md`
  (`GROK.md` is a symlink to `CLAUDE.md`).

### scripts/ (automation entry points)
- `config.py` - per-user config loader. Reads `config.json` (falls back to
  `config.example.json`); usable from Python (`from config import get`) and shell
  (`config.py identity.name`). This is how the operator's identity is injected
  into every script and prompt.
- `bootstrap.sh` - one-time setup: creates `config.json`, the folder structure,
  the `.venv`, installs the vendored xtap CLI and Python deps, and the secrets
  dir. Idempotent.
- `ingest-daily.sh` - the daily orchestrator (run by launchd). Runs each enabled
  source, then one Claude filing pass, then commits and pushes; then pulls new
  podcast episodes and YouTube likes. **Invokes AI** (see below).
- `ask.sh` - query the vault in plain language via Claude or Grok, with
  citations, no vector DB. **Invokes AI.**
- `com.brain.ingest.plist` - launchd job that runs `ingest-daily.sh` daily at
  08:00 (edit the path to your clone before installing).
- `ontology.yaml` - the closed canonical-concept registry. A small generic
  starter; the operator grows it. Governs which Topics/ notes may exist.

Source ingesters (each appends to an immutable `Sources/` subfolder):
- `x_bookmarks_ingest.py` - ingest the newest xtap X-bookmarks snapshot into
  `Sources/x-bookmarks/`, deduped by status URL.
- `x_bookmarks_cleanup.py` - after items are archived AND processed, delete those
  bookmarks from X (archive-then-remove; never deletes unarchived ones).
- `sources/x-bookmarks.sh` - snapshot X via xtap, then run the ingester.
- `goodreads_ingest.py` - pull the private all-shelves Goodreads RSS into
  `Sources/goodreads/`, one entry per (book, shelf-state).
- `substack_ingest.py` - archive the operator's published Substack essays into
  `Sources/substack/`, one note per post.
- `github_ingest.py` - capture the operator's own recent commits (via `gh`) into
  `Sources/github/`; the daily pass folds them into `Projects/`.

Podcasts (`scripts/podcasts/`):
- `shows.json` - the public podcast list to track (All-In, Lex Fridman, a16z,
  Dwarkesh, Naval, The Network State). Kept as shipped; edit for your shows.
- `enumerate_inrange.py` - list a show's in-range episodes as TSV.
- `fetch_transcript.py` - fetch one video's date, title, and cleaned transcript
  via yt-dlp.
- `synth_episode.sh` - Phase 1 worker: deep-synthesize ONE episode into its own
  note (parallel-safe, writes only that note). **Invokes AI.**
- `build_links.py` - Phase 2: scan all episode/video notes and build
  `_indexes/appearances.json` (people/topics -> episodes). Index, not prose.
- `backfill.sh` - two-phase backfill driver (parallel synth, then link build);
  restartable, self-commits.
- `master_backfill.sh` - strict-sequential driver paced around YouTube rate
  limits for the full backlog.

YouTube likes (`scripts/youtube_likes/`):
- `select_candidates.py` - pull the live Liked-videos playlist, keep long-form
  (>=20 min) not-yet-handled videos, emit as TSV.
- `synth_like.sh` - judge ONE liked video and synthesize a note only if it is
  substantive (skips music/gameplay/comedy/kids). **Invokes AI.**
- `run.sh` - run the like-synth workers in parallel; restartable, self-commits.

Intelligence layer (`scripts/intelligence/`):
- `person_claims.py` - dump a person's dated claims across all their appearances
  (reads the index + note sections; never whole transcripts).
- `brief_context.py` - assemble context for a brief: the target's ledger/claims,
  graph neighbors (co-appearances), and the operator's active theses.
- `build_ledger.sh` - build/refresh a person's dated position ledger (stance by
  theme over time, with an arc). **Invokes AI.**
- `brief.sh` - generate a pre-engagement brief on a person/company/theme: arc,
  reversals, thesis collision, ask list, kill criteria. **Invokes AI.**
- `lint.py` - deterministic health check: flags ledger gaps, ontology drift,
  dead concepts, stale theses -> `_indexes/lint-report.md`. No AI.

### tools/xtap/ (vendored X CLI)
A self-contained package (`src/xtap/`, `pyproject.toml`, `README.md`, `LICENSE`)
that taps X via your logged-in browser session: archive bookmarks/tweets/likes,
search, and serve as a RAG source. Installed into the vault venv by
`bootstrap.sh`. Data and cookies live in `~/.xtap/`, never in the vault.

## Data flow

```
                    config.json (identity, toggles, secrets_dir)
                             |  read by config.py
                             v
SOURCES  ──ingest──▶  Sources/ (immutable raw)  ──Claude filing pass──▶  wiki notes
 X bookmarks (xtap)                                                      Topics/ People/
 Goodreads RSS                                                          Library/ Projects/
 Substack feed
 GitHub commits
 Podcasts (yt-dlp) ──synth (AI)──▶ Library/podcasts/  ─┐
 YouTube likes    ──synth (AI)──▶ Library/youtube-likes/ ├─build_links.py─▶ _indexes/appearances.json
                                                          ┘
                                                              │
INTELLIGENCE   build_ledger.sh (AI) ─▶ People/ position ledgers
               brief.sh (AI) ─▶ Briefs/ pre-engagement briefs
               lint.py ─▶ _indexes/lint-report.md
                                                              │
INTERFACE      ask.sh (AI) ─▶ answers with [[citations]]  ◀───┘
               Obsidian (browse/edit the vault directly)
```

Stages: **sources → ingest (Sources/) → synthesis + filing (wiki + indexes) →
intelligence (ledgers, briefs, lint) → interface (ask, Obsidian).**

## Where AI is invoked (which scripts call an LLM, and for what)

All calls shell out to the `claude` CLI (one uses `grok` as an alternative); the
operator's identity is injected into the prompt from `config.json` via
`config.py`. Model defaults to `claude-sonnet-5`, overridable per script by env
var.

1. `scripts/ingest-daily.sh` - a single Claude pass over new `Sources/` captures:
   follows links (WebFetch), researches (WebSearch), analyzes second-order
   implications, and files substantive items into the wiki with frontmatter,
   tags, and wikilinks.
2. `scripts/podcasts/synth_episode.sh` - Claude turns one podcast transcript into
   a deep note (guests, core claims, notable segments, threads); ads stripped.
3. `scripts/youtube_likes/synth_like.sh` - Claude first judges whether a liked
   video is substantive, then synthesizes a note if so (else SKIP).
4. `scripts/intelligence/build_ledger.sh` - Claude builds a person's dated
   position ledger from their claims digest.
5. `scripts/intelligence/brief.sh` - Claude writes a pre-engagement brief from
   the assembled context (ledger, graph neighbors, theses).
6. `scripts/ask.sh` - Claude (or Grok) answers an arbitrary question against the
   vault with citations.

Deterministic, non-AI scripts: all `*_ingest.py`, `config.py`, `build_links.py`,
`enumerate_inrange.py`, `fetch_transcript.py`, `select_candidates.py`,
`person_claims.py`, `brief_context.py`, `lint.py`, and the xtap CLI.

## Prerequisites the README should list

- Python 3 (venv created by `bootstrap.sh`), and the vendored xtap install.
- The `claude` CLI (and optionally `grok`) on PATH for every AI step.
- The `gh` CLI authenticated for the GitHub source.
- `yt-dlp` (installed by bootstrap) for podcast/YouTube transcripts.
- A browser with a logged-in X session for xtap and YouTube-likes pulls.
- macOS launchd for the daily job (or adapt to cron on Linux).
- Obsidian to browse/edit the vault (optional but intended).
