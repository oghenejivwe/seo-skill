# Phase 4 — Technical

Goal: nothing on the site silently prevents it being crawled, understood or ranked.

Run `scripts/audit.py <url>` for the deterministic checks. Everything below that script can't test needs a look by hand.

---

## The three that invalidate everything else

Fix these before anything else, because while any of them is broken the rest of the work is invisible.

### 1. Rendering

**ChatGPT's crawler does not execute JavaScript.** Gemini and Copilot do. Googlebot does, but with delay and not always reliably.

If your content only exists after JavaScript runs, a meaningful share of crawlers see an empty shell.

```
Test: load the page with JavaScript disabled.
      If the content disappears, this is your first problem.
```

Fix with static generation or server-side rendering. For a framework that supports both, choose static for anything that doesn't genuinely need to be dynamic. Pre-launch this is a cheap decision; after launch it's a migration.

### 2. Crawler access

```
fetch /robots.txt
check for Disallow against:  GPTBot  OAI-SearchBot  ClaudeBot  Google-Extended
```

Sites block AI crawlers by accident constantly — inherited from a template, or set by a default they didn't know was on. **If the site sits behind Cloudflare, check its AI-bot management setting specifically**, because it blocks these by default and nothing in the repository will show it.

Blocking them is a legitimate choice if the user wants it, but it should be a choice. Opting out mostly means competitors get named in answers instead.

### 3. Sitemap

A sitemap that exists, lists every page you want indexed, updates automatically when pages are added, and is submitted to both Google and Bing.

Bing matters more than its market share suggests, because ChatGPT's search runs on Bing's index.

---

## The rest of the checklist

### Crawl and index
- `sitemap.xml` present, auto-generating, submitted to Google and Bing
- `robots.txt` present, AI crawlers allowed, admin and checkout paths disallowed
- No stray `noindex` — check page meta, the global setting in any SEO plugin, and the CMS "discourage search engines" toggle
- No canonical tags pointing somewhere unintended
- Every page reachable by at least one internal link
- Nothing important more than three clicks from home
- A 404 page that offers search and links onward rather than dead-ending

### Speed
```
LCP   under 2.5s
INP   under 200ms
CLS   under 0.1
```
Test mobile first — Google indexes mobile first, and mobile scores are almost always worse. Use two tools, because they disagree.

Speed matters more for AI retrieval than for classic ranking: when a model fetches and parses pages live, a slow page can be dropped before it's even scored.

Usual fixes, in order of payoff: convert images to WebP, compress or lazy-load video, minify, remove third-party scripts nobody asked for, enable caching, use a CDN.

### Structure
- Exactly one H1 per page
- Headings sequential — never jump from h2 to h4
- URLs match the declared pattern
- No two pages targeting the same primary keyword
- No orphan pages

### Schema
Add per page type, and validate — the validators disagree with each other, so use two.

| Page type | Schema |
|---|---|
| home | `Organization`, `WebSite` |
| product / feature | `SoftwareApplication` or `Product` |
| pricing | `Offer` |
| guide / blog | `Article` |
| anything with an FAQ block | `FAQPage` |
| comparison | `Article` + `ItemList` |
| local business | `LocalBusiness` — see `07-local.md` |

Evidence that schema directly improves AI citation is mixed. Evidence that it drives rich results in classic search is not. Add it; don't spend a week on it.

### Security and hygiene
- HTTPS with a valid certificate
- No credentials in client-side bundles — anything prefixed `NEXT_PUBLIC_`, `VITE_`, `PUBLIC_` or `EXPO_PUBLIC_` ships to every visitor
- Images: descriptive filenames, real alt text, WebP, lazy-loaded

---

## A note on build target

**On WordPress or a similar CMS**, an SEO plugin handles most of this by default — sitemap, schema, canonical tags, meta fields. You're configuring rather than building.

**On a custom or AI-generated codebase**, none of it is free. Every item above has to be built deliberately, and this is exactly where sites built quickly fall down: the content is fine and the sitemap doesn't exist. Asking a coding agent for "a detailed SEO audit" will miss a lot. Give it this checklist item by item instead.

---

## Output

Write findings to `seo/audit/` as a dated report, ranked by impact rather than by category. A blocked crawler and a missing alt tag are not the same severity and shouldn't be listed as though they are.
