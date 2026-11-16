#!/usr/bin/env python3
"""
The report of searches with volume that no page here targets, plus the open-gap test.

    python gap_report.py
    python gap_report.py --min 5000 --competitors seo/competitors --out seo/reports

Reads the keyword bank (keyword, country, volume, source), drops what the
project cannot serve, merges close variants, and writes one line per
remaining search with its volume range, its market and the nearest existing
page when one is close. Output is a markdown report to read and a CSV to sort.

THE TRAP THIS AVOIDS, TWICE OVER

Close variants first. Google Ads gives "convert png to webp" and "png to
webp converter" the same number, so a report that lists both claims two
searches worth of traffic for one. Counted that way a bank inflates its own
opportunity, and the plan built on it over-pages a single query. Variants are
merged on canon() before anything is counted, keeping the highest-volume
spelling and, on a tie, the shorter phrase.

The open-gap test second, and it is the reason this script exists. An
untargeted list is long and flat: 4,800 searches nobody here covers, sorted
by volume, which says nothing about which one to write. A keyword is an OPEN
GAP when it has volume, no page here targets it, and it appears in no
competitor's Keyword Planner website-ideas export. Those are the searches
where there is no incumbent page to outrank, and they are worth writing
first.

WHAT THE OPEN-GAP TEST DOES NOT TELL YOU

Absence from a competitor's keyword ideas means their pages do not cover that
wording. It does not prove nobody ranks for the phrase: Planner's idea list
for a site is drawn from that site's own pages, so a competitor ranking on a
page the crawl missed, a forum thread, a marketplace listing or a video can
all sit in an "open" gap. The test is also only meaningful in the markets
where competitor ideas were actually pulled. A market with no competitor
export is untested, not clear, and this report separates those rows rather
than flattering them. The header of every report it writes says all of this.

Markets come from the competitor filenames: a file whose name contains a
market code from the config counts for that market (us-example-ideas.csv ->
us). Files with no recognisable code apply to every tested market, which can
only close a gap, never open a false one. Pass --competitor-markets to say
which markets the files cover instead.

The vocabulary filters -- what this product works on, what it cannot serve,
whose brand names to drop -- live in seo/keywords.config.json, not in here.
See kwlib.load_config and assets/keywords.config.example.json.

Printing is ASCII only (the Windows console is cp1252); the report and CSV
are UTF-8, so keyword data keeps its own script.

Exits 2 on a missing config, a missing bank or a bank with no usable rows.
Having nothing to report is not a failure, so an empty gap list exits 0.
"""

import argparse
import csv
import datetime
import io
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kwlib import (ConfigError, DEFAULT_CONFIG, ascii_safe, canon,  # noqa: E402
                   classify, load_config_or_exit, load_targets, norm,
                   nospace, volume_label)

# Bank header spellings seen in the wild. First match in each tuple wins, and
# the header is compared with spacing, case and underscores ignored.
KW_COLUMNS = ("keyword", "phrase", "query", "search term", "term")
COUNTRY_COLUMNS = ("country", "market", "geo", "location", "region")
VOLUME_COLUMNS = ("volume", "avg monthly searches", "searches", "monthly searches", "avg. monthly searches")
SOURCE_COLUMNS = ("source", "label", "origin")

# Competitor exports are read for their first column only, so the header may
# be any of these -- or absent, in which case every line is taken as a phrase.
PHRASE_HEADERS = ("keyword", "keywords", "phrase", "query", "search term", "term")

COMPETITOR_SUFFIXES = (".csv", ".tsv", ".txt")


def _key(header):
    return re.sub(r"[\s_.-]+", " ", (header or "").strip().lower())


def _pick(keys, wanted):
    """The real header name for the first wanted spelling present."""
    for w in wanted:
        if w in keys:
            return keys[w]
    return None


def decode(path):
    """Read a Planner-style export as lines, whatever it was saved as.

    Keyword Planner downloads UTF-16 with a BOM and tabs between fields, and
    two title lines above the header. Anything hand-made is usually UTF-8 CSV.
    Sniffing the BOM covers both without asking the user which they have.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", "replace")
    else:
        text = raw.decode("utf-8-sig", "replace")
    return text.splitlines()


def read_bank(path):
    # Rows come from kwlib.bank_rows so this and variant_map cannot drift.
    """Rows of {keyword, country, volume, source} from the keyword bank CSV."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return [], None
    keys = {_key(k): k for k in rows[0]}
    kw_col = _pick(keys, KW_COLUMNS)
    if not kw_col:
        raise ConfigError(
            "%s has no keyword column (looked for %s); found: %s"
            % (path, "/".join(KW_COLUMNS[:3]), ", ".join(sorted(keys)) or "no header")
        )
    co_col = _pick(keys, COUNTRY_COLUMNS)
    vol_col = _pick(keys, VOLUME_COLUMNS)
    src_col = _pick(keys, SOURCE_COLUMNS)

    out = []
    for r in rows:
        kw = (r.get(kw_col) or "").strip()
        if not kw:
            continue
        try:
            volume = int(float((r.get(vol_col) or "0").strip() or 0))
        except ValueError:
            volume = 0          # a range name or a blank where a number was expected
        out.append({
            "keyword": kw,
            "country": ((r.get(co_col) or "").strip().lower() if co_col else ""),
            "volume": volume,
            "source": ((r.get(src_col) or "").strip() if src_col else ""),
        })
    return out, (vol_col is not None)


def read_phrases(path):
    """The first column of a competitor export, as raw phrases.

    Deliberately tolerant: an ideas export, a saved CSV, or a plain list one
    phrase per line all work. Volumes are ignored here -- the open-gap test
    only asks whether a competitor's pages mention the wording at all, so
    planner_import.py owns the volume parsing and this does not duplicate it.
    """
    lines = decode(path)
    if not lines:
        return []
    start, delim = 0, ","
    for i, line in enumerate(lines[:20]):           # title lines sit above the header
        d = "\t" if "\t" in line else ","
        first = _key(line.split(d)[0].strip('"'))
        if first in PHRASE_HEADERS:
            start, delim = i + 1, d
            break
    else:
        delim = "\t" if any("\t" in l for l in lines[:5]) else ","
    body = "\n".join(lines[start:])
    return [
        (row[0] or "").strip()
        for row in csv.reader(io.StringIO(body), delimiter=delim)
        if row and (row[0] or "").strip()
    ]


def collect_competitors(path, cfg, explicit):
    """Competitor wording per market, read from a directory of exports.

    Returns (per_market, tested, files, unscoped_files) where per_market maps
    a market code to the set of canonical forms its competitors' ideas cover,
    and `tested` lists the markets the open-gap test may be applied to.
    """
    per_market = defaultdict(set)
    files, unscoped_files, loose = [], [], set()
    if not path or not os.path.isdir(path):
        return per_market, [], files, unscoped_files

    codes = {c.lower() for c in cfg.markets}
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if not os.path.isfile(full) or not name.lower().endswith(COMPETITOR_SUFFIXES):
            continue
        phrases = read_phrases(full)
        if not phrases:
            continue
        files.append((name, len(phrases)))
        forms = set()
        for p in phrases:
            c = canon(p)
            if c:
                forms.add(c)
                forms.add(nospace(c))
        tokens = [t for t in re.split(r"[^0-9a-z]+", name.lower()) if t]
        market = next((t for t in tokens if t in codes), None)
        if explicit or market is None:
            loose |= forms
            unscoped_files.append(name)
        else:
            per_market[market] |= forms

    if explicit:
        tested = [m for m in explicit if m]
    else:
        tested = sorted(per_market)
    for m in tested:
        per_market[m] |= loose              # a file with no market named covers every tested one
    return per_market, tested, files, unscoped_files


def merge_variants(rows):
    """One row per (market, canonical form), highest volume winning.

    On a tie the shorter phrase wins: it is the one more people type, and it
    makes a better title. The spellings that lost are counted, so a report
    can say a line stands for four ways of writing the same search.
    """
    best = {}
    for r in rows:
        key = (r["country"], canon(r["keyword"]))
        cur = best.get(key)
        if cur is None:
            r = dict(r, variants={r["keyword"]})
            best[key] = r
            continue
        cur["variants"].add(r["keyword"])
        better = r["volume"] > cur["volume"] or (
            r["volume"] == cur["volume"] and len(r["keyword"]) < len(cur["keyword"]))
        if better:
            kept = cur["variants"]
            best[key] = dict(r, variants=kept)
    return list(best.values())


def prepare_targets(targets):
    """(word set, page) per target phrase, single-word targets dropped.

    A one-word target overlaps half the bank, so letting it be somebody's
    "nearest page" points every gap at the same page and the hint stops
    meaning anything.
    """
    out = []
    for phrase, page in targets.items():
        words = set(norm(phrase).split())
        if len(words) >= 2:
            out.append((words, page))
    return out


def nearest(words, prepared, threshold):
    """The closest existing page by Jaccard overlap of word sets, or ("", 0).

    Reported only above a threshold. Overlap on its own always names some
    page, which reads as "a page nearly covers this" when it does not, so
    the score has to clear a bar before the hint is printed at all.

    Ties break on the number of shared words and then on the page URL, so
    two runs over the same bank name the same page. Left to dictionary order
    the hint moves when a row is added to the register, and a diff of two
    reports fills up with changes that mean nothing.
    """
    best = (0.0, 0, "")
    for tw, page in prepared:
        union = len(words | tw)
        if not union:
            continue
        shared = len(words & tw)
        cand = (shared / float(union), shared, page)
        if cand[0] > best[0] or (cand[0] == best[0] and (-cand[1], cand[2]) < (-best[1], best[2])):
            best = cand
    return (best[2], best[0]) if best[0] >= threshold else ("", 0.0)


def line(row, cfg):
    """One markdown bullet. ASCII punctuation only."""
    bits = "- %s -- %s (%s)" % (row["keyword"], volume_label(row), cfg.market_name(row["country"]))
    n = len(row["variants"])
    if n > 1:
        bits += ", %d spellings" % n
    if row["near_page"]:
        bits += " - near %s" % row["near_page"]
    return bits


def write_report(fh, groups, cfg, meta):
    date = meta["date"]
    total = sum(len(g) for g in groups.values())
    fh.write("# Untargeted searches, %s\n\n" % date)
    fh.write(
        "%s searches at %s+ a month that no page here targets. Close variants are merged, "
        "brand searches and searches this project cannot serve are dropped. Volumes are "
        "Keyword Planner ranges where the export gave a range.\n\n"
        % ("{:,}".format(total), "{:,}".format(meta["min"]))
    )
    fh.write("Bank: %s, %s rows read, %s on topic and untargeted after merging.\n"
             % (meta["bank"], "{:,}".format(meta["read"]), "{:,}".format(total)))
    fh.write("Page targets: %s, %d pages.\n" % (meta["targets"] or "none given", meta["target_count"]))
    if meta["missing_filters"]:
        fh.write("\nWarning: these config filters are empty and currently match nothing: %s. "
                 "Fill them in %s before trusting the counts.\n"
                 % (", ".join(meta["missing_filters"]), meta["config"]))
    fh.write("\n## Reading the open-gap test\n\n")
    if meta["tested"]:
        fh.write(
            "An open gap is a search with volume that no page here targets and that appears in "
            "no competitor keyword-ideas export read for its market. There is no incumbent page "
            "to outrank, so these are the ones to write first.\n\n"
            "The limit, stated plainly: absence from a competitor's keyword ideas means their "
            "pages do not cover that wording. It does not prove nobody ranks for the phrase. "
            "Planner builds a site's idea list from that site's own pages, so a competitor "
            "ranking through a page the crawl missed, a forum thread or a video still sits in an "
            "open gap here. Check the live results for a phrase before committing a page to it.\n\n"
        )
        fh.write("Competitor ideas were read for: %s.\n"
                 % ", ".join(cfg.market_name(m) for m in meta["tested"]))
        fh.write("Every other market is untested, and its rows are listed separately below.\n")
        fh.write("\nFiles read (%d): %s.\n"
                 % (len(meta["files"]), ", ".join("%s (%s)" % (n, "{:,}".format(c))
                                                  for n, c in meta["files"])))
        if meta["unscoped"]:
            fh.write("No market code in the filename of %s, so these were applied to every "
                     "tested market.\n" % ", ".join(meta["unscoped"]))
    else:
        fh.write(
            "The open-gap test did not run: no competitor keyword-ideas exports were found in "
            "%s. Pull one Planner \"Start with a website\" run per competitor, drop the CSVs "
            "there with the market code in each filename, and run this again. Until then every "
            "row below is simply untargeted, which says nothing about whether a competitor "
            "already covers it.\n" % (meta["competitors"] or "the competitors directory")
        )

    order = [
        ("open", "Open gaps", "No page here and no competitor's ideas cover these."),
        ("covered", "Untargeted, but a competitor's ideas cover the wording",
         "Worth writing, with an incumbent page to beat."),
        ("untested", "Untargeted, market not tested against competitors",
         "No competitor ideas were pulled for these markets, so their standing is unknown."),
    ]
    for key, heading, blurb in order:
        rows = groups.get(key) or []
        if not rows:
            continue
        fh.write("\n## %s (%s)\n\n%s\n\n" % (heading, "{:,}".format(len(rows)), blurb))
        for r in rows:
            fh.write(line(r, cfg) + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Untargeted searches with volume, and the open-gap test against competitors.")
    ap.add_argument("--bank", default=os.path.join("seo", "keywords.csv"),
                    help="keyword bank CSV: keyword, country, volume, source")
    ap.add_argument("--targets", default=os.path.join("seo", "page-register.csv"),
                    help="page register CSV or targets JSON: which search each page is aimed at")
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help="per-project keyword config (see kwlib)")
    ap.add_argument("--competitors", default=os.path.join("seo", "competitors"),
                    help="directory of competitor keyword-ideas exports")
    ap.add_argument("--competitor-markets", default="",
                    help="comma-separated market codes the competitor files cover, "
                         "instead of reading a code out of each filename")
    ap.add_argument("--out", default=os.path.join("seo", "reports"),
                    help="directory for the report and CSV")
    ap.add_argument("--min", type=int, default=1000,
                    help="lowest monthly volume to report (default 1000)")
    ap.add_argument("--near", type=float, default=0.5,
                    help="Jaccard overlap a page needs before it is named as near (default 0.5)")
    a = ap.parse_args()

    cfg = load_config_or_exit(a.config)
    missing = cfg.missing()
    if "on_topic" in missing:
        sys.stderr.write(
            "WARNING: on_topic is empty in %s, so every keyword classifies as off-topic and this\n"
            "         report will be empty. Fill it in before reading anything into the result.\n"
            % a.config)

    try:
        targets = load_targets(a.targets)
        if not os.path.exists(a.bank):
            raise ConfigError("no keyword bank at %s (pass --bank)" % a.bank)
        rows, had_volume = read_bank(a.bank)
    except (ConfigError, ValueError) as e:
        sys.stderr.write("ERROR: %s\n" % ascii_safe(e))
        sys.exit(2)

    if not rows:
        sys.stderr.write("ERROR: no rows in %s. Check it is the bank and not an export.\n" % a.bank)
        sys.exit(2)
    if not had_volume:
        sys.stderr.write("WARNING: %s has no volume column, so every row counts as 0 and --min "
                         "will drop them all.\n" % a.bank)

    # Filter order matters only for the counts printed at the end: volume
    # first because it is the cheapest test, then brands, then classify,
    # which is the one that walks every page target.
    kept, dropped = [], defaultdict(int)
    for r in rows:
        if r["volume"] < a.min:
            dropped["below min"] += 1
            continue
        n = norm(r["keyword"])
        if cfg.brands.search(n):
            dropped["other brands"] += 1
            continue
        status, _page = classify(r["keyword"], cfg, targets)
        if status != "unused":
            dropped[status] += 1
            continue
        kept.append(r)

    merged = merge_variants(kept)
    prepared = prepare_targets(targets)
    per_market, tested, files, unscoped = collect_competitors(
        a.competitors, cfg, [m.strip().lower() for m in a.competitor_markets.split(",") if m.strip()])

    groups = {"open": [], "covered": [], "untested": []}
    for r in merged:
        r["near_page"], r["near_score"] = nearest(set(norm(r["keyword"]).split()), prepared, a.near)
        market = r["country"]
        if market not in tested:
            bucket = "untested"
        else:
            forms = per_market.get(market) or set()
            c = canon(r["keyword"])
            bucket = "covered" if (c in forms or nospace(c) in forms) else "open"
        r["bucket"] = bucket
        groups[bucket].append(r)

    for rows_ in groups.values():
        rows_.sort(key=lambda r: (-r["volume"], r["country"], r["keyword"]))

    date = datetime.date.today().isoformat()
    out_dir = a.out or "."
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    md_path = os.path.join(out_dir, "untargeted-keywords-%s.md" % date)
    csv_path = os.path.join(out_dir, "untargeted-keywords-%s.csv" % date)

    meta = {
        "date": date, "min": a.min, "bank": a.bank, "read": len(rows),
        "targets": a.targets, "target_count": len(targets), "config": a.config,
        "missing_filters": missing, "competitors": a.competitors,
        "tested": tested, "files": files, "unscoped": unscoped,
    }
    with open(md_path, "w", encoding="utf-8") as fh:
        write_report(fh, groups, cfg, meta)

    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["keyword", "country", "market", "volume", "volume_range", "open_gap",
                    "competitor_check", "nearest_page", "near_score", "spellings", "variants"])
        for key in ("open", "covered", "untested"):
            for r in groups[key]:
                w.writerow([
                    r["keyword"], r["country"], cfg.market_name(r["country"]), r["volume"],
                    volume_label(r), "yes" if key == "open" else "no",
                    "not tested" if key == "untested" else "tested",
                    r["near_page"], "%.2f" % r["near_score"], len(r["variants"]),
                    " | ".join(sorted(r["variants"])),
                ])

    print("  read %s rows from %s" % ("{:,}".format(len(rows)), a.bank))
    for reason in sorted(dropped):
        print("  dropped %-14s %s" % (reason, "{:,}".format(dropped[reason])))
    print("  %s untargeted after merging close variants (%s before)"
          % ("{:,}".format(len(merged)), "{:,}".format(len(kept))))
    if tested:
        print("  competitor ideas: %d files, markets tested: %s"
              % (len(files), ", ".join(ascii_safe(m) for m in tested)))
        print("  OPEN GAPS %s, with an incumbent %s, untested markets %s"
              % ("{:,}".format(len(groups["open"])), "{:,}".format(len(groups["covered"])),
                 "{:,}".format(len(groups["untested"]))))
    else:
        print("  no competitor exports in %s, so the open-gap test did not run" % a.competitors)
    print("  wrote %s and %s" % (md_path, csv_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
