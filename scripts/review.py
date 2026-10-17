#!/usr/bin/env python3
"""Recurring review: what to improve next, read out of Search Console exports.

Phase 7 of the seo-launch skill. Takes the CSVs the Search Console
Performance report exports and says which pages are worth touching, in what
order, and why. No credentials and no OAuth -- the export is a button in the UI.

    python review.py --queries Queries.csv --pages Pages.csv \
        --keywords seo/keywords.csv --out seo/reviews/2026-10-17

Compare two windows to catch decay and gains:

    python review.py --queries now/Queries.csv --prev-queries then/Queries.csv \
        --pages now/Pages.csv --prev-pages then/Pages.csv --out seo/reviews/...

If you have query-by-page rows (API, or an export taken with a page filter),
pass --pairs to unlock the cannibalisation and wrong-page checks.

Writes report.md (read this) and actions.csv (sort this yourself).
"""

import argparse
import csv
import datetime
import math
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------- reading

# Search Console names the first column differently depending on which tab you
# exported and which language the account is in. Match on what we recognise.
TERM_HEADERS = (
    "top queries", "query", "queries", "search query",
    "top pages", "page", "pages", "landing page", "url",
)
NUM_HEADERS = {
    "clicks": "clicks",
    "impressions": "impressions",
    "ctr": "ctr",
    "site ctr": "ctr",
    "url ctr": "ctr",
    "average ctr": "ctr",
    "position": "position",
    "average position": "position",
    "site position": "position",
    "url position": "position",
}


def to_num(raw):
    """GSC writes 1,234 and 3.5% and sometimes 3,5% depending on locale."""
    if raw is None:
        return 0.0
    s = str(raw).strip().replace("%", "").replace(" ", "")
    if not s:
        return 0.0
    # 1,234 is a thousands separator; 3,5 is a decimal comma.
    if "," in s and "." not in s:
        s = s.replace(",", "." if len(s.split(",")[-1]) != 3 else "")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_ctr(raw):
    """Always a fraction.

    Read the percent sign rather than guessing from the magnitude. A CTR of
    "0.97%" parses to 0.97, which a magnitude test reads as 97% -- and the
    queries that matter most, high impressions and almost no clicks, are
    exactly the ones written that way.
    """
    if raw is None:
        return 0.0
    s = str(raw).strip()
    val = to_num(s)
    if "%" in s:
        return val / 100.0
    return val / 100.0 if val > 1 else val


def read_gsc(path):
    """One row per term. CTR comes back as a fraction, not a percentage."""
    if not path:
        return []
    if not os.path.exists(path):
        # Do not die on a typo in a scheduled run -- the other checks still work.
        print("warning: %s not found, skipping it" % path, file=sys.stderr)
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    term_idx = next((i for i, c in enumerate(header) if c in TERM_HEADERS), None)
    if term_idx is None:
        term_idx = 0
        body = rows          # headerless export
    else:
        body = rows[1:]

    cols = {}
    for i, c in enumerate(header):
        if c in NUM_HEADERS:
            cols[NUM_HEADERS[c]] = i

    out = []
    for r in body:
        if not r or term_idx >= len(r) or not r[term_idx].strip():
            continue

        def get(k):
            return to_num(r[cols[k]]) if k in cols and cols[k] < len(r) else 0.0

        ctr = (to_ctr(r[cols["ctr"]])
               if "ctr" in cols and cols["ctr"] < len(r) else 0.0)
        imp = get("impressions")
        clicks = get("clicks")
        if not ctr and imp:      # some exports omit the CTR column
            ctr = clicks / imp
        out.append({
            "term": r[term_idx].strip(),
            "clicks": clicks,
            "impressions": imp,
            "ctr": ctr,
            "position": get("position"),
        })
    return out


def read_pairs(path):
    """query,page,clicks,impressions,ctr,position -- any column order."""
    if not path:
        return []
    if not os.path.exists(path):
        print("warning: %s not found, skipping it" % path, file=sys.stderr)
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        out = []
        for row in csv.DictReader(fh):
            low = {(k or "").strip().lower(): v for k, v in row.items()}
            q = low.get("query") or low.get("queries") or low.get("top queries")
            p = (low.get("page") or low.get("pages")
                 or low.get("top pages") or low.get("url"))
            if not q or not p:
                continue
            ctr = to_ctr(low.get("ctr"))
            out.append({
                "query": q.strip(),
                "page": p.strip(),
                "clicks": to_num(low.get("clicks")),
                "impressions": to_num(low.get("impressions")),
                "ctr": ctr,
                "position": to_num(low.get("position")
                                   or low.get("average position")),
            })
        return out


def read_targeted(path):
    """The keyword set we meant to target, from phase 1."""
    if not path or not os.path.exists(path):
        return set(), {}
    terms, homes = set(), {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            low = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
            kw = (low.get("keyword") or "").strip().lower()
            if not kw:
                continue
            terms.add(kw)
            homes[kw] = (low.get("target_url") or "").strip()
    return terms, homes


# ------------------------------------------------------------- the curve

# Three anchors the corpus actually supports, from the worked example in
# play 1: a page at position 10 taking 10 clicks takes about 68 at position 5
# and about 318 at position 1. That is 1.42% -> 9.66% -> 45.8%. Everything
# between is interpolated in log space, so treat it as a shape rather than a
# measurement -- it is here to rank opportunities against each other, not to
# forecast traffic.
ANCHORS = [(1.0, 0.458), (5.0, 0.0966), (10.0, 0.0142)]


def expected_ctr(pos):
    if pos <= 1:
        return ANCHORS[0][1]
    for (p1, c1), (p2, c2) in zip(ANCHORS, ANCHORS[1:]):
        if pos <= p2:
            t = (math.log(pos) - math.log(p1)) / (math.log(p2) - math.log(p1))
            return math.exp(math.log(c1) + t * (math.log(c2) - math.log(c1)))
    # Past position 10, extend the 5->10 slope and floor it.
    (p1, c1), (p2, c2) = ANCHORS[1], ANCHORS[2]
    slope = (math.log(c2) - math.log(c1)) / (math.log(p2) - math.log(p1))
    val = math.exp(math.log(c2) + slope * (math.log(pos) - math.log(p2)))
    return max(val, 0.0008)


TARGET_POSITION = 3.0


def opportunity(row):
    """Clicks per window sitting on the table if this reached position 3.

    Impressions times the CTR gap. Position dominates the result, which is
    the weighting we want -- a page already ranking is far cheaper to move
    than a page that does not exist yet.
    """
    if row["position"] <= TARGET_POSITION or row["impressions"] <= 0:
        return 0.0
    gain = expected_ctr(TARGET_POSITION) - max(row["ctr"],
                                               expected_ctr(row["position"]))
    return max(row["impressions"] * gain, 0.0)


# -------------------------------------------------------------- the checks

def norm_url(u):
    return re.sub(r"[?#].*$", "", (u or "").strip().rstrip("/")).lower()


def find_actions(now_q, prev_q, now_p, prev_p, pairs, targeted, homes, floor):
    """Each check answers one question and tags its rows with a verdict."""
    acts = []
    prev_qi = {r["term"].lower(): r for r in prev_q}
    prev_pi = {norm_url(r["term"]): r for r in prev_p}

    for r in [x for x in now_q if x["impressions"] >= floor]:
        pos, imp, ctr = r["position"], r["impressions"], r["ctr"]
        opp = opportunity(r)
        exp = expected_ctr(pos)
        home = homes.get(r["term"].lower(), "")
        was = prev_qi.get(r["term"].lower())

        # The highest-return recurring task: already relevant, just unclear.
        if 5 <= pos <= 15:
            acts.append(dict(
                kind="striking-distance", term=r["term"], url=home,
                position=pos, impressions=imp, clicks=r["clicks"], ctr=ctr,
                opportunity=opp,
                note="Put this exact phrase in the title, H1 and first <p>, then re-index.",
            ))
        elif 3 < pos < 5:
            acts.append(dict(
                kind="nearly-there", term=r["term"], url=home,
                position=pos, impressions=imp, clicks=r["clicks"], ctr=ctr,
                opportunity=opp,
                note="Top four is the whole prize. Link to it from the strongest related page.",
            ))

        # Placement is fine, the title is not earning the click.
        if 2 <= pos <= 10 and imp >= max(floor, 50) and ctr < 0.5 * exp:
            acts.append(dict(
                kind="ctr-gap", term=r["term"], url=home,
                position=pos, impressions=imp, clicks=r["clicks"], ctr=ctr,
                opportunity=max(imp * (exp - ctr), 0.0),
                note="CTR is %.1f%% where this position usually earns several times that. Rewrite the title and meta description."
                     % (ctr * 100),
            ))

        # Real demand, nobody clicking at all.
        if r["clicks"] == 0 and imp >= max(floor * 3, 30):
            acts.append(dict(
                kind="no-clicks", term=r["term"], url=home,
                position=pos, impressions=imp, clicks=0, ctr=0.0,
                opportunity=opp,
                note="Shown and ignored. Look at the result Google is actually displaying.",
            ))

        # Search Console telling you what the page is really about.
        if targeted and r["term"].lower() not in targeted:
            acts.append(dict(
                kind="untargeted-query", term=r["term"], url=home,
                position=pos, impressions=imp, clicks=r["clicks"], ctr=ctr,
                opportunity=opp,
                note="Not in keywords.csv. This is the phrase people type -- add it, or retitle to match.",
            ))

        if was and was["impressions"] >= floor:
            d_imp = imp - was["impressions"]
            d_pos = was["position"] - pos          # positive means improved
            if d_imp <= -0.4 * was["impressions"]:
                acts.append(dict(
                    kind="decaying", term=r["term"], url=home,
                    position=pos, impressions=imp, clicks=r["clicks"], ctr=ctr,
                    opportunity=max(was["clicks"] - r["clicks"], 0.0),
                    note="Impressions down %d from %d, position %+.1f. Refresh this before writing anything new."
                         % (abs(int(d_imp)), int(was["impressions"]), d_pos),
                ))
            elif d_pos >= 3:
                acts.append(dict(
                    kind="gaining", term=r["term"], url=home,
                    position=pos, impressions=imp, clicks=r["clicks"], ctr=ctr,
                    opportunity=opp,
                    note="Up %.1f positions. Something here works -- build the rest of this cluster."
                         % d_pos,
                ))

    # Pages that used to rank and no longer do.
    for r in now_p:
        was = prev_pi.get(norm_url(r["term"]))
        if r["impressions"] < floor and was and was["impressions"] >= floor * 3:
            acts.append(dict(
                kind="page-dropped", term=r["term"], url=r["term"],
                position=r["position"], impressions=r["impressions"],
                clicks=r["clicks"], ctr=r["ctr"],
                opportunity=max(was["clicks"], 0.0),
                note="Was at %d impressions, now %d. Confirm it is still indexed before rewriting it."
                     % (int(was["impressions"]), int(r["impressions"])),
            ))

    # Needs query-by-page rows, so these two only run when --pairs is given.
    if pairs:
        by_query = defaultdict(list)
        for p in pairs:
            if p["impressions"] >= floor:
                by_query[p["query"].lower()].append(p)

        for q, rows in by_query.items():
            rows.sort(key=lambda x: -x["impressions"])
            if len(rows) > 1:
                urls = ", ".join(norm_url(x["page"]) for x in rows[:3])
                acts.append(dict(
                    kind="cannibalising", term=q, url=norm_url(rows[0]["page"]),
                    position=rows[0]["position"],
                    impressions=sum(x["impressions"] for x in rows),
                    clicks=sum(x["clicks"] for x in rows),
                    ctr=rows[0]["ctr"],
                    opportunity=sum(opportunity(x) for x in rows[1:]),
                    note="%d pages competing: %s. Pick the owner, point the others at it."
                         % (len(rows), urls),
                ))

            home = norm_url(homes.get(q, ""))
            ranking = norm_url(rows[0]["page"])
            if home and home != ranking:
                acts.append(dict(
                    kind="wrong-page", term=q, url=ranking,
                    position=rows[0]["position"],
                    impressions=rows[0]["impressions"],
                    clicks=rows[0]["clicks"], ctr=rows[0]["ctr"],
                    opportunity=opportunity(rows[0]),
                    note="Targeted %s, ranking %s. Either the target is wrong or the two pages are too alike."
                         % (home, ranking),
                ))

    acts.sort(key=lambda a: -a["opportunity"])
    return acts


# ------------------------------------------------------------- rendering

# Order matters: this is the order to do the work in, not just to read it.
ORDER = [
    ("striking-distance", "Positions 5-15 -- do these first",
     "Google already thinks the page is relevant. Three edits and a re-index."),
    ("nearly-there", "Positions 3-5 -- one push from the top four", ""),
    ("ctr-gap", "Ranking fine, not getting clicked",
     "The position is there. The title is not selling it."),
    ("untargeted-query", "Queries you did not plan for",
     "Search Console renaming your pages. Usually better than what you guessed."),
    ("gaining", "Moving up -- build out the cluster", ""),
    ("decaying", "Losing ground -- refresh before writing anything new", ""),
    ("page-dropped", "Pages that fell off", ""),
    ("cannibalising", "Two pages, one query", ""),
    ("wrong-page", "Ranking page is not the planned page", ""),
    ("no-clicks", "Impressions, zero clicks", ""),
]

FIELDS = ["kind", "term", "url", "position", "impressions", "clicks", "ctr",
          "opportunity", "note"]


def render(acts, meta, top):
    L = ["# Review -- %s" % meta["date"], ""]
    L.append("Window: %s. %s" % (meta["window"], meta["compare"]))
    L.append("")

    if not acts:
        L.append("Nothing above the noise floor of %d impressions."
                 % meta["floor"])
        L.append("")
        L.append("If the site launched in the last week or two, that is the expected")
        L.append("result rather than a problem. Impressions move before positions do.")
        return "\n".join(L) + "\n"

    # One figure per term. Several checks fire on the same query and summing
    # every row would triple-count the same missing clicks.
    best = {}
    for a in acts:
        k = a["term"].lower()
        best[k] = max(best.get(k, 0.0), a["opportunity"])
    total = sum(best.values())
    L.append("**%d actions. Roughly %d clicks per window sitting on the table.**"
             % (len(acts), round(total)))
    L.append("")
    L.append("Judge progress on totals, never on one query position -- a query with")
    L.append("one to three impressions swings forty places on a single search.")
    L.append("")

    for kind, title, blurb in ORDER:
        rows = [a for a in acts if a["kind"] == kind]
        if not rows:
            continue
        L.append("## %s (%d)" % (title, len(rows)))
        if blurb:
            L.append("")
            L.append(blurb)
        L.append("")
        L.append("| Query or page | Pos | Impr | Clicks | On the table | Do |")
        L.append("|---|---|---|---|---|---|")
        for a in rows[:top]:
            L.append("| %s | %.1f | %d | %d | %.0f | %s |" % (
                a["term"].replace("|", "/"), a["position"],
                int(a["impressions"]), int(a["clicks"]), a["opportunity"],
                a["note"].replace("|", "/")))
        if len(rows) > top:
            L.append("")
            L.append("_%d more in actions.csv._" % (len(rows) - top))
        L.append("")

    L.append("---")
    L.append("")
    L.append("Spend the manual re-index requests on the striking-distance rows")
    L.append("first. The button is about ten a day and this is where it pays.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="Rank what to improve next from Search Console exports.")
    ap.add_argument("--queries", required=True,
                    help="Search Console Queries export for this window")
    ap.add_argument("--pages", help="Search Console Pages export for this window")
    ap.add_argument("--prev-queries", help="Queries export for the earlier window")
    ap.add_argument("--prev-pages", help="Pages export for the earlier window")
    ap.add_argument("--pairs",
                    help="query,page,... rows -- unlocks the cannibalisation checks")
    ap.add_argument("--keywords", default="seo/keywords.csv",
                    help="phase 1 keyword set")
    ap.add_argument("--out", help="directory for report.md and actions.csv")
    ap.add_argument("--window", default="unspecified",
                    help="e.g. 28 days to 2026-10-17")
    ap.add_argument("--min-impressions", type=int, default=10,
                    help="noise floor; below this a position means nothing")
    ap.add_argument("--top", type=int, default=25,
                    help="rows per section in report.md")
    a = ap.parse_args()

    now_q = read_gsc(a.queries)
    if not now_q:
        print("No rows read from %s. Check it is the Queries tab export."
              % a.queries)
        return 1

    now_p = read_gsc(a.pages)
    prev_q = read_gsc(a.prev_queries)
    prev_p = read_gsc(a.prev_pages)
    pairs = read_pairs(a.pairs)
    targeted, homes = read_targeted(a.keywords)

    acts = find_actions(now_q, prev_q, now_p, prev_p, pairs, targeted, homes,
                        a.min_impressions)

    compare = ("Compared against the earlier window."
               if prev_q else
               "No earlier window given, so no decay or gain check. "
               "Pass --prev-queries next time.")
    if not targeted:
        compare += " No keywords.csv found, so untargeted queries are not flagged."
    if not pairs:
        compare += " No --pairs, so cannibalisation is not checked."

    report = render(acts, {
        "date": datetime.date.today().isoformat(),
        "window": a.window,
        "compare": compare,
        "floor": a.min_impressions,
    }, a.top)

    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8") as fh:
            fh.write(report)
        with open(os.path.join(a.out, "actions.csv"), "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for row in acts:
                out_row = dict(row)
                out_row["opportunity"] = round(row["opportunity"], 1)
                out_row["ctr"] = round(row["ctr"], 4)
                out_row["position"] = round(row["position"], 1)
                w.writerow(out_row)
        print("Wrote %s/report.md and actions.csv -- %d actions."
              % (a.out, len(acts)))
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
