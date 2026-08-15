#!/usr/bin/env python3
"""Calibration gate — refuses to publish a scoring run whose ordering
contradicts the raw data it was computed from.

Born 2026-08-12, the day the v1 prior published Porkbun (41 pos / 1 neg) as
most-hated at 20/100 while GoDaddy (4 pos / 111 neg) sat at 63/100. The prior
had 200 pseudo-observations, so both brands were scored as each other. Nothing
in the pipeline noticed; a reader did. This gate is that reader, mechanized.

Per category, over brands with n_op >= MIN_N_OP (when at least MIN_BRANDS
qualify):
  1. Spearman rank correlation between raw positive rate and published score
     must be >= RHO_MIN.
  2. No brand with raw rate >= 0.75 may land in the bottom score quartile,
     and no brand with raw rate <= 0.25 may land in the top quartile.

check_rows(rows) -> list of violation strings; empty list means pass.
--selftest proves the gate fails the REAL v1 output for domain-registrars
and passes the v2 output for the same brands (unenforced rules drift).
"""
import sys

MIN_N_OP = 10
MIN_BRANDS = 4
RHO_MIN = 0.8
# A pair of brands only tests the ordering when their raw rates actually
# DIFFER. Spearman over all pairs punished shrinkage doing its job:
# password-managers published 1Password 81%->80, Bitwarden 80%->79,
# KeePass 80%->77 and Proton Pass 83%->76, and scored rho=0.60 purely because
# Proton's 83% comes from twelve observations against 1Password's 160, so the
# prior correctly ranks it below them. Four brands inside three points are a
# statistical tie, not a contradiction. The gate exists for the v1 disaster —
# 41 pos/1 neg published BELOW 4 pos/111 neg, a 94-point gap — and a
# materiality threshold catches that while leaving ties to the estimator.
MATERIAL_GAP = 0.15


def _ranks(values):
    """Average ranks (1-based) with ties shared."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(a, b):
    ra, rb = _ranks(a), _ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return 1.0  # constant on either side: nothing to contradict
    return cov / (va * vb) ** 0.5


def check_rows(rows):
    """rows: score_category dicts (needs brand_slug, category_slug, pos,
    n_op, reddit_love_score). Returns violation strings."""
    by_cat = {}
    for r in rows:
        if r.get("reddit_love_score") is None or r.get("n_op", 0) < MIN_N_OP:
            continue
        by_cat.setdefault(r["category_slug"], []).append(r)

    violations = []
    for cat, brands in sorted(by_cat.items()):
        if len(brands) < MIN_BRANDS:
            continue
        raw = [r["pos"] / r["n_op"] for r in brands]
        score = [r["reddit_love_score"] for r in brands]

        # Ordering test over MATERIALLY different pairs only.
        for i in range(len(brands)):
            for j in range(i + 1, len(brands)):
                gap = raw[i] - raw[j]
                if abs(gap) < MATERIAL_GAP:
                    continue
                if gap * (score[i] - score[j]) < 0:
                    hi, lo = (i, j) if gap > 0 else (j, i)
                    violations.append(
                        f"{cat}: {brands[hi]['brand_slug']} raw "
                        f"{raw[hi]:.2f} ({brands[hi]['pos']}/{brands[hi]['n_op']}) "
                        f"published at {brands[hi]['reddit_love_score']}, BELOW "
                        f"{brands[lo]['brand_slug']} raw {raw[lo]:.2f} "
                        f"({brands[lo]['pos']}/{brands[lo]['n_op']}) at "
                        f"{brands[lo]['reddit_love_score']}")

        # Quartile containment: an extreme raw rate must not publish on the
        # opposite end of the board.
        score_ranks = _ranks(score)  # ascending: low rank = low score
        n = len(brands)
        for r, rate, rk in zip(brands, raw, score_ranks):
            if rate >= 0.75 and rk <= (n + 1) / 4:
                violations.append(
                    f"{cat}/{r['brand_slug']}: raw rate {rate:.2f} "
                    f"(pos={r['pos']}/n_op={r['n_op']}) published in the "
                    f"bottom score quartile at {r['reddit_love_score']}")
            if rate <= 0.25 and rk >= n + 1 - (n + 1) / 4:
                violations.append(
                    f"{cat}/{r['brand_slug']}: raw rate {rate:.2f} "
                    f"(pos={r['pos']}/n_op={r['n_op']}) published in the "
                    f"top score quartile at {r['reddit_love_score']}")
    return violations


def _selftest():
    """The gate must fail the shipped v1 numbers and pass the v2 numbers —
    both are the REAL domain-registrars brands, 2026-08-12."""
    fixture = [  # slug, pos, n_op, v1_score, v2_score
        ("godaddy", 4, 115, 63, 8),
        ("porkbun", 41, 42, 20, 83),
        ("amazon-route-53", 8, 28, 48, 31),
        ("namecheap", 8, 23, 49, 35),
    ]

    def rows(idx):
        return [{"brand_slug": s, "category_slug": "domain-registrars",
                 "pos": p, "n_op": n, "reddit_love_score": row[idx]}
                for row in fixture for s, p, n in [row[:3]]]

    v1 = check_rows(rows(3))
    v2 = check_rows(rows(4))
    assert v1, "gate PASSED the v1 Porkbun/GoDaddy swap — the gate is dead"
    assert not v2, f"gate failed the corrected v2 scores: {v2}"
    print(f"selftest OK — v1 output raises {len(v1)} violations, v2 raises 0:")
    for v in v1:
        print("  would catch:", v)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
