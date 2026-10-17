# Phase 7 — The review loop

This is the phase you come back to. Phases 0 to 6 happen once. This one runs for the life of the project, and it is where most of the actual ranking gets done — not in the launch.

The reason it needs its own phase rather than a line in a checklist: after launch, the best available keyword research is your own Search Console data. It tells you what people really typed, which pages Google actually matched them to, and which of your guesses were wrong. That is better information than any keyword tool sells, and it only exists after you ship.

---

## The rule that makes this work

**The right question depends on how old the page is.** Ask the wrong one and you will rewrite a page that was fine, or declare a win that evaporates.

| Page age | The only question worth asking | Ignore |
|---|---|---|
| 0–7 days | Is it indexed, or merely submitted? | Position. All of it. |
| 7–21 days | What is Search Console calling this page? | Position still — see the trial spike below |
| 21–60 days | Anything in positions 5–15? | Nothing. Positions are real now |
| 60 days+ | Is it decaying? Is another page competing? | Single-query movement |

Two things justify the first two rows.

**The trial spike.** New pages get a few days at better positions than they have earned, then settle. An average position can halve and then return to roughly where it started inside two weeks — the middle reading is not progress, and acting on it means rewriting pages that were working. **Never report a win until a full week has settled.**

**Search Console renames your pages.** Within about two weeks, even at an average position of 40, it shows the exact phrases people used — and they are rarely the phrases you guessed. The pattern is consistent: real queries are shorter and blunter than planned keywords, use the verb rather than the noun, and often misspell or abbreviate. A page built around *change element position* picks up impressions for *move element*. That is a free correction to phase 1, available only by waiting.

---

## Running it

Search Console, Performance report, set the date range, **Export** (top right). You want the Queries tab and the Pages tab. No API and no OAuth — it is a button.

```bash
python scripts/review.py \
  --queries  exports/2026-10/Queries.csv \
  --pages    exports/2026-10/Pages.csv \
  --keywords seo/keywords.csv \
  --out      seo/reviews/2026-10-17 \
  --window   "28 days to 2026-10-17"
```

Keep the previous export and pass it, which is what turns a snapshot into a trend:

```bash
  --prev-queries exports/2026-09/Queries.csv \
  --prev-pages   exports/2026-09/Pages.csv
```

If you have query-by-page rows — from the Search Analytics API, or an export taken with a page filter applied — pass `--pairs`. Without them the cannibalisation and wrong-page checks cannot run, and the report says so rather than pretending.

Output is `report.md` (read it in order, it is sorted by what to do first) and `actions.csv` (sort it yourself).

### What each check is telling you

| Check | Means | Do |
|---|---|---|
| `striking-distance` | 5–15. Google already thinks you are relevant | The three kings, then re-index. Highest return per minute in the whole skill |
| `nearly-there` | 3–5. Top four is where the clicks are | Internal links from your strongest related page |
| `ctr-gap` | Position is fine, title is not earning the click | Rewrite title and meta description only. Do not touch the body |
| `untargeted-query` | Real impressions for something not in `keywords.csv` | Append it to phase 1, then retitle or build |
| `gaining` | Up three or more positions | Build the rest of that cluster. Something about it works |
| `decaying` | Impressions down 40%+ | Refresh this before writing anything new |
| `page-dropped` | Was ranking, now is not | Check it is still indexed before you rewrite it |
| `cannibalising` | Two of your pages on one query | Pick the owner, point the others at it |
| `wrong-page` | A different page ranks than the one you targeted | Either the target was wrong, or the two pages are too alike |
| `no-clicks` | Shown repeatedly, never clicked | Look at the result Google is actually displaying |

The ranking number, "on the table", is impressions times the gap between current click-through and what position three would earn. It is a shape for comparing opportunities against each other, not a traffic forecast — the curve behind it is interpolated from three data points.

---

## Reading it honestly

**Check the site is up first.** A dead host produces numbers that look exactly like an SEO problem. Do this before reading anything.

**Judge totals, never one query.** A query with one to three impressions swings forty positions on a single search. Impressions per day, distinct queries and clicks are the real signals. The script floors at ten impressions for this reason; raise it with `--min-impressions` on a bigger site.

**Impressions move before positions do.** On a young site, rising impressions with flat positions is the expected shape of progress, not a stall.

**Requests are not visitors.** Cloudflare counted 1,520 requests in a day when bot-filtered analytics counted two visits. Report the bot-filtered number.

---

## What the loop feeds back into

This is not a report you file. Each check sends you back to a specific earlier phase:

```
untargeted-query  → phase 1   append to keywords.csv with a role and a target_url
gaining           → phase 1   score the rest of that cluster, it is working
cannibalising     → phase 2   the structure has two owners for one intent
wrong-page        → phase 2   or the two pages are too similar to tell apart
striking-distance → phase 3   three edits, one page
ctr-gap           → phase 3   title and meta only
decaying          → phase 3   refresh, with the no-ai-tells skill as usual
page-dropped      → phase 4   indexing before content
```

When the loop sends you back to phase 1 or 2, **append rather than regenerate.** The user already built against those decisions.

---

## Capability drift

The product keeps moving, and pages written against last quarter's capabilities quietly become wrong. That is worse than a thin page: it ranks, gets clicked, and the visitor finds the feature missing.

So on every review, re-run the phase 0 read of the code and diff it against `seo/project.md`:

- A capability that was removed or changed → every page claiming it needs re-verifying against the code path
- A capability that was added → a tier 1 candidate in the ladder in `02-keywords.md`, which is the highest-return tier there is
- A settings option that was added → more keywords, same mine as the original harvest

A review that only looks at Search Console misses all of this, because Google cannot tell you that your copy stopped being true.

---

## Cadence

```
Week 1        Indexing only. site:<DOMAIN> and the Page Indexing report.
              Rising "crawled - currently not indexed" is the most useful
              early warning there is: pages shipped faster than their
              quality held up. Fix that before the next batch.

Week 2-4      First real review. The untargeted-query rows are the prize --
              this is Search Console doing your keyword research. Retitle to
              match. Still do not judge positions.

Month 2       The full loop, with the previous export passed in. Striking
              distance is now meaningful, decay is now detectable, and this
              is the first review where the ordering ladder applies properly.

Monthly after Full loop plus the capability-drift diff. Refresh the oldest
              money page each time -- AI-cited content skews heavily toward
              recently updated pages.

Each batch    Read the Page Indexing report after every content batch,
              regardless of the calendar. That is the feedback the
              batch-by-page-type rule exists to produce.
```

Set a reminder in the project rather than relying on someone remembering. `assets/LAUNCH.template.md` carries the dates, and the pointer appended to the project's `CLAUDE.md` is what makes the next agent to open the project pick this up without being told.

---

## What needs a human

Say these out loud rather than quietly skipping them:

- The Request Indexing button — there is no API for ordinary pages, and it is about ten a day. Spend them on the striking-distance rows first
- Exporting from Search Console, unless someone wires up the Search Analytics API
- Deciding whether a keyword genuinely describes the page. The script ranks; it cannot tell you that a high-impression query is the wrong fit for your product
- Anything that publishes, sends or pays
