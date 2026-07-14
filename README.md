---
title: "Home"
type: index
updated: 2026-07-14
---

# bootstrap-your-second-brain

An AI-maintained second brain: an Obsidian vault plus the automation that keeps
it fed, synthesized, and queryable. Point Claude Code, Codex, Grok, GLM, or
Claudian at this repo and say **"set up my second brain"** — the agent should
follow [[SETUP]] end to end.

Nothing about you is hardcoded. Identity comes from `config.json` and
`Profile/`. Notes are plain Markdown in a git repo you own.

| Start here | Purpose |
|------------|---------|
| [[SETUP]] | Bootstrap path (human + every agent harness) |
| [[TOOLS]] | Obsidian, Claudian, Omnisearch, Web Clipper, scrapers, adding ingestors |
| [[AGENTS]] | Vault contract agents must load |
| `config.example.json` | Field docs in `_fields`; copy → `config.json` |

## Recommended tools

- **[Obsidian](https://obsidian.md)** — open this folder as the vault (Title Case
  dirs are for human browsing).
- **[Claudian](https://github.com/YishenTu/claudian)** (Community Plugins id: `realclaudian`) — Claude agent chat
  inside Obsidian against the same files.
- **[Omnisearch](https://github.com/scambier/obsidian-omnisearch)** — vault search (shipped). Hotkey: **Cmd+K** / **Ctrl+K**.
- **[Obsidian Web Clipper](https://obsidian.md/clipper)** — save pages into
  `Clippings/` (inbox; file when you ask).
- Terminal agents load `CLAUDE.md` → `AGENTS.md` (Grok/Codex symlinks included).

Full stack and scraper catalog: [[TOOLS]].

## The idea (not a RAG chatbot)

Most "chat with your notes" tools re-retrieve chunks every time. This system
compiles a persistent wiki: new sources are filed once with links, ledgers, and
theses that evolve. Then:

- **Position ledgers** — how a person's views moved over time
- **Theses** — your positions with counter-evidence queues
- **Briefs** — pre-engagement reads with asks and kill criteria
- **Profile + Log** — who you are (loaded first) and dated decisions ("log this")

## Architecture

```
config.json  (identity, source toggles, secrets_dir)
     |
SOURCES -ingest-> Sources/ (immutable) -Claude file-> Topics/ People/ Library/ Projects/
 Podcasts/likes  -synth-> Library/  -build_links-> _indexes/
INTELLIGENCE: ledger / brief / lint
INTERFACE: ask.sh, log.sh, Obsidian, Claudian
```

Built-in sources (each toggleable): X bookmarks (xtap), Goodreads, Substack,
GitHub, podcasts, YouTube likes. How each works and how to add more: [[TOOLS]].

## Bootstrap (quick)

```bash
git clone https://github.com/ArtSabintsev/bootstrap-your-second-brain.git second-brain
cd second-brain
bash scripts/bootstrap.sh
# edit config.json, secrets, Profile; then:
bash scripts/doctor.sh
# install launchd when green (path already rewritten by bootstrap)
cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
```

Agent path: *"Follow SETUP.md and bootstrap my second brain. Interview me for
config. Do not invent secrets. Do not push unless I say so."*

## Day-to-day

```bash
scripts/ask.sh "what am I tracking on stablecoins?"
scripts/log.sh decision "killed idea X because Y"
scripts/intelligence/brief.sh some-person-slug
bash scripts/doctor.sh
```

## Layout

```
SETUP.md TOOLS.md AGENTS.md README.md
config.example.json   → config.json (gitignored; _fields document every key)
secrets.example/      secrets_dir layout (no real secrets)
CLAUDE.md / GROK.md / CODEX.md   harness entry → AGENTS.md
scripts/  bootstrap doctor ingest-daily ask log lib config
  intelligence/ podcasts/ youtube_likes/ sources/
tools/xtap/           vendored X CLI (state in ~/.xtap/)
Profile/ Projects/ Log/ Sources/ Topics/ People/ Theses/
Library/ Briefs/ Drafts/ Clippings/ _indexes/
tests/                agent-readiness checks (run: python3 -m unittest)
```

## Privacy

Secrets never live in the vault or config. AI steps use your installed CLIs'
credentials. Leave the tools and you still own the Markdown git history.

## Status

Working system, extracted from a private vault and stripped for forks. The
intelligence layer under `scripts/intelligence/` tracks how thinking changes
over time; TOOLS.md explains how to grow scrapers without breaking that contract.
