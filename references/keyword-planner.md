# Keyword Planner and Similarweb

Google Ads Keyword Planner is the only free source that returns volumes for thousands of
keywords at a time, and Similarweb's trial is the only free way found to discover competitors
you don't already know about. Together they replace the free volume APIs as the main source.
The free APIs cap out around 50 lookups a day, which is weeks of waiting for a list of a few
thousand phrases. One Planner upload clears the same list in a single pass.

This file is the procedure. It exists because the sequence, the defaults and the browser
quirks took about six hours to work out the first time, and almost none of it is discoverable
from the interface.

**Two rules that override everything below.** Never enter payment details and never create a
campaign. Never bypass a CAPTCHA or a bot check: the user signs in and creates accounts
themselves, and you drive the tool only once they hand you a signed-in tab.

---

## Contents

- [The account, with nothing charged](#the-account-with-nothing-charged)
- [Ranges, not exact numbers](#ranges-not-exact-numbers)
- [Two defaults that corrupt a run](#two-defaults-that-corrupt-a-run)
- [Volumes for a list you already have](#volumes-for-a-list-you-already-have)
- [Competitor ideas, one run per domain](#competitor-ideas-one-run-per-domain)
- [Local ideas, one run per market](#local-ideas-one-run-per-market)
- [What market size actually looks like](#what-market-size-actually-looks-like)
- [Driving Planner in a browser](#driving-planner-in-a-browser)
- [Similarweb on the free trial](#similarweb-on-the-free-trial)
- [Order of work](#order-of-work)

---

## The account, with nothing charged

Keyword Planner needs a Google Ads account. It does not need a campaign, and an account with
no campaign is never billed. The trap is that the signup flow is built to walk you into a
campaign, so the goal is to get through it and land on an account with nothing running.

The user does this part. Walk them through it rather than driving it:

1. Start the "Create your first campaign" flow and fill in the business name and website.
2. Skip "link accounts" when it is offered.
3. At the goal step, choose **"Set up an account only"**. This is the step that matters.
   Every other option starts a campaign.
4. The last screen shows payment settings. The user finishes that step themselves.

Once the account exists, Keyword Planner sits under Tools.

**Ask before the user picks the account settings.** Billing country, time zone and currency
cannot be changed afterwards. Getting one wrong means a new account and re-running
everything. Billing country also sets the default location target, which is the first default
you have to override on every run.

| Setting | Why it matters | Reversible |
|---|---|---|
| Billing country | sets the default location target in every tool | no |
| Time zone | the dates on any downloaded metrics | no |
| Currency | the cost columns in every export | no |

---

## Ranges, not exact numbers

An account with no ad spend gets volume ranges rather than measured numbers. The interface
shows "10K - 100K"; the CSV export writes a single value per bucket.

| Export value | Means |
|---|---|
| 500000 | 100K - 1M |
| 50000 | 10K - 100K |
| 5000 | 1K - 10K |
| 500 | 100 - 1K |
| 50 | 10 - 100 |
| 0 | 0 - 10 |
| empty | no data |

Store the bucket's **lower bound**, not the export value, and record the range in the source
column. Two reasons. A range of 10K - 100K imported at 50000 outranks a measured 40000 from
another source, which is a guess beating a fact. And whoever reads the bank six weeks later
needs to see at a glance which numbers were measured and which were bucketed.

Import the "no data" rows at 0 rather than dropping them. They stay in the bank, and the free
lookups skip them instead of spending a day's quota rediscovering that there is no data.

**The exact-numbers option exists, and it is not yours to take.** A small running campaign
(around $1 a day, paused after two days) sometimes unlocks exact volumes. Sometimes it
doesn't. It costs the user money, it needs their payment details, and the decision is theirs.
Mention it only if the ranges prove too coarse to rank a list, present it as an option, and
never set it up yourself.

In practice the ranges are coarse but workable. Lower bounds sort a few thousand keywords into
a usable priority order, and the bucket boundaries sit far enough apart that the ordering
survives the uncertainty.

---

## Two defaults that corrupt a run

Both of these produce output that looks like data and isn't.

**Location defaults to the account's billing country.** A run you believe is for Japan returns
numbers for the billing country, with no warning in the interface or in the export.

**Language defaults to English.** A run for a non-English market returns only the English
keywords that happen to appear in that market, which is a short and misleading list. The usual
symptom is a market that looks tiny when it isn't.

Set both before trusting a number, on every run, including the second run in the same session.
If a market returns fewer than about 20 ideas, check these two settings before concluding the
market is small.

---

## Volumes for a list you already have

Use **"Get search volume and forecasts"** when you already have the phrases and want numbers.

Prepare one file per market:

- CSV, a `Keyword` header, one phrase per row.
- Thousands of rows upload fine in one go.
- Merge close variants first, because Google gives close variants the same number anyway. A
  deduped list is shorter and leaves fewer rows to reconcile on the way back in.

After the upload, set the plan's location, and the language for any non-English list. Then
download **"Plan historical metrics"** as CSV.

**That file is not a plain CSV.** It is UTF-16 encoded, tab-separated, and carries two title
lines before the header row. A reader that assumes UTF-8 and commas gets one column of
mojibake, and a reader that assumes the header is line 1 treats the header as data. Open it
with `encoding="utf-16"`, `delimiter="\t"`, and skip two lines. The importer in `scripts/`
handles this already; the details are here for when the format changes.

Scale to expect: one pass resolves a few thousand phrases, with roughly a third coming back
with a range and the rest at the bottom bucket or no data. That single upload is the difference
between a queue that drains in a day and one that drains in a month.

---

## Competitor ideas, one run per domain

**"Discover new keywords"**, then **"Start with a website"**. This is the highest-yield run in
the whole procedure, because Google tells you which searches it associates with a site that
already ranks.

- Choose the **entire site**, not the single page.
- Run it in the main market, with location and language set as above.
- Download **"Keyword ideas"** as CSV.
- One run per competitor domain, one file per domain, named for the domain.

Sizes to expect: a site with a real set of public pages returns 800 to 2,000 ideas. A site with
thin public pages, one landing page, or everything behind a login returns under 200. A small
set is information about that competitor rather than a failed run.

**Keep every competitor's set.** These files are the input to the open-gap test, where a
keyword counts as open when it has volume, no page of yours targets it, and it appears in no
competitor's ideas set. You cannot reconstruct that test later without re-running every domain.

---

## Local ideas, one run per market

**"Discover new keywords"**, then **"Start with keywords"**, for markets where you have no
competitor to seed from.

**Ten seeds per run is Planner's limit.** Spend them on the product's core jobs, written the
way people in that market actually search, not translated from the English marketing copy. A
literal translation of a product name returns nothing. The blunt phrase a native would type
returns the market. For a file-conversion tool the English seeds are the format pairs and the
verbs: `png to pdf`, `heic to jpg`, `compress image`, `resize photo`. The German seed is `bild
verkleinern`, which is what people type, rather than a translation of "image compressor". If
you are unsure of the local phrasing, ask the user before spending the run.

Set location to the country and language to the local language. Both, every time.

**Countries that share a language share a run.** Switzerland with Austria in German, the UAE
with Egypt in Arabic, Hong Kong with Taiwan in Traditional Chinese. The ideas come back the
same, you save a run, and you reconcile the country column afterwards.

---

## What market size actually looks like

Output size varies by two orders of magnitude between markets. Knowing the shape in advance
stops you debugging a run that worked.

| Market shape | Ideas per run | What it means |
|---|---|---|
| Large population, Google dominant | one to several thousand | real market, filter hard |
| Small language market | tens to low hundreds | that is the whole market |
| Population searches in English | single digits to tens | wrong language, not a small market |
| Google is not the search engine | nothing useful | skip the market |

Four things follow.

Large markets return more ideas than you can use, most of them off-topic or unservable. The
work there is filtering, not harvesting.

Small markets, the Nordics being the clearest case, return a few dozen ideas and that is the
complete picture. A run returning 40 ideas is finished. Re-running it will not produce more.

Some markets return almost nothing in the local language because the people there search in
English. India is the standard case: a Hindi run can come back in single digits while the same
country in English returns a full list. When a populous market looks empty, re-run it in
English against the same country before writing the market off.

Where Google is not the search engine, Planner has nothing to tell you. Mainland China is the
clear case, so skip it and run Hong Kong and Taiwan instead. Check search-engine share before
spending a run on any market you are unsure about.

---

## Driving Planner in a browser

Planner is slow and the tab freezes for seconds at a time. Several of the failures below look
like a broken script and are actually the page catching up.

**One tab, large window, about 1536x820.** In a narrow window the metric columns and the
download button fall outside the viewport, and nothing you click lands where you expect.

**Drive it with page script, not coordinates.** The layout shifts as results load, so a
coordinate read off a screenshot is stale by the time you use it. The handles that stay put:

| What | How to reach it |
|---|---|
| Location settings | `[aria-label^="Locations settings"]` |
| Language settings | `[aria-label^="Language settings"]` |
| Clear the location list | `[aria-label="Remove all targeted locations"]` |
| Add a location | focus the dialog input, type the country, click the first "Include" |
| Run the query | the button whose text is "Get results" |
| Download | the icon whose text is `file_download`, then the menu item ".csv" |

**File uploads need a hook.** "Upload a file" opens a native file picker, which is invisible to
an agent and cannot be dismissed from the page. Hook `HTMLInputElement.prototype.click` first,
so file inputs are captured instead of opening the picker. Then click the button, attach the
file to the captured input, and dispatch a `change` event. In the other order the tab sits
blocked behind a dialog you cannot see.

**Start each market from a fresh form.** The seed editor on the results page is unreliable:
removing chips with Backspace scrolls the page, and it is easy to lose track of which chips are
left. Go back to a clean "Discover new keywords" form for each market instead of editing the
previous one.

**Downloads land in the user's Downloads folder**, all with similar names. Move each file into
its own folder straight after the download, named for the run that produced it. Then check the
row count before importing anything. A leftover file from an earlier run was once imported
under the wrong market, and that error is invisible once the rows are in the bank.

**The "turn off ad blockers" banner is often wrong.** Google Ads shows it when its own scripts
load slowly, with no ad blocker involved. Check the network panel before telling the user they
have one.

---

## Similarweb on the free trial

The trial runs about a week, so use it in week one and get the competitor list out of it first.
The user signs up themselves. What is worth the time:

**Similar sites** returns around 40 domains per site, and it is the best competitor discovery
available for free. Run it on the three to five competitors you already know and it surfaces
the ones nobody had listed. Every domain it finds becomes a Planner website-ideas run, which
is where the volume actually comes from.

**Country order** under Audience > Geography shows the top five countries for a domain. The
percentages are hidden on the trial, so you get a ranking and not a size. That is still enough
to decide which markets to research first.

**Referral sources** are visible and worth reading.

What is locked or not worth the clicks:

| Feature | State on the trial |
|---|---|
| Keyword lists | locked, "available in our Custom packages" |
| Search overview | a site's top 5 keywords only |
| Per-country data | locked |
| AI brand visibility | useless: it does not know new sites, and "Get started" does nothing |

Treat the trial as competitor discovery with a country ranking attached. Do not plan around its
keyword data, because you will not get any.

---

## Order of work

1. The user opens the Google Ads account with no campaign, and the Similarweb trial, on day
   one. The trial clock starts the moment they sign up.
2. Similarweb similar-sites on every competitor you know, to get the full competitor list.
3. Planner website ideas for every competitor domain, main market, one file per domain.
4. Planner local ideas per target market, ten local seeds, location and language set.
5. Planner volumes for whatever is left in the bank, one upload per market.
6. Import, merge close variants, filter, then reclassify against the pages that already exist.
7. Gap report, variant map and the open-gap test, then put the five groups to the user.
8. Re-rank the indexing queue by volume, highest measured first.
9. Write briefs in this order: group 1 plus the open gaps, then group 2, then groups 3 and 4
   once the user has decided whether those services are worth building at all.

Steps 3 to 5 produce the rows. Steps 1 and 2 are the ones people skip, and skipping them means
running Planner against only the competitors you happened to already know.

Step 9's order is not arbitrary. Group 1 and the open gaps are the cheapest wins on the board --
group 1 is wording on pages that already exist and rank, and an open gap has no incumbent page to
outrank. Group 2 is real work on proven demand. Groups 3 and 4 commit the product to building
something, so they are the user's call and not yours.

## Running it

One `planner_import` per export, then the two reports:

```bash
# every Planner download, one call each. --into is what puts it in the bank.
python scripts/planner_import.py downloads/us-ideas.csv     --country us --label competitor-ideas --into seo/keywords.csv

python scripts/planner_import.py downloads/de-local.csv     --country de --label local-ideas --into seo/keywords.csv

# what nobody targets, plus the open-gap test
python scripts/gap_report.py --bank seo/keywords.csv     --targets seo/page-register.csv --competitors seo/competitors --min 1000

# which existing page absorbs which variant, and what to leave alone
python scripts/variant_map.py --bank seo/keywords.csv     --rules seo/variant-rules.json --register seo/page-register.csv
```

**`--into` is not optional in practice.** Without it the import sits in `seo/imports/` and both
reports read the bank, so a harvest that worked looks like a harvest that found nothing. The
script says so when you leave it off.

### The files these read, and who writes them

| File | Written by | Holds |
|---|---|---|
| `seo/keywords.csv` | `planner_import --into` | the bank: keyword, country, volume, source |
| `seo/keywords.config.json` | you, once per project | the per-market filters. Start from `assets/keywords.config.example.json` |
| `seo/page-register.csv` | you, as pages ship | page, its original target phrase, that target's volume |
| `seo/variant-rules.json` | you, after the first gap report | ordered pattern-to-page rules for group 1 |
| `seo/competitors/` | Planner downloads | one ideas export per competitor, **named with the market code** (`us-rival-com-ideas.csv`) |

The market code in a competitor filename is what scopes the open-gap test. A file with no
market code cannot be attributed to a market, so it is read but tested against nothing, and
the report says which markets it could actually cover.
