#!/usr/bin/env python3
"""
Shared keyword handling for the keyword scripts. Standard library only.

    from kwlib import load_config, load_targets, norm, canon, classify

planner_import.py, gap_report.py and variant_map.py all normalise phrases,
merge close variants and decide whether a page already covers a search. Each
one defining that itself is how a keyword passes the import filter and then
fails the gap filter, or how two reports disagree about the same bank. One
definition here, imported everywhere.

WHY THE FILTERS ARE A CONFIG FILE AND NOT CODE IN THIS MODULE

The version this was ported from hardcoded one product's vocabulary: a few
very long regexes listing the nouns that product worked on, the searches it
could not serve, and its competitors' names. That is fine for one project
and wrong for a skill, for two separate reasons.

The first is portability. A product's vocabulary is the one part of keyword
filtering that cannot be guessed from code.

The second is the expensive one. A filter written only in English silently
throws away whole markets, and it looks like the market is empty rather than
like a bug. In the run this came from, an Arabic keyword-ideas pull returned
547 ideas and the on-topic filter kept 19 of them. The other 528 were real
searches for the product, discarded because the filter only knew the English
nouns. They came back as soon as the Arabic words were added. Nothing in the
output said so first -- the market just looked small. So media_words has to
be written in every language the project targets, and a market with no words
of its own in the config should be treated as unmeasured, not as empty.

The off_intent rules take a trigger AND an unless for the same reason. A verb
on its own is ambiguous: "translate" with a media word beside it is this kind
of product, "translate" with no media word is plain-text translation, which is
somebody else's product and an off-intent search. One pattern cannot express
that, so each rule pairs the verb that fires with the context that excuses it.
Write the pair in every language, or the market that lacks it loses its verbs.

Config keys are described in load_config. Keys starting with "_" are ignored,
so notes can be left in the file. assets/keywords.config.example.json shows
the shape filled in for a neutral product.

Printing: every message this module emits is ASCII (the Windows console is
cp1252). Keyword data is not -- that is the whole point of norm -- so put
phrases through ascii_safe before printing them anywhere.

Run it directly to check a config and see how it classifies a phrase:

    python kwlib.py --config seo/keywords.config.json "png to webp"

Exits non-zero when the config is missing or malformed, so it also works as
a gate before a long import run.
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata

DEFAULT_CONFIG = os.path.join("seo", "keywords.config.json")

# Articles canon drops. English only, and canon is honest about that below.
ARTICLES = {"a", "an", "the"}

# Matches nothing. A missing config key degrades to this rather than raising,
# so a half-written config still runs and reports less instead of crashing.
NEVER = re.compile(r"(?!x)x")

# An off_intent rule can set "unless": "MEDIA" instead of repeating the whole
# media_words list, which is what most of these rules need.
MEDIA_TOKEN = "MEDIA"

CONFIG_KEYS = ("markets", "on_topic", "media_words", "off_intent", "brands", "cant_serve", "generic")


class ConfigError(Exception):
    """Raised with a message meant for the user, not a traceback."""


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------

def norm(s):
    """Lowercase, punctuation to spaces, whitespace collapsed.

    Combining marks are kept deliberately. Devanagari and Thai vowel signs
    are marks, not alphanumerics, so anything that treats a non-alphanumeric
    character as a separator cuts every word in those scripts into fragments
    and the whole market stops matching. Do not "simplify" this to \\w or to
    a strip-punctuation call that drops marks.
    """
    s = (s or "").lower()
    return " ".join(
        "".join(ch if ch.isalnum() or unicodedata.category(ch)[0] == "M" else " " for ch in s).split()
    )


def nospace(n):
    """n with spaces removed, for comparing non-ASCII phrases.

    Google writes Japanese and Chinese keywords with spaces between the words
    where a page target has none. Compared literally, a page that already
    targets the phrase looks like an open gap.
    """
    return (n or "").replace(" ", "")


# Words that make a phrase directional. Without these, canon() cannot tell
# "A to B" from "B to A". Deliberately short: a false positive here only
# splits a merge that would otherwise have happened, while a false negative
# silently destroys a keyword, so err toward splitting.
DIRECTION_WORDS = frozenset((
    "to", "into", "from",          # en
    "a", "en", "de", "para",       # es/pt/fr
    "zu", "in", "nach", "aus",     # de
    "naar", "till", "til",         # nl/sv/da
    "ke", "jadi",                  # id
    "ni", "kara",                  # ja romanised
))


def canon(kw):
    """The canonical form of a close variant.

    Google Ads reports close variants with the same volume, so merging them
    before counting or uploading keeps a report from claiming one search five
    times. Accents are removed, a trailing s is stripped from words over three
    letters, articles are dropped, and the remaining words are sorted.

    The articles are English. A Spanish "el" or a German "der" is left in
    place, so this merges less outside English than inside it.

    Word order is dropped EXCEPT across a direction word. Sorting alone made
    "png to webp" and "webp to png" the same string, which merged two
    genuinely different searches and deleted the smaller one from every
    report. So when a direction word splits the phrase, the left side is
    fingerprinted onto the end: order still stops mattering within each side,
    but the direction survives.
    """
    s = "".join(ch for ch in unicodedata.normalize("NFKD", norm(kw))
                if not unicodedata.combining(ch))
    words = [w[:-1] if len(w) > 3 and w.endswith("s") else w
             for w in s.split() if w not in ARTICLES]
    base = " ".join(sorted(words))
    for i, w in enumerate(words):
        if w in DIRECTION_WORDS and 0 < i < len(words) - 1:
            # Only the token immediately before the direction word -- the "from"
            # term. Fingerprinting the whole left side would make "convert png
            # to webp" and "png to webp convert" different strings, which is
            # the word-order noise sorting exists to merge.
            return "%s|%s" % (base, words[i - 1])
    return base


# The keyword bank's own headers. Projects and exports spell these
# differently, and a reader that insists on one spelling returns zero rows
# without saying why -- which reads as "no keywords found" rather than
# "wrong header", and that cost a silent empty report once already.
BANK_KEYWORD_COLUMNS = ("keyword", "phrase", "query", "search term", "term")
BANK_COUNTRY_COLUMNS = ("country", "market", "geo", "location", "region")
BANK_VOLUME_COLUMNS = ("volume", "avg monthly searches", "searches",
                       "monthly searches", "avg. monthly searches")
BANK_SOURCE_COLUMNS = ("source", "label", "origin")


def header_key(header):
    return re.sub(r"[\s_.-]+", " ", (header or "").strip().lower())


def pick_column(keys, wanted):
    """The real header name for the first wanted spelling present."""
    for w in wanted:
        if w in keys:
            return keys[w]
    return None


def bank_rows(path):
    """Every bank row as {keyword, country, volume, source}, headers resolved.

    One definition, imported by both gap_report and variant_map. They each had
    their own, and the two had already drifted: one resolved header spellings
    and the other required the literal "keyword"/"volume"/"country", so the
    same bank produced a full report from one script and an empty one from the
    other.
    """
    if not os.path.exists(path):
        raise ConfigError("no keyword bank at %s" % path)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return []

    keys = {header_key(k): k for k in rows[0]}
    kw_col = pick_column(keys, BANK_KEYWORD_COLUMNS)
    if not kw_col:
        raise ConfigError(
            "%s has no keyword column (tried %s); found: %s"
            % (path, "/".join(BANK_KEYWORD_COLUMNS[:3]),
               ", ".join(sorted(keys)) or "no header"))
    co_col = pick_column(keys, BANK_COUNTRY_COLUMNS)
    vol_col = pick_column(keys, BANK_VOLUME_COLUMNS)
    src_col = pick_column(keys, BANK_SOURCE_COLUMNS)

    out = []
    for r in rows:
        kw = (r.get(kw_col) or "").strip()
        if not kw:
            continue
        try:
            vol = float(str(r.get(vol_col) or 0).replace(",", "").strip() or 0)
        except ValueError:
            vol = 0.0
        out.append({
            "keyword": kw,
            "country": (r.get(co_col) or "").strip().lower() if co_col else "",
            "volume": vol,
            "source": (r.get(src_col) or "").strip() if src_col else "",
        })
    return out


def ascii_safe(s):
    """A printable form of a keyword. Non-ASCII becomes a backslash escape.

    The console this runs on is cp1252 and raises on anything outside it, so a
    report that prints a Japanese phrase dies halfway through writing a file
    that took an hour to build.
    """
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def _compile(patterns, key, path):
    """Join a list of regex strings into one pattern. Empty list -> NEVER."""
    if not patterns:
        return NEVER
    parts = []
    for p in patterns:
        if not isinstance(p, str) or not p.strip():
            continue
        try:
            re.compile(p)
        except re.error as e:
            raise ConfigError(
                "bad regex in %s of %s: %s\n  pattern: %s" % (key, path, e, ascii_safe(p))
            )
        parts.append("(?:%s)" % p)
    if not parts:
        return NEVER
    # norm() lowercases everything first; IGNORECASE only covers a config
    # author writing "PNG" in a pattern.
    return re.compile("|".join(parts), re.IGNORECASE)


class KeywordConfig:
    """One project's keyword vocabulary, with its patterns compiled.

    Attributes:
        path        where it was loaded from
        markets     {code: display name}
        on_topic    compiled: anything matching is about this product
        media       compiled: the nouns this product operates on
        off_intent  [(trigger, unless)] compiled pairs
        brands      compiled: other products' names
        cant_serve  compiled: real searches this product cannot serve
        generic     set of words; a phrase made only of these is junk
    """

    def __init__(self, path, raw):
        self.path = path
        markets = raw.get("markets") or {}
        if not isinstance(markets, dict):
            raise ConfigError("markets in %s must be a map of {code: display name}" % path)
        self.markets = {str(k): str(v) for k, v in markets.items()}
        self.generic = {norm(w) for w in (raw.get("generic") or []) if norm(w)}
        self.media = _compile(raw.get("media_words"), "media_words", path)
        self.on_topic = _compile(raw.get("on_topic"), "on_topic", path)
        self.brands = _compile(raw.get("brands"), "brands", path)
        self.cant_serve = _compile(raw.get("cant_serve"), "cant_serve", path)

        self.off_intent = []
        for rule in raw.get("off_intent") or []:
            if not isinstance(rule, dict) or not rule.get("trigger"):
                raise ConfigError(
                    "every off_intent entry in %s needs a trigger and an unless" % path
                )
            unless = rule.get("unless") or ""
            if unless == MEDIA_TOKEN:
                need = self.media
            else:
                need = _compile([unless], "off_intent.unless", path) if unless else NEVER
            self.off_intent.append((_compile([rule["trigger"]], "off_intent.trigger", path), need))

        self.unknown = sorted(k for k in raw if not k.startswith("_") and k not in CONFIG_KEYS)

    def market_name(self, code):
        return self.markets.get(str(code), str(code).upper())

    def missing(self):
        """Which parts are empty, i.e. which filters currently pass everything."""
        out = []
        if self.on_topic is NEVER:
            out.append("on_topic")
        if self.media is NEVER:
            out.append("media_words")
        if not self.off_intent:
            out.append("off_intent")
        if self.cant_serve is NEVER:
            out.append("cant_serve")
        if self.brands is NEVER:
            out.append("brands")
        if not self.generic:
            out.append("generic")
        if not self.markets:
            out.append("markets")
        return out


def load_config(path=DEFAULT_CONFIG):
    """Read the per-project keyword config (JSON) and compile its patterns.

    Keys, all optional and all lists of regex strings unless noted:
        markets      {code: display name}
        on_topic     anything matching is about this product
        media_words  the nouns this product operates on, in every target
                     language -- see the note at the top of this file
        off_intent   [{"trigger": regex, "unless": regex}]; the trigger fires
                     unless the unless also matches. "unless": "MEDIA" reuses
                     media_words
        brands       other products' names, dropped from reports
        cant_serve   real searches this product cannot serve
        generic      plain words; a phrase made only of these is junk

    A missing key degrades to a pattern that matches nothing, so a partial
    config filters less rather than crashing. A missing file raises
    ConfigError with the path to create.
    """
    if not os.path.exists(path):
        raise ConfigError(
            "no keyword config at %s\n"
            "  Create it. Copy assets/keywords.config.example.json and replace the\n"
            "  vocabulary with this product's, in every language it targets." % path
        )
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except ValueError as e:
        raise ConfigError("%s is not valid JSON: %s" % (path, e))
    if not isinstance(raw, dict):
        raise ConfigError("%s must contain a JSON object with keys like %s" % (path, ", ".join(CONFIG_KEYS)))
    return KeywordConfig(path, raw)


def load_config_or_exit(path=DEFAULT_CONFIG):
    """load_config for a command line: prints the message and exits 2."""
    try:
        return load_config(path)
    except ConfigError as e:
        sys.stderr.write("ERROR: %s\n" % ascii_safe(e))
        sys.exit(2)


# --------------------------------------------------------------------------
# targets
# --------------------------------------------------------------------------

TARGET_COLUMNS = ("target", "primary_keyword", "primary keyword", "main target", "keyword", "phrase")
PAGE_COLUMNS = ("page", "url", "path", "page_url", "slug")


def load_targets(path):
    """Read {phrase: page_url}: which search each existing page is aimed at.

    Accepts either form, because projects keep this differently:
      * a JSON object mapping phrase -> page URL or path;
      * a CSV with a header, one column naming the phrase and one naming the
        page. Phrase column: target, primary_keyword, primary keyword,
        main target, keyword or phrase. Page column: page, url, path,
        page_url or slug. First match in that order wins, case and spacing
        in the header ignored.

    A JSON list, or a CSV with neither column, raises ConfigError. A missing
    file returns {} -- a project with no pages yet is a normal state, and
    every keyword then classifies as unused.
    """
    if not path or not os.path.exists(path):
        return {}
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raise ConfigError("%s must be a JSON object of {phrase: page}" % path)
        return {str(k): str(v) for k, v in raw.items() if str(k).strip()}

    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return {}
    keys = {re.sub(r"[\s_-]+", " ", (k or "").strip().lower()): k for k in rows[0]}
    # keys is keyed by the normalised header, so normalise the constant too --
    # looking up the raw "primary_keyword" here raised KeyError on two of the
    # spellings this function's own docstring promises to accept.
    kw_col = next((keys[c.replace("_", " ")] for c in TARGET_COLUMNS
                   if c.replace("_", " ") in keys), None)
    pg_col = next((keys[c.replace("_", " ")] for c in PAGE_COLUMNS
                   if c.replace("_", " ") in keys), None)
    if not kw_col or not pg_col:
        raise ConfigError(
            "%s needs a page column (%s) and a target column (%s); found: %s"
            % (path, "/".join(PAGE_COLUMNS[:3]), "/".join(TARGET_COLUMNS[:3]),
               ", ".join(sorted(keys)) or "no header")
        )
    out = {}
    for r in rows:
        phrase, page = (r.get(kw_col) or "").strip(), (r.get(pg_col) or "").strip()
        if phrase and page:
            out[phrase] = page
    return out


# Prepared targets, keyed by the identity of the dict passed in. classify is
# called once per keyword over banks of tens of thousands, and normalising
# every target each time dominates the run. The dict itself is held in the
# cache so its id cannot be reused by another object, and the length is
# checked so a caller that adds a target gets a rebuild.
_PREPARED = {}


def _prepare(targets):
    hit = _PREPARED.get(id(targets))
    if hit and hit[0] is targets and hit[1] == len(targets):
        return hit[2]
    rows = []
    for phrase, page in targets.items():
        n = norm(phrase)
        if n:
            rows.append((n, nospace(n), set(n.split()), page))
    rows.sort(key=lambda r: len(r[0]), reverse=True)
    _PREPARED.clear()
    _PREPARED[id(targets)] = (targets, len(targets), rows)
    return rows


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def off_intent(n, cfg):
    """True when the phrase is a search this product cannot serve.

    Three ways in: cant_serve matches; the phrase is made only of generic
    words ("free online file file"); or an off_intent trigger fires and its
    unless does not. norm is applied again here because it is idempotent and
    cheap, and a caller passing a raw keyword would otherwise fail quietly.
    """
    n = norm(n)
    if not n:
        return False
    if cfg.cant_serve.search(n):
        return True
    words = set(n.split())
    if cfg.generic and words <= cfg.generic:
        return True
    return any(trig.search(n) and not need.search(n) for trig, need in cfg.off_intent)


def classify(kw, cfg, targets):
    """Return (status, page) for one keyword.

    Status is one of:
        off-intent  a search this product cannot serve
        off-topic   nothing to do with this product
        used        a page already targets this search; page is that URL
        unused      on topic, nothing targets it yet; page is ""

    Two subtleties, both of which cost a market or a duplicate page when they
    are left out:

    (a) non-ASCII phrases are also compared with spaces removed, because
        Google spaces Japanese and Chinese words apart where targets do not;
    (b) a page targeting a longer variant covers the shorter one, so a
        two-word phrase inside a target counts as used, and a target whose
        words are all present in the keyword counts as used too. The longest
        such target wins, since it is the most specific page.
    """
    n = norm(kw)
    if not n:
        return "off-topic", ""
    if off_intent(n, cfg):
        return "off-intent", ""
    if not cfg.on_topic.search(n):
        return "off-topic", ""

    rows = _prepare(targets)
    nz = nospace(n)
    for tn, tz, _tw, page in rows:                        # longest target first
        if tn in n or (len(tn) >= 3 and not tn.isascii() and tz in nz):
            return "used", page

    if len(n.split()) >= 2:                               # the keyword sits inside a longer target
        for tn, _tz, _tw, page in reversed(rows):         # shortest containing target wins
            if " %s " % n in " %s " % tn:
                return "used", page

    words = set(n.split())                                # every word of a target is present
    for tn, _tz, tw, page in rows:
        if tw and tw <= words:
            return "used", page
    return "unused", ""


# --------------------------------------------------------------------------
# volumes
# --------------------------------------------------------------------------

# Planner ranges as the import writes them into the source column.
RANGE_RE = re.compile(r"(\d+(?:K|M)?-\d+(?:K|M)?)\s*$", re.IGNORECASE)


def volume_label(row):
    """The human label for a row's volume.

    Planner gives ranges without ad spend, and the import stores the range's
    lower bound as the number plus the range name in the source column. The
    name is what a report should show: 5000 on its own reads as a measurement
    when it means 1K-10K. Falls back to the formatted number, or "no data".

    Hyphens, not en dashes -- this goes to a cp1252 console.
    """
    if hasattr(row, "get"):
        source = str(row.get("source") or "")
        volume = row.get("volume")
    else:
        source, volume = "", row
    m = RANGE_RE.search(source)
    if m:
        return m.group(1).upper()
    if source.strip().lower().endswith("no data"):
        return "no data"
    try:
        return "{:,}".format(int(float(volume)))
    except (TypeError, ValueError):
        return "no data"


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Check a keyword config and classify phrases with it.")
    ap.add_argument("phrases", nargs="*", help="phrases to classify")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--targets", default=None, help="page register CSV or targets JSON")
    a = ap.parse_args()

    cfg = load_config_or_exit(a.config)
    try:
        targets = load_targets(a.targets) if a.targets else {}
    except (ConfigError, ValueError) as e:
        sys.stderr.write("ERROR: %s\n" % ascii_safe(e))
        sys.exit(2)

    print("  config %s" % a.config)
    print("  markets %d, media patterns %s, off_intent rules %d, generic words %d"
          % (len(cfg.markets), "set" if cfg.media is not NEVER else "EMPTY",
             len(cfg.off_intent), len(cfg.generic)))
    gaps = cfg.missing()
    if gaps:
        print("  empty (these filters currently match nothing): %s" % ", ".join(gaps))
    if cfg.unknown:
        print("  ignored keys: %s" % ", ".join(cfg.unknown))
    print("  targets %d from %s" % (len(targets), a.targets or "none given"))
    for p in a.phrases:
        status, page = classify(p, cfg, targets)
        print("  %-11s %-40s %s" % (status, ascii_safe(p)[:40], ascii_safe(page)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
