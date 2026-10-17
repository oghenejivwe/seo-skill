# Phase 0 — Understand the project

Goal: a short, honest description of what this thing actually does, who it's for, and what it can't do. Everything downstream depends on it, and a wrong answer here produces pages that rank for searches the product can't satisfy.

## Read the code, not the copy

Landing pages overstate. Not dishonestly, usually — they describe the roadmap in the present tense, or they describe the best case as the typical case. If you take keywords from the homepage, you inherit that, and you end up targeting searches where a visitor arrives, finds the thing doesn't do what they came for, and leaves.

A bounce from a page you ranked is worse than never ranking, because you spent the budget and bought a negative engagement signal.

So work from the source:

| Look at | To learn |
|---|---|
| Routes / pages / app directory | What surfaces exist, which are public, which are gated |
| Models, schema, migrations | What objects the product actually manipulates — these are your entities |
| API surface, controllers, handlers | What it can do, in verbs |
| Feature flags, env vars, config | What's shipped versus half-built versus off |
| Auth and pricing code | Who it's for, what tiers exist, what's free |
| Package manifest, integrations | What it connects to — integration queries are high-intent and under-served |
| README, CHANGELOG | Intent and recent direction |
| Tests | The behaviours someone cared enough to protect |

Then read the marketing copy, if any exists, and **diff it against what you found**. Where they disagree, tell the user plainly. That conversation is usually valuable on its own and it's the right moment to have it, before anything is written.

## What to produce

Write `seo/project.md`. Keep it short enough that it can be pasted into a prompt.

```markdown
# <project>

## What it is
One paragraph. Plain words. What a user can actually do with it today.

## Who it's for
The specific person. Not "businesses" — "a solo founder who needs X and
currently does it in a spreadsheet".

## What it genuinely does
- verb + object, one line each, only shipped behaviour

## What it doesn't do
- the things the copy implies and the code doesn't support
- the adjacent things people will assume it does

## Entities
The nouns the product manipulates. These become the vocabulary everything
else is built from — keywords, URLs, headings, schema.

## Integrations
What it connects to. Each one is a potential page and usually under-served.

## How it makes money
Free, freemium, subscription, marketplace, ads. Determines which keywords
are worth anything.

## Conversion event
What counts as a win. Signup, booking, purchase, install, lead.

## Competitors
3–5, with URLs. Direct ones and the "what people use instead" ones —
often a spreadsheet, a notepad, or an agency.

## Stage
pre-launch / live with no traffic / live with traffic
```

## The stage question changes everything

Ask, or infer, and record it — the rest of the skill branches on this.

**Pre-launch, no domain history.** You cannot rank for anything competitive for months, because there's no authority to rank on. Spending phase 3 on head terms is wasted. Weight the plan toward: the long tail, integration and comparison pages, and AI-search citation work, which is the one channel where a new project can appear immediately. See `08-aeo.md`.

**Live, no traffic.** Something is usually broken rather than missing. Run phase 4's audit early — out of order is fine — because a JavaScript-rendering problem or a blocked crawler explains more zero-traffic sites than bad content does.

**Live with traffic.** You have real query data. Phase 1 gets much better and much cheaper: Search Console tells you what you already rank for, and the fastest wins are pages already sitting just outside the top few positions. Prioritise those before writing anything new.

## Before moving on

Show the user `seo/project.md` and ask them to correct it. They know things the code doesn't say — who's actually buying, which feature people really come for, what the sales conversations keep circling back to. Two minutes of correction here saves rewriting phase 1.
