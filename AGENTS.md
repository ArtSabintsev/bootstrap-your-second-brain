---
title: "Vault contract"
type: schema
updated: 2026-07-14
---

# AGENTS.md - Vault contract

This repo is a config-driven "second brain": an Obsidian vault plus the
automation that keeps it fed and useful. It is also the persistent memory the
operator's agents (Claude Code, Grok CLI, Codex) load for context. "The
operator" is whoever cloned and configured this repo; their identity, handles,
and interests come from `config.json` (see Bootstrap / SETUP.md), never hardcoded.

## Structure

```
README.md    <- Home / Map of Content (Obsidian-friendly)
SETUP.md     <- human + AI bootstrap walkthrough (setup intent)
TOOLS.md     <- Obsidian / Claudian / Web Clipper + scrapers + how to extend
Profile/     <- who the operator is: identity, work, beliefs, working-with-me
Projects/    <- one note per thing the operator builds or runs
Topics/      <- canonical concepts only (governed by scripts/ontology.yaml)
People/      <- one note per person; core people carry a position ledger
Theses/      <- the operator's own evolving positions, dated, with counter-evidence
Library/     <- processed reading and references (incl. podcasts/, youtube-likes/)
Briefs/      <- generated pre-engagement briefs (query answers, filed back)
Digests/     <- generated morning digests: what got filed, added, updated each day
Log/         <- append-only dated operator journal (decisions, lessons, ideas)
Sources/     <- IMMUTABLE raw inputs: capture archive, feed pulls, X bookmarks
_indexes/    <- machine-readable graph (appearances.json), lint reports
Clippings/   <- inbox: Obsidian Web Clipper + mobile write here
Drafts/      <- the operator's own writing in progress (posts, essays)
tools/       <- vendored code (e.g. xtap); install into .venv; state outside vault
scripts/     <- automation entry points; scripts/intelligence/ is the brain layer
todos.md     <- open actions
```

Folder names are Title Case so humans can browse them in Obsidian. Filenames
are kebab-case. Notes use YAML frontmatter + `[[wikilinks]]` so agents and
Obsidian share one graph.

## Session bootstrap (load before you answer)

On every non-trivial interactive session (strategy, prioritization, drafting in
the operator's name, briefs, "what should I do", anything that depends on who
they are):

1. Read `Profile/00-overview.md` and `Profile/working-with-me.md` first (if they exist).
2. Pull other `Profile/` notes as needed (`identity`, career/goals, interests).
3. Prefer vault + Profile + Theses over generic model knowledge.

Do not invent the operator's identity from training data when Profile notes or
`config.json` exist. The vault wins.

Thin queries that are pure vault lookups (a specific note, a person ledger
slug) can skip the full Profile pass, but still follow standing voice rules.

## If asked to bootstrap this repo

This is a first-class intent for Claude Code, Codex, Grok, GLM-class agents,
and Claudian. Follow **SETUP.md** end to end; use **TOOLS.md** for app and
scraper recommendations.

You **may**: write `config.json` (field docs in `config.example.json` `_fields`),
seed `Profile/`, place secret files only under `secrets_dir`, edit
`scripts/podcasts/shows.json`, run `scripts/bootstrap.sh` and
`scripts/doctor.sh`, install launchd after path rewrite.

You **must**: interview for handles/IDs; disable sources the operator will not
configure; stop and ask for secrets rather than inventing them; run doctor and
fix FAILs for enabled sources.

You **must not**: commit secrets into the vault, invent credentials, or push
unless the operator explicitly says to push.

## Intelligence layer (not an archive)

The vault is a decision instrument, not a pile of metadata. Consolidation rules:

- **Topics are closed.** Only concepts in `scripts/ontology.yaml` get a note.
  Agents propose additions; they never auto-mint. Unmatched ideas stay as
  claims on the episode note, not new stubs. The operator grows the ontology
  over time.
- **The graph is an index, not prose.** `scripts/podcasts/build_links.py` writes
  `_indexes/appearances.json` (people/topics -> episodes). No markdown minting.
- **Evolution of thought is the point.** Core people get a dated **position
  ledger** (`scripts/intelligence/build_ledger.sh`): stance-by-theme over time
  with an arc and the next reversal to watch. `Theses/` holds the operator's own
  positions the same way.
- **The highest-value output** is the pre-engagement **brief**
  (`scripts/intelligence/brief.sh <slug>`): it graph-traverses, reads the
  target's ledger and the operator's theses, and answers "what did they claim
  over time, where did they reverse, does it confirm or pressure my theses" plus
  asks + kill criteria. Briefs are filed to `Briefs/` so explorations compound.
- **Lint** (`scripts/intelligence/lint.py`) periodically flags ledger gaps,
  ontology drift, dead concepts, and stale theses -> `_indexes/lint-report.md`.

## Operator log (`Log/`)

Append-only dated journal for decisions, lessons, killed ideas, and "remember
this" moments. Not a second Topics tree and not a substitute for Theses.

- File path: `Log/YYYY-MM-DD.md` (one file per day; create if missing).
- Standing phrases that authorize a write without further permission:
  - "log this" / "log this to my second brain"
  - "remember this" / "remember this decision"
  - "kill this idea" (log as a kill, with reason if given)
- Allowed write surface for those phrases: **`Log/` only**, plus optional
  checkboxes on `todos.md` if the entry implies an open action.
- Do **not** mint Topics, edit Sources, or rewrite Profile/Theses from a log
  command. Promote repeated log themes into Theses or Profile only when the
  operator explicitly asks.
- Entry shape:

  ```
  - **decision|lesson|idea|kill** (HH:MM): <one dense line>
  ```

CLI: `scripts/log.sh [decision|lesson|idea|kill] <text>` appends to today's file.

Ideas without a log command still go to `Clippings/` or `Drafts/`, not a
parallel Ideas/ folder.

## Ask the brain

`scripts/ask.sh [-m claude|grok] "question"` routes a question to a CLI agent,
answered against the vault with citations. No vector database: the agent greps
and reads selectively. `-s` saves the answer to `Briefs/`.

## Bootstrap (fork your own brain)

Per-user values live in `config.json` (identity, browser, models, podcast
cutoff, which sources are enabled), copied from `config.example.json`. Secrets
never go in the vault or the config; they live in the `secrets_dir` (default
`~/Developer/helpers`). Full checklist: `SETUP.md`. Quick path:
`bash scripts/bootstrap.sh`, edit `config.json`, add secrets, auth X, run
`scripts/doctor.sh`, install the daily job. Every ingest script reads
`config.json` via `scripts/config.py`.

## Automation

`scripts/ingest-daily.sh` runs daily via launchd (`com.brain.ingest`, 08:00).
Sources run independently (each toggled in `config.json` under `sources`), then
one Claude pass files substantive items into the wiki and one local commit
records everything. It syncs with the remote (pull --rebase before running, push
when done) on the **current git branch** (master or main) and never mutates the
external accounts except optional X-bookmark cleanup after successful process.

- **X bookmarks** - vendored xtap CLI (`tools/xtap`; cookies and snapshots stay
  in `~/.xtap/`) -> `Sources/x-bookmarks/`
- **Goodreads** - private all-shelves RSS (key in the `secrets_dir`, never in the
  vault) -> `Sources/goodreads/`, one entry per (book, shelf-state)
- **Substack** - the operator's publication feed (`identity.substack_feed`) ->
  one archival note per published essay under `Sources/substack/`
- **GitHub** - the operator's own recent commits via the `gh` CLI ->
  `Sources/github/`; the daily pass folds these into `Projects/` so the vault
  tracks what is actively being built
- **Podcasts** - YouTube auto-captions for the shows in
  `scripts/podcasts/shows.json`. Each episode gets a deep-synthesis note under
  `Library/podcasts/<show>/`; recurring guests become `People/` notes and
  recurring themes become threaded `Topics/` notes. Notes-only: transcripts are
  cleaned in a tmp dir and discarded, never committed. Ads and sponsor reads are
  stripped at synthesis. `scripts/podcasts/backfill.sh` does the one-time
  backlog; the daily job picks up new episodes.
- **YouTube likes** - the Liked-videos playlist is pulled live each run (no
  stored catalog; the synthesized notes plus `.status/youtube-likes-skip.log`
  are the watermark). Only substantive long-form videos get a
  `Library/youtube-likes/` note; music, gameplay, comedy, and kids' content are
  judged out and skipped. Shares the podcast YouTube-access lock so the two
  never throttle each other.

Filing items from these daily captures is standing-authorized; rule 4 still
governs everything else in `Clippings/`.

## Skills

Agents working this vault should use the skill that fits the task rather than
improvising: a `writer`/publishing skill for any drafted prose (always run the
voice gate, no em-dashes), analysis and visual-output skills for data and
slides, and a peer-consult skill for cross-model review. The originality/voice
gates are mandatory for anything published under the operator's name.

## Rules

1. **Query is read-only by default.** Answer from the vault and cite notes. Do
   not write new notes unless the operator explicitly asks, **except** the
   standing log phrases (append to `Log/` only), bootstrap/setup when asked, and
   the daily ingest filing pass.
2. **Sources/ is immutable.** Never edit anything under it.
3. **Never rewrite note bodies.** When asked to file or restructure, you may
   add frontmatter, tags, and wikilinks, and re-file or re-title notes. Body
   text stays verbatim unless the operator asks for edits to a specific note.
   `Log/` entries are append-only; do not rewrite prior log lines.
4. **Clippings/ is the operator's inbox.** File a clipping into the right folder
   only when asked; archive the original under `Sources/` when you do.
5. **Commit when a unit of work is done. Never push unless the operator says to.**
   Standing exception: the daily ingest job pulls --rebase before running and
   pushes when done.
6. **Secrets never enter the vault.** Live credentials stay in the `secrets_dir`;
   reference by pointer only.
7. **No em dashes in drafted prose** (standing rule).

## Conventions

- Frontmatter on every content note: `title`, `tags`, `created`, `updated`,
  plus `aliases` and `source` (original URL) when they apply.
- Tags come from this exact list: `ai-agents` `ai-coding` `ai-enablement`
  `agent-memory` `ventures` `crypto` `bitcoin` `privacy` `sovereignty`
  `philosophy` `history` `science` `productivity`, with `unsorted` as the only
  fallback. The operator owns this list; extend it deliberately, in step with
  `scripts/ontology.yaml`.
- Link with `[[wikilinks]]` (basename, optional `|label`). Kebab-case
  filenames. One concept per note; prefer many small interlinked notes.

`CLAUDE.md`, `GROK.md`, and `CODEX.md` all forward here. Edit this file only.
