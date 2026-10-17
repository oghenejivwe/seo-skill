# Phase 1 — Keywords

Goal: `seo/keywords.csv` — **every keyword the product can serve and has a realistic chance to rank for.** There is no upper limit. A thousand is fine. Ten thousand is fine.

What limits the list is fit, not count. A keyword earns its place by passing three gates, and the ones that fail go on a reject list with the reason so nobody researches them twice.

---

## The three gates

**1. The product does the job.** Not "could plausibly" — does. Trace the code path that serves the query and confirm it works on a real input. See *Trace the code path* below.

**2. The results page shows pages like the one we'd build.** If every result is a long explainer and we'd ship a tool page, that's a mismatch, and no amount of optimisation fixes it.

**3. There's a realistic chance to rank.** Either it's long tail, or it survives the difficulty check with the corrected proxy below.

Anything that passes all three is in, whatever its volume. Zero-volume keywords are not a special category to ration — volume data lags reality by months and is missing entirely for anything new or niche. If a real person asked the question and the product answers it, it's in.

---

## Every keyword gets a home

Most keywords join a page that already exists. Only a keyword whose results don't overlap any existing page's results needs a new page.

So each keyword gets a `role` and a `target_url`:

| role | means |
|---|---|
| `primary` | the cluster head. Drives the URL, title, H1 and opening line. One per page |
| `variation` | a near-identical phrasing. Same page, no separate action |
| `secondary` | a different intent inside the cluster. May deserve its own page later |
| `faq` | becomes a question heading and answer on an existing page |
| `section` | becomes a section heading on an existing page |

The warning in `03-architecture.md` against a page per keyword still stands. Scale comes from pages that serve many queries each, not from thousands of thin pages.

A new site picks up queries in Search Console far faster than it gains pages, and most of what arrives belongs on a page that already exists. Expect distinct queries to outnumber your pages by an order of magnitude within the first month.

---

## Scaling the research

Three things change when the list runs to thousands.

**Cluster by pattern first.** Group by the shape of the query — format pairs, platforms, languages, question forms — and only run SERP-overlap checks where a pattern is genuinely ambiguous. Fetching ten results for each of ten thousand keywords is not practical on free sources, and most of those fetches would confirm something the pattern already told you.

**Use a bulk volume source.** Google Ads Keyword Planner is free with an Ads account and handles thousands of terms. DataForSEO is the paid alternative. Trends and autocomplete are for spot checks, not for bulk.

**Past 1,000 rows, use the API.** Search Console's Performance table and its export both stop at 1,000 rows. The Search Analytics API returns up to 25,000 rows per request, paged with `startRow`, up to 50,000 rows a day per search type. Google documented these limits in its October 2022 post *A deep dive into Search Console performance data filtering and limits*.

---

## Three things most keyword advice gets wrong

**Clustering by topic similarity.** Grouping keywords that "mean roughly the same thing" is a guess at what Google thinks. Google will tell you directly: pull the top ten results for two keywords and count shared URLs. Start at **4 of 10** and tune. seodata.dev gives an overlap score out of 20 for free, which is the same signal without the fetching.

**Scoring individual keywords.** A page ranks for hundreds of queries, so the head term's volume understates it, sometimes by ten or fifteen times. Score the **cluster** — traffic potential is the sum.

**Assuming a keyword deserves a page.** Check the parent topic. Take the page ranking first, find which query sends *that page* the most traffic. If it's broader, your keyword is a section, not a page.

---

## Harvest

### Capability-gap harvest — start here

Turn the phase-0 capability list into a harvest source. Every capability, every user-facing setting, every input and output format, every upload path, with the phrases people would type for it. Mark each one **page exists** or **no page**.

This works on live sites too, and it usually finds more than competitor research does.

The pattern to expect: a product quietly handles half a dozen jobs that have no page at all. Each becomes a page, a cluster or an FAQ answer. A headline feature drawing a few hundred searches a month sitting next to a secondary capability drawing several thousand, with nothing pointing at the second one, is the normal starting position rather than an unusual one.

### Settings are long-tail keywords

Every option in the settings schema is a candidate query and a candidate FAQ.

Settings labels become queries almost verbatim. A checkbox for stripping metadata becomes *remove metadata from X*. A toggle for preserving formatting becomes *keep formatting when converting X*. A numeric limit becomes *max file size for X*. Read the schema rather than the interface — options that never got a visible label still describe behaviour people search for.

### Check other countries for every core keyword

Look up the same query in the largest non-English markets before assuming English is the market. This feeds `hreflang` and localised pages in phase 2.

English-first assumptions can be off by an order of magnitude. A term with a few dozen monthly English searches can run into the hundreds in one non-English country, and for some categories — particularly file formats tied to software popular in a single market — the largest audience is not English-speaking at all. A product can have its biggest market in a language nobody on the team reads.

### Count competitor features across many sites

Fetch the sitemaps and tool hubs of 15–40 competitors, map URLs to tool types, count how many competitors offer each type. That produces a ranked gap list without asking a model anything.

Then check demand separately, because what competitors build and what people search are different things.

The trap: ten competitors in a category all ship the same feature, and the research turns up no search volume for its name at all. People want it inside the tool; they do not go looking for it. Feature parity is a product decision, not a keyword.

### Community questions

Harvest thread titles with a `site:` search, turn each into an FAQ question in the asker's own words, and keep the thread URLs for the outreach phase. Prefer recent threads — Reddit archives old ones and they can't take replies.

### The Trends anchor method

To compare dozens of niche terms on one scale, query five at a time and put the **same anchor term in every batch**. Everything then lands on a comparable scale. Convert to rough volumes using one anchor whose volume you know, and state the error range — about threefold either way in practice.

---

## Sources

These worked from an automated session in October 2026.

| Source | Gives | Reach it | Limits |
|---|---|---|---|
| **Google Search Console** | Real queries, impressions, clicks, CTR, position, indexing status, external links | Performance report URL params: `start_date=YYYYMMDD&end_date=YYYYMMDD` or `num_of_days=7/28/90`, `metrics=CLICKS%2CIMPRESSIONS%2CCTR%2CPOSITION`, `breakdown=page`. 500 rows a page | Lags 2–3 days. Table and export stop at 1,000 rows. Needs the account holder's login |
| **seodata.dev** | US monthly volumes from Google Ads data; other countries via API; an **overlap score (x/20)** that says whether two keywords share results — a free clustering signal | `https://www.seodata.dev/keyword/TERM-WITH-HYPHENS`; API `https://api.seodata.dev/v1/keyword?q=TERM&country=us` (also `id`, `br`, `mx`) | Free quota ran out inside one session. No difficulty score. Some terms have no data. Label as estimates |
| **Google Trends** | Relative demand on one scale, worldwide or by country | `trends.google.com/trends/explore`, exact phrases in quotes, five terms per request | Relative only. Returned 429 once; 60 seconds cleared it |
| **Google Autocomplete** | Whether people type a phrase, and its variants | `https://suggestqueries.google.com/complete/search?client=firefox&q=TERM`, plus `&hl=LANG&gl=COUNTRY` | **Silently drops any query containing a word on its profanity list**, so a keyword with an unfortunate substring looks dead while paid tools show real volume for it. A missing suggestion proves nothing |
| **Semrush free domain overview** | A competitor's top keywords and positions, Authority Score, referring domains, organic traffic | `https://www.semrush.com/website/DOMAIN/overview/` | Uses the domain's top-country database, which may not be the US. Returns 404 for small competitor domains, which is itself a finding — too little traffic to be in the index |
| **Similarweb** | Visits, traffic sources, countries | `https://www.similarweb.com/website/DOMAIN/` | Sometimes serves a bot check |
| **HypeStat** | Visit estimates, share of traffic from search | `https://hypestat.com/info/DOMAIN` | Disagreed with Semrush on visits and top country for the same sites. Cross-check only |
| **indexator.ai** | Worldwide keyword estimates | Keyword pages | Estimates. Label them |
| **Exploding Topics** | Whether a topic is growing or fading | Topic pages | Coarse |
| **Competitor sitemaps** | Every page a competitor has | `/sitemap.xml` and sitemap indexes | Some sites split or block them |
| **The product's code** | What the product can actually do — tool registry, settings schema, formats, upload routes, supported hosts | The repository | Needs repo access |
| **DuckDuckGo lite `site:`** | Reddit and forum thread titles — real questions in users' words | `https://lite.duckduckgo.com/lite/?q=site%3Areddit.com+TERM` | Worked from a browser session; served bot checks to scripted requests later in the run. Reddit blocks direct fetching |
| **PageSpeed Insights API** | Core Web Vitals, performance scores | Google API key with PageSpeed enabled | — |

### Blocked from an automated session — skip these

Ahrefs' free tools (Keyword Generator, Difficulty Checker, Traffic Checker) sit behind a Cloudflare check. SpyFu and WordStream return 403. Startpage serves a bot challenge. Keyword Surfer times out. Bing fetched with curl returns results matching only the first word of each query. Reddit blocks crawlers.

**Never bypass a CAPTCHA or bot check.** Where a source blocks automation, say so and move to the next one.

### Your own search tool is not Google

An agent's built-in web search can return no result at all for a page that Search Console shows ranking in the top two. The index behind it is not Google's, and for long-tail or recently published pages the gap is wide. Treat agent search as a proxy and say so in any output that relies on it.

### Not used yet, worth setting up

Google Ads Keyword Planner — free with an Ads account, and the bulk volume source the scaled list needs. DataForSEO — pay-as-you-go from a $50 deposit, standard-queue SERP request $0.0006. Bing Webmaster Tools — free, gives Bing's own query data.

---

## Enrich

Volume, cost per click, SERP features, and — if live — your current position and which URL holds it.

Cost per click is an intent signal rather than an advertising metric: it says whether this traffic converts for somebody. No advertisers at all is a warning more often than an opportunity.

---

## Cluster

Pattern first, SERP overlap where the pattern is ambiguous.

```
pattern groups:   format pairs      png→webp, webp→png, heic→jpg …
                  platforms         youtube, vimeo, zoom …
                  languages         per-market variants
                  question forms    "how do i …", "can you …"

then, only where unclear:
    fetch top 10 for each keyword
    group where >= 4 URLs are shared
```

Each group is one search intent. Name it after its highest-traffic-potential member.

---

## Score

```
traffic_potential  sum of volume across the cluster
intent             from SERP composition
difficulty         from SERP composition, corrected (below)
business_fit       does satisfying this lead to the conversion event?
```

### Intent, read off the results page

| Results are | Intent |
|---|---|
| Featured snippet, knowledge panel, People Also Ask dominant | Informational |
| Comparison articles, best-of lists, review roundups | Commercial |
| Shopping carousel, heavy ads, product pages, maps | Transactional |
| One brand's own pages | Navigational |

Keyword modifiers are a weaker secondary signal. **When the modifier and the results disagree, the results win.**

**Intent traps.** The phrase often doesn't mean what you assume:
- a term that reads like your feature can mean something else entirely to the people typing it. Check the results before assuming the match
- a modifier changes the expected output. *generator* searchers usually want to create and edit something; *converter* searchers want one file to come out the other side. Serving the wrong one ranks and then bounces
- two terms sharing all twenty results are one page, not two. An overlap score settles it before you split them

### Difficulty, without a backlink index

```
easier   forum and Q&A threads ranking in the top 10
         ranking pages whose titles don't contain the phrase
         thin pages, stale last-modified dates
harder   all ten are established brands
         every title is an exact phrase match
         many SERP features eating the click
```

**An unfamiliar domain is not evidence of weakness.** Small single-purpose tool sites ranking for format pairs turned out to have Authority Scores around 35 and 1,200–1,400 referring domains. Look any unknown domain up on Semrush's free overview before calling a results page easy.

### The AI-overview filter

Can a chat answer satisfy this searcher completely? If yes the click is gone regardless of rank — so the goal changes from earning the click to being named in the answer. Flag those for `08-aeo.md`.

Queries where the user has to *do* something resist this: calculator, checker, generator, converter, template, finder, planner, tool.

---

## Trace the code path before you build

For every keyword marked **build**, name the code path that serves it and confirm it works on a real file. This is gate 1, and it is the one most likely to be skipped.

The failure this catches: a conversion that looks like a page-only job, where tracing the code shows the input goes to a reader that handles one input shape and fails on the other rather than falling through to the slower path that would have worked. The capability is half-present. A page alone would have promised a job the product cannot finish, and the visitor finds that out instead of you.

---

## If the site is already live, diagnose before you plan

**Striking distance.** Filter to positions above 4.9. Already ranking, already judged relevant, just not clear enough. Fixing these beats writing anything new — see the procedure in `04-content.md`.

**Cannibalisation.** Filter to one query, open the Pages view. Two of your own URLs splitting impressions with positions that swap means they're competing.

**Query–page mismatch.** A page ranking for something it doesn't target is either a keyword that deserves its own page, or a page aimed at the wrong intent.

**Let Search Console rename your pages.** Within about two weeks, even at an average position of 40, it shows the exact phrases people actually used — which are rarely the phrases you guessed.

The pattern is consistent enough to plan around: real queries are shorter and blunter than planned keywords, reach for the verb instead of the noun, and routinely abbreviate or misspell. A page built around *change element position* collects impressions for *move element*. Retitle the title, H1 and opening line to match what people actually type.

**Compare date windows rather than eyeballing.** Pull a before-window and an after-window using the URL parameters above, turn on all four metrics, and compute per-query movement.

**Noise rules.** A query with one to three impressions can swing forty positions on a single search. Judge progress on totals — impressions per day, distinct queries, clicks — not on individual query positions.

**Expect a trial spike.** New pages get a few days at better positions than they have earned and then settle back. An average position can halve and return to roughly where it started inside two weeks, so the middle reading is not progress. Don't call a win until a full week has settled.

---

## Prioritisation

With no cap on the list, the ordering question replaces the cutting question. It is not one ranked list — it is four questions asked in order, and each one eliminates most of what's left.

Nothing enters the ladder at all until its code path is verified. A keyword the product can't actually serve is not a low priority, it's a reject.

### The ladder

```
0  ALREADY RANKING    positions 5-15      retitle, re-index. no new pages
1  CAN DO, NO PAGE    capability + demand  the page is simply missing
2  CONVERTS, NO PAGE  money pages          traffic needs somewhere to go
3  ONE CLUSTER        feeds the best money page, built out completely
4  EVERYTHING ELSE    batched by page type
```

**Tier 0 — what already ranks.** Before writing anything new. The page exists, Google already judged it relevant, and the fix is a title, an H1 and a first `<p>`.

The click-through curve is why this outranks everything: roughly 45.8% at position one, about 1.42% at position ten, and almost flat between five and fifteen. Tenth to fifth is around seven times the traffic. Tenth to first is around thirty. Nothing written from scratch returns that for thirty seconds of work.

Skip this tier if the site is new and nothing ranks yet.

**Tier 1 — capabilities with demand and no page.** The highest-return tier for a live product, and the one most often skipped. The capability already works, people are already searching for it, and there is nothing on the site to rank. No build risk, no "will this work" risk — a missing page.

This is the tier that produces results like a working capability sitting behind a 2,900/month search with no page pointing at it. The settings schema is the same mine — every option is somebody's search.

**Tier 2 — money pages that don't exist.** Build the pages that convert before the pages that feed them. Informational content shipped first produces traffic with nowhere to go, which is the standard way to waste a quarter.

**Tier 3 — one cluster, finished.** Not the ten best-scoring keywords scattered across eight topics. Pick the cluster that feeds your strongest money page and build all of it.

**Tier 4 — the rest**, in batches by page type.

### Within a tier, score

```
+ traffic potential       the cluster sum, never the head term's volume
+ current position        weight this heaviest — ranking beats not ranking
+ commercial intent       over informational
+ cpc                     proxy for whether this traffic converts for anyone
- difficulty
- serp features           each one eats the click before you get it
- build cost              word count, and whether the code path already exists
```

### Batch by page type, not by score

Score says what is worth doing. Page type says what to do **together**.

Ship all the audio pages, then all the platform pages — not the twenty highest-scoring pages spread across eight types.

The reason is feedback, not rate limiting. After each batch the Page Indexing report tells you something specific: these got indexed, those didn't. If the batch was one page type you have learned whether that template works. If it was scattered you have learned nothing you can act on.

That is also the honest answer to "why not ship everything at once". You can — Google sets no rate limit. But the first batch tells you whether the pages are too thin or too alike, and that is worth knowing before four hundred of them exist.

### What flips the order

**No domain authority yet.** Head terms are wasted effort for months regardless of score. The order becomes long tail, integration and comparison pages, and getting mentioned on other people's pages — the one channel where being new isn't disqualifying. See `08-aeo.md`.

**Live with real traffic.** Tier 0 dominates, and you may not need to write anything for weeks. Once the site has a Search Console history, stop guessing at tier 0 and let `scripts/review.py` rank it — see `09-review.md`. Your own query data beats any keyword tool for this, and it is the one source Google gives you for free.

### What you deliberately don't do

Head terms you cannot win. A keyword scoring well on volume and intent is still the wrong choice when the top ten are established brands with thousands of referring domains. Park it, write the reason in the reject column, move on. Re-check it when the site's own authority has moved, not before.

---

## Output

`seo/keywords.csv`, one row per keyword:

```
cluster, keyword, role, target_url, volume, country, cpc, serp_features,
intent, traffic_potential, difficulty_proxy, business_fit,
current_position, current_url, parent_topic, code_path, decision, notes
```

`decision` is **build**, **later**, or **skip**. Everything skipped keeps its reason, so the same keyword doesn't get researched twice.

Then show the user the clusters sorted by traffic potential. **They approve batches, not a capped list** — typically one batch per page type. Business fit is the one thing only they can score.
