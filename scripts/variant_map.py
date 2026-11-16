#!/usr/bin/env python3
"""
Sort untargeted keywords into the ones an existing page should absorb and the
ones that need a page of their own.

    python variant_map.py --bank seo/keywords.csv

The decision this automates is the one that is expensive to get wrong. A
keyword that is a close variant of a search an existing page already targets
gets WORDING on that page. It does not get a page. Two pages aimed at the
same search split their own links and impressions, and a set of near-identical
pages is what a doorway page looks like from the outside. So the mapped output
says where each variant goes and which parts of the page to leave alone, and
it stops at six variants per page, past which the copy reads as stuffing.

The other half is the guard from section 5.3 of the brief. Before a keyword is
allowed to reword a live page, its volume is compared against the volume of
that page's original target in the page register. Two phrases with the same
volume are the same search as far as Google is concerned, so the page already
covers it: editing the copy risks what currently ranks and gains nothing. Those
rows are flagged, not proposed. The trap is that they look like the most
attractive finds in the bank, because they carry the biggest numbers.

The mapping rules are per project, so they live in a JSON file rather than in
this script: an ordered list of pattern -> page, first match wins. A rule may
only point at a page that exists in the register. A rule pointing somewhere
else is reported and the run stops, because a silent skip looks exactly like
"no keyword matched that page" and nobody goes looking.

Outputs two CSVs in --out: variant-map-<date>.csv (what to add to which page)
and new-page-candidates-<date>.csv (everything else). Exits 2 on a missing or
broken config, rules file or register -- all three are worth fixing before the
run rather than working around.

Normalising, close-variant merging and the on-topic filters are kwlib's, the
same ones gap_report.py uses. If the two disagreed, a keyword could be a gap
in one report and a variant in the other.
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kwlib import (  # noqa: E402
    ConfigError,
    DEFAULT_CONFIG,
    PAGE_COLUMNS,
    RANGE_RE,
    TARGET_COLUMNS,
    ascii_safe,
    bank_rows,
    canon,
    classify,
    load_config_or_exit,
    load_targets,
    norm,
    nospace,
    off_intent,
    volume_label,
)

DEFAULT_BANK = os.path.join("seo", "keywords.csv")
DEFAULT_RULES = os.path.join("seo", "variant-rules.json")
DEFAULT_REGISTER = os.path.join("seo", "page-register.csv")
DEFAULT_OUT = os.path.join("seo", "reports")

# Six variants is the cap from the brief. It is a judgement about how much
# extra wording a page carries before it reads as written for a crawler.
CAP = 6

# Where each variant goes, strongest first. The URL, title, H1 and first
# sentence are missing from this list deliberately -- see UNTOUCHED.
PLACEMENTS = (
    "second sentence",
    "one H2",
    "FAQ question",
    "FAQ question",
    "FAQ question",
    "meta description, after the main keyword",
)

UNTOUCHED = "url, title, H1, first sentence"

# Two volumes this close are one search. Planner's buckets are coarser than
# this anyway, so the ratio only matters for measured numbers.
SAME_SEARCH_RATIO = 1.25

# Volume columns a register might use. The page and target column names come
# from kwlib, so the register this reads is the register load_targets reads.
VOLUME_COLUMNS = ("volume", "searches", "search volume", "monthly searches", "volume estimate")
VOLUME_SOURCE_COLUMNS = ("volume source", "source", "volume from")

RULES_SHAPE = """\
no variant rules at %s
  Create it. An ordered list; the first rule whose market and pattern match
  a keyword wins, and every page named must exist in the register:

  {
    "_about": "which existing page absorbs which wording",
    "rules": [
      {"_why": "format pairs belong on the converter page for that pair",
       "markets": ["us"], "pattern": "png.*webp|webp.*png", "page": "/png-to-webp"},
      {"markets": ["es"], "pattern": "convertir.*webp", "page": "/es/png-a-webp"},
      {"_why": "matched on purpose and mapped nowhere: these need their own page",
       "markets": ["*"], "pattern": "batch|bulk", "page": ""}
    ]
  }

  markets: bank country codes; omit it or use ["*"] for every market.
  pattern: a regex matched against the normalised keyword -- lowercased, with
           punctuation already turned into spaces, so do not write punctuation
           into it. For CJK, write the pattern without spaces; a non-ASCII
           keyword is also matched with its spaces removed.
  page:    a page URL from the register, or "" to stop the search for a rule
           and send the keyword to the new-page candidates on purpose."""


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------

class Rule(object):
    """One ordered pattern -> page mapping."""

    def __init__(self, markets, pattern, page, why):
        self.markets = markets          # set of codes, or empty for any
        self.pattern = pattern          # compiled
        self.page = page                # "" means map nowhere, deliberately
        self.why = why

    def covers(self, country):
        return not self.markets or country in self.markets

    def hits(self, n):
        """Match the normalised keyword, and its spaces-removed form too.

        Google writes Japanese and Chinese keywords with spaces between the
        words. A pattern written the way the phrase is actually spelled would
        otherwise never fire on the market it was written for.
        """
        if self.pattern.search(n):
            return True
        return not n.isascii() and bool(self.pattern.search(nospace(n)))


def load_rules(path, pages):
    """Read the ordered rules and check every page against the register.

    `pages` is the set of page URLs the register knows. A rule aimed at a page
    that is not in it is an error: either the page was renamed, in which case
    the rule needs updating, or the page was never built, in which case those
    keywords are new-page candidates and should be reported as such.
    """
    if not os.path.exists(path):
        raise ConfigError(RULES_SHAPE % path)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except ValueError as e:
        raise ConfigError("%s is not valid JSON: %s" % (path, e))

    if isinstance(raw, dict):
        raw = raw.get("rules")
    if not isinstance(raw, list):
        raise ConfigError("%s must hold a list of rules under \"rules\"\n\n%s"
                          % (path, RULES_SHAPE % path))

    rules, bad = [], []
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            raise ConfigError("rule %d in %s is not an object" % (i, path))
        pattern, page = r.get("pattern"), r.get("page")
        if not pattern or page is None:
            raise ConfigError("rule %d in %s needs a pattern and a page "
                              "(page \"\" to map nowhere)" % (i, path))
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ConfigError("bad regex in rule %d of %s: %s\n  pattern: %s"
                              % (i, path, e, ascii_safe(pattern)))
        page = str(page).strip()
        if page and page not in pages:
            bad.append((i, page))
        markets = {str(m).strip().lower() for m in (r.get("markets") or []) if str(m).strip()}
        rules.append(Rule(set() if "*" in markets else markets, compiled, page, r.get("_why") or ""))

    if bad:
        raise ConfigError(
            "%s maps to %d page(s) the register does not list:\n%s\n"
            "  Fix the page URL, or drop the rule and let those keywords show up\n"
            "  as new-page candidates."
            % (path, len(bad), "\n".join("    rule %d -> %s" % (i, ascii_safe(p)) for i, p in bad))
        )
    if not rules:
        raise ConfigError("%s has no rules in it" % path)
    return rules


# --------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------

def _column(keys, names):
    for want in names:
        hit = keys.get(want.replace("_", " "))
        if hit:
            return hit
    return None


def load_register(path):
    """Read {page: {target, volume, label}} -- what each page was built for.

    This is the other side of kwlib.load_targets, which answers "which page
    owns this phrase". The guard needs the reverse plus the volume the page was
    aimed at, and a register without a volume column makes that check
    impossible, so the run says so instead of passing everything.
    """
    if not os.path.exists(path):
        raise ConfigError(
            "no page register at %s\n"
            "  It is the list of pages and what each one targets: a CSV with a page\n"
            "  column, a target column and a volume column. Without it there is\n"
            "  nothing to map a variant onto." % path
        )
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return {}, False

    keys = {re.sub(r"[\s_-]+", " ", (k or "").strip().lower()): k for k in rows[0]}
    pg_col = _column(keys, PAGE_COLUMNS)
    tg_col = _column(keys, ("main target",) + TARGET_COLUMNS)
    vol_col = _column(keys, VOLUME_COLUMNS)
    src_col = _column(keys, VOLUME_SOURCE_COLUMNS)
    if not pg_col:
        raise ConfigError("%s needs a page column (%s); found: %s"
                          % (path, "/".join(PAGE_COLUMNS[:3]), ", ".join(sorted(keys)) or "no header"))

    out = {}
    for r in rows:
        page = (r.get(pg_col) or "").strip()
        if not page:
            continue
        volume = None
        if vol_col:
            try:
                volume = float(str(r.get(vol_col) or "").replace(",", "").strip())
            except ValueError:
                volume = None
        label = volume_label({"source": r.get(src_col) or "", "volume": volume}) if vol_col else "no data"
        out[page] = {
            "target": (r.get(tg_col) or "").strip() if tg_col else "",
            "volume": volume,
            "label": label,
        }
    return out, bool(vol_col)


# --------------------------------------------------------------------------
# the 5.3 guard
# --------------------------------------------------------------------------

def _is_range(label):
    return bool(RANGE_RE.match(label or ""))


def same_search(kw_label, kw_volume, pg_label, pg_volume):
    """Would Google treat these two phrases as the same search?

    Two tests, because a bank mixes measured numbers with Planner buckets:
    identical bucket names, or measured numbers within SAME_SEARCH_RATIO of
    each other. Returns (verdict, why) and says so in words, since the whole
    point is that a person decides whether to touch the page.

    A page with no recorded volume gets a pass rather than a verdict. The
    honest answer there is that nobody knows, and the register is the thing
    to fix.
    """
    if not pg_volume:
        return False, "page volume unknown -- check the register and Search Console first"
    if _is_range(kw_label) and _is_range(pg_label):
        if kw_label == pg_label:
            return True, "same range as the page target (%s)" % pg_label
        return False, "bigger range than the page target (%s vs %s)" % (kw_label, pg_label)
    if kw_volume and pg_volume:
        hi, lo = max(kw_volume, pg_volume), min(kw_volume, pg_volume)
        if lo > 0 and hi / lo <= SAME_SEARCH_RATIO:
            return True, "volume within %d%% of the page target (%s vs %s)" % (
                int((SAME_SEARCH_RATIO - 1) * 100), kw_label, pg_label)
    return False, ""


# --------------------------------------------------------------------------
# bank
# --------------------------------------------------------------------------

def read_bank(path, cfg, targets, minimum):
    """The untargeted keywords worth acting on, close variants merged.

    Four things drop a row: under --min, a competitor's name, an intent this
    product cannot serve, and a search a page already covers. What survives is
    grouped by (country, canonical form) with the highest-volume spelling kept,
    because Google reports close variants at the same volume and counting them
    separately inflates every number downstream.
    """
    rows = bank_rows(path)          # header spellings resolved in kwlib

    best, seen, dropped = {}, 0, {"min": 0, "brand": 0, "off": 0, "used": 0}
    for r in rows:
        kw = r["keyword"]
        if not kw:
            continue
        seen += 1
        volume = r["volume"]
        if volume < minimum:
            dropped["min"] += 1
            continue
        n = norm(kw)
        if cfg.brands.search(n):
            dropped["brand"] += 1
            continue
        if off_intent(n, cfg):
            dropped["off"] += 1
            continue
        status, _page = classify(kw, cfg, targets)
        if status != "unused":
            dropped["used" if status == "used" else "off"] += 1
            continue

        country = (r.get("country") or "").strip().lower()
        key = (country, canon(kw))
        row = {
            "keyword": kw,
            "country": country,
            "volume": volume,
            "label": volume_label({"source": r.get("source") or "", "volume": volume}),
        }
        if key not in best or volume > best[key]["volume"]:
            best[key] = row
    return list(best.values()), seen, dropped


# --------------------------------------------------------------------------

def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(
        description="Which existing page absorbs a keyword as wording, and which keywords need a new page.")
    ap.add_argument("--bank", default=DEFAULT_BANK, help="keyword bank CSV (default: %s)" % DEFAULT_BANK)
    ap.add_argument("--rules", default=DEFAULT_RULES, help="ordered pattern -> page rules, JSON")
    ap.add_argument("--register", default=DEFAULT_REGISTER, help="page register CSV")
    ap.add_argument("--min", type=int, default=1000, dest="minimum",
                    help="skip keywords under this volume (default: 1000)")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="keyword config JSON")
    ap.add_argument("--out", default=DEFAULT_OUT, help="directory for the two CSVs")
    a = ap.parse_args()

    cfg = load_config_or_exit(a.config)
    try:
        register, has_volumes = load_register(a.register)
        rules = load_rules(a.rules, set(register))
        targets = load_targets(a.register)
        rows, seen, dropped = read_bank(a.bank, cfg, targets, a.minimum)
    except (ConfigError, ValueError) as e:
        sys.stderr.write("ERROR: %s\n" % ascii_safe(e))
        return 2

    gaps = cfg.missing()
    if gaps:
        print("  WARNING  these filters are empty and currently match nothing: %s" % ", ".join(gaps))
    if not has_volumes:
        print("  WARNING  %s has no volume column, so the same-search check below cannot run."
              % ascii_safe(a.register))

    # First match wins. A rule with an empty page matched on purpose and sends
    # the keyword on to the candidates, so a later rule cannot claim it.
    by_page, unmapped = {}, []
    for r in sorted(rows, key=lambda x: -x["volume"]):
        rule = next((ru for ru in rules if ru.covers(r["country"]) and ru.hits(norm(r["keyword"]))), None)
        if rule is None:
            r["note"] = "no rule matched"
            unmapped.append(r)
        elif not rule.page:
            r["note"] = rule.why or "matched a rule that maps nowhere"
            unmapped.append(r)
        else:
            by_page.setdefault(rule.page, []).append(r)

    # Per page: the guard first, then the cap over whatever survives it.
    mapped, flagged, over_cap = [], 0, 0
    for page in sorted(by_page):
        info = register.get(page) or {}
        keep = []
        for r in by_page[page]:
            covered, why = same_search(r["label"], r["volume"], info.get("label"), info.get("volume"))
            if covered:
                flagged += 1
                mapped.append((page, r, "leave the page alone", "", why))
            else:
                keep.append((r, why))
        for rank, (r, why) in enumerate(keep):
            if rank < CAP:
                mapped.append((page, r, "add as wording", PLACEMENTS[rank], why))
            else:
                over_cap += 1
                mapped.append((page, r, "over the %d-variant cap -- leave out" % CAP, "", why))

    if not os.path.isdir(a.out):
        os.makedirs(a.out)
    date = datetime.date.today().isoformat()
    map_path = os.path.join(a.out, "variant-map-%s.csv" % date)
    new_path = os.path.join(a.out, "new-page-candidates-%s.csv" % date)

    write_csv(map_path,
              ["page", "keyword", "country", "volume", "range", "action", "placement",
               "leave_untouched", "page_target", "page_volume", "note"],
              [[page, r["keyword"], r["country"], int(r["volume"]), r["label"], action, placement,
                UNTOUCHED, (register.get(page) or {}).get("target", ""),
                (register.get(page) or {}).get("label", ""), note]
               for page, r, action, placement, note in mapped])
    write_csv(new_path,
              ["keyword", "country", "volume", "range", "note"],
              [[r["keyword"], r["country"], int(r["volume"]), r["label"], r["note"]]
               for r in sorted(unmapped, key=lambda x: -x["volume"])])

    adds = sum(1 for m in mapped if m[2] == "add as wording")
    print("  bank      %d rows, %d kept at %d+ (close variants merged)" % (seen, len(rows), a.minimum))
    print("  dropped   %d under volume, %d other brands, %d off-intent, %d already targeted"
          % (dropped["min"], dropped["brand"], dropped["off"], dropped["used"]))
    print("  mapped    %d keyword(s) onto %d existing page(s)" % (len(mapped), len(by_page)))
    print("    %d to add as wording, %d already covered by the page, %d over the %d-variant cap"
          % (adds, flagged, over_cap, CAP))
    print("  new pages %d candidate(s) no existing page should absorb" % len(unmapped))
    print("  wrote     %s" % ascii_safe(map_path))
    print("            %s" % ascii_safe(new_path))

    if adds:
        print("\n  On every mapped page, leave the %s as they are." % UNTOUCHED)
        print("  Add the variants where the placement column says: strongest in the")
        print("  second sentence, then one H2, then two or three FAQ questions, and")
        print("  the meta description last, after the main keyword.")
    if flagged:
        print("\n  %d keyword(s) carry the same volume as the page's own target, so they" % flagged)
        print("  are the same search and the page already covers them. Rewording it")
        print("  risks what ranks now for nothing. Read its Search Console queries")
        print("  before overruling that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
