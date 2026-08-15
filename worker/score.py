#!/usr/bin/env python3
"""Compute the Reddit Love Score from scored mentions.

This is the method, in code. Every number a reader can check on the site is
computed here, and every constant comes from methodology_params.

  N_op = pos + neg
  p_tilde = (x_pos + alpha_0) / (N_op + alpha_0 + beta_0)
  Reddit Love Score = round(100 * p_tilde)

Usage:
    python3 worker/score.py --scored worker/.cache/corpus/crm.scored.json
    python3 worker/score.py --all
"""
import argparse, json, math, os, sys, time
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# ── frozen constants from the methodology ───────────────────────────────────
# These match what freeze_methodology.py wrote to methodology_params.

LABEL = {"neu": 0, "pos": 1, "neg": 2, "abstain": 3}
# v2 prior (methodology 2.0.0): shrink toward the category's pooled opinionated
# positive rate, leave-one-out by MENTION mass, at a fixed small strength. v1's
# brand-rate method-of-moments fit collapsed to a 200-pseudo-observation prior
# whenever fewer than 4 brands cleared n_op>=30 — in a 2-big-brand category each
# brand was scored against the OTHER brand's rate at 5x its own evidence, which
# is how Porkbun (41 pos / 1 neg) published 20 while GoDaddy (4 pos / 111 neg)
# published 63.
PRIOR_K = 10            # pseudo-observations the prior contributes, total
PRIOR_P0_SMOOTH = 10    # Beta(5,5)-style smoothing inside p0 itself
PRIOR_POOL_MIN = 30     # below this LOO pool, the row is flagged prior_fallback
BOOTSTRAP_B = 1999
CI_LEVEL = 0.90
ICC_FLOOR = 0.10
SCORING_WINDOW_MONTHS = 12

TIERS = {
    "deep": {"pp": 4, "n_min": 600},
    "standard": {"pp": 5, "n_min": 400},
    "thin": {"pp": 7, "n_min": 200},
}
DIVERSITY_FLOORS = {
    "authors": 50,
    "subreddits": 5,
    "thread_share": 0.20,
    "author_share": 0.05,
}


def load_categories():
    import csv
    return {r["slug"]: r for r in csv.DictReader(open(os.path.join(REPO, "data", "categories.csv")))}


# ── the leave-one-out prior ─────────────────────────────────────────────────

def fit_prior_pooled(brand_counts, exclude_slug):
    """The v2 prior: the category's pooled positive rate, excluding the brand.

    p0   = (pooled_pos + S/2) / (pooled_op + S)   with S = PRIOR_P0_SMOOTH,
    prior = Beta(K*p0, K*(1-p0))                   with K = PRIOR_K.

    Leave-one-out is by mention mass, not by brand: every other brand's
    opinionated mentions vote in proportion to how many there are, so a
    category with one big brand and ten small ones gets a prior all eleven
    actually support. K is fixed and small — 10 pseudo-observations — so a
    brand with 40 real opinions is ~80% its own data, never 17%.

    brand_counts: [(slug, pos, n_op)] over every brand in the category.
    Returns (alpha0, beta0, fallback) — fallback marks a LOO pool under
    PRIOR_POOL_MIN, where p0 leans mostly on the 0.5-centered smoothing.
    """
    op = sum(p for slug, p, n in brand_counts if slug != exclude_slug)
    on = sum(n for slug, p, n in brand_counts if slug != exclude_slug)
    p0 = (op + PRIOR_P0_SMOOTH / 2) / (on + PRIOR_P0_SMOOTH)
    return PRIOR_K * p0, PRIOR_K * (1 - p0), on < PRIOR_POOL_MIN


# ── ICC and DEFF ────────────────────────────────────────────────────────────

def compute_icc(y, cluster_ids):
    """One-way random-effects ICC from a binary outcome.

    DEFF = 1 + (m_tilde - 1) * ICC
    where m_tilde = sum(n_j^2)/N — Kish's size-weighted mean.
    """
    clusters = defaultdict(list)
    for yi, ci in zip(y, cluster_ids):
        clusters[ci].append(yi)

    k = len(clusters)
    if k < 5:
        return ICC_FLOOR, False

    N = len(y)
    y_bar = np.mean(y)

    # Between-cluster mean square
    MSB = sum(len(c) * (np.mean(c) - y_bar) ** 2 for c in clusters.values()) / (k - 1)

    # Within-cluster mean square (binary simplification)
    MSW_num = sum(len(c) * np.mean(c) * (1 - np.mean(c)) for c in clusters.values())
    MSW = MSW_num / (N - k) if N > k else 1e-9

    # Unequal cluster size correction
    n_sizes = np.array([len(c) for c in clusters.values()])
    n0 = (N - np.sum(n_sizes ** 2) / N) / (k - 1)

    denom = MSB + (n0 - 1) * MSW
    if denom <= 0:
        return ICC_FLOOR, False

    icc = (MSB - MSW) / denom
    return max(0.0, min(1.0, icc)), True


def compute_deff(n_sizes, icc):
    """Kish's DEFF with the size-weighted mean cluster size."""
    N = sum(n_sizes)
    if N == 0:
        return 1.0
    m_tilde = sum(n ** 2 for n in n_sizes) / N
    return 1 + (m_tilde - 1) * icc


# ── cluster bootstrap ──────────────────────────────────────────────────────

def bootstrap_ci(y, cluster_ids, alpha0, beta0, B=BOOTSTRAP_B, level=CI_LEVEL):
    """Resample whole clusters; the prior is held fixed.

    Under the v2 pooled prior that is correct, not a shortcut: the prior is
    computed from every OTHER brand's mentions, and resampling this brand's
    threads does not move it.
    """
    clusters = defaultdict(list)
    for yi, ci in zip(y, cluster_ids):
        clusters[ci].append(yi)
    cluster_list = list(clusters.values())
    k = len(cluster_list)
    if k < 3:
        return None, None

    rng = np.random.default_rng(seed=42)
    scores = np.empty(B)

    for b in range(B):
        idx = rng.integers(0, k, size=k)
        y_star = np.concatenate([cluster_list[i] for i in idx])
        x_pos = y_star.sum()
        n_op = len(y_star)
        if n_op < 2:
            scores[b] = 0.5
            continue
        scores[b] = (x_pos + alpha0) / (n_op + alpha0 + beta0)

    alpha_half = (1 - level) / 2
    lo = np.percentile(scores, alpha_half * 100)
    hi = np.percentile(scores, (1 - alpha_half) * 100)
    return round(lo, 4), round(hi, 4)


# ── the scoring pipeline ───────────────────────────────────────────────────

def score_category(cat_slug, mentions, categories):
    """Score every brand in one category. Returns list of score dicts."""
    cat = categories.get(cat_slug, {})
    tier = cat.get("threshold_tier", "thin")
    n_min = TIERS.get(tier, TIERS["thin"])["n_min"]
    precision_pp = TIERS.get(tier, TIERS["thin"])["pp"]

    # Group mentions by brand
    by_brand = defaultdict(list)
    for m in mentions:
        by_brand[m["brand_slug"]].append(m)

    # Per-brand opinionated counts for the pooled prior — every brand votes
    # with its mention mass, no minimum.
    brand_counts = []
    for slug, ms in by_brand.items():
        p = sum(1 for m in ms if m.get("label") == "pos")
        g = sum(1 for m in ms if m.get("label") == "neg")
        brand_counts.append((slug, p, p + g))

    now = time.strftime("%Y-%m-%d")
    window_start = f"{int(now[:4]) - 1}{now[4:]}"  # trailing 12 months

    results = []
    for slug, ms in by_brand.items():
        pos = sum(1 for m in ms if m.get("label") == "pos")
        neg = sum(1 for m in ms if m.get("label") == "neg")
        neu = sum(1 for m in ms if m.get("label") == "neu")
        abstain = sum(1 for m in ms if m.get("label") == "abstain")
        n = len(ms)
        n_op = pos + neg

        # Diversity
        authors = set(m.get("author") for m in ms if m.get("author"))
        subreddits = set(m.get("subreddit") for m in ms if m.get("subreddit"))
        threads = set(m.get("thread_id") for m in ms if m.get("thread_id"))
        thread_counts = defaultdict(int)
        author_counts = defaultdict(int)
        for m in ms:
            if m.get("thread_id"):
                thread_counts[m["thread_id"]] += 1
            if m.get("author"):
                author_counts[m["author"]] += 1
        max_thread_share = max(thread_counts.values(), default=0) / max(n, 1)
        max_author_share = max(author_counts.values(), default=0) / max(n, 1)

        # ICC and DEFF — computed twice, carry the larger
        opinionated = [(1 if m["label"] == "pos" else 0) for m in ms if m.get("label") in ("pos", "neg")]
        thread_ids = [m.get("thread_id", "?") for m in ms if m.get("label") in ("pos", "neg")]
        author_ids = [m.get("author", "?") for m in ms if m.get("label") in ("pos", "neg")]

        icc_t, icc_t_ok = compute_icc(opinionated, thread_ids) if len(opinionated) >= 5 else (ICC_FLOOR, False)
        icc_a, icc_a_ok = compute_icc(opinionated, author_ids) if len(opinionated) >= 5 else (ICC_FLOOR, False)

        thread_sizes = list(defaultdict(int, {t: thread_ids.count(t) for t in set(thread_ids)}).values())
        author_sizes = list(defaultdict(int, {a: author_ids.count(a) for a in set(author_ids)}).values())

        deff_t = compute_deff(thread_sizes, icc_t)
        deff_a = compute_deff(author_sizes, icc_a)
        deff = max(deff_t, deff_a)
        n_eff = n_op / deff if deff > 0 else n_op

        # Eligibility
        failed_test, failed_observed, failed_required = None, None, None
        eligible = True

        if n_eff < n_min:
            eligible = False
            failed_test = "n_eff"
            failed_observed = f"{n_eff:.0f}"
            failed_required = str(n_min)
        elif len(authors) < DIVERSITY_FLOORS["authors"]:
            eligible = False
            failed_test = "authors"
            failed_observed = str(len(authors))
            failed_required = str(DIVERSITY_FLOORS["authors"])
        elif len(subreddits) < DIVERSITY_FLOORS["subreddits"]:
            eligible = False
            failed_test = "subreddits"
            failed_observed = str(len(subreddits))
            failed_required = str(DIVERSITY_FLOORS["subreddits"])
        elif max_thread_share > DIVERSITY_FLOORS["thread_share"]:
            eligible = False
            failed_test = "thread_share"
            failed_observed = f"{max_thread_share:.1%}"
            failed_required = f"{DIVERSITY_FLOORS['thread_share']:.0%}"
        elif max_author_share > DIVERSITY_FLOORS["author_share"]:
            eligible = False
            failed_test = "author_share"
            failed_observed = f"{max_author_share:.1%}"
            failed_required = f"{DIVERSITY_FLOORS['author_share']:.0%}"

        # The score
        alpha0, beta0, prior_fallback = fit_prior_pooled(brand_counts, slug)
        if n_op > 0:
            p_tilde = (pos + alpha0) / (n_op + alpha0 + beta0)
            score = round(100 * p_tilde)
            polarization = 2 * min(pos, neg) / n_op if n_op > 0 else None
        else:
            p_tilde = None
            score = None
            polarization = None

        # Bootstrap CI
        ci_low, ci_high = None, None
        if eligible and n_op >= 10 and opinionated:
            ci_low, ci_high = bootstrap_ci(opinionated, thread_ids, alpha0, beta0)

        results.append({
            "brand_slug": slug,
            "category_slug": cat_slug,
            "pos": pos, "neg": neg, "neu": neu, "abstain": abstain,
            "n": n, "n_op": n_op, "n_eff": round(n_eff, 1),
            "deff": round(deff, 3), "deff_thread": round(deff_t, 3), "deff_author": round(deff_a, 3),
            "icc_thread": round(icc_t, 4), "icc_author": round(icc_a, 4),
            "icc_estimated": icc_t_ok and icc_a_ok,
            "alpha0": round(alpha0, 3), "beta0": round(beta0, 3),
            "reddit_love_score": score,
            "polarization": round(polarization, 4) if polarization is not None else None,
            "neutral_share": round(neu / n, 4) if n > 0 else 0,
            "abstain_share": round(abstain / n, 4) if n > 0 else 0,
            "ci_low": ci_low, "ci_high": ci_high,
            "n_authors": len(authors), "n_subreddits": len(subreddits), "n_threads": len(threads),
            "max_thread_share": round(max_thread_share, 4),
            "max_author_share": round(max_author_share, 4),
            "eligible": eligible,
            "failed_test": failed_test,
            "failed_observed": failed_observed,
            "failed_required": failed_required,
            "window_start": window_start,
            "window_end": now,
            "methodology_version": "2.1.0",
        })

    # Rank by score descending
    ranked = sorted([r for r in results if r["eligible"] and r["reddit_love_score"] is not None],
                    key=lambda x: -x["reddit_love_score"])
    for i, r in enumerate(ranked, 1):
        r["rank_desc"] = i
        r["rank_asc"] = len(ranked) - i + 1

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", help="path to a .scored.json file")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    categories = load_categories()
    corpus_dir = os.path.join(HERE, ".cache", "corpus")

    if args.scored:
        files = [args.scored]
    elif args.all:
        files = sorted(os.path.join(corpus_dir, f)
                       for f in os.listdir(corpus_dir)
                       if f.endswith(".scored.json"))
    else:
        ap.error("pass --scored PATH or --all")

    all_results = []
    for f in files:
        data = json.load(open(f))
        cat = data["category_slug"]
        mentions = data["mentions"]
        print(f"  {cat}: {len(mentions)} mentions", end="", flush=True)
        results = score_category(cat, mentions, categories)
        eligible = [r for r in results if r["eligible"]]
        print(f" -> {len(results)} brands, {len(eligible)} eligible")
        all_results.extend(results)

    out = os.path.join(corpus_dir, "_all_scores.json")
    with open(out + ".tmp", "w") as f:
        json.dump({"scored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "scores": all_results}, f, indent=1)
    os.replace(out + ".tmp", out)
    print(f"\nwrote {out} — {len(all_results)} brand×category scores")


if __name__ == "__main__":
    main()
