# Agent bootstrap (CLAUDE.md / GROK.md / CODEX.md)

This repo is a config-driven second brain: an Obsidian vault plus the automation
that feeds it, and the persistent memory agents load for context.

**Single source of truth:** `AGENTS.md` (schema, rules, intelligence layer).  
**Setup path:** `SETUP.md` (interview → config → secrets → auth → doctor → schedule).  
**Tools and scrapers:** `TOOLS.md` (Obsidian, Claudian, Web Clipper, every source, how to add ingestors).

## Intent routing (read this first)

| Operator says roughly… | You do… |
|------------------------|---------|
| "set up / bootstrap / configure my second brain" | Follow **SETUP.md** end to end. You may write `config.json`, seed `Profile/`, place secrets only under `secrets_dir`, fill `shows.json` (interview for shows, find the URLs), run `bootstrap.sh` + `doctor.sh`. Interview for handles and IDs. **Never invent secrets or push** unless the operator explicitly says to push. |
| "what should I install / which apps" | Recommend from **TOOLS.md**: Obsidian, Claudian, Web Clipper, CLIs. |
| normal vault Q&A | Query is read-only; load Profile first on non-trivial work; cite `[[wikilinks]]`. |
| "log this / remember this / kill this idea" | Append only to `Log/YYYY-MM-DD.md` (or `scripts/log.sh`). |

## Session start (non-trivial work)

1. Read `Profile/00-overview.md` and `Profile/working-with-me.md` if present.
2. Prefer vault + Profile + Theses over generic model knowledge.
3. Follow voice rules in Profile/working-with-me and AGENTS.md (no em dashes in drafted prose).

## Harnesses

`GROK.md` and `CODEX.md` are symlinks to this file so Claude Code, Grok CLI,
Codex, GLM-class, and Claudian-style agents share one entry point. Codex also
reads `AGENTS.md` natively. Edit this file only (not the symlinks).

@AGENTS.md
