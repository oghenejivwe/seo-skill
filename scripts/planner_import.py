#!/usr/bin/env python3
"""
Turn a Google Ads Keyword Planner export into one normalised CSV the rest of
the keyword scripts read. Standard library only.

    python planner_import.py ~/Downloads/planner-us.csv --country us
    python planner_import.py ideas.csv --country jp --label competitor-ideas

THE EXPORT FORMAT IS A TRAP, THREE TIMES OVER

Planner's "Download" button writes UTF-16 with a byte-order mark, separates
fields with tabs rather than commas, and puts two title lines above the real
header. Opened the obvious way -- utf-8, comma, header on line one -- it
parses into one unusable column of mojibake, or raises a decode error on the
first byte. So this detects the BOM, decodes accordingly, finds the line that
starts with "Keyword" followed by a delimiter, and parses from there. A file
somebody re-saved from a spreadsheet falls back to utf-8-sig and commas.

The first title line also begins with "Keyword" ("Keyword Stats 2026-11-03
at ..."), which is why the header hunt insists on a tab or comma straight
after the word. Matching the bare prefix picks the title line and loses the
real header.

VOLUMES ARE RANGES, NOT NUMBERS

An account with no ad spend gets buckets, and the export writes one fixed
value per bucket: 500000 means 100K-1M, 50000 means 10K-100K, 5000 means
1K-10K, 500 means 100-1K, 50 means 10-100, 0 means 0-10, and an empty cell
means Planner has no data at all.

This stores the bucket's LOWER bound, so a range can never outrank a volume
that was actually measured, and names the range in the source column so the
distinction survives into every later report. kwlib.volume_label reads that
column back. Rows with no data import at 0 rather than being skipped, so the
slower per-keyword lookups elsewhere treat them as asked and answered instead
of re-querying them on every run.

WHY IT SHOUTS THE ROW COUNT

Exports land in the browser's download folder with near-identical names, and
in the run this was ported from a stale file was imported under the wrong
market -- a whole country's bank filled with another country's keywords, all
of it plausible, none of it true. The count, the market and a few sample
phrases print in a block at the end so they are checked against the Planner
screen before the numbers are believed.

Exits 1 when the header cannot be found, the volume column is missing, or
nothing survives the on-topic filter, so a scripted harvest stops instead of
writing an empty bank.
"""

import argparse
import csv
import datetime
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kwlib import (NEVER, DEFAULT_CONFIG, ascii_safe, bank_rows, canon,  # noqa: E402
                    load_config_or_exit, norm)

# Bucket value in the export -> (lower bound stored, range name written to source).
# Hyphens are ASCII: this goes to a cp1252 console and into CSVs other scripts read.
BUCKETS = {
    500000: (100000, "100K-1M"),
    50000: (10000, "10K-100K"),
    5000: (1000, "1K-10K"),
    500: (100, "100-1K"),
    50: (10, "10-100"),
    0: (0, "0-10"),
}

# Header line: the word Keyword, optionally quoted, then a delimiter. The
# delimiter is the whole point -- see the docstring on the title line.
HEADER_RE = re.compile(r'^"?keyword"?\s*[\t,]', re.IGNORECASE)

OUT_DIR = os.path.join("seo", "imports")


def count(n, word):
    """'1 row' / '7 rows', with a thousands separator. Reports get read."""
    return "%s %s%s" % ("{:,}".format(n), word, "" if n == 1 else "s")


def read_export(path):
    """Return (rows, header_line) from a Planner export.

    rows are dicts keyed by the export's own column names. Raises ValueError
    with a message for the user when the header cannot be found.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    if not raw.strip():
        raise ValueError("%s is empty" % path)

    # utf-16 without a declared endianness honours the BOM, which both of
    # Planner's variants carry.
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        lines = raw.decode(encoding).splitlines()
    except UnicodeDecodeError as e:
        raise ValueError("cannot decode %s as %s: %s" % (path, encoding, e))

    start = next((i for i, line in enumerate(lines) if HEADER_RE.match(line)), None)
    if start is None:
        raise ValueError(
            "no header row in %s\n"
            "  Expected a line beginning 'Keyword' followed by a tab or comma.\n"
            "  Planner writes two title lines above it; a file with neither is\n"
            "  probably the wrong download (a plan, a forecast, or a saved page)."
            % path
        )

    delimiter = "\t" if "\t" in lines[start] else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])), delimiter=delimiter)
    return list(reader), (reader.fieldnames or [])


def pick_columns(fields):
    """Return (keyword column, volume column). Either may be None."""
    kw_col = next((f for f in fields if f and f.strip().lower().startswith("keyword")), None)

    # "Avg. monthly searches" in both export types. The monthly breakdown
    # columns are named "Searches: Nov 2025" and must not be mistaken for it,
    # hence the colon test on the fallback.
    vol_col = next((f for f in fields if f and "monthly searches" in f.lower()), None)
    if not vol_col:
        vol_col = next(
            (f for f in fields if f and "searches" in f.lower() and ":" not in f), None
        )
    return kw_col, vol_col


def cell_number(cell):
    """The integer in a volume cell, or None when the cell holds no number.

    Planner writes 500000, some locales write 500.000 or 500,000, and a row
    with no data is blank or a dash. Everything that is not a digit, a dot or
    a minus goes, then the dots are treated as separators unless the value is
    a clean decimal such as 50.0.
    """
    s = re.sub(r"[^\d.\-]", "", (cell or "").strip())
    if not s.strip(".-"):
        return None
    if s.count(".") > 1 or re.search(r"\.\d{3}$", s):      # 500.000 is a separator, not a decimal
        s = s.replace(".", "")
    try:
        return int(float(s))
    except ValueError:
        return None


def bucket(cell):
    """(volume stored, range name) for one volume cell.

    A bucket value is indistinguishable from a measurement that happens to
    land on it: an account with ad spend reporting exactly 500 searches is
    written as the 100-1K range. The export carries nothing that separates
    the two, so the ambiguity is named here rather than hidden -- it costs one
    row its precision and never inflates a range into a measurement.
    """
    n = cell_number(cell)
    if n is None:
        return 0, "no data"
    if n in BUCKETS:
        return BUCKETS[n]
    return n, "exact"


def merge_into_bank(rows, bank_path):
    """Fold an import into the bank, keeping the highest volume per keyword.

    The reports read the bank, not seo/imports, so without this step an import
    is invisible to every one of them -- which looks exactly like a harvest
    that found nothing.

    A keyword is the same bank entry per (keyword, country), matched on norm()
    rather than the raw string so casing and punctuation do not create a
    second row. Close variants are deliberately NOT merged here: the variant
    map needs every spelling, and canon() is applied when counting, not when
    storing.
    """
    existing = []
    if os.path.exists(bank_path):
        existing = bank_rows(bank_path)

    index = {}
    out = []
    for r in existing:
        key = (norm(r["keyword"]), r["country"])
        if key in index:
            continue                      # bank already had a duplicate
        index[key] = len(out)
        out.append(dict(r))

    added = updated = 0
    for r in rows:
        key = (norm(r["keyword"]), r["country"])
        if key not in index:
            index[key] = len(out)
            out.append(dict(r))
            added += 1
            continue
        cur = out[index[key]]
        if r["volume"] > cur["volume"]:   # a measured number beats a stale one
            cur.update(r)
            updated += 1

    d = os.path.dirname(os.path.abspath(bank_path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(bank_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["keyword", "country", "volume", "source"])
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in
                        ("keyword", "country", "volume", "source")})
    return added, updated, len(out)


def main():
    ap = argparse.ArgumentParser(
        description="Normalise a Keyword Planner export (UTF-16, tab-separated) into a bank CSV."
    )
    ap.add_argument("export", help="the CSV downloaded from Keyword Planner")
    ap.add_argument("--country", required=True,
                    help="market code this export was pulled for, e.g. us")
    ap.add_argument("--label", default="planner",
                    help="what this run was (default: planner). Goes in the source column, "
                         "so competitor-ideas and local-ideas stay tellable apart later.")
    ap.add_argument("--out", default=None,
                    help="output CSV (default: %s/planner-<country>-<label>-<date>.csv)" % OUT_DIR)
    ap.add_argument("--into", default=None,
                    help="also merge the result into this bank, e.g. seo/keywords.csv. "
                         "Without it the import sits in seo/imports and the reports, "
                         "which read the bank, will not see it")
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help="keyword config (default: %s)" % DEFAULT_CONFIG)
    a = ap.parse_args()

    cfg = load_config_or_exit(a.config)
    country = a.country.strip().lower()

    # An absent on_topic compiles to a pattern that matches nothing, which as
    # a filter would reject the whole export. That inverts what kwlib means by
    # an empty filter -- it passes everything -- so an empty one is treated as
    # no filter, loudly, rather than as a bank with one keyword in it.
    filtering = cfg.on_topic is not NEVER
    if not filtering:
        print("")
        print("  WARNING: on_topic is empty in %s, so nothing will be filtered." % a.config)
        print("  Every row in the export goes into the bank, relevant or not.")

    try:
        rows, fields = read_export(a.export)
    except (IOError, OSError) as e:
        sys.stderr.write("ERROR: cannot read %s: %s\n" % (a.export, e))
        return 1
    except ValueError as e:
        sys.stderr.write("ERROR: %s\n" % ascii_safe(e))
        return 1

    kw_col, vol_col = pick_columns(fields)
    if not kw_col:
        sys.stderr.write("ERROR: no Keyword column in %s; columns: %s\n"
                         % (a.export, ", ".join(ascii_safe(f) for f in fields if f)))
        return 1
    if not vol_col:
        # Importing the file anyway would mark every phrase as checked and
        # empty, which is worse than importing nothing.
        sys.stderr.write(
            "ERROR: no volume column in %s; columns: %s\n"
            "  Download 'Plan historical metrics' or 'Keyword ideas', not the plan table.\n"
            % (a.export, ", ".join(ascii_safe(f) for f in fields if f))
        )
        return 1

    out = a.out or os.path.join(
        OUT_DIR, "planner-%s-%s-%s.csv" % (country, a.label, datetime.date.today().isoformat())
    )

    kept = {}                                  # norm(keyword) -> [keyword, country, volume, source]
    off_topic = merged = ranged = nodata = 0
    for r in rows:
        kw = (r.get(kw_col) or "").strip()
        n = norm(kw)
        if not n:
            continue
        if filtering and not cfg.on_topic.search(n):
            off_topic += 1
            continue
        volume, name = bucket(r.get(vol_col))
        row = [kw, country, volume, "%s %s" % (a.label, name)]
        if n in kept:
            # The same phrase twice in one export, usually a spelling Planner
            # lists under two ideas groups. Highest volume wins, as in 4.1.
            merged += 1
            if volume > kept[n][2]:
                kept[n] = row
            continue
        kept[n] = row

    for row in kept.values():
        if row[3].endswith("no data"):
            nodata += 1
        elif not row[3].endswith("exact"):
            ranged += 1

    if not kept:
        sys.stderr.write(
            "ERROR: %d rows read, none on topic. Nothing written.\n"
            "  Either this export is for another product, or on_topic in %s does\n"
            "  not cover this market's language. A filter written only in English\n"
            "  empties a non-English market and looks like an empty market.\n"
            % (len(rows), a.config)
        )
        return 1

    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["keyword", "country", "volume", "source"])
        w.writerows(kept.values())

    distinct = len({canon(row[0]) for row in kept.values()})

    print("")
    print("  read      %s from %s" % (count(len(rows), "row"), os.path.basename(a.export)))
    print("  kept      %s%s  (%s off topic, %s merged as duplicates)"
          % ("{:,}".format(len(kept)), " on topic" if filtering else " unfiltered",
             "{:,}".format(off_topic), "{:,}".format(merged)))
    print("  volumes   %s a range, %s measured, %s with no data"
          % ("{:,}".format(ranged), "{:,}".format(len(kept) - ranged - nodata), "{:,}".format(nodata)))
    print("  searches  %s distinct after merging close variants" % "{:,}".format(distinct))
    print("            (every spelling is kept in the file; the variant map needs them)")
    print("  wrote     %s" % out)

    if cfg.markets and country not in cfg.markets:
        print("")
        print("  WARNING: '%s' is not one of the markets in %s (%s)."
              % (country, a.config, ", ".join(sorted(cfg.markets))))
        print("  Check the code before the bank fills with it.")

    # The leftover-export guard. The count comes from the file, the market from
    # the flag, and nothing connects them except the person reading this.
    samples = [ascii_safe(row[0]) for row in list(kept.values())[:3]]
    named = (" (%s)" % ascii_safe(cfg.market_name(country))) if country in cfg.markets else ""
    print("")
    print("  " + "-" * 64)
    print("  ROW COUNT %s   ->   market %s%s"
          % ("{:,}".format(len(rows)), country.upper(), named))
    print("  file %s" % os.path.abspath(a.export))
    for s in samples:
        print("    e.g. %s" % s[:70])
    print("  Does the count match what the Planner screen showed, and do those")
    print("  phrases look like this market's language? If not, this is a leftover")
    print("  download. Delete the output and pull the export again.")
    print("  " + "-" * 64)
    print("")
    if a.into:
        bank_in = [{"keyword": r[0], "country": r[1], "volume": r[2],
                    "source": r[3]} for r in kept.values()]
        added, updated, total = merge_into_bank(bank_in, a.into)
        print("  bank      %s" % a.into)
        print("            %d added, %d raised to a higher volume, %d rows total"
              % (added, updated, total))
    else:
        print("  NOT IN THE BANK YET. gap_report and variant_map read the bank,")
        print("  not seo/imports, so re-run with --into seo/keywords.csv or this")
        print("  import will not appear in any report.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
