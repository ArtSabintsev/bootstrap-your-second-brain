# bootstrap-your-second-brain

An AI-maintained second brain: an Obsidian vault plus the automation that keeps
it fed, synthesized, and queryable. Clone it, fill in one config file, run one
script, and a daily job pulls from your accounts, uses an LLM to synthesize what
actually matters, and files it into an interlinked knowledge graph you can ask
questions of in plain language.

Nothing about you is hardcoded. Your identity comes from `config.json`. Your
notes are plain Markdown in a git repo you own, so any tool (Obsidian, Claude
Code, Grok, an Obsidian plugin) can read and write them.

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

That is the difference between a pile of notes and a brain.

## Architecture

Four layers. Data flows one direction.

```
            config.json  (identity, source toggles, secrets_dir)
                 |  read by scripts/config.py
                 v
SOURCES  ─ingest→  Sources/ (immutable raw)  ─Claude filing pass→  wiki notes
 X bookmarks (xtap)                                                Topics/ People/
 Goodreads RSS                                                     Library/ Projects/
 Substack feed
 GitHub commits
 Podcasts (yt-dlp)  ─synth (AI)→  Library/podcasts/       ┐
 YouTube likes      ─synth (AI)→  Library/youtube-likes/  ├─build_links→ _indexes/appearances.json
                                                          ┘
INTELLIGENCE   build_ledger.sh (AI) → People/ position ledgers
               brief.sh       (AI) → Briefs/ pre-engagement briefs
               lint.py             → _indexes/lint-report.md
                 |
INTERFACE      ask.sh (AI) → answers with [[citations]]
               Obsidian    → browse and edit the vault directly
```

1. **Sources.** Passive capture from where you already are: X bookmarks,
   Goodreads shelves, your Substack posts, your GitHub commits, podcasts, and
   YouTube likes. Everything lands in `Sources/`, which is immutable. That is the
   raw record, never rewritten.
2. **Ingest and synthesis.** A daily LLM pass reads the new captures, follows
   their links, researches context, and files the substantive ones into the wiki
   with tags and wikilinks. Podcasts and long-form videos get deep-synthesized
   into structured notes (guests, dated claims, notable segments, ads stripped).
3. **Intelligence.** Deterministic code builds a people-and-topics graph index;
   the LLM builds position ledgers and briefs; a lint pass reports what needs
   attention.
4. **Interface.** Ask the vault anything in plain language (Claude or Grok), or
   open it in Obsidian and browse the graph.

## Where the AI does the work, and where it does not

The LLM does judgment and synthesis. Deterministic code does the plumbing. There
is no vector database. Retrieval is agentic grep-and-read: the model searches the
files selectively, which is cheaper and needs no embedding infrastructure.

Six places call an LLM (all shell out to the `claude` CLI; `ask.sh` also
supports `grok`). Your identity is injected into each prompt from `config.json`:

1. `scripts/ingest-daily.sh` runs the daily pass over new captures. It follows
   links, researches context, analyzes second-order implications, and files the
   substantive items with frontmatter and wikilinks.
2. `scripts/podcasts/synth_episode.sh` turns one transcript into a deep note.
3. `scripts/youtube_likes/synth_like.sh` judges whether a liked video is
   substantive, then synthesizes a note only if it is.
4. `scripts/intelligence/build_ledger.sh` builds a person's dated position ledger.
5. `scripts/intelligence/brief.sh` writes a pre-engagement brief.
6. `scripts/ask.sh` answers an arbitrary question against the vault, with citations.

Everything else is plain code with no AI: the source ingesters, the graph index
(`build_links.py`), transcript fetching, candidate selection, and the lint pass.
Keeping synthesis in the model and plumbing in code is what keeps it debuggable
and cheap.

## Privacy and data ownership

- Secrets (API keys, RSS keys, cookies) never live in the vault or the config.
  They stay in a `secrets_dir` outside the repo. `config.json` is gitignored.
- The vault is plain Markdown in a git repo you control, not a proprietary format
  and not a cloud service. If you stop using this, your brain is still yours.
- The AI steps send content to whichever model you configure. Point them at your
  own key, or a local model, for anything sensitive.

## Bootstrap

```bash
git clone <this-repo> second-brain && cd second-brain
bash scripts/bootstrap.sh     # creates config.json, the venv, installs xtap + deps, folder structure

$EDITOR config.json           # your name, context, interests, handles, browser
# put secrets in your secrets_dir (e.g. the Goodreads RSS key)
.venv/bin/xtap auth browser --browser <your-browser>   # log your X session into the tool
$EDITOR scripts/podcasts/shows.json                    # the shows you follow

# install the daily job (macOS launchd; edit the path in the plist first):
cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
```

Then use it:

```bash
scripts/ask.sh "what am I tracking on stablecoins?"      # query via Claude
scripts/ask.sh -m grok "who disagrees with my AI thesis?" # or Grok
scripts/intelligence/brief.sh some-person-slug            # a pre-engagement brief
```

Or open the vault in Obsidian and browse. For a chat sidebar that runs the same
`claude` agent inside Obsidian, install the community plugin "Claudian."

## Prerequisites

- Python 3 (the venv is created by `bootstrap.sh`).
- The `claude` CLI on PATH (and optionally `grok`) for the AI steps.
- The `gh` CLI, authenticated, for the GitHub source.
- `yt-dlp` (installed by bootstrap) for podcast and YouTube transcripts.
- A browser with a logged-in X session (for `xtap` and YouTube-likes pulls).
- macOS launchd for the daily job, or adapt `ingest-daily.sh` to cron on Linux.
- Obsidian to browse and edit the vault (optional but intended).

## Layout

```
config.example.json   copy to config.json (gitignored) and fill in
AGENTS.md             the vault contract: schema, rules, intelligence layer
CLAUDE.md / GROK.md   thin entry points that forward to AGENTS.md
scripts/              all automation (see "Where the AI does the work")
  config.py           per-user config loader
  bootstrap.sh        one-time setup
  ingest-daily.sh     the daily orchestrator
  ask.sh              query the vault
  ontology.yaml       the closed canonical-concept registry (you grow it)
  intelligence/       ledgers, briefs, lint (the decision layer)
  podcasts/ youtube_likes/ sources/   the ingest + synthesis pipelines
tools/xtap/           vendored CLI that taps X (archive, search, RAG source)
Sources/ Topics/ People/ Theses/ Library/ Briefs/ Drafts/ _indexes/   the vault
```

## Status

This is a working system, extracted from a private personal vault and stripped
of its content. The config-driven design means it runs for anyone. Start in
`scripts/intelligence/` to see the part that is genuinely novel: the ledgers,
theses, and briefs that track how thinking changes over time.
