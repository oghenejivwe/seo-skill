# SEO — post-launch checklist

> Written by the `seo-launch` skill on `<DATE>`.
> If you are an agent picking this project up: this file is the handoff.
> Read it before touching anything SEO-related, and update the boxes as
> you go so the next person knows where things stand.

**Project:** `<PROJECT>`
**Domain:** `<DOMAIN>`
**Launched:** `<LAUNCH DATE>`
**Plan:** `seo/structure.yaml` — the page plan and the source of truth for internal links
**Keywords:** `seo/keywords.csv`
**What this project actually is:** `seo/project.md`

---

## Needs a human with account access

These cannot be automated. They are also time-sensitive — every day the site
is live and unregistered is a day Google doesn't know it exists.

```
[ ] Google Search Console
      add property, verify via DNS (survives hosting changes)
      submit <DOMAIN>/sitemap.xml
[ ] Bing Webmaster Tools
      can import directly from Search Console
      submit the same sitemap
      ChatGPT's search runs on Bing's index — this one is not optional
[ ] Analytics installed and recording
[ ] Request indexing for the home page and each money page
      URL Inspection -> Request Indexing. Roughly 10 per day.
```

Money pages for this project:

```
<LIST OF MONEY PAGE URLS>
```

---

## Week one

```
[ ] Confirm pages are indexed, not merely submitted
      site:<DOMAIN> and the Coverage report
[ ] Check Search Console for crawl errors
[ ] Add an AI traffic segment in analytics, matching source against:
      chatgpt.com, perplexity, gemini.google.com,
      copilot.microsoft.com, claude.ai
[ ] Add "How did you hear about us?" to signup or checkout,
    with an AI assistant option
      Most AI-driven discovery never shows as AI traffic — people read
      the name, then search the brand or type the domain. Asking is the
      only way to see it, and it only becomes useful with history.
[ ] Baseline AI visibility: ask each major assistant the questions these
    pages target, record who gets named
```

Target questions to track:

```
<LIST OF TARGET QUESTIONS>
```

---

## Weeks two to four

```
[ ] Watch impressions rather than rankings — impressions move first
[ ] Diagnose anything in "crawled, currently not indexed"
      Google read the page and declined to store it. Usually too thin,
      too generic, or duplicating another page. Fix, then request again.
[ ] Get listed where this category gets compared — roundups,
    directories, comparison posts
      For a new project this is the fastest route into AI answers,
      because citation visibility arrives long before domain authority.
[ ] Answer real questions in the communities these users are already in.
    Say who you are and where you work. Five honest answers beat five
    hundred automated ones, which get removed and get the account banned.
```

---

## The review loop — this is the part that does the ranking

Everything above happens once. This repeats, and it is where most of the
traffic actually comes from. Re-run the `seo-launch` skill and it picks up
at phase 7.

**Review dates for this project:**

```
[ ] <LAUNCH+7>    indexing only
[ ] <LAUNCH+21>   what Search Console is calling these pages
[ ] <LAUNCH+60>   the full loop, first time positions are trustworthy
[ ] monthly after
```

Each one: Search Console → Performance -> set the range -> Export. Keep the
Queries and Pages CSVs, then run

```
python scripts/review.py --queries Queries.csv --pages Pages.csv   --prev-queries <LAST MONTH>/Queries.csv   --keywords seo/keywords.csv --out seo/reviews/<DATE>
```

It ranks what to fix by the clicks each fix is worth. No credentials needed;
the export is a button.

**The question depends on the page age, and asking the wrong one wastes the
review.** At a week, only ask whether pages are indexed. At two to three
weeks, read the queries people actually typed and retitle to match — these
are almost never the phrases you guessed, and this is the cheapest keyword
research that exists. Positions mean nothing until about three weeks, because
new pages get a few good days and then settle back. Don't call a win until a
full week has settled.

```
[ ] Positions 5-15 → target keyword into the title, H1 and opening line,
    then request re-indexing. Highest return per minute, every time.
[ ] Queries you never planned for → add them to seo/keywords.csv
[ ] Two pages competing for one query → pick the owner, point the other at it
[ ] Impressions down 40%+ on a page → refresh it before writing anything new
[ ] Re-read the code against seo/project.md → did the product change?
    A page claiming a capability the product no longer has is worse than
    no page: it ranks, gets the click, and disappoints.
[ ] Refresh the oldest money page — AI-cited content skews heavily
    toward recently updated pages
[ ] Re-ask the assistants the target questions. Named more, or less?
```

Judge totals — impressions per day, distinct queries, clicks. Never one
query's position: a query with one to three impressions swings forty places
on a single search.

---

## Still outstanding from the build

```
<ANYTHING PHASE 5 COULD NOT CLOSE>
```

---

## Rules that still apply

- **Gate on quality per page, not on page count or publishing rate.**
  There is no cap and no ramp. Every page passes the same gate: capability
  verified in the code, duplicate check passed, keyword in the title, H1 and
  first paragraph, every FAQ answer opening with the answer. Batch by page
  type so the Page Indexing report teaches you something.
- **Verify every citation** before a page goes live — fetch the URL,
  confirm it resolves, confirm the claim is on the page.
- **Internal links come from `seo/structure.yaml`**, not from judgement.
- **Run `no-ai-tells` on all prose.** Copy that reads like a chatbot
  wrote it gets bounced, and bounce feeds back into ranking.
- **Word count is an observation, not a target.**
