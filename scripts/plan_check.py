#!/usr/bin/env python3
"""Gate the page plan before anything gets written.

The three places Google reads to decide what a page is about are the title
tag, the H1, and the first sentence of body copy. A page missing its target
phrase in any of them is not a style problem -- it is ambiguous about its own
subject, and it leaves clicks and impressions on the table for no reason.

lint.py catches this, but only once a page exists. By then the copy is
written and the fix is a rewrite. This checks the plan instead, so the three
slots are decided at the same time as the URL and the page cannot be drafted
without them.

    python plan_check.py seo/structure.yaml

Exits non-zero if any page would fail, which makes it usable as a gate
between phase 2 and phase 3.

Shares its keyword matching with lint.py on purpose. If the two disagreed,
a plan could pass here and fail there.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint import has_kw, looks_like_interface, norm  # noqa: E402

LEDE_MAX_WORDS = 35
TITLE_MAX = 60

# Only the scalar fields this check reads. Anything nested under a page --
# requires:, links_to:, schema: -- is deliberately skipped.
WANTED = ("url", "primary_keyword", "title", "h1", "lede", "type", "status")


def _scalar(raw):
    """Strip a trailing comment, then quotes. Keeps '#' inside a quoted value."""
    s = raw.strip()
    if s[:1] in ("'", '"'):
        q = s[0]
        end = s.find(q, 1)
        while end != -1 and s[end - 1] == "\\":
            end = s.find(q, end + 1)
        if end != -1:
            return s[1:end].replace("\\" + q, q)
    s = re.sub(r"\s+#.*$", "", s).strip()
    if s in ('""', "''", "null", "~"):
        return ""
    return s


def load(path):
    """Read the `pages:` list without a YAML dependency.

    The plan is a flat list of pages with scalar fields, so a scoped reader
    is more honest than making the whole skill depend on PyYAML for one
    check. It tracks indentation and ignores anything nested inside a page.
    """
    pages, cur = [], None
    in_pages = False
    item_indent = key_indent = None

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            body = line.strip()

            if not in_pages:
                if re.match(r"^pages\s*:", body):
                    in_pages = True
                continue

            # A top-level key at or left of `pages:` ends the list.
            if indent == 0 and not body.startswith("-"):
                break

            if body.startswith("- "):
                if item_indent is None:
                    item_indent = indent
                if indent == item_indent:
                    if cur is not None:
                        pages.append(cur)
                    cur = {}
                    key_indent = None
                    body = body[2:].strip()
                    indent += 2
                else:
                    continue            # a nested list entry
            if cur is None:
                continue

            m = re.match(r"^([A-Za-z_][\w-]*)\s*:(.*)$", body)
            if not m:
                continue
            key, rest = m.group(1), m.group(2)

            if key_indent is None:
                key_indent = indent
            if indent > key_indent:
                continue                # nested under another key

            if key in WANTED:
                cur[key] = _scalar(rest)

    if cur is not None:
        pages.append(cur)
    return pages


def check_page(page, seen_titles):
    """Return (errors, warnings) for one planned page."""
    errs, warns = [], []
    url = page.get("url") or "<no url>"
    kw = (page.get("primary_keyword") or "").strip()

    if not kw:
        errs.append("no primary_keyword -- nothing to optimise toward")
        return errs, warns          # every other check depends on it

    # --- the three kings ------------------------------------------------
    for field, label in (("title", "title tag"),
                         ("h1", "H1"),
                         ("lede", "first sentence of body copy")):
        val = (page.get(field) or "").strip()
        if not val:
            errs.append("%s is empty. Write it now, with %r in it, not after "
                        "the body copy exists" % (label, kw))
            continue
        if not has_kw(val, kw):
            errs.append("%s does not contain %r: %r" % (label, kw, val[:70]))

    # --- the lede is the one people get wrong ---------------------------
    lede = (page.get("lede") or "").strip()
    if lede:
        if looks_like_interface(lede):
            errs.append("lede reads as interface text, not an opening line: %r. "
                        "This is the slot template furniture steals." % lede[:70])
        n = len(lede.split())
        if n > LEDE_MAX_WORDS:
            warns.append("lede is %d words. One sentence that answers the "
                         "question reads better than a paragraph." % n)

    # --- title hygiene --------------------------------------------------
    title = (page.get("title") or "").strip()
    if title:
        if len(title) > TITLE_MAX:
            warns.append("title is %d chars, over %d -- Google will truncate it"
                         % (len(title), TITLE_MAX))
        key = norm(title).strip()
        if key in seen_titles:
            errs.append("title duplicates %s. Two pages claiming one subject "
                        "compete with each other" % seen_titles[key])
        else:
            seen_titles[key] = url
        half = title[: max(1, len(title) // 2)]
        if not has_kw(half, kw):
            warns.append("keyword is in the back half of the title. Front-load it")

    # --- h1 should not just be the brand or a tagline -------------------
    h1 = (page.get("h1") or "").strip()
    if h1 and title and norm(h1) == norm(title) and len(h1.split()) < 3:
        warns.append("H1 and title are both very short and identical -- "
                     "likely a tagline rather than a subject")

    return errs, warns


def main():
    ap = argparse.ArgumentParser(
        description="Check every planned page carries its keyword in the "
                    "title, H1 and opening line before any page is written.")
    ap.add_argument("plan", nargs="?", default="seo/structure.yaml")
    ap.add_argument("--warnings-fail", action="store_true",
                    help="treat warnings as blocking too")
    a = ap.parse_args()

    if not os.path.exists(a.plan):
        print("No plan at %s. Phase 2 writes it." % a.plan)
        return 2

    pages = load(a.plan)
    if not pages:
        print("No pages in %s yet." % a.plan)
        return 2

    seen_titles = {}
    n_err = n_warn = 0
    clean = []

    for page in pages:
        url = page.get("url") or "<no url>"
        errs, warns = check_page(page, seen_titles)
        n_err += len(errs)
        n_warn += len(warns)
        if not errs and not warns:
            clean.append(url)
            continue
        print("\n%s" % url)
        for e in errs:
            print("  FAIL  %s" % e)
        for w in warns:
            print("  warn  %s" % w)

    print("\n%s" % ("-" * 60))
    print("%d pages checked. %d clean, %d failures, %d warnings."
          % (len(pages), len(clean), n_err, n_warn))

    if n_err:
        print("\nFix the plan before writing any of these pages. Putting the")
        print("keyword in the title, H1 and opening line costs nothing now and")
        print("is a rewrite once the copy exists.")
        return 1
    if n_warn and a.warnings_fail:
        return 1
    print("\nEvery page has its keyword in all three places. Clear for phase 3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
