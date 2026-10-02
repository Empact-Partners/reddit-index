"""The score's arithmetic, with no dependencies.

The published number is `round(100 * Q_0.10(Beta(pos + a0, neg + b0)))` with a
leave-one-out pooled prior. These functions are the ones in worker/score.py
(which pulls in numpy for its bootstrap) and lib/data/page-score.ts, lifted out
so a container without numpy and a recompute script can both use them. The
three must agree to the integer: `python3 worker/numerics.py --selftest` runs
the fixtures the site's own test uses (tests/fixtures-page-score.json).
"""
from __future__ import annotations

import math

PRIOR_K = 10            # pseudo-observations the prior contributes, total
PRIOR_P0_SMOOTH = 10    # Beta(5,5)-style smoothing inside p0 itself
PRIOR_POOL_MIN = 30     # below this leave-one-out pool the prior leans on the smoothing
SCORE_QUANTILE = 0.10   # the published score is this posterior quantile


def fit_prior_pooled(others):
    """others: [(pos, n_op)] for every OTHER brand in the category (leave-one-out by mention mass)."""
    op = sum(p for p, n in others)
    on = sum(n for p, n in others)
    p0 = (op + PRIOR_P0_SMOOTH / 2) / (on + PRIOR_P0_SMOOTH)
    return PRIOR_K * p0, PRIOR_K * (1 - p0), on < PRIOR_POOL_MIN


def _betacf(a, b, x, itmax=200, eps=3e-14):
    """Continued fraction for the incomplete beta (Numerical Recipes §6.4)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Regularised incomplete beta I_x(a,b) — the Beta CDF."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1.0 - x) / b


def beta_quantile(a, b, q):
    """Inverse Beta CDF by bisection. No scipy on this box, and the score
    must be reproducible, so this is deterministic rather than sampled."""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def page_score(pos, neg, alpha0, beta0):
    """The integer the site shows. Rounds half up, as JavaScript's Math.round does
    (Python's round() goes to the even neighbour on an exact half)."""
    return int(math.floor(100 * beta_quantile(pos + alpha0, neg + beta0, SCORE_QUANTILE) + 0.5))


if __name__ == "__main__":
    import json
    import os
    import sys
    if "--selftest" in sys.argv:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "tests", "fixtures-page-score.json")
        bad = 0
        cases = json.load(open(path))
        for c in cases:
            a0, b0, fb = fit_prior_pooled([tuple(x) for x in c["others"]])
            got = page_score(c["pos"], c["neg"], a0, b0)
            ok = (got == c["score"] and abs(a0 - c["alpha0"]) < 1e-9 and abs(b0 - c["beta0"]) < 1e-9
                  and fb == c["fallback"])
            bad += not ok
            if not ok:
                print("MISMATCH", c, "got", got, a0, b0, fb)
        print(f"numerics selftest: {len(cases) - bad}/{len(cases)} fixtures match")
        sys.exit(1 if bad else 0)
