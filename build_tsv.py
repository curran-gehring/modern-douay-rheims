#!/usr/bin/env python3
"""Build the Modern Douay-Rheims + Clementine Vulgate verse TSVs.

Reads the vendored scrollmapper sources (source/DRC.json = Challoner
Douay-Rheims, source/VulgClementine.json = Clementine Vulgate — a matched
pair: identical 78-book lists, verse-for-verse aligned, Vulgate Psalm
numbering) and writes:

    modern_douay_rheims_verses.tsv   Challoner DR -> deterministic modernize()
    vulgata_clementina_verses.tsv    Clementine Latin, same keys

Line format matches the Modern Brenton TSV consumed by FirstWord's ingest:

    <CODE> <chapter>:<verse>\t<text>

Book codes are USFM/OSIS-style 3-char codes (GEN, EXO, ...), same family the
Modern Brenton TSV uses, so the downstream ingest can share coordinate maps.

Both TSVs carry the FULL canon (incl. deuterocanon); consumers decide what
to keep. A key-parity gate fails the build if the two TSVs ever diverge.

Run:  python build_tsv.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from modernize import modernize, residual_archaisms
from reconcile import reconcile

HERE = Path(__file__).resolve().parent

# scrollmapper book name -> USFM-style code (order matches the source lists).
BOOK_CODES = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM",
    "Deuteronomy": "DEU", "Joshua": "JOS", "Judges": "JDG", "Ruth": "RUT",
    "I Samuel": "1SA", "II Samuel": "2SA", "I Kings": "1KI", "II Kings": "2KI",
    "I Chronicles": "1CH", "II Chronicles": "2CH", "Ezra": "EZR",
    "Nehemiah": "NEH", "Tobit": "TOB", "Judith": "JDT", "Esther": "EST",
    "Job": "JOB", "Psalms": "PSA", "Proverbs": "PRO", "Ecclesiastes": "ECC",
    "Song of Solomon": "SNG", "Wisdom": "WIS", "Sirach": "SIR",
    "Isaiah": "ISA", "Jeremiah": "JER", "Lamentations": "LAM",
    "Baruch": "BAR", "Ezekiel": "EZK", "Daniel": "DAN", "Hosea": "HOS",
    "Joel": "JOL", "Amos": "AMO", "Obadiah": "OBA", "Jonah": "JON",
    "Micah": "MIC", "Nahum": "NAM", "Habakkuk": "HAB", "Zephaniah": "ZEP",
    "Haggai": "HAG", "Zechariah": "ZEC", "Malachi": "MAL",
    "I Maccabees": "1MA", "II Maccabees": "2MA",
    "Matthew": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN",
    "Acts": "ACT", "Romans": "ROM", "I Corinthians": "1CO",
    "II Corinthians": "2CO", "Galatians": "GAL", "Ephesians": "EPH",
    "Philippians": "PHP", "Colossians": "COL", "I Thessalonians": "1TH",
    "II Thessalonians": "2TH", "I Timothy": "1TI", "II Timothy": "2TI",
    "Titus": "TIT", "Philemon": "PHM", "Hebrews": "HEB", "James": "JAS",
    "I Peter": "1PE", "II Peter": "2PE", "I John": "1JN", "II John": "2JN",
    "III John": "3JN", "Jude": "JUD", "Revelation of John": "REV",
    # Vulgate-appendix material — emitted (consumers skip what they lack
    # ids for), coded with the standard USFM apocrypha codes.
    "Prayer of Manasses": "MAN", "I Esdras": "1ES", "II Esdras": "2ES",
    "Additional Psalm": "PS2", "Laodiceans": "LAO",
}


def load(name: str) -> dict[tuple[str, int, int], str]:
    """{(code, chapter, verse): text} for one scrollmapper JSON."""
    books = json.loads((HERE / "source" / name).read_text(encoding="utf-8"))["books"]
    out: dict[tuple[str, int, int], str] = {}
    for book in books:
        code = BOOK_CODES[book["name"]]  # KeyError = unexpected book: fail loud
        for ch in book["chapters"]:
            c = int(ch["chapter"])
            for vv in ch["verses"]:
                v = int(vv["verse"])
                text = " ".join(vv["text"].split())  # collapse whitespace/newlines
                if not text:
                    continue
                key = (code, c, v)
                if key in out:
                    raise SystemExit(f"duplicate key {key} in {name}")
                out[key] = text
    return out


def write_tsv(path: Path, verses: dict[tuple[str, int, int], str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (code, c, v), text in verses.items():  # dicts preserve source order
            f.write(f"{code} {c}:{v}\t{text}\n")


# Post-modernize per-verse fixups for 2sg verbs neither license can reach
# (the thou-form sits in the PREVIOUS verse: "...thou... [17] And knowest
# his will [18]"). Applied verbatim; a stale entry fails the build.
POST_FIXES: dict[tuple[str, int, int], list[tuple[str, str]]] = {
    ("ROM", 2, 18): [("knowest", "know"), ("approvest", "approve")],
    # Source mixes eth/est inside one who-clause ("who giveth me revenge,
    # and bringest down"); render both 3sg like the surrounding clause.
    ("2SA", 22, 48): [("bringest", "brings")],
}


def main() -> int:
    drc = reconcile(load("DRC.json"))  # conform DR grid to the Vulgate grid
    vul = load("VulgClementine.json")

    # GATE — key parity: the pair promise (join 1:1 on identical keys) must
    # hold exactly; a mismatch means the vendored sources changed shape.
    only_drc = drc.keys() - vul.keys()
    only_vul = vul.keys() - drc.keys()
    if only_drc or only_vul:
        print(f"KEY PARITY FAILED: {len(only_drc)} DR-only, {len(only_vul)} "
              f"VUL-only; e.g. {sorted(only_drc)[:3]} / {sorted(only_vul)[:3]}")
        return 1

    modern = {k: modernize(t) for k, t in drc.items()}
    for key, subs in POST_FIXES.items():
        for old, new in subs:
            if old not in modern.get(key, ""):
                print(f"POST_FIX stale: {old!r} not in {key}")
                return 1
            modern[key] = modern[key].replace(old, new)

    # Residual-archaism report: what the conservative pass left untouched.
    residual: Counter[str] = Counter()
    for t in modern.values():
        residual.update(w.lower() for w in residual_archaisms(t))
    changed = sum(1 for k in drc if modern[k] != drc[k])

    write_tsv(HERE / "modern_douay_rheims_verses.tsv", modern)
    write_tsv(HERE / "vulgata_clementina_verses.tsv", vul)

    print(f"{len(modern)} verses (keys identical across both TSVs)")
    print(f"modernized {changed} verses ({changed/len(modern):.1%})")
    print(f"residual archaic tokens: {sum(residual.values())} "
          f"across {len(residual)} types; top 25:")
    for w, n in residual.most_common(25):
        print(f"  {n:6}  {w}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
