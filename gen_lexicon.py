#!/usr/bin/env python3
"""Generate PROPOSED -eth/-est modernization lexicons from the DR corpus.

One-time generator (not part of the build): scans the Challoner DR for
archaic verb inflections, derives each token's modern form via reverse
Early-Modern-English morphology, and writes proposal TSVs:

    lexicon_eth.proposed.tsv    walketh -> walks     (3rd person singular)
    lexicon_est.proposed.tsv    walkest -> walk      (2nd person singular)

Each line: token<TAB>modern<TAB>count<TAB>note. Lines whose derivation was
ambiguous or failed carry modern='?' for hand resolution. The REVIEWED
files (lexicon_eth.tsv / lexicon_est.tsv — '?' lines resolved or deleted)
are what modernize.py loads; the generator never feeds the build directly,
so the shipped mapping is always the curated one.

Derivation:
  1. IRREGULAR seed map (goeth->goes, seest->see, sheweth->shows, ...).
  2. Candidate stems (bare / +e / i->y / undoubled) validated against
     /usr/share/dict/words, disambiguated by CORPUS frequency of the
     candidate as a standalone token (web2 lists archaic spellings like
     'knowe'/'passe', so dictionary presence alone over-generates; a real
     modern lemma also occurs on its own in the DR text, its ghost variant
     doesn't). Ties or dual-frequency hits -> flagged AMBIGUOUS.
  3. Tokens that appear capitalized mid-sentence in >=80% of occurrences
     are treated as proper nouns (Miphiboseth, Aseneth) and skipped.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDS = {w.strip().lower() for w in
         Path("/usr/share/dict/words").read_text().splitlines() if w.strip()}

# Hebrew letter names (Ps 118 / Lam acrostics) + ordinals + common
# non-verb -eth/-est vocabulary. Never transformed, never proposed.
STOP = {
    "aleph", "beth", "gimel", "daleth", "zain", "heth", "teth", "jod",
    "caph", "lamed", "samech", "sade", "coph", "res", "thau",
    "teeth", "beneath", "nazareth", "elizabeth", "seth", "japheth",
    "twentieth", "thirtieth", "fortieth", "fiftieth", "sixtieth",
    "seventieth", "eightieth", "ninetieth", "hundredth",
    "priest", "harvest", "forest", "manifest", "honest", "earnest",
    "tempest", "conquest", "request", "interest", "modest", "rest",
    "west", "east", "best", "breast", "chest", "guest", "feast", "beast",
    "nest", "pest", "test", "vest", "jest", "crest", "quest", "arrest",
    "attest", "contest", "detest", "digest", "invest", "protest",
    "suggest", "behest", "bequest", "unrest", "incest", "dishonest",
    "farthest", "furthest", "southwest", "northwest", "southeast",
    "northeast", "finest", "basest", "choicest",  # superlatives in DR usage
    "wrest",   # the verb 'wrest' itself, not a 2sg inflection
}
_SUPERLATIVE_HINT = re.compile(
    r"(great|high|low|old|young|small|strong|weak|pur|wis|holi|mighti|"
    r"rich|poor|deep|sweet|hard|soft|near|far|last|least|utmost|inner|"
    r"utter|eld|larg|long|short|fair|dear|vil|nobl|simpl)est$")

# Curated irregulars applied before morphology (short stems, EME-only
# spellings, irregular pasts that take -est in 2sg).
IRREGULAR_ETH = {
    "goeth": "goes", "doeth": "does", "seeth": "sees", "lieth": "lies",
    "dieth": "dies", "useth": "uses", "sheweth": "shows",
    "fleeth": "flees", "freeth": "frees", "agreeth": "agrees",
    "honoureth": "honours", "behoveth": "behoves", "hasteth": "hastens",
    "layeth": "lays", "payeth": "pays", "sayeth": "says",
    "stayeth": "stays", "slayeth": "slays", "prayeth": "prays",
    "obeyeth": "obeys", "buyeth": "buys", "hideth": "hides",
    "biddeth": "bids", "letteth": "lets", "putteth": "puts",
    "setteth": "sets", "getteth": "gets", "sitteth": "sits",
    "cutteth": "cuts", "shutteth": "shuts", "spitteth": "spits",
    "begetteth": "begets", "forgetteth": "forgets",
}
IRREGULAR_EST = {
    "goest": "go", "doest": "do", "seest": "see", "liest": "lie",
    "diest": "die", "usest": "use", "shewest": "show", "owest": "owe",
    "fleest": "flee", "sayest": "say", "layest": "lay", "hidest": "hide",
    # 2sg PAST forms (unlike -eth, -est attaches to past stems too)
    "camest": "came", "madest": "made", "gavest": "gave",
    "heardest": "heard", "becamest": "became", "begannest": "began",
    "sawest": "saw", "knewest": "knew", "tookest": "took",
    "spakest": "spoke", "wentest": "went", "saidst": "said",
    "leddest": "led", "didst": "did", "settest": "set", "puttest": "put",
    "lettest": "let", "sittest": "sit", "begettest": "beget",
    "wouldest": "would", "shouldest": "should", "couldest": "could",
    "mayest": "may", "mightest": "might", "oughtest": "ought",
}

_WORD = re.compile(r"[A-Za-z]+")


def modern_3sg(lemma: str) -> str:
    if re.search(r"[^aeiou]y$", lemma):
        return lemma[:-1] + "ies"
    if re.search(r"(s|sh|ch|x|z|o)$", lemma):
        return lemma + "es"
    return lemma + "s"


def derive_lemma(token: str, suffix: str, freq: Counter[str]) -> tuple[str | None, str]:
    stem = token[: -len(suffix)]
    if len(stem) < 3:
        return None, "stem too short"
    cands: list[str] = []
    if stem.endswith("i") and stem[:-1] + "y" in WORDS:      # carrieth -> carry
        cands.append(stem[:-1] + "y")
    if stem in WORDS:                                        # bringeth -> bring
        cands.append(stem)
    if stem + "e" in WORDS:                                  # endureth -> endure
        cands.append(stem + "e")
    if len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in WORDS:
        cands.append(stem[:-1])                              # doubled consonant
    cands = list(dict.fromkeys(cands))
    if not cands:
        return None, "no dictionary stem"
    if len(cands) == 1:
        return cands[0], "ok"
    # Disambiguate by standalone corpus frequency (know:1200 vs knowe:0).
    scored = sorted(cands, key=lambda c: freq.get(c, 0), reverse=True)
    top, runner = scored[0], scored[1]
    if freq.get(top, 0) > 0 and freq.get(runner, 0) == 0:
        return top, f"ok (corpus {top}:{freq.get(top,0)} vs {runner}:0)"
    return scored[0], f"AMBIGUOUS {[(c, freq.get(c,0)) for c in scored]}"


def main() -> None:
    books = json.loads((HERE / "source" / "DRC.json").read_text("utf-8"))["books"]
    eth: Counter[str] = Counter()
    est: Counter[str] = Counter()
    freq: Counter[str] = Counter()        # all lowercase tokens
    caps: Counter[str] = Counter()        # capitalized mid-sentence
    total: Counter[str] = Counter()
    for book in books:
        for ch in book["chapters"]:
            for vv in ch["verses"]:
                text = vv["text"]
                for m in _WORD.finditer(text):
                    w = m.group(0)
                    lw = w.lower()
                    freq[lw] += 1
                    total[lw] += 1
                    # mid-sentence capital = proper-noun signal
                    if w[0].isupper():
                        prior = text[: m.start()].rstrip()
                        if prior and prior[-1] not in ".?!:;":
                            caps[lw] += 1
                    if lw in STOP or len(lw) < 5:
                        continue
                    if lw.endswith("eth"):
                        eth[lw] += 1
                    elif lw.endswith("est") and not _SUPERLATIVE_HINT.search(lw):
                        est[lw] += 1

    def proper_noun(tok: str) -> bool:
        return total[tok] > 0 and caps[tok] / total[tok] >= 0.8

    for name, counter, suffix, render, irregular in (
        ("lexicon_eth.proposed.tsv", eth, "eth", modern_3sg, IRREGULAR_ETH),
        ("lexicon_est.proposed.tsv", est, "est", lambda l: l, IRREGULAR_EST),
    ):
        lines, unresolved, skipped = [], 0, 0
        for tok, n in counter.most_common():
            if tok in irregular:
                lines.append(f"{tok}\t{irregular[tok]}\t{n}\tirregular")
                continue
            if proper_noun(tok):
                skipped += 1
                continue
            lemma, note = derive_lemma(tok, suffix, freq)
            modern = render(lemma) if lemma else "?"
            if modern == "?" or note.startswith("AMBIGUOUS"):
                unresolved += 1
            lines.append(f"{tok}\t{modern}\t{n}\t{note}")
        (HERE / name).write_text("\n".join(lines) + "\n", "utf-8")
        print(f"{name}: {len(lines)} types "
              f"({sum(counter.values())} tokens), {unresolved} need review, "
              f"{skipped} proper-noun skips")


if __name__ == "__main__":
    main()
