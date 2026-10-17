#!/usr/bin/env python3
"""
Per-page on-page linter. Deterministic rules, no model involved.

    python lint.py page.html --keyword "png to webp"
    python lint.py https://example.com/png-to-webp --keyword "png to webp"
    python lint.py ./dist --keyword "..." --json
    python lint.py URL --keyword "..." --check-links     (fetches internal links)

Severity:
    error  costs rankings or indexability
    warn   worth fixing, not urgent
    info   cosmetic or stylistic

Exit code 1 if any error-level rule fails, so it can gate a build.
"""

import argparse
import json
import os
import re
import statistics
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; seo-launch-lint/1.1)"
STOPWORDS = {"a", "an", "the", "for", "to", "of", "in", "on", "and", "or", "with", "your", "you"}
CHROME = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "button", "select"}

# Phrases that mark a paragraph as interface furniture rather than copy.
INTERFACE_MARKERS = (
    "drop", "drag", "paste", "upload", "click here", "choose a file", "select a file",
    "nothing is uploaded", "runs entirely in your browser", "no sign-up", "no signup",
    "free, no account", "tap to", "browse files", "or paste", "privacy-first",
)

WEAK_ANSWER_OPENERS = ("it depends", "well,", "well ", "there are many", "this varies",
                       "generally speaking", "in general,", "that's a great question")

AI_TELLS = ("rather than", "not just", "it's not about", "serves as", "stands as",
            "plays a crucial", "plays a vital", "underscores the", "the evolving landscape")


class Page(HTMLParser):
    """Parses a page into the handful of structures the rules need."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_desc = ""
        self.og = {}
        self.canonical = ""
        self.robots = ""
        self.headings = []        # {level, text, id, order}
        self.paragraphs = []      # {text, order, in_chrome}
        self.links = []           # (href, anchor, in_chrome)
        self.imgs = []            # (src, alt)
        self.schema = []
        self._order = 0
        self._chrome = 0
        self._cur = None          # ("title"|"h"|"p"|"a"|"ldjson", payload)
        self._a = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in CHROME:
            self._chrome += 1
            if tag == "script" and a.get("type") == "application/ld+json":
                self._cur = ("ldjson", None)
            return
        if tag == "title":
            self._cur = ("title", None)
        elif tag == "meta":
            n = (a.get("name") or "").lower()
            p = (a.get("property") or "").lower()
            if n == "description":
                self.meta_desc = a.get("content", "")
            elif n == "robots":
                self.robots = (a.get("content") or "").lower()
            elif p.startswith("og:"):
                self.og[p] = a.get("content", "")
        elif tag == "link" and "canonical" in (a.get("rel") or "").lower():
            self.canonical = a.get("href", "")
        elif re.fullmatch(r"h[1-6]", tag):
            self._order += 1
            self.headings.append({"level": int(tag[1]), "text": "", "id": a.get("id", ""), "order": self._order})
            self._cur = ("h", None)
        elif tag == "p":
            self._order += 1
            self.paragraphs.append({"text": "", "order": self._order, "in_chrome": self._chrome > 0})
            self._cur = ("p", None)
        elif tag == "a" and a.get("href"):
            self._a = [a["href"], "", self._chrome > 0]
            self._cur = ("a", None)
        elif tag == "img":
            self.imgs.append((a.get("src", ""), a.get("alt", "")))
        elif tag in ("li", "td", "dd"):
            self._order += 1
            self.paragraphs.append({"text": "", "order": self._order, "in_chrome": self._chrome > 0})
            self._cur = ("p", None)

    def handle_endtag(self, tag):
        if tag in CHROME:
            self._chrome = max(0, self._chrome - 1)
        if tag == "a" and self._a:
            self.links.append(tuple(self._a))
            self._a = None
        self._cur = None

    def handle_data(self, d):
        if self._cur is None:
            return
        kind = self._cur[0]
        if kind == "title":
            self.title += d.strip()
        elif kind == "h" and self.headings:
            self.headings[-1]["text"] += d.strip() + " "
        elif kind == "p" and self.paragraphs:
            self.paragraphs[-1]["text"] += d
        elif kind == "a" and self._a is not None:
            self._a[1] += d.strip()
            if self.paragraphs and not self._a[2]:
                self.paragraphs[-1]["text"] += d
        elif kind == "ldjson":
            try:
                blob = json.loads(d)
                for n in blob if isinstance(blob, list) else [blob]:
                    if isinstance(n, dict) and n.get("@type"):
                        t = n["@type"]
                        self.schema += t if isinstance(t, list) else [t]
            except Exception:
                pass

    # ---- derived views -------------------------------------------------

    @property
    def prose(self):
        return [p for p in self.paragraphs if not p["in_chrome"] and p["text"].strip()]

    @property
    def text(self):
        return re.sub(r"\s+", " ", " ".join(p["text"] for p in self.prose)).strip()

    def first_p_after_h1(self):
        """The paragraph Google reads first. Template furniture usually sits here."""
        h1s = [h for h in self.headings if h["level"] == 1 and h["text"].strip()]
        if not h1s:
            return None
        after = [p for p in self.paragraphs if p["order"] > h1s[0]["order"] and p["text"].strip()]
        return after[0] if after else None

    def faqs(self):
        """(question heading, first answer paragraph) for every heading containing '?'."""
        out = []
        for i, h in enumerate(self.headings):
            if "?" not in h["text"]:
                continue
            nxt = self.headings[i + 1]["order"] if i + 1 < len(self.headings) else 10 ** 9
            body = [p for p in self.paragraphs if h["order"] < p["order"] < nxt and p["text"].strip()]
            out.append((h, body[0] if body else None))
        return out


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())


def has_kw(hay, kw, loose=True):
    h, k = norm(hay), norm(kw).strip()
    if k and k in h:
        return True
    if not loose:
        return False
    words = [w for w in k.split() if w and w not in STOPWORDS]
    return bool(words) and all(w in h for w in words)


def looks_like_interface(text):
    t = text.strip()
    if len(t.split()) < 8:
        return True
    low = t.lower()
    return any(m in low for m in INTERFACE_MARKERS)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 2]


def resolve_links(links, base, timeout=10):
    """Fetch internal links and report any that don't return 200."""
    bad = []
    seen = set()
    for href, _anchor, in_chrome in links:
        if in_chrome or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        url = urllib.parse.urljoin(base, href)
        if url in seen:
            continue
        seen.add(url)
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status >= 400:
                    bad.append((url, r.status))
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 405:  # HEAD not allowed; retry with GET
                try:
                    with urllib.request.urlopen(
                        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout
                    ) as r2:
                        if r2.status >= 400:
                            bad.append((url, r2.status))
                    continue
                except Exception as e2:
                    code = getattr(e2, "code", "error")
            bad.append((url, code or "error"))
    return bad, len(seen)


def lint(page, kw, url_path=None, base=None, check_links=False):
    r = []

    def rule(sev, name, ok, detail=""):
        r.append({"severity": sev, "rule": name, "passed": bool(ok), "detail": str(detail)})

    # --- title / meta -------------------------------------------------
    t = page.title.strip()
    rule("error", "title present", t, f"{len(t)} chars")
    rule("error", "title contains keyword", has_kw(t, kw), repr(t[:70]))
    rule("warn", "title <= 60 chars", len(t) <= 60, f"{len(t)} chars")
    if t and has_kw(t, kw):
        rule("info", "keyword front-loaded in title", has_kw(t[: max(1, len(t) // 2)], kw))

    md = (page.meta_desc or "").strip()
    rule("warn", "meta description present", md, f"{len(md)} chars")
    if md:
        rule("warn", "meta <= 160 chars", len(md) <= 160, f"{len(md)} chars")
        rule("info", "meta contains keyword", has_kw(md, kw))
    rule("info", "og:description present", page.og.get("og:description"))
    rule("info", "og:image present", page.og.get("og:image"))

    # --- headings -----------------------------------------------------
    h1s = [h for h in page.headings if h["level"] == 1 and h["text"].strip()]
    rule("error", "exactly one H1", len(h1s) == 1, f"found {len(h1s)}")
    if h1s:
        rule("error", "H1 contains keyword", has_kw(h1s[0]["text"], kw), repr(h1s[0]["text"].strip()[:70]))
        rule("info", "H1 mirrors title", has_kw(t, h1s[0]["text"]) or has_kw(h1s[0]["text"], t))

    levels = [h["level"] for h in page.headings if h["text"].strip()]
    jumps = [(levels[i], levels[i + 1]) for i in range(len(levels) - 1) if levels[i + 1] - levels[i] > 1]
    rule("warn", "heading levels sequential", not jumps, f"jumps: {jumps}" if jumps else "")

    # --- the first paragraph under the H1 -----------------------------
    # This is the sentence Google reads first. A "keyword somewhere in the
    # first 100 words" check passes even when a trust badge or upload hint
    # sits here. Template furniture in that slot is the common failure, and
    # it is invisible in the source file because the template inserts it.
    fp = page.first_p_after_h1()
    if fp is None:
        rule("error", "first <p> under H1 exists", False, "no paragraph follows the H1")
    else:
        txt = re.sub(r"\s+", " ", fp["text"]).strip()
        rule("error", "first <p> under H1 is real copy, not interface text",
             not looks_like_interface(txt), repr(txt[:80]))
        rule("error", "first <p> under H1 contains keyword", has_kw(txt, kw), repr(txt[:80]))

    body = page.text
    first100 = " ".join(body.split()[:100])
    rule("warn", "keyword in first 100 words", has_kw(first100, kw))

    wc = len(body.split())
    rule("info", "body word count", wc > 0, f"{wc} words")
    if wc > 50:
        occ = len(re.findall(re.escape(norm(kw).strip()), norm(body)))
        density = occ / max(wc, 1) * 100
        rule("warn", "keyword density under 3%", density < 3.0, f"{density:.2f}% ({occ}x)")

    # --- FAQ ----------------------------------------------------------
    faqs = page.faqs()
    if faqs:
        no_id = [h["text"].strip()[:40] for h, _ in faqs if not h["id"]]
        rule("warn", "every question heading has an id", not no_id,
             f"{len(no_id)} missing" + (f" e.g. {no_id[0]!r}" if no_id else ""))

        long_open, weak_open, missing = [], [], 0
        for h, ans in faqs:
            if ans is None:
                missing += 1
                continue
            first = (sentences(ans["text"]) or [ans["text"].strip()])[0]
            if len(first.split()) > 25:
                long_open.append(first[:50])
            if first.lower().lstrip().startswith(WEAK_ANSWER_OPENERS):
                weak_open.append(first[:50])
        rule("error", "every question has an answer", not missing, f"{missing} unanswered")
        rule("error", "FAQ answers open in <= 25 words", not long_open,
             f"{len(long_open)} too long" + (f" e.g. {long_open[0]!r}" if long_open else ""))
        rule("warn", "FAQ answers open with the answer", not weak_open,
             f"{len(weak_open)} hedge" + (f" e.g. {weak_open[0]!r}" if weak_open else ""))
    rule("info", "4-12 question headings", 4 <= len(faqs) <= 12, f"{len(faqs)}")

    # --- AI-writing numbers -------------------------------------------
    # Turns "this sounds AI-written" into figures that can be watched.
    sents = sentences(body)
    if len(sents) >= 8:
        lens = [len(s.split()) for s in sents]
        med = statistics.median(lens)
        spread = statistics.pstdev(lens)
        uniform = 15 <= med <= 20 and spread < 6
        rule("info", "sentence length varies", not uniform, f"median {med:.0f}, stdev {spread:.1f}")
    emd = body.count("—") + body.count("–")
    rule("info", "em dashes in prose", emd <= 3, f"{emd}")
    tells = {p: len(re.findall(re.escape(p), body, re.I)) for p in AI_TELLS}
    hits = {k: v for k, v in tells.items() if v}
    rule("info", "AI phrasing tells", sum(hits.values()) <= 2,
         ", ".join(f"{k} x{v}" for k, v in hits.items()) if hits else "")

    # --- links --------------------------------------------------------
    internal = [(h, a) for h, a, chrome in page.links
                if not chrome and not re.match(r"https?://", h)
                and not h.startswith(("#", "mailto:", "tel:", "javascript:"))]
    external = [(h, a) for h, a, chrome in page.links if not chrome and re.match(r"https?://", h)]
    rule("warn", "has internal links in body copy", len(internal) >= 3, f"{len(internal)}")
    rule("info", "2+ external links", len(external) >= 2, f"{len(external)}")
    generic = [a for _, a, c in page.links
               if not c and a.strip().lower() in {"click here", "here", "read more", "learn more", "link"}]
    rule("info", "no generic anchor text", not generic, f"{generic[:3]}" if generic else "")

    if check_links and base:
        bad, checked = resolve_links(page.links, base)
        rule("error", "internal links resolve", not bad,
             f"{len(bad)} of {checked} broken" + (f" e.g. {bad[0]}" if bad else ""))
    elif check_links:
        rule("info", "internal links resolve", True, "skipped - no base URL")

    # --- media / schema / index ---------------------------------------
    no_alt = [s for s, alt in page.imgs if not alt.strip()]
    rule("warn", "all images have alt text", not no_alt, f"{len(no_alt)} of {len(page.imgs)} missing")
    raster = [s for s, _ in page.imgs if re.search(r"\.(png|jpe?g)(\?|$)", s, re.I)]
    rule("info", "images are WebP", not raster, f"{len(raster)} raster")
    alts = {a.strip().lower() for _, a in page.imgs if a.strip()}
    rule("info", "alt text not duplicated", not (len(page.imgs) > 1 and len(alts) == 1))

    rule("warn", "structured data present", page.schema, ", ".join(sorted(set(page.schema))))
    rule("error", "not noindex", "noindex" not in page.robots, page.robots)

    # --- URL ----------------------------------------------------------
    if url_path:
        rule("error", "URL contains keyword", has_kw(url_path.replace("-", " ").replace("/", " "), kw), url_path)
        rule("warn", "URL uses hyphens not underscores", "_" not in url_path, url_path)
        rule("info", "URL is lowercase", url_path == url_path.lower(), url_path)

    return r


def load(src):
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "replace")
        p = urllib.parse.urlparse(src)
        return html, (p.path or "/"), src
    with open(src, encoding="utf-8", errors="replace") as f:
        return f.read(), None, None


def render(src, results):
    print(f"\n  {src}\n")
    for sev in ("error", "warn", "info"):
        rows = [x for x in results if x["severity"] == sev]
        if not rows:
            continue
        fails = [x for x in rows if not x["passed"]]
        print(f"  {sev.upper()}  {len(rows) - len(fails)}/{len(rows)} passing")
        for x in fails:
            d = f"  ({x['detail']})" if x["detail"] else ""
            print(f"    FAIL  {x['rule']}{d}")
        print()
    errs = sum(1 for x in results if x["severity"] == "error" and not x["passed"])
    print(f"  {'BLOCKED - ' + str(errs) + ' error(s)' if errs else 'OK'}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="HTML file, directory, or URL")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--url-path", default=None)
    ap.add_argument("--check-links", action="store_true", help="fetch internal links (slow)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    targets = []
    if os.path.isdir(a.source):
        for root, _, files in os.walk(a.source):
            targets += [os.path.join(root, f) for f in files if f.endswith((".html", ".htm"))]
    else:
        targets = [a.source]

    failed = 0
    payload = {}
    for tgt in targets:
        html, derived, base = load(tgt)
        pg = Page()
        try:
            pg.feed(html)
        except Exception:
            pass
        res = lint(pg, a.keyword, a.url_path or derived, base, a.check_links)
        payload[tgt] = res
        failed += sum(1 for x in res if x["severity"] == "error" and not x["passed"])
        if not a.json:
            render(tgt, res)

    if a.json:
        print(json.dumps(payload, indent=2))
    sys.exit(1 if failed else 0)
