---
name: seo-launch
description: End-to-end SEO for a project, built in before launch rather than bolted on after. Use this whenever the user is starting or has just built a new site, app, directory, SaaS or product and wants it found in search — and also when they say "optimise this for SEO", "set up SEO", "do keyword research for this", "plan the site structure", "we're about to launch", or ask about Search Console, sitemaps, robots.txt, meta tags, titles, schema or why they aren't ranking. Run it on a fresh codebase before content is written, because the URL and architecture decisions it makes are expensive to reverse later. It reads the code to work out what the product actually does, researches keywords, plans the structure, writes the pages, enforces the technical rules, gates the launch, and leaves a post-launch checklist for whoever runs the project next. Use it again on any live project the skill has touched before, whenever the user asks to review SEO, check how pages are performing, work out why traffic dropped, find what to improve next, or has a Search Console export to look at — it re-enters at the review loop and ranks what to fix by the clicks each fix is worth.
---

# SEO from day one

Most SEO work is retrofitting: someone built a site, launched it, got no traffic, and now wants it fixed. The fix is always more expensive than doing it first, because URLs are already indexed, content is already written against the wrong intent, and the architecture doesn't match how anyone searches.

This skill does it in the other order. The point is that a handful of decisions — what the URL pattern is, which page owns which search intent, how pages link to each other — cost nothing to get right before launch and cost months to change after.

## Resume before you start

This runs in phases over days or weeks, not in one pass. **Before doing anything, check whether a previous run left state:**

```
seo/
  project.md        what this thing actually is          → phase 0
  keywords.csv      scored, clustered keyword set        → phase 1
  structure.yaml    the page plan. THE source of truth   → phase 2
  content/          briefs and drafts                    → phase 3
  audit/            technical findings                   → phase 4
  LAUNCH.md         post-launch checklist                → phase 5
  reviews/          dated review reports                 → phase 7
```

If `seo/` exists, read what's there, tell the user which phase they're in, and pick up from the next one. **If `seo/LAUNCH.md` exists, the project is live and the answer is almost always phase 7** — the review loop, not a fresh pass through phases 0 to 6. Don't redo finished phases — the user paid for those decisions and redoing them silently changes answers they've already built against.

If `seo/` doesn't exist, start at phase 0.

---

## The phases

```
0  UNDERSTAND    read the code → seo/project.md
1  KEYWORDS      harvest, cluster, score → seo/keywords.csv
2  ARCHITECTURE  clusters → pages → seo/structure.yaml
3  CONTENT       write the pages against the contract
4  TECHNICAL     build rules + audit → seo/audit/
5  LAUNCH GATE   blocking checks, then hand off → seo/LAUNCH.md
6  POST-LAUNCH   consoles, indexing, first checks
7  REVIEW        re-enter on a cadence → seo/reviews/<date>/
```

Phases 0 to 6 run once. **Phase 7 runs for the life of the project**, and it is where most of the ranking actually happens. Each of its findings sends you back into an earlier phase with real data instead of estimates.

Each phase produces one artifact and stops. Show the user the artifact, get agreement, move on. Phases 1 and 2 are where the expensive mistakes live — don't rush past them to get to writing.

---

### Phase 0 — Understand the project

Read `references/01-discovery.md`.

The single most important rule here: **read the code, not the marketing copy.** Landing pages systematically overstate what a product does. If you derive keywords from the homepage, you inherit the overstatement and end up targeting searches the product can't actually satisfy — which produces pages that rank, get clicked, and bounce. Bouncing is worse than not ranking.

So: read the routes, the models, the API surface, the feature flags, the actual components. Work out what it genuinely does today, what it does badly, and what it doesn't do at all. Then compare that against whatever copy exists and flag the gaps to the user.

Output `seo/project.md`.

### Phase 1 — Keywords

Read `references/02-keywords.md`.

**There is no cap on the list.** A thousand keywords is fine, ten thousand is fine. What limits it is fit: the product genuinely does the job, the results page shows pages like the one we'd build, and there's a realistic chance to rank. Most keywords join a page that already exists as an FAQ or a section rather than getting one of their own.

The method differs from most keyword advice in several ways the reference explains: start the harvest from the product's own capabilities and settings rather than from a seed, cluster by **pattern first and SERP overlap where ambiguous**, score **clusters** rather than keywords, check **parent topic** before creating a page, and **trace the code path** before committing to build.

Output `seo/keywords.csv`.

### Phase 2 — Architecture

Read `references/03-architecture.md`.

Clusters become pages. One cluster, one search intent, one page. The URL pattern gets declared once and never deviates — consistency matters more than whether you put the category or the location first.

**Every page declares its title, H1 and opening line here, each carrying the page's primary keyword** — at the same time as the URL, not later while drafting. Those are the three places Google reads to decide what a page is about, and the edit costs seconds now against a rewrite once copy exists. `scripts/plan_check.py` fails the plan if any page is missing any of the three, and phase 3 does not start until it exits clean.

`seo/structure.yaml` becomes the source of truth for internal linking for the life of the project. **Links get generated by walking this file, never by asking a model which pages feel related.** Models link things that seem topically similar, which quietly breaks the hierarchy search engines and AI systems use to understand the site.

Output `seo/structure.yaml`.

### Phase 3 — Content

Read `references/04-content.md`.

Each page is written against a contract with four parts: what the cluster says to target, what the SERP says the shape should be, what the human must supply, and the structural rules.

The title, H1 and opening line arrive **already decided** from phase 2, so drafting does not get to invent them. If the SERP read says the page should be something else, change them in `structure.yaml` and re-run `plan_check.py` — never only in the draft, or the plan and the page disagree about what the page is for.

**Delegate all prose to the `no-ai-tells` skill.** Invoke it for every page before the page is considered done. Writing that reads like a chatbot wrote it gets bounced by readers, and bounce is a ranking signal — this isn't a style preference, it's part of the job. The two-pass method in that skill (draft on substance, then hunt the tells) is the right shape for this work.

The part that decides whether this is a content system or a slop machine is the human input gate. Every page needs at least one real story, two real numbers with sources, and one original image or screenshot. If the project has none of those yet, say so and ask — do not generate around the hole.

Ship in batches, one per page type, at whatever size suits. The user approves the batch rather than each page. Matrix pages — format pairs, one page per platform, each tool in each language — reach the most keywords and carry the most duplicate risk, so each needs facts drawn from the code that only apply to it.

### Phase 4 — Technical

Read `references/05-technical.md`.

Run `scripts/audit.py` for the deterministic checks and `scripts/lint.py` on each page. The things that silently invalidate everything else, in order: JavaScript-dependent rendering, blocked AI crawlers, and a missing or stale sitemap.

### Phase 5 — Launch gate

Read `references/06-launch.md`.

A short list of blocking checks. Nothing ships until they pass, because each one makes the rest of the work invisible.

Then write `seo/LAUNCH.md` into the project and append a pointer to the project's `CLAUDE.md`, so whoever opens the project next — human or agent — picks up the post-launch tasks without being told.

### Phase 6 — Post-launch

Read `references/06-launch.md` (second half).

Search Console and Bing Webmaster Tools registration, sitemap submission, and first indexing checks. Mostly reminders, because most of it needs someone with account access. The recurring work is phase 7, not here.

Then move to phase 7. Phase 6 is the one-time registration work; everything recurring lives in phase 7.

Two things worth knowing before you plan around them: **indexing at scale runs on the sitemap and internal links, not on requests** — the manual button is about ten a day and Google's Indexing API only accepts job postings and livestreams. And **check the site is actually up before reading any data**, because a dead host produces numbers that look exactly like an SEO problem.

### Phase 7 — The review loop

Read `references/09-review.md`.

Come back here a week after launch, again at two to four weeks, again at two months, then monthly. Run `scripts/review.py` against a Search Console export — it needs no credentials, because the export is a button in the UI — and it returns a ranked list of what to improve, sorted by the clicks each fix is worth.

**The question worth asking depends on how old the page is.** At a week, only indexing. At two to four weeks, what Search Console is calling the page, which is usually better than what you guessed and is the cheapest correction to phase 1 available. At three weeks to two months, positions 5–15. Past two months, decay and cannibalisation. Asking about position too early is how people rewrite pages that were fine — new pages get a few good days and then settle back, so nothing counts until a full week has settled.

Every review also re-reads the code and diffs it against `seo/project.md`. The product moves, and a page claiming a capability the product no longer has is worse than a thin page: it ranks, gets the click, and disappoints. Google cannot tell you your copy stopped being true.

When a finding sends you back to phase 1 or 2, **append rather than regenerate** — the user has already built against those decisions.

---

## Branches

**Local business** — if the project has a physical location or serves a geographic area, read `references/07-local.md` after phase 0. Local SEO is a different game: you're ranking a Google Business Profile in a map, not a URL in a list, and the keyword framework in phase 1 barely applies.

**AI search** — read `references/08-aeo.md` during phase 3. Showing up in ChatGPT, Gemini and Perplexity is mostly the same work as ranking in Google, with three genuine additions. Worth doing for a new project specifically because citation visibility arrives faster than domain authority does.

---

## Rules that hold across every phase

**Constrain the model with data, not with prompts.** Wherever there's a canonical list — the declared URL pattern, the page hierarchy, Google Business Profile's official categories — look it up rather than asking a model to decide. The failures that make AI-built sites obviously AI-built are all cases where something was inferred that should have been retrieved.

**Verify every citation.** If a page cites a source, fetch the URL, confirm it resolves, confirm the claim is actually on the page. Models invent plausible sources, and the whole approach of answering directly and citing your evidence collapses if the evidence is fictional.

**Gate on quality per page, not on page count or publishing rate.** Google's spam policies define scaled content abuse by intent — pages built to manipulate rankings rather than help users — and set no limit on either number or speed. So there's no cap here. Every page passes the same gate before it ships: the capability is verified in the code, the copy passes the duplicate check, the keyword is in the title, H1 and first `<p>`, and every FAQ answer opens with the answer. Ship in batches or all at once, as the user prefers.

**Every page carries its target phrase in the title, the H1 and the first sentence of body copy.** No page ships without all three. They are the three places Google reads to work out what a page is about, and they are enforced at both ends: `plan_check.py` blocks the plan before a page is written, `lint.py` blocks the page afterwards at error level, reading the rendered HTML rather than the template. The opening line is the one that gets missed, because on most tool and app pages the first `<p>` under the H1 is template furniture — a trust line, a privacy claim, an upload hint — and a "keyword in the first 100 words" check passes while the sentence Google reads first says nothing about the topic. Three string edits do not guarantee a ranking. Their absence reliably costs impressions, which is a different and much safer claim.

**Word count is not a target.** It's an observation about what the top results happen to contain. Brief to the low end of that range — lean copy that covers the topic beats padded copy that covers it twice.

**The user approves before anything goes live.** Phases 0 through 4 touch nothing but the `seo/` directory. Phase 5 is the first thing that changes the site.

---

## Reference files

| File | Read it when |
|---|---|
| `references/01-discovery.md` | Phase 0 — working out what the project is |
| `references/02-keywords.md` | Phase 1 — the keyword method in full |
| `references/03-architecture.md` | Phase 2 — URL patterns, page planning, linking |
| `references/04-content.md` | Phase 3 — the page contract and writing rules |
| `references/05-technical.md` | Phase 4 — the technical checklist |
| `references/06-launch.md` | Phase 5 and 6 — the gate and the handoff |
| `references/07-local.md` | Only if the project has a physical location |
| `references/08-aeo.md` | Phase 3, for AI search visibility |
| `references/09-review.md` | Phase 7 — the recurring loop, and how to read it honestly |

| Script | Does |
|---|---|
| `scripts/audit.py` | robots.txt and AI crawlers, JS render test, sitemap, PageSpeed, schema |
| `scripts/lint.py` | per-page on-page rules, with autofix where it's safe |
| `scripts/plan_check.py` | gates the plan: keyword in every page's title, H1 and lede |
| `scripts/review.py` | ranks what to improve next from Search Console exports |

| Asset | Is |
|---|---|
| `assets/structure.schema.yaml` | The shape of `seo/structure.yaml` |
| `assets/LAUNCH.template.md` | The post-launch checklist dropped into the project |
