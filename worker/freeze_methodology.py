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
VERSION = "1.0.0-provisional"

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
    ("estimator", "global", "empirical_bayes_beta_binomial",
     "p_tilde = (x_pos + alpha0) / (N_op + alpha0 + beta0); Reddit Love Score = round(100 * p_tilde). "
     "One published number, 0-100 (decisions/0006)."),
    ("prior_fit", "global", "method_of_moments_leave_one_out",
     "alpha0 and beta0 are fitted per category across every OTHER brand in it, so the dominant "
     "brand is not pinned to its own mean (07 §1)."),
    ("prior_min_n_op", "global", 30,
     "A brand contributes to the prior only above this many opinionated mentions. Below it a rate "
     "is noise and destabilises the moment estimate. Never stated in the spec."),
    ("prior_m_fallback", "global", 200,
     "Prior strength used when the moment estimate is degenerate (variance <= 0, or fewer than 4 "
     "contributing brands). A fallback that fires silently is the hidden knob 07 §6 warns about, "
     "so it is named, published, and flagged per row when it fires."),
    ("prior_m_clip", "global", [20, 2000],
     "Bounds on the fitted prior strength. Method-of-moments on a handful of brands can return an "
     "absurd value in either direction."),

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

    # ── uncertainty ─────────────────────────────────────────────────────────
    ("ci_level", "global", 0.90, "07 §5."),
    ("bootstrap_B", "global", 1999,
     "0.05 * (B + 1) = 100 exactly, so the 90% percentile endpoints are exact order statistics "
     "with no interpolation and no tie-handling ambiguity. The spec never states B."),
    ("bootstrap_unit", "global", "whole_clusters_thread_and_author_carry_wider",
     "Threads and authors are crossed rather than nested, so a single joint resample is not well "
     "defined. Resample each design separately and carry the wider interval, consistent with the "
     "max(DEFF) rule."),
    ("bootstrap_refit_prior", "global", True,
     "The prior is refitted inside every replicate. Holding it fixed produces an interval "
     "CONDITIONAL on the fitted prior and understates the spread — the same criticism 07 §2 levels "
     "at Wilson."),
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
    ("sentiment_engine", "global", "claude_cli_max_plan_local",
     "06 §3's eight-stage cascade exists to avoid a per-million API bill and depends on a "
     "1,000-1,500 item gold set that does not exist. Classification runs locally through the "
     "Claude Max subscription instead of any metered API, which removes both the cost argument and "
     "an ML-training dependency from the critical path."),
    ("sentiment_model_version", "global", "claude-cli-absa-1",
     "mention_sentiment.model_version. Re-scoring under a new version APPENDS a row, never "
     "overwrites — the primary key carries the version for that reason."),

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
