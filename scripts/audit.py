#!/usr/bin/env python3
"""
Site-level technical SEO audit. Standard library only.

    python audit.py https://example.com
    python audit.py https://example.com --max-pages 200
    python audit.py https://example.com --psi-key $GOOGLE_API_KEY --json

Checks, roughly in order of how badly each one hurts:
  0. Host is alive          -- a dead host looks exactly like an SEO problem
  1. JavaScript dependency  -- ChatGPT's crawler does not execute JS
  2. Crawler access         -- robots.txt, Cloudflare, and a real user-agent sweep
  3. Sitemap sweep          -- fetch every URL, not just the home page
  4. Duplicate content      -- text-length spread and pairwise similarity
  5. Repeated openings      -- the duplicate problem at sentence level
  6. HTTP behaviour         -- HEAD, redirects, 404s
  7. Head tags              -- title, meta, H1, og:, schema
  8. PageSpeed              -- with --psi-key
"""

import argparse
import difflib
import json
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; seo-launch-audit/1.1)"
TIMEOUT = 30

AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Google-Extended", "PerplexityBot"]

# A CDN can block a user agent that robots.txt allows, so fetch as each one.
CRAWLER_UAS = {
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0; +claudebot@anthropic.com",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot",
}

# Hosting-provider error pages. These return 200 sometimes, so status alone misses them.
HOST_ERRORS = [
    (r"modal-http:.*is disabled", "Modal workspace disabled"),
    (r"\bDEPLOYMENT_NOT_FOUND\b", "Vercel deployment missing"),
    (r"Application error.*Heroku", "Heroku application error"),
    (r"Not Found - Request ID", "Netlify deploy missing"),
    (r"Error 1016|Origin DNS error", "Cloudflare origin DNS error"),
    (r"502 Bad Gateway|503 Service (Temporarily )?Unavailable", "Upstream error"),
    (r"This domain is parked|Buy this domain", "Parked domain"),
]


def fetch(url, timeout=TIMEOUT, ua=UA, method="GET"):
    req = urllib.request.Request(url, headers={"User-Agent": ua}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace") if method == "GET" else ""
            return r.status, dict(r.headers), body, r.geturl()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, dict(e.headers or {}), body, url
    except Exception as e:
        return None, {}, str(e), url


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_desc = ""
        self.og = {}
        self.robots_meta = ""
        self.canonical = ""
        self.h1 = []
        self.schema = []
        self.imgs = 0
        self.imgs_no_alt = 0
        self.body = []
        self._cur = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        # nav/header/footer are shared across every page. Counting them would
        # inflate both the similarity scores and the repeated-opening check.
        if tag in ("script", "style", "noscript", "nav", "header", "footer", "aside"):
            self._skip += 1
            if tag == "script" and a.get("type") == "application/ld+json":
                self._cur = "ldjson"
            return
        if tag == "title":
            self._cur = "title"
        elif tag == "meta":
            n = (a.get("name") or "").lower()
            p = (a.get("property") or "").lower()
            if n == "description":
                self.meta_desc = a.get("content", "")
            elif n == "robots":
                self.robots_meta = (a.get("content") or "").lower()
            elif p.startswith("og:"):
                self.og[p] = a.get("content", "")
        elif tag == "link" and "canonical" in (a.get("rel") or "").lower():
            self.canonical = a.get("href", "")
        elif tag == "h1":
            self.h1.append("")
            self._cur = "h1"
        elif tag == "img":
            self.imgs += 1
            if not (a.get("alt") or "").strip():
                self.imgs_no_alt += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "nav", "header", "footer", "aside"):
            self._skip = max(0, self._skip - 1)
        self._cur = None

    def handle_data(self, d):
        if self._cur == "title":
            self.title += d.strip()
        elif self._cur == "h1" and self.h1:
            self.h1[-1] += d.strip()
        elif self._cur == "ldjson":
            try:
                blob = json.loads(d)
                for n in blob if isinstance(blob, list) else [blob]:
                    if isinstance(n, dict) and n.get("@type"):
                        t = n["@type"]
                        self.schema += t if isinstance(t, list) else [t]
            except Exception:
                pass
        elif self._skip == 0:
            self.body.append(d)

    @property
    def text(self):
        t = re.sub(r"\s+", " ", " ".join(self.body)).strip()
        # Skip links sit outside nav and would otherwise be every page's
        # first sentence, hiding the real repeated-opening problem.
        return re.sub(r"^(skip to (main )?(content|navigation)\b[\s.,:-]*)+", "", t, flags=re.I)


def strip_js(html):
    no_script = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", no_script)).strip()


def host_error(body):
    for pat, label in HOST_ERRORS:
        if re.search(pat, body, re.I):
            return label
    return None


def first_sentence(text, words=6):
    s = re.split(r"(?<=[.!?])\s", text.strip())[0] if text.strip() else ""
    return " ".join(s.split()[:words]).lower()


def read_sitemap(origin, depth=0, seen=None):
    """Return the URL list, following sitemap indexes one level."""
    seen = seen if seen is not None else set()
    urls, found_at = [], None
    for cand in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/sitemap.txt"):
        u = urllib.parse.urljoin(origin, cand)
        if u in seen:
            continue
        seen.add(u)
        s, _, body, _ = fetch(u)
        if s != 200 or not body.strip():
            continue
        found_at = cand
        if "<sitemapindex" in body.lower() and depth < 2:
            for child in re.findall(r"<loc>\s*(.*?)\s*</loc>", body, re.I):
                cs, _, cbody, _ = fetch(child)
                if cs == 200:
                    urls += re.findall(r"<loc>\s*(.*?)\s*</loc>", cbody, re.I)
                    urls_lastmod_src.append(cbody)
        else:
            urls = re.findall(r"<loc>\s*(.*?)\s*</loc>", body, re.I)
            urls_lastmod_src.append(body)
        break
    return urls, found_at


urls_lastmod_src = []  # raw sitemap bodies, for lastmod counting


def check(url, psi_key=None, max_pages=50):
    parts = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    url = urllib.parse.urlunparse(parts)
    origin = f"{parts.scheme}://{parts.netloc}"
    out = {"url": url, "findings": [], "pages": []}

    def add(sev, area, msg, fix=None):
        out["findings"].append({"severity": sev, "area": area, "finding": msg, "fix": fix})

    # --- 0. host alive -------------------------------------------------
    status, headers, html, final = fetch(url)
    out["status"] = status
    if status != 200:
        add("blocker", "reachability", f"Home page returned {status}.",
            "Nothing else can be assessed until this resolves.")
        return out
    he = host_error(html)
    if he:
        add("blocker", "reachability", f"Site is serving a hosting error page: {he}.",
            "The site is down. Any Search Console or analytics data from this window is meaningless.")
        return out

    ex = Extract()
    try:
        ex.feed(html)
    except Exception:
        pass

    # --- 1. JS dependency ----------------------------------------------
    visible = strip_js(html)
    out["text_without_js"] = len(visible)
    if len(visible) < 500:
        add("blocker", "rendering", f"Only ~{len(visible)} characters survive with JavaScript removed.",
            "ChatGPT's crawler does not execute JS. Use static generation or server-side rendering.")
    elif len(visible) < 1500:
        add("warn", "rendering", f"~{len(visible)} characters without JavaScript - thin.",
            "Confirm the main content is server-rendered, not hydrated client-side.")

    # --- 2a. robots.txt -------------------------------------------------
    rstatus, _, robots, _ = fetch(urllib.parse.urljoin(origin, "/robots.txt"))
    robots = robots if rstatus == 200 else ""
    out["robots_txt"] = rstatus == 200
    if rstatus != 200:
        add("warn", "crawl", "No robots.txt found.", "Add one that allows crawlers and declares the sitemap.")

    blocked = []
    for bot in AI_BOTS:
        m = re.search(rf"user-agent:\s*{re.escape(bot)}\s*(.*?)(?=user-agent:|$)", robots, re.S | re.I)
        if m and re.search(r"disallow:\s*/\s*$", m.group(1), re.M | re.I):
            blocked.append(bot)
    out["ai_bots_blocked"] = blocked
    if blocked:
        add("blocker", "crawl", f"robots.txt blocks: {', '.join(blocked)}",
            "These sit behind ChatGPT, Claude and Google's AI surfaces. Remove unless blocking is deliberate.")
    if "sitemap:" not in robots.lower():
        add("warn", "crawl", "robots.txt does not declare a sitemap.", f"Add: Sitemap: {origin}/sitemap.xml")

    behind_cf = "cloudflare" in str(headers.get("Server", "")).lower() or "cf-ray" in {k.lower() for k in headers}
    if behind_cf:
        add("info", "crawl", "Site is behind Cloudflare.",
            "Check Cloudflare's AI bot management setting - it blocks AI crawlers by default and nothing in the repo shows it.")

    # --- 2b. user-agent sweep -------------------------------------------
    ua_results = {}
    for name, agent in CRAWLER_UAS.items():
        s, _, b, _ = fetch(url, timeout=20, ua=agent)
        ua_results[name] = s
    out["crawler_sweep"] = ua_results
    refused = [n for n, s in ua_results.items() if s != 200]
    if refused:
        add("blocker", "crawl", f"These crawlers do not get a 200: {', '.join(f'{n} ({ua_results[n]})' for n in refused)}",
            "A CDN or WAF is blocking a user agent that robots.txt allows. Check Cloudflare bot rules or your WAF.")

    # --- 3. sitemap sweep ------------------------------------------------
    urls_lastmod_src.clear()
    sm_urls, sm_path = read_sitemap(origin)
    out["sitemap"] = {"path": sm_path, "entries": len(sm_urls)} if sm_path else None
    if not sm_path:
        add("blocker", "crawl", "No sitemap found.",
            "Generate sitemap.xml and submit it to Search Console and Bing Webmaster Tools.")
    else:
        raw = " ".join(urls_lastmod_src)
        lastmods = len(re.findall(r"<lastmod>", raw, re.I))
        if sm_urls and lastmods < len(sm_urls):
            add("warn", "crawl", f"{len(sm_urls) - lastmods} of {len(sm_urls)} sitemap URLs have no lastmod.",
                "Accurate lastmod is how Google decides what to recrawl. At scale it matters more than indexing requests.")

    pages = []
    for u in sm_urls[:max_pages]:
        s, h, b, final_u = fetch(u, timeout=20)
        if s is None:
            pages.append({"url": u, "status": None})
            continue
        e = Extract()
        try:
            e.feed(b)
        except Exception:
            pass
        pages.append({
            "url": u, "status": s, "title": e.title.strip(),
            "meta": (e.meta_desc or "").strip(), "h1": [x for x in e.h1 if x.strip()],
            "text_len": len(e.text), "text": e.text,
            "og_desc": bool(e.og.get("og:description")), "og_img": bool(e.og.get("og:image")),
            "schema": sorted(set(e.schema)), "host_error": host_error(b),
            "first_sentence": first_sentence(e.text),
        })
    out["pages"] = [{k: v for k, v in p.items() if k != "text"} for p in pages]
    ok_pages = [p for p in pages if p.get("status") == 200]

    if sm_urls:
        broken = [p for p in pages if p.get("status") != 200]
        if broken:
            add("blocker", "crawl", f"{len(broken)} of {len(pages)} sitemap URLs do not return 200.",
                f"e.g. {broken[0]['url']} -> {broken[0].get('status')}. A sitemap listing dead URLs wastes crawl budget.")
        downed = [p for p in ok_pages if p.get("host_error")]
        if downed:
            add("blocker", "reachability", f"{len(downed)} pages serve a hosting error page despite a 200.",
                f"e.g. {downed[0]['url']}: {downed[0]['host_error']}")

        no_title = [p for p in ok_pages if not p["title"]]
        long_title = [p for p in ok_pages if len(p["title"]) > 60]
        no_meta = [p for p in ok_pages if not p["meta"]]
        no_h1 = [p for p in ok_pages if not p["h1"]]
        multi_h1 = [p for p in ok_pages if len(p["h1"]) > 1]
        dup_titles = [t for t, c in Counter(p["title"] for p in ok_pages if p["title"]).items() if c > 1]

        if no_title:
            add("blocker", "on-page", f"{len(no_title)} pages have no title tag.", f"e.g. {no_title[0]['url']}")
        if dup_titles:
            add("blocker", "on-page", f"{len(dup_titles)} titles are used on more than one page.",
                f"e.g. {dup_titles[0]!r}. Duplicate titles are a cannibalisation signal.")
        if long_title:
            add("warn", "on-page", f"{len(long_title)} titles exceed 60 characters.", "They will be truncated in results.")
        if no_meta:
            add("warn", "on-page", f"{len(no_meta)} pages have no meta description.", f"e.g. {no_meta[0]['url']}")
        if no_h1:
            add("blocker", "on-page", f"{len(no_h1)} pages have no H1.", f"e.g. {no_h1[0]['url']}")
        if multi_h1:
            add("warn", "on-page", f"{len(multi_h1)} pages have more than one H1.", f"e.g. {multi_h1[0]['url']}")

        no_og = [p for p in ok_pages if not (p["og_desc"] and p["og_img"])]
        if no_og:
            add("info", "social", f"{len(no_og)} pages lack og:description or og:image.",
                "Preview cards fall back to whatever the platform scrapes.")

        # --- 4. duplicate text ----------------------------------------
        if len(ok_pages) >= 3:
            lens = [p["text_len"] for p in ok_pages]
            spread = statistics.pstdev(lens)
            med = statistics.median(lens)
            out["text_len_spread"] = {"median": med, "stdev": round(spread, 1)}
            if med and spread / max(med, 1) < 0.05:
                add("warn", "duplication",
                    f"Visible-text length is near-identical across {len(ok_pages)} pages "
                    f"(median {med:.0f} chars, stdev {spread:.0f}).",
                    "Pages built from one template with a word swapped. Give each facts specific to it, from the code.")

            # quick_ratio() compares character counts and ignores order, so it
            # is an upper bound -- two pages with the same vocabulary in
            # different sentences score near-identical. Use it to screen, then
            # confirm with ratio(), which actually aligns the text. Reporting
            # the screening number overstates duplication, sometimes badly.
            worst = []
            for i in range(len(ok_pages)):
                for j in range(i + 1, len(ok_pages)):
                    a, b = ok_pages[i], ok_pages[j]
                    if not a["text"] or not b["text"]:
                        continue
                    ta, tb = a["text"][:4000], b["text"][:4000]
                    sm = difflib.SequenceMatcher(None, ta, tb)
                    if sm.quick_ratio() <= 0.90:
                        continue                      # cannot reach the bar
                    ratio = sm.ratio()                # the real number
                    if ratio > 0.90:
                        worst.append((round(ratio * 100, 1), a["url"], b["url"]))
            worst.sort(reverse=True)
            out["near_duplicates"] = worst[:10]
            if worst:
                top = worst[0]
                add("blocker", "duplication",
                    f"{len(worst)} page pairs are over 90% identical in body text.",
                    f"worst: {top[0]}% between {top[1]} and {top[2]}. Distinct keywords and "
                    f"separate URLs are fine and should stay -- what is missing is a reason to "
                    f"rank each one. Give every page facts from the code that apply only to it.")

            # --- 5. repeated openings ---------------------------------
            openers = Counter(p["first_sentence"] for p in ok_pages if p["first_sentence"])
            repeated = [(s, c) for s, c in openers.items() if c > 1]
            out["repeated_openings"] = repeated
            if repeated:
                s, c = max(repeated, key=lambda x: x[1])
                add("warn", "duplication", f"{sum(c for _, c in repeated)} pages share an opening sentence shape.",
                    f"{c} pages start {s!r}. Vary the lede - repeated shapes read as templated.")

    # --- 6. HTTP behaviour ------------------------------------------------
    hstatus, _, _, _ = fetch(url, method="HEAD", timeout=15)
    if hstatus == 405:
        add("warn", "http", "HEAD returns 405.",
            "Link checkers and social preview cards use HEAD. Return 200.")
    elif hstatus not in (200, 301, 302, None):
        add("info", "http", f"HEAD returns {hstatus}.")

    bogus = urllib.parse.urljoin(origin, "/this-path-should-not-exist-seo-audit")
    bstatus, _, bbody, _ = fetch(bogus, timeout=15)
    if bstatus == 200 and "404" not in bbody[:2000].lower():
        add("warn", "http", "An unknown path returns 200 instead of 404.",
            "Soft 404s get indexed and dilute the site. Return a real 404 status.")

    # --- 7. head tags on the home page -------------------------------------
    if ex.robots_meta and "noindex" in ex.robots_meta:
        add("blocker", "index", "Home page carries a noindex directive.", "Remove it.")
    if ex.canonical:
        cu = urllib.parse.urlparse(urllib.parse.urljoin(url, ex.canonical))
        if (cu.netloc, cu.path.rstrip("/")) != (parts.netloc, parts.path.rstrip("/")):
            add("warn", "index", f"Home page canonical points elsewhere: {ex.canonical}", "Confirm this is intended.")
    out["title"] = ex.title.strip()
    out["schema"] = sorted(set(ex.schema))
    if not ex.schema:
        add("warn", "schema", "Home page has no JSON-LD structured data.", "Add Organization and WebSite.")
    if parts.scheme != "https":
        add("blocker", "security", "Site is not served over HTTPS.", "Install a certificate.")

    # --- 8. pagespeed -------------------------------------------------------
    if psi_key:
        q = urllib.parse.urlencode({"url": url, "strategy": "mobile", "key": psi_key})
        s, _, body, _ = fetch("https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + q, timeout=120)
        if s == 200:
            try:
                score = int(json.loads(body)["lighthouseResult"]["categories"]["performance"]["score"] * 100)
                out["pagespeed_mobile"] = score
                if score < 50:
                    add("blocker", "speed", f"Mobile PageSpeed {score}/100.", "Convert images to WebP, defer scripts, enable caching.")
                elif score < 80:
                    add("warn", "speed", f"Mobile PageSpeed {score}/100.", "Aim for 80+.")
            except Exception:
                add("info", "speed", "PageSpeed returned an unexpected payload.")
        else:
            add("info", "speed", f"PageSpeed request failed ({s}).")

    order = {"blocker": 0, "warn": 1, "info": 2}
    out["findings"].sort(key=lambda f: order.get(f["severity"], 9))
    return out


def render(r):
    icons = {"blocker": "[BLOCKER]", "warn": "[warn]   ", "info": "[info]   "}
    print(f"\n  {r['url']}  ->  HTTP {r.get('status')}")
    if r.get("sitemap"):
        print(f"  sitemap: {r['sitemap']['entries']} URLs, {len(r.get('pages', []))} swept")
    if r.get("crawler_sweep"):
        print("  crawlers: " + "  ".join(f"{k}={v}" for k, v in r["crawler_sweep"].items()))
    print()
    if not r["findings"]:
        print("  Nothing flagged.\n")
    for f in r["findings"]:
        print(f"  {icons.get(f['severity'], '')} {f['area']}: {f['finding']}")
        if f.get("fix"):
            print(f"              -> {f['fix']}")
    counts = Counter(f["severity"] for f in r["findings"])
    print("\n  " + "  ".join(f"{k}: {v}" for k, v in counts.items()) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--json", action="store_true")
    p.add_argument("--psi-key", default=None)
    p.add_argument("--max-pages", type=int, default=50, help="sitemap URLs to sweep (default 50)")
    a = p.parse_args()
    res = check(a.url, a.psi_key, a.max_pages)
    print(json.dumps(res, indent=2)) if a.json else render(res)
    sys.exit(1 if any(f["severity"] == "blocker" for f in res["findings"]) else 0)
