# Phase 3 — Content

Goal: pages that satisfy the intent their cluster owns, written in a voice a human would read.

**Invoke the `no-ai-tells` skill for the prose on every page.** Not as a final polish — as part of writing. Copy that reads like a chatbot produced it gets bounced, and bounce feeds back into ranking, so this is part of the work rather than a matter of taste.

---

## The page contract

Four parts. The first two come from data, the third comes from a human, the fourth is structural.

### 1. From the cluster

```
primary keyword        the cluster head
variations             same page, no separate action
faq / section keywords become headings on this page
secondary keywords     flagged for possible future pages
traffic potential      sum of cluster volume
intent                 informational / commercial / transactional
page type              from structure.yaml
code path              the thing that actually serves this query

title                  from structure.yaml. carries the primary keyword
h1                     from structure.yaml. carries the primary keyword
lede                   from structure.yaml. carries the primary keyword
```

**The last three arrive already decided.** Phase 2 wrote them and `scripts/plan_check.py` passed them, so drafting does not get to invent a title or wander into a different opening sentence. If a page genuinely needs different ones — the SERP read in part 2 changes what the page should be — change them in `structure.yaml`, re-run the check, and carry on. Never only in the draft, or the plan and the page quietly disagree about what the page is for.

### 2. From the SERP

Open the top five results and read them. All of them.

```
word count      average of the top 3, excluding forums
section count   average of the top 3
media           images, charts, tables, video?
table stakes    topics all five cover — you must too
gaps            what all five miss — your differentiation
questions       People Also Ask for this cluster, reworded
format          what shape actually ranks
```

**Word count is an observation, not a target.** Brief to the low end of the range. Lean copy that covers everything beats padded copy that covers it twice.

### 3. From the human — the gate

```
>= 1 story          something that actually happened
>= 2 numbers        real, with source and date
>= 1 original image screenshot, photo, diagram you made
1 opinion           what's overrated, wrong, or misunderstood here
```

This is what separates a content system from a slop machine. Everything else here can be assembled from public information, which means everyone can assemble it.

**If the project has none of them, stop and ask.** A page with invented specifics is worse than a thin one, because it's wrong rather than merely light. For a pre-launch project the honest substitute is why you built it, what you tried first and abandoned, benchmarks you ran, screenshots of the real product.

### 4. Structure

**Answer first.** Open every section with the answer, then the context. Readers scan the start and end of a passage and skim the middle; models weight them the same way.

**Sections stand alone.** Any section should make sense read cold, because that's how AI systems chunk pages and you don't control the boundaries.

**Direct answers under question headings.** About twenty-five words, before any elaboration, no links inside. Every question heading gets an `id` so outreach replies can link straight to the answer.

**Name things specifically.** Specific entities and relationships give readers and machines something to work with.

**One idea per sentence.** If it needs a second reading, split it.

**Cite everything, then verify it.** Fetch each URL, confirm it resolves, confirm the claim is on the page. Models produce plausible sources that don't exist.

**Formats that get quoted.** Tables, numbered lists, FAQ blocks, comparison matrices get lifted into AI answers in a way paragraphs don't.

---

## Quality gates, not rate limits

There is no cap on how many pages ship or how fast. Google's spam policies define scaled content abuse as many pages generated mainly to manipulate rankings rather than to help users — they set no page count and no publishing rate. Google's crawl-budget guidance is written for sites over a million pages changing weekly, or over 10,000 changing daily; it tells smaller sites that a current sitemap and the Page Indexing report are enough.

So the check is quality per page, applied to every page.

**Before a page ships:**

```
[ ] the capability is verified in the code, on a real input
[ ] the copy passes the duplicate check (scripts/audit.py)
[ ] the keyword is in the title, the H1 and the first <p>
[ ] every FAQ answer opens with the answer
```

**Batches or all at once — the founder chooses.** The default is one batch per page type: all the audio pages, then all the platform pages, at any size. Each batch's Search Console data then shows which page types get indexed and draw impressions before the next batch is written. **The user approves each batch, not each page.**

### Matrix pages carry the most risk

Format A to format B, one page per platform, each tool in each language — these reach the most keywords and are the most likely to come out near-identical.

Give each one facts specific to it, taken from the code. A tool registry or capability table usually records what each variant loses, what its limits are and where it behaves differently, and that is the material that makes pair pages genuinely differ. If the codebase has no such record, the pages have nothing to differ on and the honest move is to say so rather than pad them.

**Vary the sentence patterns too.** A matrix invites one template sentence repeated with a word swapped. Repeated lede shapes read as templated to people and to Google. `scripts/audit.py` flags repeated openings across pages.

---

## Treat copy as data

Keep page copy in a structured file that a build step turns into the site, rather than hand-editing templates.

Then **validate it by running that real parser before handoff**, not a stand-in:

```
[ ] every page parses
[ ] title <= 60 characters
[ ] meta <= 160 characters
[ ] every link resolves
[ ] every FAQ answer leads with the answer
```

### Fingerprint copy against capability

Record, per page, which capability data its copy was checked against — settings schema included — and fail a test when that data changes.

The failure this prevents: copy checked against the obvious surface — formats, operations, endpoints — while the settings schema goes unread. The errors that follow skew toward telling readers a tool *cannot* do something it can, which is the expensive direction. A visitor who is told the feature is missing leaves; one who finds it works is merely surprised.

Copy drifts out of true when the product moves. A fingerprint turns that into a failing test instead of a customer discovering it.

---

## Check the first sentence in the rendered page

"The three places that matter most" names the first sentence of body copy. Check it in the **rendered HTML**, not the source file, because template elements sit between the H1 and the copy.

The common failure: the first `<p>` under the H1 is template furniture — a trust line, a privacy claim, an upload hint, a paste instruction. The keyword appears further down, so a naive first-100-words check passes while the sentence Google reads first says nothing about the topic. Interface copy sits in that slot on most tool pages, and it is invisible in the source file because the template inserts it.

The fix is a one-sentence lede, rendered as the first `<p>` under the H1 and above the tool. `scripts/lint.py` enforces it at error level.

---

## Per-page on-page rules

`scripts/lint.py` checks these. Run it before a page is considered done.

```
title           primary keyword, front-loaded, <= 60 chars, unique sitewide
meta            150–160 chars, keyword present, ends with a reason to click
h1              exactly one, contains the primary keyword, mirrors the title
                NOT a tagline
first <p>       the first paragraph under the H1 contains the keyword
                and is real copy, not interface text
headings        sequential. h2 then h3, never skip a level
url             matches the declared pattern, contains the keyword
internal links  editorial, generated from structure.yaml, and they resolve
external links  2–3 to real sources, verified
images          descriptive filenames, real alt text, WebP, lazy-loaded
schema          per the page type in structure.yaml
faq             every question heading has an id; answers open with the answer
ai-writing      sentence-length spread, em dashes, "rather than" / "not just"
```

### The three places that matter most

Every page carries its target phrase in all three. No page ships without them.

1. **The title tag**
2. **The H1**
3. **The first sentence of body copy, as rendered**

The URL is worth including when it is still being decided, and the meta description is free to fill while you are in there — but Google rewrites a large share of meta descriptions, so neither carries the same weight as these three.

Both ends are enforced, deliberately. `scripts/plan_check.py` blocks the plan before a page is written; `scripts/lint.py` blocks the page afterwards, at error level, checking the rendered HTML rather than the template. Passing the first and failing the second means the template moved something — almost always interface copy landing in the first `<p>`.

Stating the limit honestly: three string edits do not guarantee a ranking, and claiming otherwise would be dishonest. What they do is remove an ambiguity you control. A page that never names its own subject in the places Google looks is leaving clicks and impressions on the table for no reason, and the edit takes about thirty seconds.

---

## For a site that already has pages

If phase 0 found content ranking anywhere, **fix that before writing anything new.**

```
1. Search Console → filter position > 4.9
2. For each page in that band:
     click the keyword → see which page it lands on
     click the page → remove the query filter
     → every query that page already gets traffic for
3. Choose the target: real impressions, AND it describes the page,
   AND it serves the conversion event.
   Highest impressions is not automatically right.
4. Put that keyword in the title, the H1, and the first <p>
5. Search Console → URL Inspection → Request Indexing
```

Click-through collapses below the top few positions, so a page sitting tenth earns almost nothing despite being judged relevant. And you start from something already indexed rather than waiting for discovery.

If nothing moves within a fortnight, check in order: **intent mismatch** (is the page type what the SERP shows?), then **depth** (what do the top three have that you don't), then **links**.
