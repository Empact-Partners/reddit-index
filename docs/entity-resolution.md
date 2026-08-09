# Entity resolution — how a word becomes a brand mention

Rules only. No classifier, no embedding, no guessing: a surface form either
clears its evidence bar or the mention does not exist. The recall loss is
real, per-brand, and published — a floor is honest, a guess is not.

## The mechanics

- **Aho-Corasick over every surface form** (brand names, aliases, domains),
  with hard word boundaries: `stripe` never matches inside `pinstripe`.
  URLs are matched before prose; code blocks and quoted (`>`) text are
  stripped first.
- **Every surface form is its own row** with its own class — `monday.com`
  and bare `monday` are the same brand and nothing like the same evidence.

## The three classes (per surface form)

| Class | Bar | Example |
|---|---|---|
| SAFE | accept on a word-boundary match | `QuickBooks`, any domain |
| AMBIGUOUS | accept with ≥1 corroborating signal | `Notion` |
| HOSTILE | accept with ≥2 corroborating signals AND no stop-context hit | `Square` |

Corroborating signals: another brand from the same category in the text, a
category noun nearby, the brand's domain in the thread, the subreddit being
one of the brand's category's scoring subs.

- **Qualified forms are always SAFE**: `Close CRM` and `close.com` are
  unambiguous even though bare `close` never matches at all.
- **Bare-disabled**: tokens so common no stop-context list reaches the
  precision bar (`close`, `make`, `front`, `square`, `remote`, …) are never
  matchable bare. Those brands resolve only through qualified forms — their
  mention counts run structurally low, never wrong.
- **Stop-contexts** hard-reject the ordinary sense: "cyber monday",
  "pick up the slack", "linear regression", "wasabi peas".

## Where the gazetteer comes from

The original 145 brands are hand-curated. Expansion brands are drafted by a
model fleet, adversarially reviewed by a second model, and then pass
deterministic gates that do the actual trust work:

1. dedupe against existing brands (slug or domain collision merges, never duplicates)
2. an alias that is an English dictionary word is forced AMBIGUOUS or bare-disabled
3. an alias claimed by two brands loses its bare form for both
4. domains must resolve in DNS (a wrong domain would be auto-accept poison)
5. stop-contexts must contain the token they guard
6. every category needs ≥4 surviving brands (the prior needs peers)

Rejects are journaled, never silently dropped. Generator:
`data/enumerate_brands.py`; output: `data/brand-seed-new.csv` →
`data/gen_brands.py` → `data/brands.csv` + `data/brand-aliases.csv`.

## Known limits

- Precision is designed-for, not yet human-audited (see
  [methodology-review.md](methodology-review.md)).
- Vendor-run subreddits (r/shopify and kin) are excluded from scoring at the
  database level — a trigger rejects the insert, so the exclusion is
  structural, not a filter that can silently regress.
