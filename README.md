# seo-launch

A Claude Code skill that does SEO for a project end to end — built in before launch rather than bolted on after, and then re-entered on a cadence for the life of the project.

It exists because the usual order is backwards. People build a site, launch it, get no traffic, and then try to fix it. By then URLs are indexed, copy is written against the wrong intent, and the architecture does not match how anyone searches. A handful of decisions cost nothing to get right beforehand and months to change afterwards.

## Install

```bash
git clone https://github.com/oghenejivwe/seo-skill.git ~/.claude/skills/seo-launch
```

The directory name has to be `seo-launch` — that is what Claude Code matches against the skill name, regardless of what the repo is called. It picks the skill up from `~/.claude/skills/`. It triggers on its own when you mention SEO, keywords, Search Console, site structure, or an imminent launch.

## The phases

```
0  UNDERSTAND    read the code -> seo/project.md
1  KEYWORDS      harvest, cluster, score -> seo/keywords.csv
2  ARCHITECTURE  clusters -> pages -> seo/structure.yaml
3  CONTENT       write the pages against the contract
4  TECHNICAL     build rules + audit -> seo/audit/
5  LAUNCH GATE   blocking checks, then hand off -> seo/LAUNCH.md
6  POST-LAUNCH   consoles, indexing, first checks
7  REVIEW        re-enter on a cadence -> seo/reviews/<date>/
```

Phases 0 to 6 run once. Phase 7 runs forever, and it is where most of the ranking actually happens. Each phase writes one file and stops for approval, so a run is resumable — the skill reads `seo/` first and picks up where it left off.

## What is different about it

**It reads the code, not the marketing copy.** Landing pages systematically overstate what a product does. Derive keywords from the homepage and you inherit the overstatement, then build pages that rank, get clicked and bounce. Bouncing is worse than not ranking.

**Keywords start from the product's own capabilities**, not from a seed term. Every feature and every settings option is somebody's search. Capabilities that work and have no page are the highest-return tier there is: no build risk, demand already proven, just a missing page.

**Nothing gets built until its code path is verified.** A keyword the product cannot actually serve is a reject, not a low priority.

**Prioritisation is a ladder, not a score.** Positions 5-15 first, then capabilities with no page, then money pages, then one cluster finished properly. Scoring only breaks ties within a tier.

**Quality gates per page, not per batch.** There is no publishing ramp and no page cap — Google defines scaled content abuse by intent, not by count or speed. Batching is by page type, so the Page Indexing report after each batch tells you whether that template works.

**The question worth asking depends on how old the page is.** At a week, only indexing. At two to three weeks, what Search Console says people actually typed. Positions mean nothing until about three weeks, because new pages get a few good days then settle back.

**The target phrase goes in three places on every page** — the title tag, the H1, and the first sentence of body copy. Enforced at both ends: the plan is gated before a page is written, the rendered page is checked after. The opening line is the one that gets missed, because template furniture usually occupies that slot and a "keyword in the first 100 words" check passes anyway.

**Prose is delegated.** All writing goes through a companion `no-ai-tells` skill before a page counts as done. If you do not have one, the skill will say so rather than writing unchecked copy — any two-pass editor that drafts on substance first and hunts the usual tells second will do.

## Scripts

Standard library only, no dependencies.

| Script | Does |
|---|---|
| `scripts/audit.py` | robots.txt and AI crawler access, JS render test, sitemap, PageSpeed, schema, duplicate-body detection across the whole sitemap |
| `scripts/lint.py` | per-page on-page rules — the three kings, FAQ answer openers, AI-writing tells, link resolution — with autofix where it is safe |
| `scripts/plan_check.py` | gates the page plan — every page must carry its keyword in the title, H1 and opening line before anything is written |
| `scripts/review.py` | ranks what to improve next from a Search Console CSV export |

`review.py` needs no credentials. The export is a button in the Search Console UI.

```bash
python scripts/review.py \
  --queries  exports/Queries.csv \
  --pages    exports/Pages.csv \
  --keywords seo/keywords.csv \
  --out      seo/reviews/2026-10-17
```

Pass the previous month's export as `--prev-queries` to turn a snapshot into a trend. Pass `--pairs` if you have query-by-page rows, which unlocks the cannibalisation and wrong-page checks.

## What it will not do

Outreach sends, Reddit posting, responses to negative reviews, anything involving payment, and bypassing a CAPTCHA or bot check. Where a data source blocks automation the skill says so and moves to the next one. It prepares drafts and target lists and hands them over.

## Where it came from

Distilled from 26 SEO video transcripts, then corrected against a live project. Several widely repeated rules did not survive that — the publishing ramp traced back to an uncited caveat, and the Indexing API only accepts job postings and livestreams rather than ordinary pages. The contradictions between sources are documented rather than smoothed over.
