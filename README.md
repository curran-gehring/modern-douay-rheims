# Modern Douay-Rheims

A contemporary-English revision of the Challoner Douay-Rheims Bible
(1749–52), produced by fully deterministic substitution — the
Douay-Rheims counterpart of
[modern-brenton-septuagint](https://github.com/curran-gehring/modern-brenton-septuagint).
Ships together with the Clementine Vulgate on an identical verse grid, so
the English and its Latin source pair 1:1 by coordinate.

## Outputs

| file | contents |
|---|---|
| `modern_douay_rheims_verses.tsv` | Challoner DR → modernized English, `BOOK ch:v<TAB>text` |
| `vulgata_clementina_verses.tsv` | Clementine Vulgate (Latin), same keys |

35,809 verses each (full canon incl. deuterocanon; consumers keep what
they have book ids for). Versification is the Vulgate's native grid —
Psalms follow the Gallican/LXX numbering (Ps 22 = Hebrew Ps 23).

## Pipeline

```
source/DRC.json  source/VulgClementine.json     (vendored scrollmapper texts)
        │                │
   reconcile.py          │     14 curated boundary fixes conform the DR grid
        │                │     to the Vulgate grid (5 merges, 6 splits,
        │                │     3 supplied omissions) — verified against the
        │                │     CATSS Clementine text as an independent witness
        ▼                ▼
   modernize.py    build_tsv.py    key-parity gate: both TSVs must carry
        │                          IDENTICAL keys or the build fails
        ▼
   lexicon_eth.tsv / lexicon_est.tsv    curated verb-morphology lexicons
```

The modernization is conservative and word-level only — no paraphrase, no
reordering. Pronouns (thou/thee/thy/thine → you/your/yours), auxiliaries
(hath/dost/shalt → has/do/shall), verb inflections via corpus-generated,
hand-curated lexicons (walketh → walks; walkest → walk, licensed only in
verses that address someone as thou or by who-vocative, and blocked after
articles/possessives so superlatives like "the greatest" survive), plus
unto → to, shew → show, hearken → listen. Everything the pass cannot
transform safely is left alone and reported.

Regenerate:

```bash
python3 build_tsv.py            # rebuild both TSVs (self-validating)
python3 modernize.py            # rule-set self-test
python3 gen_lexicon.py          # regenerate lexicon PROPOSALS (dev only)
python3 curate_lexicon.py       # apply hand-curation -> shipped lexicons
```

## Sources & license

Source texts are the [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases)
transcriptions of the Challoner Douay-Rheims and the Clementine Vulgate —
both public domain. The tooling and the modernized text in this
repository are dedicated to the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
