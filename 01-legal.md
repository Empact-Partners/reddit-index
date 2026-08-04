# Legal Position and Risk Register

⚠️ **This is not legal advice.** It is an internal risk document written from primary sources by non-lawyers. Before redditindex.com goes live, get an Estonian data-protection opinion and a US media-law read on the final page copy. Nothing below is a clearance to publish.

## Bottom line

- Reddit's terms do not permit what Reddit Index does. A business may not "access or use any of the Reddit Services and Data by or on behalf of a business," and that restriction expressly reaches derived data ([Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms)).
- Displaying stored comment text breaches the narrow display licence in [Data API Terms §2.4](https://www.redditinc.com/policies/data-api-terms) and Developer Terms §4.2 simultaneously. Links back and usernames are required whatever else we do.
- Aggregate-only scores would not fix the contract problem. Data API Terms §6 reaches "any data or models that were derived from User Content." Aggregation helps on copyright, not on contract, and contract is the theory Reddit is actually pressing — the one that survived preemption in *Anthropic*.
- ⚠️ The name breaches Reddit's trademark clauses outright. [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms) both bar Reddit marks in a product name absent written consent, and "Reddit Index" on redditindex.com sits inside both ([0001](decisions/0001-name-reddit-index.md)).
- The enforcement path for the name is a UDRP filing, not a lawsuit. Reddit runs them *pro se* for roughly $1,500 and has won every one we found: [reddit.win](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html), [redditpromotion.com / redditshop.com](https://www.wipo.int/amc/en/domains/decisions/text/2019/d2019-2964.html), [reddit.co](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html).
- ⚠️ Low traffic is not a defence against a UDRP. It is a registrar-level administrative proceeding: no damages, no discovery, no proof anyone visited the site. It needs only that Reddit notices.
- Losing one costs the domain, not the project. The pipeline, index, methodology and content all survive a transfer, and that asymmetry is the entire reason the name was judged affordable.
- ⚠️ The real asset at stake is not this website. The [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) permits Reddit to suspend "associated accounts, bots, domains, or subreddits" — which reaches Empact's live Reddit operation across roughly 28 partner projects (internal Empact figure, not from the research corpus).
- Owner decision, recorded: we display full comment text with links back, knowingly, without a Reddit agreement. That is a priced risk, not a compliant design, and this document does not pretend otherwise.

## 1. The clause-level table

Two contracts bind. **Data API Terms** — effective June 19, 2023, last revised **July 20, 2026** ([text](https://www.redditinc.com/policies/data-api-terms)). **Developer Terms** — effective September 24, 2024, last revised **March 24, 2026** ([text](https://www.redditinc.com/policies/developer-terms)).

| Clause | What it says | What it means for Reddit Index |
|---|---|---|
| [Data API Terms §2.4](https://www.redditinc.com/policies/data-api-terms) | Non-exclusive, revocable licence to "copy and display the User Content using the Data API"; "You may not modify the User Content except to format it for such display." | A ranking computed from comments is arguably not "display." Our brand pages are display plus derivation. 🔴 |
| [Data API Terms §3.1](https://www.redditinc.com/policies/data-api-terms) | Commercial purposes, or any use "not expressly permitted," require "a separate agreement with Reddit." | We have no such agreement. An Empact-operated lead-gen asset is commercial on any reading. 🔴 |
| [Data API Terms §3.2](https://www.redditinc.com/policies/data-api-terms) | No deriving revenues without express written approval; must "immediately delete" any data not required for the approved use case. | No approved use case exists, so every stored comment is arguably data we must delete. 🔴 |
| [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) | "You are not permitted to use the Reddit Trademarks in, or as part of the name of your App," or in logos promoting it. | Breached. The product is **Reddit Index** on redditindex.com, and there is no written authorization. Priced, not defended ([0001](decisions/0001-name-reddit-index.md)). 🔴 |
| [Data API Terms §4.2](https://www.redditinc.com/policies/data-api-terms) | The only licensed wordmark form is "[insert name] for Reddit." | The one safe harbour, and we are outside it. "Reddit Index" is not "[name] for Reddit," so no licensed construction covers us. 🟡 |
| [Data API Terms §6](https://www.redditinc.com/policies/data-api-terms) | On termination, delete cached or stored User Content "including any data or models that were derived from User Content and Materials." | Termination obligates deleting the rankings, not just the comment store. The whole site is derived data. 🔴 |
| [Developer Terms §2.2](https://www.redditinc.com/policies/developer-terms) | Defines "Reddit Services and Data" to include content "obtained through or otherwise derived from" the Services. | This definition is what makes §4.1 reach our scores, not only raw comments. 🔴 |
| [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) | If content is deleted, protected, suspended, withheld, modified, or removed, you must delete or modify it "as soon as possible." | The contract says "as soon as possible" and names no interval. We implement a nightly job. Build it regardless of everything else. 🟡 |
| [Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms) | No access or use "by or on behalf of a business or as part of a service or product that is monetized"; no revenue "including from any data derived from the foregoing." | The core breach. Empact Partners operating it openly is exactly the fact pattern this clause names. 🔴 |
| [Developer Terms §4.2](https://www.redditinc.com/policies/developer-terms) | No derivative works, copying, reproduction, redistribution, or syndication; no behavior "likely to violate our Public Content Policy." | Republishing comment bodies on our own pages is reproduction and redistribution. 🔴 |
| [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) | Attribution is mandatory: "a link back to the User Content on our Services, cite the applicable User's username, and clearly indicate that the User Content is from our Services." | Cheap and non-negotiable. Every mention gets permalink, username, "from Reddit." 🟡 |
| [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms) | "you are not permitted to use the Reddit Trademarks in the name of your App or to promote or identify your App," without Reddit's prior written consent. | Breached twice: the mark is in the product name and in the domain, and both appear in outreach materials. Same decision, same price ([0001](decisions/0001-name-reddit-index.md)). 🔴 |
| [Developer Terms §7.3](https://www.redditinc.com/policies/developer-terms) | Deletion on Reddit's request, on the user's request, or when retention is no longer necessary. | Requires a working removal route for individual Redditors, not only for brands. 🟡 |
| [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) | Approval required before accessing data; no commercialization "without express written approval," extending to "commercial and non-commercial mining, scraping." Enforcement includes suspending "associated accounts, bots, domains, or subreddits." | The blast-radius clause. See risk 8. 🔴 |

The Responsible Builder Policy also prohibits "processing data to derive or infer potentially sensitive characteristics about Reddit users." Scoring *brands* is fine under that line. Profiling *individual users* is not, and we must never build it.

## 2. Reddit names this exact use case

Reddit's [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) lists "companies that help brands monitor trends associated with their brands" among its data licensee categories. That describes Empact Partners.

The same policy says you may use Reddit content "for non-commercial uses, such as learning and community, but talk to us if you have commercial purposes in mind." Licensees also may not keep displaying content deleted by Redditors or removed by Reddit.

Reddit's developer documentation lists "Free product features available for upsell" as commercial use, and answers "No" to displaying Reddit content alongside ads ([Developer Platform: Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)).

**INFERENCE:** a free, ad-free site that exists to open sales conversations is "a free product feature available for upsell." Ad-free helps far less than it feels like it should.

## 3. The two priced decisions, stated plainly

Two choices in this product are breaches the owner made with the clauses in front of him. Both are recorded here as decisions, not as findings of compliance.

**The display ([decision 0002](decisions/0002-display-full-mentions.md)).** Reddit Index shows full Reddit comment text on brand pages, with links back to the original threads. This breaches Data API Terms §2.4, §3.1, and §3.2, Developer Terms §4.1 and §4.2, and the Responsible Builder Policy.

It also adds per-commenter copyright exposure an aggregate-only site would not carry, and that exposure has no mitigation. [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) states that User Content is owned by Users and not by Reddit, so no Reddit licence can reach it.

Attribution and free removal reduce the sympathy cost of such a claim, not the claim itself. What the display buys is the product: the outreach asset only works because a founder can read the actual sentences.

**The name ([decision 0001](decisions/0001-name-reddit-index.md)).** The product is Reddit Index on redditindex.com. This breaches Data API Terms §4.1 and Developer Terms §5.3, which bar Reddit marks in a product name without written consent we do not have and did not seek.

What the name buys is legibility: it says what it is in a cold email with no sentence of explanation. What it costs is the domain if Reddit files a UDRP, plus the option on non-Reddit sources — Phase 3 in [12-phasing.md](12-phasing.md) cannot ship under this name without a rename.

This document's job is to keep both prices visible, not to relitigate either.

## 4. Risk register

| # | Risk | Severity | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 | Reddit revokes API access / bans the app | Medium | 🔴 High | Accept. Never collect through credentials shared with a partner-facing system. Keep an independent data path. | Build lead |
| 2 | Reddit contract action (the *Anthropic* theory) | High | 🟡 Low-Med *(conditional — see below)* | No proxy rotation or block circumvention; comply instantly on first contact. | Vlad |
| 3 | Takedown notice / DMCA from Reddit | Medium | 🟡 Medium | Pre-agreed rule: comply in full within 48 hours, no argument, no partial compliance. | Vlad |
| 4 | Individual commenter copyright claim over displayed comment text | Medium | 🟡 Low-Med | **None exists short of not displaying the text** ([0002](decisions/0002-display-full-mentions.md)). Authors own their comments and Reddit cannot license them ([Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms)). Permalink, username, and free removal cut the sympathy cost, not the claim. | Build lead |
| 5 | GDPR complaint or Art. 17 erasure request (usernames + comment text are pseudonymous personal data) | Medium | 🔴 Med-High | Published privacy notice with a documented legitimate-interests assessment ([EDPB Guidelines 1/2024](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202401_legitimateinterest_en.pdf)); working erasure route; retention cap. | Vlad + counsel |
| 6 | Defamation / trade libel from a brand placed in "Most Hated" | High | 🟡 Medium | The superlative ships and is priced in [0005](decisions/0005-superlative-labels.md). The measured variable appears beside it on every surface; methodology frozen, versioned, and published at `/methodology`; see §6. | Vlad |
| 7 | ⚠️ UDRP filed over redditindex.com, domain transferred ([Carey, D2020-1834](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html)) | Medium | 🟡 Medium *(rises with visibility, §4.2)* | **Nothing prevents a UDRP except not using the name.** Mitigation is recovery, not avoidance: `redditbrandindex.com` registered before launch, canonical host in one config value, links relative, `brandsonreddit.com` as the migration target ([0001](decisions/0001-name-reddit-index.md)). | Vlad |
| 8 | ⚠️ Reddit suspends "associated accounts, bots, domains, or subreddits" — reaching Empact's personas, aged accounts, and production Reddit agent | **Critical** | 🟡 Low-Med | Hard-separate infrastructure: distinct registrant, hosting, and API credentials, no shared IPs or accounts with partner operations. Never link Reddit Index from a Reddit comment. | Build lead |
| 9 | Outreach recast as a reputational shakedown | High | 🟡 Medium | Removal and correction always free, never mentioned near a commercial offer ([Mugshots.com charges](https://thecrimereport.org/2018/05/18/california-sues-mugshots-com-over-removal-fees/)); outreach shows only the recipient's own data. | Vlad |
| 10 | Small-n noise producing a visibly wrong ranking | Medium | 🔴 High | Minimum mention threshold; publish raw n and n_eff per brand; suppress below threshold. | Build lead |
| 11 | ⚠️ Empact partners, prospects, and Qvery competitors appear in rankings Empact operates | High | 🔴 High | Disclose every partner and related entity on the `/methodology` page; scoring blind to partner status; inclusion rule frozen before the first scoring run. See §4.1. | Vlad |

Risk 8 should govern architecture. The website is replaceable in a weekend. Empact's Reddit operation is years of aged accounts across roughly 28 partner projects (internal Empact figure), and it is the actual revenue line.

The name does not widen that blast radius, but it makes the trigger cheaper. A reddit-named domain is a standing, searchable signal, and the [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) reaches "domains" by name. Hard separation is what keeps risk 7 from becoming risk 8.

### 4.1 The conflict of interest runs both ways

Empact sells Reddit comment placement, and Empact has commercial relationships with companies the index ranks. Those are two separate conflicts and each needs its own control.

**Direction one — our content in the corpus.** Comments Empact placed on behalf of a partner could inflate that partner's score. The control is in [06-sentiment.md](06-sentiment.md): Empact-placed comments are identified and excluded from scoring.

**Direction two — our commercial interest in the result.** Empact partners, prospects, and vendors competing with Qvery land on the board. Excluding them quietly is a disclosed methodology exception a plaintiff reads as curation to commercial interest — the *Suzuki* fact pattern ([FindLaw](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html)).

**The rule:** partners and related entities are disclosed on the `/methodology` page, scoring is blind to partner status, and the inclusion rule is frozen before the first scoring run like every other methodology decision. A rule written after seeing who ranked where is the fact that loses the case.

### 4.2 Risk 2's likelihood is conditional, and the GTM contradicts it

The Low-Med rating on risk 2 assumes Reddit Index stays below Reddit's enforcement threshold. The plan does not. [10-seo-aeo.md](10-seo-aeo.md) makes being cited by AI engines the primary success metric, and [11-outreach-play.md](11-outreach-play.md) targets an annual PR study, 500+ ranked companies, ≥40 badge embeds, and ≥60 referring domains.

Low visibility and those targets are mutually exclusive. Either the likelihood is re-rated upward once the growth plan runs, or the growth targets are capped as a deliberate legal choice. [Decision 0002](decisions/0002-display-full-mentions.md) already names growing visibility as a revisit trigger; this note records that the register's number depends on it.

## 5. Mitigations to build in from day one

These are cheap, none is conditional on either priced decision, and every one improves our posture if a dispute starts.

| Mitigation | Why | Source |
|---|---|---|
| Username + permalink + "from Reddit" on every mention | Mandatory attribution; also makes the page verifiably honest | [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) |
| Nightly delete-sync purging deleted, removed, or edited content | Contractual duty ("as soon as possible"), and the most sympathetic fact we can hold | [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) |
| Zero ads, ever, anywhere on the domain | Ads convert an argument into a clear breach | [Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) |
| Free, fast, no-questions removal for Redditors and brands, never bundled with a sales offer | Kills the pay-to-remove narrative | [Mugshots.com charges](https://thecrimereport.org/2018/05/18/california-sues-mugshots-com-over-removal-fees/) |
| Methodology frozen and version-controlled **before** first scoring run | The fact that decides the defamation case | [Suzuki v. Consumers Union](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html) |
| The measured variable printed beside every superlative | "sentiment index 21/100 · 412 opinionated mentions · Jan–Jun 2026" is checkable; "Most Hated" alone is not | [Milkovich](https://supreme.justia.com/cases/federal/us/497/1/) |
| Plain-text company names, no logos | Nominative fair use limit | [New Kids on the Block](https://digitalcommons.law.ggu.edu/cgi/viewcontent.cgi?article=1631&context=ggulrev) |
| Non-affiliation notice in the footer of **every** page: "Not affiliated with, endorsed by, or sponsored by Reddit, Inc." | Implied affiliation is the theory UDRP panels actually run on, and the name invites it | [Carey, D2020-1834](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) |
| No Reddit visual identity, ever: no `#FF4500`, no Snoo, no Reddit Sans, no lookalike mark | Trade dress stacked on top of the name turns a survivable UDRP into an easy one | [Brand Guidelines](https://redditinc.com/hubfs/Reddit%20Inc/PDF/reddit_brand_guidelines_version_2022_2022-04-01-160548_akmi.pdf) |
| Defensive `redditbrandindex.com` registered **before** launch, redirecting to the primary | A defensive name bought after a complaint lands reads as bad faith, not protection | [0001](decisions/0001-name-reddit-index.md) |
| Migration plan kept warm: canonical host in one config value, all internal links relative, `brandsonreddit.com` as the target | A forced move should cost a day, not a quarter. "Brands on Reddit" is descriptive, with Reddit as the subject covered rather than the leading mark, which is a materially better UDRP posture | [0001](decisions/0001-name-reddit-index.md) |

The research recommended labelling the columns with the measured variable instead of a superlative. The owner chose "Most Loved" and "Most Hated," and that exposure is priced in [decision 0005](decisions/0005-superlative-labels.md), which carries the conditions the label is accepted under. It is not listed above, because a mitigation the product contradicts is not a mitigation in force.

## 6. Defamation

*Milkovich v. Lorain Journal*, 497 U.S. 1 (1990), killed the blanket opinion defence: a statement is actionable if it implies a provably false assertion of fact, however labelled ([Justia](https://supreme.justia.com/cases/federal/us/497/1/)). So the question is whether a ranking is provably false.

Two rulings say a disclosed-methodology comparative rating is not. In *Aviation Charter v. Aviation Research Group/US*, 416 F.3d 864 (8th Cir. 2005), a safety rating built from public databases was "a subjective interpretation of multiple objective data points" ([FindLaw](https://caselaw.findlaw.com/us-8th-circuit/1147137.html)).

In *ZL Technologies v. Gartner*, 709 F. Supp. 2d 789 (N.D. Cal. 2010), a $132M claim over Magic Quadrant placement was dismissed because "the general tenor of the MQ Report negates the impression that Gartner is asserting an objective fact" ([CourtListener](https://www.courtlistener.com/opinion/2540667/zl-technologies-inc-v-gartner-inc/)). The mechanism in both is disclosed, visibly subjective methodology.

The cautionary case is *Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003): summary judgment for the publisher was reversed because a jury could find the test course had been altered ([FindLaw](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html)). Method-tampering, not the verdict, is what reaches a jury.

**Operational rule:** freeze the methodology before seeing results, version-control it, log every scoring change with a timestamp, and never adjust it after seeing where a company landed. The fatal fact in *Suzuki* is an adjustment that makes a company rank **worse**. Our policy bans post-hoc changes in either direction, because a favourable one proves the dial turns.

⚠️ **Estonia is a materially worse flag than the US caselaw suggests.** In *Delfi AS v. Estonia* [GC], no. 64569/09 (2015), the ECtHR found no Article 10 violation where Estonian courts held a news portal liable for anonymous reader comments it merely hosted, even though it removed them on notice ([Columbia GFoE](https://globalfreedomofexpression.columbia.edu/cases/delfi-as-v-estonia/)).

Empact Partners OÜ is an Estonian entity, and Reddit Index does not merely host: it selects, ranks, and republishes comments with our own characterization on top. **INFERENCE:** worse than Delfi's posture, with no EU analogue to the US §230 shield that protected a republisher in [*Barrett v. Rosenthal*](https://caselaw.findlaw.com/court/ca-supreme-court/1282926.html).

UK-domiciled brands face a higher bar: s.1(2) of the Defamation Act 2013 requires a for-profit claimant to show serious financial loss ([legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2013/26/section/1)). Whether s.9 bars a US brand suing an Estonian publisher is **NOT VERIFIED**.

## 7. Nominative fair use and logos

*New Kids on the Block v. News America Publishing*, 971 F.2d 302 (9th Cir. 1992), permits referring to a marked product where it is not readily identifiable otherwise, only so much of the mark as is necessary is used, and nothing suggests sponsorship ([discussion](https://digitalcommons.law.ggu.edu/cgi/viewcontent.cgi?article=1631&context=ggulrev)).

Limb two is where logos fail. Plain-text word marks pass routinely; stylized logos, brand colors, and taglines do not. **Rule: plain-text company names only, no logos on a negative-ranking page, plus an explicit disclaimer of affiliation.** The EU referential-use provision in Art. 14(1)(c) EUTMR is **NOT VERIFIED** here.

**INFERENCE:** the same test run against REDDIT in our own name fails limbs two and three. Putting the mark in a product name uses more of it than identification requires, and leading with it reads as sponsorship. The name rests on the priced risk in [0001](decisions/0001-name-reddit-index.md), not on fair use, and this section should never be cited as covering it.

## 8. Litigation backdrop

Reddit is litigating on contract rather than copyright, and its contract theory has cleared its first procedural hurdle. Nothing has been decided on the merits, and no court has held that Reddit wins.

**Reddit v. Anthropic** (filed June 2025) was remanded to California state court on March 30, 2026, the court holding the contract, unjust-enrichment, trespass, and UCL claims contain "extra elements" and are therefore not preempted by the Copyright Act ([Crowell & Moring](https://www.crowell.com/en/insights/client-alerts/northern-district-of-california-court-holds-state-tort-and-contract-claims-not-preempted-by-federal-copyright-act-remands-reddit-v-anthropic-to-state-court), [Loeb](https://www.loeb.com/en/insights/publications/2026/04/reddit-inc-v-anthropic-pbc)).

Reddit brought no copyright claim there. It sued on its terms of use, and surviving preemption is what matters to us: that is the theory reaching derived data and aggregate scores, and it is now proceeding.

In **Reddit v. Perplexity, SerpApi, Oxylabs and AWMProxy** (S.D.N.Y., filed October 22, 2025), the DMCA §1201 circumvention claims survived dismissal around August 1, 2026, while unfair competition and unjust enrichment were dismissed as preempted ([Law.com](https://www.law.com/newyorklawjournal/2026/07/31/reddits-dmca-claims-against-perplexity-serpapi-survive-ai-scraping-challenge/)).

That case is about proxy rotation and block circumvention at scale. **Hard rule: never route around a Reddit block, never rotate IPs to evade rate limits, never strip Reddit content out of SERPs.** That conduct turns a contract dispute into a §1201 claim.

Reddit locked down robots.txt in 2024 and restricted the Internet Archive to its homepage in 2025 ([report](https://www.yahoo.com/news/articles/reddit-blocking-internet-archive-halt-092725165.html)). The direction of travel is one way, and it is not toward us.

---

[← Back to README](README.md) · [Naming decision](decisions/0001-name-reddit-index.md) · [Display decision](decisions/0002-display-full-mentions.md) · [Data acquisition and storage](02-data-acquisition.md) · [Phase 1 category list](data/phase1-categories.csv)
