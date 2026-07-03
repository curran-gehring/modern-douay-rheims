#!/usr/bin/env python3
"""Turn the proposed lexicons into the curated finals modernize.py loads.

Applies the hand-resolution table below to lexicon_{eth,est}.proposed.tsv
and writes lexicon_{eth,est}.tsv. Every '?' / AMBIGUOUS proposal line must
be covered by FIXES (or the token dropped via DROP) — the script fails if
any survives, so an updated corpus can't silently ship an unreviewed guess.

Each fix documents its reasoning; several correct source typos whose intent
is unambiguous from the verse and its Latin partner.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

FIXES_ETH = {
    "aileth": "ails",
    "tilleth": "tills",
    "rageth": "rages",
    "oweth": "owes",
    "endeavoureth": "endeavours",       # British spelling, matches DR register
    "acheth": "aches",
    "rideth": "rides",
    "wasteth": "wastes",                # verb waste, not archaic 'wast'
    "dishonoureth": "dishonours",
    "comitteth": "commits",             # source typo for 'committeth' (EZK 18)
    "biteth": "bites",
    "loatheth": "loathes",
    "mareth": "mars",
    "contendeth": "contends",
    "inebreateth": "inebriates",        # source typo, PSA 22:5 'chalice which'
    "fretteth": "frets",
    "belieth": "belies",
    "museth": "muses",
    "pineth": "pines",
    "breatheth": "breathes",
    "overcameth": "overcomes",          # 1JN 5:4; Vulgate 'vincit' (present)
}
FIXES_EST = {
    "plattest": "plait",                # JDG 16:13, Samson's locks (braiding)
    "clothest": "clothe",
    "endeavourest": "endeavour",
    "dishonourest": "dishonour",
}
# Superlative-only adjectives that slipped past the stem filters — never a
# 2sg verb anywhere in this corpus ("clearest oil", "the bravest", ...).
# "meanest" is NOT here: "what meanest thou" is a frequent real verb use.
DROP: set[str] = {
    "clearest", "bravest", "stoutest", "goodliest", "chiefest",
    "cleanest", "fattest", "fiercest", "rightest",
}


def curate(src: str, dst: str, fixes: dict[str, str]) -> None:
    out, unresolved = [], []
    for line in (HERE / src).read_text("utf-8").splitlines():
        tok, modern, count, note = line.split("\t")
        if tok in DROP:
            continue
        if tok in fixes:
            out.append(f"{tok}\t{fixes[tok]}\t{count}\tcurated")
            continue
        if modern == "?" or note.startswith("AMBIGUOUS"):
            unresolved.append(tok)
            continue
        out.append(f"{tok}\t{modern}\t{count}\t{note}")
    if unresolved:
        raise SystemExit(f"{src}: unreviewed proposals remain: {unresolved}")
    (HERE / dst).write_text("\n".join(out) + "\n", "utf-8")
    print(f"{dst}: {len(out)} mappings")


if __name__ == "__main__":
    curate("lexicon_eth.proposed.tsv", "lexicon_eth.tsv", FIXES_ETH)
    curate("lexicon_est.proposed.tsv", "lexicon_est.tsv", FIXES_EST)
