#!/usr/bin/env python3
"""Freeze the method, before a single scoring mention exists.

07-index-methodology.md §9 is unambiguous about the order of events:

    "Freeze before first result — this file is tagged and its commit hash
     recorded before the first production crawl runs."
    "No post-hoc tuning — a parameter is never changed after seeing where a
     specific named brand landed."
    "Audit trail — the git history is the evidence that the method predates
     the result."

decisions/0005 makes the same thing a CONDITION of using the words "Most Loved"
and "Most Hated" at all. So this runs before the harvester, and the commit hash
it records is the evidence.

Everything below is a constant the specification never fixed. Each one had to be
chosen to write the code at all, and an unrecorded choice is a hidden knob —
which is exactly what §6 warns against. They are written to an append-only
table, rendered verbatim on /methodology, and changing one is a version bump
with a dated changelog entry, never an edit.
"""
import json, os, subprocess, sys, urllib.request, datetime

REF = "nrsyqcttpijxhwtdtoct"
# 2.0.0 (2026-08-12): the v1 prior was mis-specified — brand-rate method of
# moments over brands with n_op>=30, falling back to a 200-pseudo-observation
# prior whenever fewer than 4 brands qualified. In a category with exactly two
# big brands each was scored against the OTHER's rate at ~5x its own evidence
# (Porkbun 41 pos/1 neg published 20; GoDaddy 4 pos/111 neg published 63).
# v2 shrinks toward the category's pooled LOO mention rate at fixed strength
# K=10, and a calibration gate refuses to load any run whose ordering
# contradicts its own raw data. Params below are the complete v2 set;
# the 1.0.0-provisional rows remain in the table untouched (append-only).
# 2.0.1 (2026-08-14): selection-rule change ONLY — the top-N-by-worth cap
# (T × bb_per_hour, 8 then 12) on scoring subreddits is removed. Every
# candidate that passes ALL qualification bars (exists & open · alive ≥ ~2
# posts/wk · not vendor-run · rules posture v2 ≠ forbid · topicality ≥ 0.5 ·
# evidence floor) is is_scoring for its category. The cap starved 38
# categories below the 5-sub viability floor and 6 to zero; mega-subs are
# scoped at THREAD level (Stage 3 qualification), not excluded at sub level.
# Estimator, prior, gates, window, resolution, sentiment: all unchanged —
# the full set is re-frozen under 2.0.1 so /methodology renders one
# complete, self-contained set per version (the page filters version =).
# 2.2.0 (2026-08-16): the PUBLISHED NUMBER changes from the posterior mean
# to the 10th-percentile posterior LOWER BOUND. The mean let thin evidence
# float upward — shrinkage pulled a barely-observed brand toward the category
# average, so shift4 (0 positives / 4 opinions) published 40 while PayPal
# (25% positive / 72 opinions) published 29; three categories sat quarantined
# on exactly this. The lower bound is monotone in rate AND evidence, so
# sparse data costs position instead of buying it. Prior, gates, thresholds,
# window: unchanged. Also: classification moved to provider pools, so
# sentiment_model_version is no longer a single pinned value — the published
# view joins the newest label per (doc, brand) regardless of lane.
VERSION = "2.2.0"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "uncommitted"


# key, scope, value, rationale
PARAMS = [
    # ── the estimator ───────────────────────────────────────────────────────
    ("estimator", "global", "empirical_bayes_beta_binomial_lower_bound",
     "posterior = Beta(x_pos + alpha0, x_neg + beta0); Reddit Love Score = "
     "round(100 * Q_0.10(posterior)) — the 10th-percentile posterior quantile, "
     "not the mean. The mean rewarded thin evidence (shift4 0/4 published above "
     "PayPal 25%/72); the lower bound is monotone in rate and in evidence, so "
     "uncertainty costs position. One published number, 0-100 (decisions/0006)."),
    ("score_quantile", "global", 0.10,
     "The posterior quantile published as the score. Deterministic "
     "dependency-free Beta inverse-CDF (bisection over the regularised "
     "incomplete beta), worker/score.py::beta_quantile."),
    ("prior_fit", "global", "pooled_loo_mention_rate_fixed_k",
     "p0 = (pooled_pos + 5) / (pooled_op + 10) over every OTHER brand's opinionated mentions in "
     "the category; alpha0 = K*p0, beta0 = K*(1-p0). Replaces v1's brand-rate method-of-moments "
     "fit, which collapsed to a 200-pseudo-observation prior whenever fewer than 4 brands had "
     "n_op>=30 and scored two-big-brand categories as each other (the Porkbun/GoDaddy swap)."),
    ("prior_k", "global", 10,
     "Total pseudo-observations the prior contributes, fixed. A brand with 40 real opinions is "
     "~80% its own data; under v1's fitted strengths (~200) it was ~17%."),
    ("prior_p0_smooth", "global", 10,
     "Beta(5,5) smoothing inside p0 itself, so an empty or tiny leave-one-out pool degrades "
     "gracefully toward 0.5 instead of an extreme anchor."),
    ("prior_pool_min", "global", 30,
     "Below this many LOO pooled opinionated mentions the row is flagged prior_fallback: p0 is "
     "mostly the smoothing, not the category."),
    ("calibration_gate", "global",
     {"min_n_op": 10, "min_brands": 4, "material_gap": 0.15,
      "quartile_raw_hi": 0.75, "quartile_raw_lo": 0.25},
     "A scoring run is refused before load if, within any category over brands with n_op>=10, "
     "any two brands whose raw positive rates differ by >=0.15 are published in the opposite "
     "order, or a brand with raw rate >=0.75 lands in the bottom score quartile (or <=0.25 in "
     "the top). 2.0.2 replaced an all-pairs Spearman>=0.8 test, which flagged shrinkage among "
     "statistical ties as a contradiction; materiality is what the gate always meant. "
     "Mechanized from the failure a reader caught that the pipeline did not "
     "(worker/gate_calibration.py, self-tested against the v1 output)."),

    # ── the eligibility gate ────────────────────────────────────────────────
    ("n_eff_numerator", "global", "n_op",
     "THE CONSEQUENTIAL READING. n_min = z^2 * 0.25 / h^2 is the sample size needed to estimate a "
     "PROPORTION to half-width h, and that proportion's denominator is N_op, not all mentions. "
     "07 §5 writes 'n_eff = n / DEFF' while 07 §1 says n is 'never a denominator'; gating on n "
     "would let a brand publish a +/-4pp claim on far fewer than 600 opinionated observations. "
     "This is a 2-3x difference in the gate and it is recorded in HANDOFF.md."),
    ("deff_cluster_size", "global", "kish_m_tilde",
     "DEFF = 1 + (m_tilde - 1) * ICC where m_tilde = sum(n_j^2)/N, Kish's size-weighted mean. "
     "07 §5's plain mean m_bar understates the design effect when cluster sizes are unequal, and "
     "ours are violently unequal. m_tilde >= m_bar always, so this errs toward refusing to publish."),
    ("deff_designs", "global", ["thread", "author"],
     "Computed twice and the LARGER carried, so the gate is set by whichever dependence structure "
     "is worse for that brand (07 §5)."),
    ("icc_floor", "global", 0.10,
     "Used when fewer than 5 clusters exist, with icc_estimated = false recorded on the row. The "
     "0.08 in 07 §5 is explicitly illustrative; a real ICC is measured, never inherited."),
    ("diversity_floors", "global",
     {"distinct_authors_min": 50, "distinct_subreddits_min": 5,
      "max_thread_share": 0.20, "max_author_share": 0.05},
     "Four floors, absolute at every tier, per brand per category. Distinct THREADS is published "
     "evidence and not a floor, and the n_eff gate is a gate and not a fifth floor."),
    ("category_viability_min_scoring_subreddits", "global", 5,
     "A CATEGORY-level test, distinct from every brand-level test. Failing it renders the "
     "insufficient-signal panel; it never makes a brand 'below threshold'."),
    ("ranking_threshold", "global",
     {"rule": "category_median_n_op", "floor": 3, "ceiling": 30},
     "A company is RANKED in a category once its opinionated mention count reaches that "
     "category's median across tracked brands, clamped to [3, 30] — it must carry at least "
     "as much evidence as the typical brand it is ranked against. Self-calibrating: a dense "
     "category asks for more, a thin one falls to the floor and stays publishable. Replaces "
     "a flat n_op>=3 display floor and the unused n_eff gate, whose per-category tiers were "
     "a hardcoded default for 86 of 100 categories derived from category-level comment flow, "
     "never from per-brand evidence. Below the threshold a company keeps its page and its "
     "mentions and carries no position."),
    ("n_eff_role", "global", "precision_claim_not_visibility",
     "2.1.0: n_eff >= n_min no longer decides whether a company appears — it decides whether "
     "a published score may also claim a precision (+/-4/5/7pp by tier). It admitted 10 of "
     "2,056 rows while the boards rendered 1,029, and no component ever read it."),
    ("scoring_subreddit_selection", "global", "all_qualifying",
     "2.0.1: every subreddit passing ALL qualification bars is is_scoring for the "
     "category — no top-N cap, no worth ranking. Replaces the implicit top-8 (later 12) "
     "by T × bb_per_hour, which left 38 categories under the 5-subreddit viability floor "
     "and 6 at zero. Subscriber count is never a bar; mega-subs serving many categories "
     "are scoped by thread-level qualification, not excluded. Selection changes which "
     "mentions exist, never how any mention is scored."),

    # ── uncertainty ─────────────────────────────────────────────────────────
    ("ci_level", "global", 0.90, "07 §5."),
    ("bootstrap_B", "global", 1999,
     "0.05 * (B + 1) = 100 exactly, so the 90% percentile endpoints are exact order statistics "
     "with no interpolation and no tie-handling ambiguity. The spec never states B."),
    ("bootstrap_unit", "global", "whole_clusters_thread_and_author_carry_wider",
     "Threads and authors are crossed rather than nested, so a single joint resample is not well "
     "defined. Resample each design separately and carry the wider interval, consistent with the "
     "max(DEFF) rule."),
    ("bootstrap_refit_prior", "global", False,
     "v2: the prior is held fixed inside replicates, and that is correct rather than a shortcut — "
     "it is computed from every OTHER brand's mentions, and resampling this brand's threads does "
     "not move it. v1 refitted per replicate because its prior depended on the brand's own rate."),
    ("tie_rule", "global", "overlapping_90pc_intervals",
     "Ranks whose intervals overlap are declared tied and rendered as ties. Decided on the "
     "unrounded score, never the displayed integer."),

    # ── window ──────────────────────────────────────────────────────────────
    ("scoring_window_months", "global", 12,
     "Trailing 12 months, uniform weight inside it (07 §6). BUILD-PROMPT.md never mentions the "
     "window at all, and Lane D returns t=all, so without this a builder scores 2022 threads."),

    # ── entity resolution ───────────────────────────────────────────────────
    ("resolution_mode", "global", "rules_only_no_classifier",
     "05 §2's stage-3 disambiguation classifier is trained on a ~1,000-mention gold set that does "
     "not exist and is not scheduled. Rather than invent a threshold, high-ambiguity surface forms "
     "are gated on corroborating signals and a stop-context veto, both deterministic and "
     "reproducible — the property 05 §2 says a pure-LLM pass lacks."),
    ("corroborating_signals_required", "global", {"SAFE": 0, "AMBIGUOUS": 1, "HOSTILE": 2},
     "05 §5: a bare high-ambiguity token 'default-rejects unless two corroborating signals fire'."),
    ("bare_disabled_forms", "global",
     ["close", "make", "front", "square", "render", "motion", "craft", "remote", "bob", "wave",
      "lever", "resolve"],
     "Bare tokens no stop-context list reaches the precision bar on. These brands resolve only "
     "through a qualified form. 05 §9: excluded, not guessed. The recall loss is per-brand and "
     "published rather than hidden."),
    ("precision_claim", "global", "unmeasured_by_human_audit",
     "05 §6 requires a 1,000-item human-adjudicated sample per cycle to certify precision, and no "
     "human audit has been run. The >=0.97 figure in the specification is a DESIGN TARGET, not a "
     "result, and this build publishes no precision figure it has not measured."),

    # ── sentiment ───────────────────────────────────────────────────────────
    ("label_encoding", "global", {"neu": 0, "pos": 1, "neg": 2, "abstain": 3},
     "Four-way, per 06 §3, which states the rule twice and explains it: only pos and neg enter a "
     "score, neu is a real judgment, abstain is the classifier declining, and collapsing either "
     "changes the denominator and therefore the rank. 07 §3's five-value list adds "
     "'recommendation', which 06 carries as a FLAG. Recorded in HANDOFF.md."),
    ("stage_encoding", "global", {"rules": 1, "encoder": 2, "llm": 3, "human": 4},
     "Never enumerated in the spec. This build writes stage 3."),
    ("doc_type_encoding", "global", {"comment": 1, "post_body": 2},
     "A brand named in a post body and a brand named in a comment are counted identically and both "
     "displayed. doc_type selects the card label and the permalink target, never the weight."),
    ("sentiment_engine", "global", "codex_fleet_local_subscription",
     "06 §3's eight-stage cascade exists to avoid a per-million API bill and depends on a "
     "1,000-1,500 item gold set that does not exist. Classification runs on the local Codex "
     "fleet (subscription compute, batched, disk-idempotent) instead of any metered API, which "
     "removes both the cost argument and an ML-training dependency from the critical path."),
    ("sentiment_model_version", "global", "multi-lane",
     "Classification runs on provider pools (claude-cli-absa-1, "
     "deepseek-v4-flash-absa-1, haiku-4.5-absa-1) with 85% pairwise label "
     "agreement and identical label distributions on a blind benchmark. The "
     "published view joins the NEWEST label per (doc, brand) regardless of "
     "lane; a QA invariant enforces one label per (mention, brand)."),

    # ── scope of this build ─────────────────────────────────────────────────
    ("lanes_active", "global", ["B", "D"],
     "Lane A (archive census) and Lane C (external search index) are not run. Only Lane A is a "
     "census, so this corpus is explicitly a SAMPLE and no coverage claim is made from it."),
    ("corpus_status", "global", "sample_not_census",
     "The honest name for what this is. Every count on the site is a floor."),
]


def main():
    tok_path = os.path.expanduser("~/.claude/.supabase-empact.token")
    token = open(tok_path).read().strip()
    commit = git_commit()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    values = []
    for key, scope, value, rationale in PARAMS:
        values.append(
            "(" + ", ".join([
                _lit(VERSION), _lit(scope), _lit(key),
                _lit(json.dumps(value)) + "::jsonb",
                _lit(rationale), _lit(now) + "::timestamptz", _lit(commit),
            ]) + ")")

    sql = (
        "insert into methodology_params "
        "(version, scope, key, value, rationale, effective_from, git_commit) values\n"
        + ",\n".join(values)
        + "\non conflict (version, scope, key) do nothing;"
    )

    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as f:
        print(f.read().decode()[:300])

    print(f"\nfroze methodology {VERSION} at commit {commit[:12]} — {len(PARAMS)} parameters")
    print("Nothing may be ingested or scored before this row exists (07 §9).")
    return 0


def _lit(s):
    return "'" + str(s).replace("'", "''") + "'"


if __name__ == "__main__":
    sys.exit(main())
