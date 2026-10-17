# Phase 5 — Launch gate, and Phase 6 — After launch

---

# Phase 5 — The gate

Seven blocking checks. Each one, if wrong, makes some or all of the preceding work invisible.

```
[ ] Content is in the HTML without JavaScript
[ ] robots.txt allows GPTBot, OAI-SearchBot, ClaudeBot, Google-Extended
    (and Cloudflare's AI-bot setting has been checked, not assumed)
[ ] Pages return 200 when fetched AS each of those crawlers —
    a CDN can block a user agent that robots.txt allows
[ ] sitemap.xml exists, lists every page, carries accurate lastmod,
    and regenerates automatically
[ ] HTTPS with a valid certificate
[ ] Every page has a unique title, a single H1, and a real first <p>
[ ] No accidental noindex anywhere
[ ] Every page has at least one internal link pointing at it
```

Then the non-blocking but strongly advised:

```
[ ] PageSpeed above 80 on mobile
[ ] Schema on the home page and every money page
[ ] og:description and og:image on every page
[ ] HEAD returns 200, not 405 — link checkers and preview cards use it
[ ] A "how did you hear about us?" field on signup or checkout
```

That last one looks trivial and isn't. Most AI-driven discovery never appears in analytics — someone reads your name, then types your domain or searches your brand, and it books as direct or organic. Asking is the only way to see it, and it has to be collecting from day one to be worth anything later.

## Then hand off

**1. Write `seo/LAUNCH.md`** from `assets/LAUNCH.template.md`, filled in with this project's domain, page list, target keywords, and what's still open.

**2. Append a pointer to the project's `CLAUDE.md`**, so whoever opens the repository next — person or agent — picks the work up without being told it exists:

```markdown
## SEO

This project has an SEO plan at `seo/`. If you are working on this project
after launch, read `seo/LAUNCH.md` — it lists the post-launch tasks that
need a human with account access, and they are time-sensitive.

Current phase: <phase>
Last updated: <date>
```

Keep it to a few lines. The detail belongs in `seo/LAUNCH.md`, not in a file loaded into every conversation.

---

# Phase 6 — After launch

## Before reading any data, check the site is up

A dead site produces data that looks like an SEO problem.

The case to watch for: a hosting account is suspended or a workspace disabled, and every URL starts returning the provider's one-line error page — often with a 200 status, which is why nothing alerts. Search Console data for that window means nothing, and reading it as a ranking problem sends you rewriting pages that were fine.

`scripts/audit.py` detects hosting-provider error text in the body and reports the site as down. Run it first.

## Day one — registration

```
[ ] Google Search Console
      add property, verify via DNS
      submit <DOMAIN>/sitemap.xml
[ ] Bing Webmaster Tools
      can import directly from Search Console
      submit the same sitemap
      ChatGPT's search runs on Bing's index — not optional
[ ] Analytics installed and recording
```

**If DNS is on Cloudflare, try the domain property route first.** Search Console can verify a domain property through Cloudflare directly, without anyone writing a TXT record by hand. Domain properties also cover every subdomain and both protocols, which URL-prefix properties do not.

## Indexing at scale

Manual indexing requests run about ten a day. That cannot cover thousands of pages, so it isn't the mechanism.

**The mechanism is the sitemap with accurate `lastmod`, plus links from pages Google has already indexed.** Spend the manual requests on the most valuable new pages and on pages with queries sitting at positions 5–15.

Two things that are no longer true and are still widely repeated:

- **The Indexing API accepts job postings and livestreams only.** It does not work for ordinary pages. The only route for those is the Request Indexing button in the account holder's Search Console.
- **Google retired sitemap pings in 2023.** IndexNow reaches Bing and Yandex, not Google.

### After each batch, read the Page Indexing report

| Status | Means | Do |
|---|---|---|
| **Discovered – currently not indexed** | Google hasn't crawled it yet | Add links from already-indexed pages. Request indexing for the valuable ones |
| **Crawled – currently not indexed**, and rising | Google looked and passed — usually too alike or too thin | **Fix before the next batch.** This is the signal that the batch had a duplicate problem |
| **Not found (404)** | — | Check whether the removal was intentional before fixing anything |
| **Page with redirect** | Expected for old URLs | Nothing |

A rising "crawled – currently not indexed" count is the most useful early warning there is. It says the pages shipped faster than their quality held up.

## Week one

```
[ ] Confirm pages are indexed, not merely submitted
      site:<DOMAIN> and the Page Indexing report
[ ] Check for crawl errors
[ ] Add an AI traffic segment in analytics, matching source against:
      chatgpt.com, perplexity, gemini.google.com,
      copilot.microsoft.com, claude.ai
[ ] Baseline AI visibility: ask each major assistant the questions
    your money pages target, record who gets named
```

### Analytics basics that prevent false readings

**Requests are not visitors.** Cloudflare's HTTP Traffic counted 1,520 requests in a day when bot-filtered Web Analytics counted **2 visits**. Report the bot-filtered number.

**Request counts by country mostly show bots.** On that same day the Netherlands and France ranked second and fourth by requests, against two real visits. Both host large datacentres.

**Check the cache hit rate.** 74 of those 1,520 requests came from cache — 4.9% — so roughly 1,440 a day reached the paid backend, most of them bots. That's a cost problem as well as a measurement one.

**Impressions are not visits.** Compare Search Console clicks against analytics visits to see how much traffic arrives from somewhere other than search.

## Weeks two to four

```
[ ] Watch impressions, not rankings — impressions move first
[ ] Compare date windows properly: pull a before-window and an
    after-window with the Performance URL parameters, all four
    metrics on, and compute per-query movement
[ ] Let Search Console rename your pages (below)
[ ] Triage the indexing report (above)
[ ] Get listed where this category gets compared — roundups,
    directories, comparison posts
[ ] Answer real questions in the communities your users are in.
    Say who you are and where you work.
```

### Noise rules

A query with one to three impressions can swing forty positions on a single search. Judge progress on **totals** — impressions per day, distinct queries, clicks — never on one query's position.

### Expect a trial spike

New pages get a few days at better positions than they have earned and then settle back. An average position can halve and then return to roughly where it started inside two weeks. **Don't report a win until a full week has settled.**

### Let Search Console rename your pages

Within about two weeks, even at an average position of 40, it shows the exact phrases people used — which are rarely the phrases you guessed.

The pattern is consistent: real queries are shorter and blunter than planned keywords, reach for the verb instead of the noun, and routinely abbreviate or misspell. A page built around *change element position* collects impressions for *move element*. Retitle the title, H1 and first `<p>` to match what people actually type.

## The recurring loop lives in phase 7

Everything from here on repeats, so it has its own reference: `09-review.md`.
Read that rather than working from this file. It covers which question to ask
at which page age, how to run `scripts/review.py` against a Search Console
export, and how each finding routes back into an earlier phase.

The short version, because it is the single highest-return recurring task:
**anything sitting in positions 5-15 gets the target keyword in its title, H1
and first `<p>`, then a re-index request.** Spend the ~10 daily requests there
before anywhere else.

## What needs a human

Be explicit rather than quietly skipping these:

- Verifying domain ownership in Search Console
- The Request Indexing button — there is no API for ordinary pages
- Anything involving payment
- Posting under the project's own identity in communities
- Sending outreach email

Prepare the drafts and the target lists. Hand them over. Don't send.
