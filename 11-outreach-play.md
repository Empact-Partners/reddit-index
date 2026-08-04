# 11 — GTM and Outreach Play

## Bottom line

- The rate-then-sell mechanic is proven, but only in the form where **the rated company can see and fix its own score for free**. SecurityScorecard's entire funnel is a free, unlimited self-scorecard ([SecurityScorecard free tier](https://securityscorecard.com/pricing-packages/free/), [free public scorecard](https://securityscorecard.com/free-account-public-scorecard/)).
- What is contested is **publishing individual company scores**. The industry's own governing document says: "Rating companies should not publicize an individual organization's rating" — Principle 6, [U.S. Chamber of Commerce, Principles for Fair and Accurate Security Ratings, 2017](https://www.uschamber.com/security/cybersecurity/principles-for-fair-and-accurate-security-ratings). Reddit Index does exactly that by design.
- **Guilt-framed cold email raises reply rate but cuts meetings booked by 14%** ([Gong cold email stats](https://www.gong.io/blog/cold-email-stats)). Replies are not the goal, so the "most hated" angle is banned even though it would perform on the vanity metric.
- Recommended motion: **positive-led public ranking, negative diagnosis delivered privately and free.** The public site leads with most loved; the low-sentiment finding is what the email offers to explain in private.
- Badges are a **distribution and AI-citation play, not a link-building play**. Google requires widget and badge links to be `nofollow` or `sponsored` ([Google spam policies](https://developers.google.com/search/docs/essentials/spam-policies)).
- **No template in this file carries a literal figure.** Every number is a merge field. A fabricated statistic inside a cold email about somebody's reputation is the worst possible place to be caught with one.
- ⚠️ **The threshold squeeze is real:** at `n_eff ≥ 400` plus four independence floors, only category head brands qualify to be ranked, and those are largely not Empact retainer buyers. §6 proposes a two-tier site. That proposal is untested and it has a cost, priced there.

---

## 1. What the precedents actually show

| Precedent | Worked? | What actually did the work |
|---|---|---|
| [SecurityScorecard](https://securityscorecard.com/pricing-packages/free/) / BitSight / UpGuard | Yes, but | The buyer is a **third party** (procurement, vendor risk), not the rated company. The rated company's free scorecard is a remediation funnel, not a shaming funnel. |
| [HubSpot Website Grader](https://www.hubspot.com/blog/bid/2411/100-000-Website-Hopefuls-Try-To-Make-The-Grade-In-Internet-Marketing) | Yes | Self-serve, self-scored, no outreach required. 100,000 sites graded per HubSpot's own post. The widely-repeated "4 million websites" and "10 million leads" figures are **NOT VERIFIED**. |
| [ACSI](https://theacsi.com/solutions/acsi-logo-licensing) | Yes | Monetizes the **badge**, not the outreach. Logo licensing is a named product line covering 400+ companies across 40+ industries. |
| [G2](https://documentation.g2.com/docs/g2-badges) / Clutch / Capterra | Yes | The badge is earned, seasonal, and status-bearing. G2's "Users Love Us" requires 20 reviews at 4.0+; free profiles get only that badge, everything else is paywalled. |

**Inference, not sourced:** every durable version of this play sells to the winners or to third-party buyers of the rated. No verified precedent monetizes "you rank badly, pay us."

Three things follow. The negative column is a credibility asset and a conversation opener, never the offer. The badge is the monetizable artifact. The free self-diagnostic is the funnel.

---

## 2. The recommended motion

**Public: positive only, at volume.** Category pages lead with the most loved column, the badge, and the methodology link. That is the half that gets embedded, shared, and cited by AI engines.

**Private: the negative diagnosis, free, unbundled.** The email says "you are not in the Top 10 for your category, and here are the specific threads driving it." No published claim about that company is required for the email to land.

This keeps Empact inside Chamber [Principle 1 (transparency) and Principle 2 (right to dispute)](https://www.uschamber.com/security/cybersecurity/principles-for-fair-and-accurate-security-ratings) even while breaching Principle 6 on the head brands. It converts the same data from an accusation into a gift.

**The superlative always travels with the measured variable.** "Most Loved" and "Most Hated" are the owner's column labels and they do not change ([decisions/0005-superlative-labels.md](decisions/0005-superlative-labels.md)). Every surface carrying them — page, badge, email, press cut — shows the sentiment index, the opinionated mention count, and the window immediately beside the label.

⚠️ Reddit Index displays full Reddit comment text by owner decision. That is a deliberate, priced risk documented in [01-legal.md](01-legal.md), and it raises the cost of getting right-of-reply wrong. Outreach must never imply the brand page is negotiable in exchange for a commercial conversation.

---

## 3. Email angles, ranked

| # | Angle | Verdict | Why this rank |
|---|---|---|---|
| 1 | **"You made the list"** (winners, badge is the ask) | 🟢 Lead with this | Matches every verified precedent. Positive framing avoids the [Gong](https://www.gong.io/blog/cold-email-stats) guilt penalty; the consult is the follow-on, not the ask. |
| 2 | **"Your category report is ready"** (trajectory, data-first) | 🟢 Use at volume | The category is the subject line; the brand's position sits inside. Sentiment movement is the news, and it is legitimately volatile ([Semrush](https://www.semrush.com/blog/most-cited-domains-ai/)). |
| 3 | **"The threads buyers read before choosing you"** (evidence) | 🟡 ICP-qualified only | Specific, non-published, remediation-framed. High value, but it needs a real thread list, so it does not scale beyond scored accounts. |
| 4 | **"You are in the most hated column"** | 🔴 Do not use | Predicted higher replies, lower meetings. Gong measured guilt wording at −14% meetings booked; pitching cuts reply rates up to 57% across [28M+ emails](https://www.gong.io/blog/does-cold-email-even-work-any-more-heres-what-the-data-says). Plus defamation and PR exposure when the rating is sentiment, not fact. |

Ordering rationale: angles 1 and 2 put the category first and the recipient second, which keeps the meeting rate intact. Angle 3 inverts that and pays for it with specificity. Angle 4 inverts it and pays nothing.

**Two hard constraints on every template.** [07-index-methodology.md §8](07-index-methodology.md) requires cold outreach to lead with the brand's own trajectory and never with the cross-brand rank alone, because the rank carries the size-and-adoption-model confound and the trajectory does not. And the window is the frozen trailing 12 months, never a window picked to make a sentence work.

**Template rule: no literal figures.** Every number resolves from the brand's own record at send time. A template shipped with an illustrative statistic eventually sends that statistic to a prospect, and a post-hoc method inconsistency is the fatal fact in a *Suzuki*-pattern claim ([01-legal.md](01-legal.md)).

**Worked example — angle 1:**

```
Subject: {{Brand}} on Reddit — your 12-month sentiment trend

Hi {{first_name}},

Over the trailing 12 months your positive share on Reddit
moved from {{positive_share_start}} to {{positive_share_end}},
across {{opinionated_mention_count}} opinionated mentions in
{{thread_count}} threads.

That trend also puts {{Brand}} at #{{rank}} in the Most Loved
column for {{category}} — sentiment index {{sentiment_index}},
{{opinionated_mention_count}} opinionated mentions,
{{window_start}}–{{window_end}}.

The page, the badge, and every thread behind the number are
free and open, no signup:
redditindex.com/brand/{{brand_slug}}

{{n_positive_drivers}} threads are doing most of the lifting
for you and {{n_negative_drivers}} is working against you.
Happy to send that breakdown — no charge, we built the index
and the analysis is already done.

Vlad
Empact Partners (we build and operate Reddit Index)
```

Brand pages live at `/brand/{slug}` and category pages at `/category/{slug}` per [00-concept.md](00-concept.md). A brand page is global rather than per-category, so a category-nested link would point at a URL the site does not serve.

Note the disclosure in the signature. Empact operates the index openly per [00-concept.md](00-concept.md), so the email says so rather than letting the prospect find out later.

---

## 4. The badge play

Feature priority: (1) a dated, category-scoped seasonal badge that expires and forces annual re-embed; (2) one-click embed with pre-written LinkedIn and press copy; (3) a public methodology page at `/methodology` that the badge links to.

The badge face carries the superlative and the measured variable together: category, "Most Loved", rank, sentiment index, opinionated mention count, and the window. A badge that travels off-site with only the superlative on it is the one artifact we cannot correct after the fact.

**SEO reality, stated plainly.** Google requires badge and widget links to be `rel="nofollow"` or `rel="sponsored"`, and names "exchanging goods or services for links" as a link scheme ([spam policies](https://developers.google.com/search/docs/essentials/spam-policies)).

Separately, embedding a third-party rating widget makes the embedding page **ineligible for star rich results**, and sites "must not aggregate reviews or ratings from other websites" ([Google review snippet docs](https://developers.google.com/search/docs/appearance/structured-data/review-snippet)).

So G2's claim that badges "supplement your SEO initiatives" ([G2 badge docs](https://documentation.g2.com/docs/g2-badges)) is **overstated for the embedding brand**. Never repeat it in a pitch. The badge earns brand distribution and AI citation surface, and SEO value accrues to the Reddit Index methodology and index pages via editorial coverage.

---

## 5. ICP segmentation

Score every ranked or profiled company. Contact only those meeting **3 of 5**.

| Signal | What it proves |
|---|---|
| Named VP / Head / Director of Marketing or Demand Gen on LinkedIn | A budget owner exists |
| Funded Series A–C, or 50–500 headcount | Retainer is affordable |
| Already paying for reputation surfaces — a G2 paid profile (any badge beyond "Users Love Us" implies paid tier, [G2 docs](https://documentation.g2.com/docs/g2-badges)), Clutch verified badge, or an active review-request flow | Willingness to pay is demonstrated, not assumed |
| ≥1 negative Reddit thread ranking top 10 for a branded or "alternatives" query | The problem is already costing them |
| Competitor mention velocity rising | Urgency exists |

**Hard excludes:** sub-20 headcount, PLG-only with no marketing hire, agencies, and anyone with near-zero Reddit volume. The last one matters most — no mentions means no diagnosis, and the email becomes a pitch.

This list is also the page-generation list. §6 explains why nothing outside it should get a profile page.

---

## 6. ⚠️ The threshold squeeze

[07-index-methodology.md](07-index-methodology.md) gates eligibility on **`n_eff ≥ 400`**, where `n_eff = n / DEFF` and `DEFF = 1 + (m̄ − 1)·ICC`. Reddit mentions cluster inside mega-recommendation threads and by author, so raw `n` overstates the information in a sample and the naive 384 → 400 derivation is insufficient on its own.

Four independence floors sit on top: distinct authors, distinct subreddits, distinct threads, and a cap on the share of mentions from any single thread. Together they are what stops a coordinated push from producing a ranking.

**Sourcing, stated plainly.** The 400 figure is an internal derivation in this repo, not a research-corpus finding. It is defensible because the derivation is published; it is not a fact anyone else has validated. The design-effect correction tightens it further, because `n_eff` is always below `n`.

It also means only category head brands qualify. Head brands are Salesforce-class incumbents, and those companies do not buy consultancy retainers from a boutique. The statistically sound half of the product and the commercially useful half point at different companies.

**Do not resolve this by lowering the threshold.** A weakened cutoff produces rankings that a rated company can trivially discredit, which destroys the PR and AI-citation asset that is the actual moat.

**Proposed resolution — inference, not sourced, and untested.** Run a two-tier site. Tier 1 is **Ranked** at `n_eff ≥ 400` with published position, badges, and PR value. Tier 2 is **Profiled** below threshold: a brand page with mentions and a clearly labeled "not enough data to rank" state, no position, no most-hated placement.

Outreach pipeline comes from Tier 2, where Empact ICP actually lives and where no ranking claim has been published at all. Tier 1 carries credibility, press, and citations. The badge revenue and the retainer revenue come from different tiers by design.

### What Tier 2 costs

A Tier 2 page has no computed index by construction, and the computed index is the entire unique-benefit defense. [10-seo-aeo.md](10-seo-aeo.md) classifies reproduced comment text as no benefit on top of the feed and states that any page whose value collapses to a list of somebody else's comments forfeits the Scraping-clause defense.

So Tier 2 carries the full display exposure — the copyright and GDPR risks and the Delfi-style republication posture in [01-legal.md](01-legal.md), plus the delete-sync burden — with none of the offsetting defense. It earns nothing in search either: below-threshold pages ship `noindex,follow` ([10-seo-aeo.md](10-seo-aeo.md)). A Tier 2 page's only value is the outreach artifact.

**Therefore bound the Tier 2 population by policy.** Generate a profile page only for a company already on the ICP-qualified outreach list (§5), never for the whole category roster. The exposure scales with a number we choose, so choose a small one and record it.

**Open decision, flagged not decided.** [decisions/0002-display-full-mentions.md](decisions/0002-display-full-mentions.md) priced full comment display against a page that carries a published index. Tier 2 has no index, so it is not the trade that was priced. If the two-tier proposal is adopted, whether Tier 2 shows comment bodies or only counts, dates and thread links needs its own decision record.

**Population.** Tier 1 projects to roughly 150–300 brands across 50 categories (§9). Tier 2 is the tail below them and is enumerated nowhere: the [seed gazetteer](data/brand-gazetteer-seed.csv) holds 113 head brands across 17 categories, and head brands are exactly the ones that clear Tier 1.

---

## 7. Claim-your-profile, corrections, and right of reply

Gate the full report — thread list, sentiment drivers, competitor deltas — behind claim-your-profile. Leave the rank and a one-line summary public. Published conversion benchmarks for this pattern are all low-quality SEO aggregations and are **NOT VERIFIED**; instrument a first-party baseline instead.

Corrections and right of reply run on a separate track with a separate reply-to address. A named human reviews every dispute against the source threads.

⚠️ **A correction request must never be answered with a commercial offer, in the same message or in a follow-up sequence.** That pairing is what turns reputation outreach into something that looks coercive. Suppress every claimant who files a dispute from all outbound for 90 days.

---

## 8. Content and PR flywheel

Annual **"State of Reddit Brand Sentiment"**, quarterly category cuts, and a permanently live methodology page at `/methodology`. Sentiment volatility is the story: Semrush measured ChatGPT citing Reddit in ~60% of responses in early August 2025, collapsing to ~10% by mid-September 2025 ([Semrush 3-month study](https://www.semrush.com/blog/most-cited-domains-ai/)).

Realistic link expectation, **SECONDARY evidence, low confidence**: the average digital PR campaign earns links from 42 referring domains at average DR 61, at roughly $750 per earned link ([reporteroutreach.com, aggregating Digitaloft / Reboot / BuzzStream](https://www.reporteroutreach.com/blog/digital-pr-statistics)).

The bigger payoff is AI citation: longitudinal studies of this shape get cited as sources by AI engines, which is the asset class Reddit Index is building.

---

## 9. Success criteria, first 6 months of Phase 1

The clock starts when the site ships, not at project start. Phase 0 runs 3–5 weeks ahead of it, and [12-phasing.md](12-phasing.md) records Phase 1 elapsed time as not estimable until the 38 unmapped categories land. Every leading target below is provisional until they do.

| Type | Metric | Target | Where the number comes from |
|---|---|---|---|
| Leading | Ranked (Tier 1) brands live | ≥150 | Derived below from the assessed categories |
| Leading | Detected badge embeds | ≥30 | No benchmark exists — first-party baseline |
| Leading | Profiled (Tier 2) ICP accounts claiming a profile | ≥10% | Benchmarks **NOT VERIFIED** (§7) — first-party baseline |
| Leading | Referring domains to index and methodology pages | ≥40 | One digital PR campaign averages 42 RDs (§8, secondary) |
| Leading | Index cited in an AI engine answer for "reddit brand sentiment" class queries | ≥1 | Binary |
| Lagging | **Meetings booked per 1,000 sends** | **≥3** | [Gong](https://www.gong.io/blog/does-cold-email-even-work-any-more-heres-what-the-data-says): 344 emails per meeting ≈ 2.9/1,000 |
| Lagging | Qualified opportunities | ≥8 | Funnel arithmetic below |
| Lagging | Closed retainers | ≥2 | No verified close-rate benchmark — first-party baseline |
| Lagging | Takedown or legal demands | 0 | — |

**Where ≥150 comes from.** The only anchor is the Phase 0 gate: ≥10 brands clearing `n_eff ≥ 400` in Password Managers, the richest of the 12 categories assessed in [04-subreddit-mapping.md](04-subreddit-mapping.md). Of those 12, six are 🟢 rich, four are 🟡 partial (top-3 only, or one segment), and two are 🔴 unrankable.

Hold that ratio across 50 categories: roughly 25 rich, 17 partial, 8 unrankable. Rich categories will average well under the richest one's 10 — call it 5 — and partial categories publish about 3. That gives 25×5 + 17×3 ≈ 175, with a ceiling near 300 only if every rich category matched Password Managers.

A 500+ target requires 50 categories each out-performing the single richest one assessed, on 38 mappings nobody has run. It is not reachable and it is not the target.

**The funnel, recomputable.** Six thousand sends over six months at ≥3 meetings per 1,000 gives ≥18 meetings. Eight qualified opportunities is 44% of those; two closed retainers is 25% of the opportunities. Neither rate is benchmarked anywhere in the research. Both are baselines to instrument, not forecasts.

The meetings-per-1,000 target is the one that decides everything, because it is the only line with an external benchmark behind it. Beat 2.9 or this play is not better than generic outbound.

**Kill criterion:** reply rate high but meetings per 1,000 below 2.9 for two consecutive months. That is the guilt-penalty signature, and it means the negative half has leaked into the outreach.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [01-legal.md](01-legal.md) · [07-index-methodology.md](07-index-methodology.md) · [12-phasing.md](12-phasing.md)
