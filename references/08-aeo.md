# AI search visibility

Read during phase 3.

Showing up in ChatGPT, Gemini, Claude and Perplexity is mostly the same work as ranking in Google. Those assistants run searches and summarise what comes back, so if you're invisible to search you're invisible to them.

Three things genuinely differ, and one of them matters enormously for a new project.

---

## 1. You're competing for mentions, not positions

In classic search, being first wins. In an AI answer there is no first — the model reads a dozen sources and synthesises. The brand named most often across those sources is the one that ends up in the answer, even if your URL is the top citation.

So the work shifts outward. Being on other people's pages — roundups, comparisons, "best X for Y" lists, forum threads — matters more than any single page you control. Branded mentions across the web correlate with AI visibility more strongly than backlinks do.

**For a pre-launch project this is the single most useful fact in this file.** Domain authority takes months. A mention in a roundup published tomorrow can put you in an answer tomorrow. It's the one channel where being new isn't disqualifying.

Practical:
- Find the "best X" and "X vs Y" pages in your category that don't mention you. Those are your targets.
- Pitch with something of value — data you have, a free tier, an interview — not a request.
- Answer real questions in the communities where your users already are. Say who you are and where you work, and give a genuinely useful answer. Five honest contributions beat five hundred automated ones, which get removed and get the account banned.
- Video is under-supplied in unglamorous B2B categories. Nobody makes videos about niche integrations, and nothing stops you.

## 2. The tail is much longer

People type six words into Google and twenty-five into a chat window, with follow-ups. The result is a long tail of very specific questions, many of which nobody has ever searched and therefore nobody has written about.

That's an opening. If you're the only page answering a specific question, you're the only possible citation.

Where those questions come from:
- Sales calls and support tickets. Whatever people keep asking you.
- Convert your target keywords into the questions a person would actually ask around them.
- Simulate the decomposition: ask a model to answer a question from its own knowledge with no search, then ask it which searches it would run to verify each claim it just made and to fill what it missed. Those are the sub-queries. Use them to check topic coverage — not as keyword targets, since almost none have measurable volume.

## 3. Documentation and help content is badly under-used

A large share of chat questions are "can it do X", "does it work with Y", "how do I Z". That's documentation territory, and SEO work almost never touches it.

- Put docs in a subdirectory, not a subdomain
- Cross-link articles to each other
- Fill the tail: you have pages for the common questions and nothing for the obscure integration nobody has written about. That obscure one has no competition at all.

---

## Writing for it

Everything in `04-content.md` applies. Three habits matter disproportionately:

**Answer immediately under the heading.** About twenty-five words, before any elaboration. This is what gets lifted.

**Sections that stand alone.** Models chunk pages and you don't control the boundaries. A section that depends on three paragraphs of earlier context breaks when it's quoted on its own.

**Specific over general.** Name the entities, give real numbers, cite the source. Vague claims don't get quoted because there's nothing to quote.

One more worth knowing: if you invent a framework or a term, **attach your name to it**. Otherwise models absorb the idea and repeat it as common knowledge with no attribution.

---

## Technical

Covered in `05-technical.md`, but the one that bites hardest:

**ChatGPT's crawler doesn't run JavaScript.** If the content needs JS, it sees nothing. Test by disabling JavaScript and reloading.

Also check `robots.txt` for `GPTBot`, `OAI-SearchBot`, `ClaudeBot` and `Google-Extended`, including whatever Cloudflare is doing by default.

---

## Measuring it

Harder than classic SEO, and worth setting up anyway because it only becomes useful with history.

**Ask the assistants directly.** Take the questions your money pages target, ask each major assistant, record whether you're named and who else is. Repeat weekly. Answers vary between runs, so ask each question a few times and in a couple of phrasings — you're measuring a rate, not a position.

**Segment AI referral traffic** in analytics by source.

**Ask your users.** "How did you hear about us?" with an AI assistant option. Most AI-driven discovery never shows as AI traffic — people read your name, then search your brand or type your domain. Asking is the only way to see it.

Expect the numbers to look small and the conversion rate to look large. Traffic from assistants is typically a low single-digit percentage of the total and converts several times better than search, because the model has already explained why you're a fit before the person arrives.
