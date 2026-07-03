#!/usr/bin/env python3
"""Deterministic Early-Modern-English -> contemporary-English modernizer.

The Challoner Douay-Rheims (1749-52) is written in the same archaic register
as the KJV: thou/thee/thy, -est / -eth verb inflections, hath/doth/saith,
etc. This module modernizes that register with a CURATED, fully
deterministic rule set -- the Douay-Rheims analogue of the "de-thee" pass
that produced the Modern Brenton Septuagint. (Modern Brenton could stay
small because Adam Boyd's Updated Brenton had already modernized the verb
morphology; no such pre-modernized Douay-Rheims exists, so the -eth/-est
inflections are handled here via vendored lexicons generated from the
corpus by gen_lexicon.py and hand-curated by curate_lexicon.py.)

Design rules (never trade fidelity for coverage):
  * Only transform tokens on an explicit map or in a curated lexicon. An
    unknown "-eth"/"-est" word is left ALONE rather than risk mangling
    "beneath", "Nazareth", "harvest", "greatest".
  * -est is ambiguous (2sg verb vs superlative), so lexicon -est hits apply
    only in verses that address someone as thou/thee/thy AND when the token
    isn't preceded by an article/degree word (the/thy/a/an/most/more/O).
  * Preserve capitalization pattern and surrounding punctuation.
  * Pure word-level substitution; no reordering or paraphrase.

`residual_archaisms(text)` reports archaic tokens the pass could not safely
modernize, so the build surfaces (not silently keeps) them.
"""
from __future__ import annotations

import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_lexicon(name: str) -> dict[str, str]:
    out = {}
    for line in (_HERE / name).read_text("utf-8").splitlines():
        tok, modern, _count, _note = line.split("\t")
        out[tok] = modern
    return out


# Curated corpus lexicons: walketh->walks / walkest->walk (see gen_lexicon.py).
_ETH = _load_lexicon("lexicon_eth.tsv")
_EST = _load_lexicon("lexicon_est.tsv")

# ---------------------------------------------------------------------------
# Whole-word swaps (case-insensitive match, case pattern preserved)
# ---------------------------------------------------------------------------
_PRONOUNS = {
    "thou": "you", "thee": "you", "thy": "your", "ye": "you",
    "thyself": "yourself",
}

_VERBS = {
    "art": "are", "wast": "were", "wert": "were",
    "hast": "have", "hath": "has", "hadst": "had",
    "dost": "do", "doth": "does", "didst": "did",
    "shalt": "shall", "wilt": "will", "wouldst": "would",
    "shouldst": "should", "couldst": "could", "canst": "can",
    "mayst": "may", "mightst": "might",
    "saith": "says", "sayst": "say", "saidst": "said",
    "spake": "spoke", "sware": "swore",
    "shew": "show", "shewed": "showed", "shewn": "shown",
    "shews": "shows",
}

_OTHER = {
    "unto": "to",
    "hearken": "listen", "hearkened": "listened", "hearkens": "listens",
    "peradventure": "perhaps",
    "whither": "where", "thither": "there", "hither": "here",
    "howbeit": "however", "verily": "truly",
}

_LEXICAL = {**_PRONOUNS, **_VERBS, **_OTHER}

# Archaic tokens intentionally left to residual reporting rather than
# guessing a modern form.
_KNOWN_ARCHAIC = {"thine", "mine", "wherefore", "wot", "wist"}

# Words that block an -est verb reading of the FOLLOWING token
# ("the greatest", "their meanest", "most holiest", "O purest").
_EST_BLOCKERS = {"the", "thy", "a", "an", "most", "more", "o",
                 "their", "his", "her", "our", "your", "its", "whose"}

_THOU = re.compile(r"\b(thou|thee|thy|thyself)\b", re.IGNORECASE)
# Vocative address licenses 2sg for the verse even without a thou-form:
# "O God, who avengest me, and subduest the people..." (PSA 17:48).
_WHO_VOCATIVE = re.compile(r"\b[Ww]ho\s+[A-Za-z]{4,}est\b")
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _match_case(src: str, out: str) -> str:
    if src.isupper():
        return out.upper()
    if src[:1].isupper():
        return out[:1].upper() + out[1:]
    return out


def _swap_thine_mine(text: str) -> str:
    """`thine`/`mine` -> `your`/`my` before a vowel-word, else `yours`/`mine`.

    "thine eyes" -> "your eyes"; "it is thine" -> "it is yours".
    ("mine" as the possessive pronoun 'belonging to me' stays "mine".)
    """
    def repl(m: re.Match) -> str:
        word = m.group("w")
        nxt = m.group("nxt") or ""
        base = "your" if word.lower() == "thine" else "my"
        standalone = "yours" if word.lower() == "thine" else "mine"
        if nxt and re.match(r"[AaEeIiOoUuHh]", nxt):
            return _match_case(word, base) + m.group("gap") + nxt
        return _match_case(word, standalone) + m.group("gap") + nxt

    pat = re.compile(r"\b(?P<w>[Tt]hine|[Mm]ine)\b(?P<gap>\s*)(?P<nxt>[A-Za-z]*)")
    return pat.sub(repl, text)


def modernize(text: str) -> str:
    # 2sg (-est) readings are licensed by a thou-form in the verse (detected
    # BEFORE the pronoun swap erases them) or by a who-vocative whose "who"
    # heads an -est verb in the curated lexicon.
    m = _WHO_VOCATIVE.search(text)
    has_thou = bool(_THOU.search(text)) or bool(
        m and m.group(0).split()[-1].lower() in _EST)
    text = _swap_thine_mine(text)

    def repl(m: re.Match) -> str:
        w = m.group(0)
        lw = w.lower()
        out = _LEXICAL.get(lw) or _ETH.get(lw)
        if out is None and has_thou and lw in _EST:
            prior = _WORD_RE.findall(text[: m.start()])
            if not prior or prior[-1].lower() not in _EST_BLOCKERS:
                out = _EST[lw]
        return _match_case(w, out) if out else w

    return _WORD_RE.sub(repl, text)


_ARCHAIC_SUFFIX = re.compile(r"^[A-Za-z]{4,}(est|eth)$")


def residual_archaisms(text: str) -> list[str]:
    """Archaic tokens left unmodernized (for build-time reporting)."""
    out = []
    for m in _WORD_RE.finditer(text):
        w = m.group(0)
        lw = w.lower()
        if lw in _KNOWN_ARCHAIC:
            out.append(w)
        elif _ARCHAIC_SUFFIX.match(lw) and lw in (_ETH.keys() | _EST.keys()):
            out.append(w)   # lexicon hit that survived (blocked -est, etc.)
    return out


# ---------------------------------------------------------------------------
# Self-test: run `python modernize.py` to verify the rule set.
# ---------------------------------------------------------------------------
_CASES = [
    ("The Lord ruleth me: and I shall want nothing.",
     "The Lord rules me: and I shall want nothing."),
    ("Thou shalt not kill.", "You shall not kill."),
    ("Thy kingdom come. Thy will be done.", "Your kingdom come. Your will be done."),
    ("thine eyes", "your eyes"),
    ("it is thine", "it is yours"),
    ("What hast thou done?", "What have you done?"),
    ("He hath spoken; he doth know.", "He has spoken; he does know."),
    ("Thou art my son.", "You are my son."),
    ("Whither goest thou?", "Where go you?"),
    ("He that believeth in me liveth for ever.",
     "He that believes in me lives for ever."),
    ("Thou knowest that I love thee.", "You know that I love you."),
    ("Come unto me and hearken to my words.",
     "Come to me and listen to my words."),
    ("Shew me thy face; he sheweth mercy.", "Show me your face; he shows mercy."),
    # -est guards: superlative / no-thou verses must NOT convert.
    ("Thou art the greatest and the meanest of men.",
     "You are the greatest and the meanest of men."),
    ("The finest gold of the land.", "The finest gold of the land."),
    ("He dwellest not here.", "He dwellest not here."),  # no thou: left alone
    # Untouchables.
    ("Jesus went to Nazareth beneath the west gate against them.",
     "Jesus went to Nazareth beneath the west gate against them."),
    ("Elizabeth said the best.", "Elizabeth said the best."),
    ("Aleph. Beth. Gimel. Daleth.", "Aleph. Beth. Gimel. Daleth."),
]


def _selftest() -> int:
    bad = 0
    for src, want in _CASES:
        got = modernize(src)
        if got != want:
            bad += 1
            print(f"FAIL\n  in:   {src}\n  want: {want}\n  got:  {got}")
    print(f"{len(_CASES) - bad}/{len(_CASES)} cases pass")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
