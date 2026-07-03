#!/usr/bin/env python3
"""Conform the scrollmapper Challoner DR verse grid to the Clementine Vulgate.

The two vendored sources disagree at exactly 14 verse boundaries. In every
case the scrollmapper VulgClementine grid MATCHES the catss Clementine
Vulgate (`catss/raw_vul.tsv` — the text vulgate.sqlite / vulgate_verse_map
derive from, i.e. the alignment anchor devices already have), so the Vulgate
grid is authoritative and only DR is adjusted. Three fix classes, each
curated by hand after inspecting the full text of both editions:

  MERGE  — DR splits a verse the Vulgate prints as one (all 5 are
           chapter-final): append DR's extra verse to the previous verse.
  SPLIT  — DR merges two Vulgate verses into one: split the DR verse at a
           curated phrase (phrase STARTS the new second verse) and shift any
           subsequent verses up by one.
  SUPPLY — the scrollmapper DRC simply omits a verse the Vulgate has: patch
           in the authentic public-domain Challoner text (each matches its
           Latin partner clause-for-clause).

Every rule is validated at apply time (phrase found exactly once, both
halves non-empty, target key present/absent as expected) — a vendored-source
update that invalidates a rule fails the build rather than silently
misaligning.
"""
from __future__ import annotations

Key = tuple[str, int, int]

# (book, chapter, verse_to_remove): its text is appended to verse-1.
MERGES: list[Key] = [
    ("ISA", 45, 26),
    ("PSA", 15, 11),
    ("PSA", 42, 6),
    ("PSA", 125, 7),
    ("PSA", 135, 27),
]

# (book, chapter, verse): split at `phrase` (which begins the new verse+1);
# all later verses in the chapter shift up by one.
SPLITS: list[tuple[str, int, int, str]] = [
    ("1TH", 4, 11, "and that you walk honestly"),
    ("2SA", 13, 38, "And king David ceased"),
    ("2TH", 2, 10, "Therefore God shall send"),
    ("ISA", 46, 11, "Hear me, O ye hardhearted"),
    ("PSA", 150, 5, "let every spirit praise"),
    ("SIR", 29, 16, "and better than the spear"),
]

# Verses the scrollmapper DRC omits entirely: authentic Challoner text.
SUPPLY: dict[Key, str] = {
    ("1KI", 17, 19): (
        "And Elias said to her: Give me thy son. And he took him out of "
        "her bosom, and carried him into the upper chamber where he abode, "
        "and laid him upon his own bed."
    ),
    ("BAR", 6, 37): "They shew no pity to the widow, nor do good to the fatherless.",
    ("PRO", 30, 29): (
        "There are three things, which go well, and the fourth that "
        "walketh happily:"
    ),
}


def reconcile(drc: dict[Key, str]) -> dict[Key, str]:
    """Return a new dict with the DR grid conformed to the Vulgate grid."""
    out = dict(drc)

    for book, ch, v in MERGES:
        key, prev = (book, ch, v), (book, ch, v - 1)
        if key not in out or prev not in out:
            raise SystemExit(f"MERGE rule stale: {key} / {prev} missing")
        if (book, ch, v + 1) in out:
            raise SystemExit(f"MERGE rule stale: {key} is not chapter-final")
        out[prev] = out[prev].rstrip() + " " + out.pop(key).lstrip()

    for book, ch, v, phrase in SPLITS:
        key = (book, ch, v)
        text = out.get(key)
        if text is None or text.count(phrase) != 1:
            raise SystemExit(f"SPLIT rule stale: {key} phrase {phrase!r} "
                             f"not found exactly once")
        head, tail = text.split(phrase, 1)
        head, tail = head.rstrip(), (phrase + tail).strip()
        if not head or not tail:
            raise SystemExit(f"SPLIT rule stale: {key} produces empty half")
        # Shift later verses up by one, highest first so keys never collide.
        later = sorted((vv for (b, c, vv) in out if b == book and c == ch and vv > v),
                       reverse=True)
        for vv in later:
            out[(book, ch, vv + 1)] = out.pop((book, ch, vv))
        out[key] = head
        out[(book, ch, v + 1)] = tail

    for key, text in SUPPLY.items():
        if key in out:
            raise SystemExit(f"SUPPLY rule stale: {key} now present in source")
        out[key] = text

    return out
