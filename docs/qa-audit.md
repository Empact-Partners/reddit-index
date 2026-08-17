# Reddit Index — data QA audit

Generated 2026-08-16 22:32 against the live corpus.

Corpus: 373,538 mentions · 331,400 labelled · 187,303 threads · 4,000 score rows.

## 1. Consistency invariants

- PASS — every score has labelled mentions behind it
- PASS — n_op equals pos + neg
- PASS — scored n never exceeds collected mentions
- PASS — ranks are contiguous 1..k per category
- PASS — no orphan sentiment rows
- PASS — one label per (mention, brand)

**All invariants pass.**

