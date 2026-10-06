
## Applied (2026-10-06, during the day between the gate nights; nothing loaded)

The decisive fact, read from `data/gen_brands.py`: a multi-word or dotted form is SAFE on sight (accepted on a word
boundary with no corroboration), so an ordinary-English multi-word name is worse than an ordinary single word (which
is HOSTILE: two corroborating signals and no stop context). The generator now honours `bare_disabled_forms` for
qualified forms too (one line), and every such name is listed there; the brand still matches by its domain and its
distinctive forms. The row-by-row changes are in `data/phase-b/brand-review-log.csv` (30), the reviewed rows in
`data/phase-b/brand-seed-rows.reviewed.csv` (178: Overture dropped).
