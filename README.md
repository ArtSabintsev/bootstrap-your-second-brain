# bootstrap-your-second-brain

An AI-maintained second brain: an Obsidian vault plus the automation that keeps
it fed, synthesized, and queryable. Clone it, fill in one config file, run one
script, and a daily job pulls from your accounts, uses an LLM to synthesize what
actually matters, and files it into an interlinked knowledge graph you can ask
questions of in plain language.

Nothing about you is hardcoded. Your identity comes from `config.json` and
`Profile/`. Your notes are plain Markdown in a git repo you own, so any tool
(Obsidian, Claude Code, Grok, Codex) can read and write them.

**Full setup (human or AI agent):** see [SETUP.md](SETUP.md).  
**Vault contract for agents:** see [AGENTS.md](AGENTS.md).

## The idea, and why it is not a RAG chatbot

Most "chat with your notes" tools do retrieval-augmented generation: you dump
files in, the model retrieves chunks at query time, and answers from scratch on
every question. Nothing accumulates. Ask something that needs five documents and
the model re-finds and re-reasons them every single time.

This system does the opposite. An LLM builds and maintains a persistent,
interlinked wiki that sits between you and the raw sources. When a new source
arrives, the model reads it, extracts what matters, and integrates it into the
existing notes: updating entity pages, noting where it contradicts an older
claim, strengthening or challenging the running synthesis. Knowledge is compiled
once and kept current, not re-derived per query.

Then it goes one step past that, which is what turns it from an archive into a
decision instrument:

- **Position ledgers.** For recurring people, it tracks how their views moved
  over time, dated, with citations. Not "what does X think" but "X was a skeptic
  in 2023 and had capitulated by 2026, here is the arc, here is the next reversal
  to watch."
- **Theses.** Your own positions, each with a dated timeline and a
  counter-evidence queue, so the system can flag when a new source pressures
  something you believe.
- **Briefs.** Before a meeting or a decision, one command produces a read on a
  person, company, or theme: their arc, their reversals, how it collides with
  your theses, an ask list, and kill criteria.
- **Profile + Log.** Who you are (loaded before non-trivial answers) and an
  append-only decision journal ("log this") so the brain compounds from both
  passive capture and intentional writeback.

That is the difference between a pile of notes and a brain.

## Architecture

Four layers. Data flows one direction.

```
            config.json  (identity, source toggles, secrets_dir)
                 |  read by scripts/config.py
                 v
SOURCES  -ingest->  Sources/ (immutable raw)  -Claude filing pass->  wiki notes
 X bookmarks (xtap)                                                Topics/ People/
 Goodreads RSS                                                     Library/ Projects/
 Substack feed                                                     Profile/ Log/
 GitHub commits
 Podcasts (yt-dlp)  -synth (AI)->  Library/podcasts/       ┐
 YouTube likes      -synth (AI)->  Library/youtube-likes/  +-build_links-> _indexes/
                                                           ┘
INTELLIGENCE   build_ledger.sh (AI) -> People/ position ledgers
               brief.sh       (AI) -> Briefs/ pre-engagement briefs
               lint.py             -> _indexes/lint-report.md
                 |
INTERFACE      ask.sh / log.sh (AI + journal) -> answers with [[citations]]
               Obsidian    -> browse and edit the vault directly
```

## Bootstrap (quick)

```bash
git clone https://github.com/ArtSabintsev/bootstrap-your-second-brain.git second-brain
cd second-brain
bash scripts/bootstrap.sh

# then:
# 1. edit config.json
# 2. place secrets (see secrets.example/README.md)
# 3. fill Profile/
# 4. xtap auth + gh auth as needed
bash scripts/doctor.sh

cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
```

Point an AI agent at this repo and say "follow SETUP.md and bootstrap my second
brain" if you want the interview-and-configure path.

## Day-to-day

```bash
scripts/ask.sh "what am I tracking on stablecoins?"
scripts/ask.sh -m grok "who disagrees with my AI thesis?"
scripts/log.sh decision "killed idea X because Y"
scripts/intelligence/brief.sh some-person-slug
bash scripts/doctor.sh
```

## Prerequisites

- Python 3 (venv created by `bootstrap.sh`)
- `claude` CLI on PATH (and optionally `grok`) for AI steps
- `gh` CLI, authenticated, if `sources.github` is on
- `yt-dlp` (installed by bootstrap) for podcast and YouTube transcripts
- Browser with a logged-in X session (for xtap and YouTube-likes)
- macOS launchd for the daily job, or adapt `ingest-daily.sh` to cron
- Obsidian to browse and edit (optional but intended)

## Layout

```
SETUP.md              full bootstrap walkthrough (human + AI)
config.example.json   copy to config.json (gitignored)
secrets.example/      documents secrets_dir layout (no real secrets)
AGENTS.md             vault contract for agents
CLAUDE.md / GROK.md / CODEX.md   thin entry points -> AGENTS.md
scripts/
  bootstrap.sh        one-time setup + Profile seeds + plist path
  doctor.sh           health checks for config, sources, CLIs
  lib.sh              shared helpers (branch, source toggles)
  ingest-daily.sh     daily orchestrator (honors config.sources)
  ask.sh              query the vault
  log.sh              append to Log/YYYY-MM-DD.md
  ontology.yaml       closed canonical-concept registry
  intelligence/       ledgers, briefs, lint
  podcasts/ youtube_likes/ sources/
tools/xtap/           vendored X CLI
Profile/ Projects/ Log/ Sources/ Topics/ People/ Theses/
Library/ Briefs/ Drafts/ Clippings/ _indexes/
```

## Privacy and data ownership

- Secrets never live in the vault or config. They stay in `secrets_dir`.
- The vault is plain Markdown in a git repo you control.
- AI steps send content to whichever model the CLIs use. Point them at your own
  keys or local models for sensitive material.

## Status

Working system, extracted from a private personal vault and stripped of content.
Config-driven so it runs for anyone. The intelligence layer under
`scripts/intelligence/` is the novel part: ledgers, theses, and briefs that track
how thinking changes over time.
