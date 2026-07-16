# Bootstrapping Your Second Brain | 2026

**Mode:** conference / capstone
**Voice:** writer Part 3, terse, tables, named evidence
**Evidence:** live vault (counts verified 2026-07-16), X bookmark captures, Grok adversarial review 2026-07-16

---

## 01 · Title

**BOOTSTRAPPING YOUR SECOND BRAIN**

Everything I'm interested in: filed, sorted, and processed while I sleep.

`2026 | Arthur Ariel Sabintsev`

---

## 02 · Why now: The Fourth Turning is here.

Strauss and Howe's cycle: every 80 years or so, a crisis era tears up the old order and builds a new one. My read: we're in it, and it went kinetic in 2022.

| Date | Event |
|------|-------|
| **2020-03** | Covid. The turning opens. Institutions strain, money prints, trust breaks |
| **2022-02-24** | Russia invades Ukraine. My read: World War 3 starts here. The vault's corpus starts the same day |
| **2022-11** | The AI Industrial Revolution: ChatGPT ships. The fastest capability ramp of my lifetime lands inside the crisis era |

**Callout card (bordered, centered): The corpus starts 2022-02-24, the day of the invasion.** Everything filed since is scoped to this era. Podcasts carry most of the backfill; the other feeds joined as I built them.

---

## 03 · Problem: Tracking the world as it changes is hard.

AI captures what I care about, passively and actively. Everything that lands gets processed by AI and filed.

**Sources** (logos with names): X · Goodreads · Substack · GitHub · Podcasts · YouTube · Meetings · Chats

**Workflow:**

| Function | What it does |
|------|---------|
| **Overnight Filing** | New captures get read, linked, tagged, and filed into the wiki that night |
| **Morning Digest** | A short list of what got filed last night and where it went |
| **Active Discussions** | Chat with the data: ask questions, challenge a thesis, drop an idea |

**Tools:**

| Tool | |
|------|---|
| **[Obsidian](https://obsidian.md)** | The vault UI: graph, backlinks, mobile |
| **Obsidian Plugins** | [Claudian](https://github.com/YishenTu/claudian) · [Omnisearch](https://github.com/scambier/obsidian-omnisearch) |
| **CLI AI Models** | [Codex](https://openai.com/codex/) · [Claude](https://claude.com/claude-code) · [Grok](https://x.ai) · [Qwen](https://github.com/QwenLM/qwen-code) |


---

## 04 · Architecture: The whole thing is markdown and git.

Karpathy, [llm-wiki.md, April 2026](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase." (gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

Rendered as a five-stage logo pipeline (brand icons inlined, offline-safe):

| Stage | Card |
|-------|------|
| **Capture** | Eight feeds (X, Goodreads, Substack, GitHub, Podcasts, YouTube, Meetings, Chats). Bookmark, like, shelve, commit. Zero effort at capture time |
| **Archive** | `Sources/`, immutable. Raw data captured and versioned |
| **File · nightly** | AI processes everything at 5am every day, using the best model installed on the machine. Each capture gets read, summarized, and filed with links and tags |
| **The graph** | Obsidian-native. People 392 · Topics 123 · Theses 9 · Library 1,519. One note per person, topic, thesis |
| **Use** | One contract, three CLIs (Claude, Codex, Grok). Chat is the frontend; the scripts run underneath. Ledgers, briefs, morning digest |

---

## 05 · Ingest: One nightly job, eight sources, one commit.

launchd fires `com.brain.ingest` at 05:00. Each source runs on its own, then a single Claude pass reads the new captures and files what matters into the wiki.

| Source (logo cards) | What lands |
|--------|-----------|
| **X bookmarks** | xtap CLI (my own fork) → dated capture per bookmark |
| **Goodreads** | Private RSS → one entry per (book, shelf-state) |
| **Substack** | My published essays, archived verbatim, and posts I've saved |
| **GitHub** | My commits → folded into `Projects/`, where my head is at |
| **Podcasts** | YouTube captions → deep note per episode, backfilled to **2022-02-24**. Ads stripped. Transcript discarded |
| **YouTube likes** | Long-form captions kept + summarized |
| **Meetings** | Meeting notes from Drive, filed under the company or person they're about |
| **Conversations** | Inferences and decisions from active chats with the AI, logged and filed |

---

## 06 · Harness: AGENTS.md is the orchestrator.

| Layer | What it is |
|-------|-----|
| **The contract** | `AGENTS.md`: folder schema, write rules, the intelligence layer. Every agent loads it before touching the vault |
| **Entry points** | `CLAUDE.md` = `CODEX.md` = `GROK.md`, symlinks to one file. Whatever CLI opens the repo reads the same rules |
| **Any AI** | Claude, Codex, Grok, Qwen are interchangeable. Chat is the frontend. The nightly process chooses the best locally installed AI with an active subscription (Fable → Sol → Opus → Grok → Sonnet) |


Right side: the vault structure from AGENTS.md (Profile, Projects, People, Theses, Topics, Library, Briefs, Digests, Log, Sources, scripts).

---

## 07 · Thesis Example: AI kills SaaS.

**The thesis, plainly:** companies rent business software (SaaS) because building their own was always too expensive. AI collapses the cost of building software, so the vendors lose the power to charge rent.

| Date | Evidence |
|------|----------|
| **2024-05** | Chamath's incubator 8090 names the play: build software that's 80% as good as the vendor's for 90% less money. Enterprises replace systems at a quarter to a tenth of the cost |
| **2024-07** | Chamath, at the All-In Napa special: the stack gets rebuilt by 10-to-30-person companies; "no room for $500M into a SaaS company" |
| **2024-12** | Chamath, on All-In, calls software down an order of magnitude: ~$5.1T market to ~$500B. Aaron Levie, CEO of Box, dissents on the spot |
| **2025-06** | Chamath again: "the jig is totally up for software." Hundreds of millions in licenses replaced by tens of millions in custom builds |
| **2026-02** | Jason Calacanis reports 7+ production agents replacing software he used to buy, including self-hosting Mattermost instead of paying for Slack |
| **2026-04** | Medallia, a customer-experience SaaS vendor, is handed to its creditors; roughly $5.1B of equity wiped as enterprises spin up agents instead of renewing |
| **2026-05** | **Counter:** Marc Benioff, CEO of Salesforce: "not my first SaaSpocalypse." Governed data and twenty-year C-suite relationships are a moat cheap code can't cross |
| **2026-06** | **Counter:** Nikesh Arora, CEO of Palo Alto Networks, splits the difference: analytical SaaS is "over," but infrastructure software is undervalued. A pricing-power collapse, not a software extinction |

**Current verdict (below the table): Holding, so far. Companies keep the software, but the vendors are losing the power to raise prices.** What would kill it, on file: revenue and renewal rates hold up in the actual numbers; a high-profile compliance failure in an in-house AI build revives the buy case; or the consulting layer re-forms so completely that net spend never falls.

---

## 08 · Person Example: Even the best VCs change their minds.

Every core person in the vault has a position ledger: dated claims, stance by stance. This is Ben Horowitz, cofounder of Andreessen Horowitz, which raised roughly 18.3% of all US venture capital in 2025.

Three themed cards, initial position then the arc:

**AI moats (reversal):** 2024-05 wrappers durable via workflow integration → 2026-02 AI breaks the mythical man month → 2026-04 old moats dissolving, runway "maybe five weeks." Verdict: full reversal in two years; watching whether he names an a16z SaaS holding he expects to hit zero.

**Venture structure (doubling down):** 2025-04 a16z runs like a company, one boss, central control → 2025-08 predicts VC splits into a few giants plus small specialists, middle squeezed out → 2026-05 declares the small partnership "structurally obsolete" while a16z raises nearly a fifth of all US venture money. Verdict: consistent and hardening; watching whether a named mid-size firm actually folds.

**Defense tech (doubling down):** 2024-10 names the threat, America depends on China's DJI for drones → 2025-11 declares the debate won, the Valley builds for the military again → 2026-05 punishes a defector, attacking Anthropic for quitting a Pentagon deal. Verdict: doubling down and getting sharper; watching whether he calls Anthropic unreliable on future defense deals.

---

## 09 · Objections: "Isn't this Obsidian + ChatGPT?"

| The room says (cards) | The answer |
|------|--------|
| **"Notes app."** | A notes app is only as good as the hours you put into it. This one does the reading and filing while I sleep, updates my positions when new evidence lands, and keeps every older version with its date |
| **"Just RAG."** | Retrieval (RAG) answers one question, then forgets. This builds things that exist before I ask: person ledgers, dated theses, 392 people and growing. Every night's filing compounds on the last |
| **"The model lies."** | The model can never edit the raw captures, every claim links back to its source, and every change is versioned. A bad note can get written, but it can always be traced and fixed; the evidence underneath stays clean |
| **"Search will break at scale."** | The notes are heavily structured: names, dates, links, so plain search plus an agent that reads works today. Over time the data gets consolidated (not built yet). If that stops being enough, I add search by meaning, where "Taiwan invasion" also finds the note that says "cross-strait risk." The notes stay plain files |
| **"Why not ChatGPT's memory?"** | Platform memory is a black box: I can't read it, edit it, or take it with me. This is plain files I own. I can switch between Claude, Codex, and Grok and lose nothing |

---

## 10 · Close: What else I use it for.

| Use | What it looks like |
|-----|--------------------|
| **Travel planning** | A master plan plus one note per trip: Japan 2027, Utah hiking, Panama. The agent works the windows and sequencing |
| **Meeting prep** | Before a call, a brief from the vault: who they are, what they've claimed, what to ask. Notes file back in after |
| **Writing** | Substack essays drafted against the corpus |
| **Investment decisions** | Six of the nine theses carry live diligence, that is: dated evidence, counters, kill criteria |
| **Decision log** | Decisions, lessons, and killed ideas, one dated line each. I can see what I believed and when |
| **Where my head is** | My GitHub commits fold into project notes, so the vault tracks what I'm actually building |

**Get started with your own second brain** (bordered callout): [github.com/ArtSabintsev/bootstrap-your-second-brain](https://github.com/ArtSabintsev/bootstrap-your-second-brain)
