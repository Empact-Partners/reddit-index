# Legal Position and Risk Register

⚠️ **This is not legal advice.** It is an internal risk document written from primary sources by non-lawyers. Before ugcranks.com goes live, get an Estonian data-protection opinion and a US media-law read on the final page copy. Nothing below is a clearance to publish.

## Bottom line

- Reddit's terms do not permit what UGC Ranks does. A business may not "access or use any of the Reddit Services and Data by or on behalf of a business," and that restriction expressly reaches derived data ([Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms)).
- Displaying stored comment text breaches the narrow display licence in [Data API Terms §2.4](https://www.redditinc.com/policies/data-api-terms) and Developer Terms §4.2 simultaneously. Links back and usernames are required whatever else we do.
- Aggregate-only scores would not fix the contract problem. Data API Terms §6 reaches "any data or models that were derived from User Content." Aggregation helps on copyright, not on contract, and contract is what Reddit wins on.
- The name is the one thing already handled correctly. "Reddit" is out of the product name and the domain per Data API Terms §4.1, which removes the risk with the cheapest, most proven enforcement path against us.
- ⚠️ The real asset at stake is not this website. The [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) permits Reddit to suspend "associated accounts, bots, domains, or subreddits" — which reaches Empact's live Reddit operation across roughly 28 partner projects.
- Owner decision, recorded: we display full comment text with links back, knowingly, without a Reddit agreement. That is a priced risk, not a compliant design, and this document does not pretend otherwise.

## 1. The clause-level table

Two contracts bind. **Data API Terms** — effective June 19, 2023, last revised **July 20, 2026** ([text](https://www.redditinc.com/policies/data-api-terms)). **Developer Terms** — effective September 24, 2024, last revised **March 24, 2026** ([text](https://www.redditinc.com/policies/developer-terms)).

| Clause | What it says | What it means for UGC Ranks |
|---|---|---|
| [Data API Terms §2.4](https://www.redditinc.com/policies/data-api-terms) | Non-exclusive, revocable licence to "copy and display the User Content using the Data API"; "You may not modify the User Content except to format it for such display." | A ranking computed from comments is arguably not "display." Our brand pages are display plus derivation. 🔴 |
| [Data API Terms §3.1](https://www.redditinc.com/policies/data-api-terms) | Commercial purposes, or any use "not expressly permitted," require "a separate agreement with Reddit." | We have no such agreement. An Empact-operated lead-gen asset is commercial on any reading. 🔴 |
| [Data API Terms §3.2](https://www.redditinc.com/policies/data-api-terms) | No deriving revenues without express written approval; must "immediately delete" any data not required for the approved use case. | No approved use case exists, so every stored comment is arguably data we must delete. 🔴 |
| [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) | "You are not permitted to use the Reddit Trademarks in, or as part of the name of your App," or in logos promoting it. | Satisfied. The product is UGC Ranks on ugcranks.com. No Reddit wordmark in name, domain, or logo. 🟢 |
| [Data API Terms §4.2](https://www.redditinc.com/policies/data-api-terms) | The only licensed wordmark form is "[insert name] for Reddit." | We do not use it, and should not adopt it later without checking whether it implies affiliation. 🟢 |
| [Data API Terms §6](https://www.redditinc.com/policies/data-api-terms) | On termination, delete cached or stored User Content "including any data or models that were derived from User Content and Materials." | Termination obligates deleting the rankings, not just the comment store. The whole site is derived data. 🔴 |
| [Developer Terms §2.2](https://www.redditinc.com/policies/developer-terms) | Defines "Reddit Services and Data" to include content "obtained through or otherwise derived from" the Services. | This definition is what makes §4.1 reach our scores, not only raw comments. 🔴 |
| [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) | If content is deleted, protected, suspended, withheld, modified, or removed, you must delete or modify it "as soon as possible." | Requires a nightly delete-sync job. This one we should build regardless of everything else. 🟡 |
| [Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms) | No access or use "by or on behalf of a business or as part of a service or product that is monetized"; no revenue "including from any data derived from the foregoing." | The core breach. Empact Partners operating it openly is exactly the fact pattern this clause names. 🔴 |
| [Developer Terms §4.2](https://www.redditinc.com/policies/developer-terms) | No derivative works, copying, reproduction, redistribution, or syndication; no behavior "likely to violate our Public Content Policy." | Republishing comment bodies on our own pages is reproduction and redistribution. 🔴 |
| [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) | Attribution is mandatory: "a link back to the User Content on our Services, cite the applicable User's username, and clearly indicate that the User Content is from our Services." | Cheap and non-negotiable. Every mention gets permalink, username, "from Reddit." 🟡 |
| [Developer Terms §7.3](https://www.redditinc.com/policies/developer-terms) | Deletion on Reddit's request, on the user's request, or when retention is no longer necessary. | Requires a working removal route for individual Redditors, not only for brands. 🟡 |
| [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) | Approval required before accessing data; no commercialization "without express written approval," extending to "commercial and non-commercial mining, scraping." Enforcement includes suspending "associated accounts, bots, domains, or subreddits." | The blast-radius clause. See risk 8. 🔴 |

The Responsible Builder Policy also prohibits "processing data to derive or infer potentially sensitive characteristics about Reddit users." Scoring *brands* is fine under that line. Profiling *individual users* is not, and we must never build it.

## 2. Reddit names this exact use case

Reddit's [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) lists "companies that help brands monitor trends associated with their brands" among its data licensee categories. That describes Empact Partners.

The same policy says you may use Reddit content "for non-commercial uses, such as learning and community, but talk to us if you have commercial purposes in mind." Licensees also may not keep displaying content deleted by Redditors or removed by Reddit.

Reddit's developer documentation lists "Free product features available for upsell" as commercial use, and answers "No" to displaying Reddit content alongside ads ([Developer Platform: Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)).

**INFERENCE:** a free, ad-free site that exists to open sales conversations is "a free product feature available for upsell." Ad-free helps far less than it feels like it should.

## 3. The decision, stated plainly

UGC Ranks will display full Reddit comment text on brand pages, with links back to the original threads. The owner reviewed the clauses above and chose this. Recorded here as a decision, not a finding of compliance.

This breaches Data API Terms §2.4, §3.1, and §3.2, Developer Terms §4.1 and §4.2, and the Responsible Builder Policy. It adds per-commenter copyright exposure an aggregate-only site would not carry.

What it buys is the product itself: the outreach asset only works because a founder can read the actual sentences. This document's job is to keep the price visible, not to relitigate it.

## 4. Risk register

| # | Risk | Severity | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 | Reddit revokes API access / bans the app | Medium | 🔴 High | Accept. Never collect through credentials shared with a partner-facing system. Keep an independent data path. | Build lead |
| 2 | Reddit contract action (the *Anthropic* theory) | High | 🟡 Low-Med | Stay small; no proxy rotation or block circumvention; comply instantly on first contact. | Vlad |
| 3 | Takedown notice / DMCA from Reddit | Medium | 🟡 Medium | Pre-agreed rule: comply in full within 48 hours, no argument, no partial compliance. | Vlad |
| 4 | Individual commenter copyright claim over a quoted comment | Low | 🟡 Low-Med | Short excerpts where possible; permalink + username; free removal on request. | Build lead |
| 5 | GDPR complaint or Art. 17 erasure request (usernames + comment text are pseudonymous personal data) | Medium | 🔴 Med-High | Published privacy notice with a documented legitimate-interests assessment ([EDPB Guidelines 1/2024](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202401_legitimateinterest_en.pdf)); working erasure route; retention cap. | Vlad + counsel |
| 6 | Defamation / trade libel from a brand placed in "most hated" | High | 🟡 Medium | Frame as the measured variable; freeze and publish methodology; see §6. | Vlad |
| 7 | UDRP or trademark action over the domain | Low | 🟢 Low | Already mitigated by dropping "reddit" from the name ([Reddit v. Carey, WIPO D2020-1834](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html)). | Done |
| 8 | ⚠️ Reddit suspends "associated accounts, bots, domains, or subreddits" — reaching Empact's personas, aged accounts, and production Reddit agent | **Critical** | 🟡 Low-Med | Hard-separate infrastructure: distinct registrant, hosting, and API credentials, no shared IPs or accounts with partner operations. Never link UGC Ranks from a Reddit comment. | Build lead |
| 9 | Outreach recast as a reputational shakedown | High | 🟡 Medium | Removal and correction always free, never mentioned near a commercial offer ([Mugshots.com charges](https://thecrimereport.org/2018/05/18/california-sues-mugshots-com-over-removal-fees/)); outreach shows only the recipient's own data. | Vlad |
| 10 | Small-n noise producing a visibly wrong ranking | Medium | 🔴 High | Minimum mention threshold; publish n per brand; suppress below threshold. | Build lead |

Risk 8 should govern architecture. The website is replaceable in a weekend. Empact's Reddit operation is years of aged accounts across roughly 28 partner projects, and it is the actual revenue line.

## 5. Mitigations to build in from day one

These are cheap, none is conditional on the display decision, and every one improves our posture if a dispute starts.

| Mitigation | Why | Source |
|---|---|---|
| Username + permalink + "from Reddit" on every mention | Mandatory attribution; also makes the page verifiably honest | [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) |
| Nightly delete-sync purging deleted, removed, or edited content | Contractual duty, and the most sympathetic fact we can hold | [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) |
| Zero ads, ever, anywhere on the domain | Ads convert an argument into a clear breach | [Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) |
| Free, fast, no-questions removal for Redditors and brands, never bundled with a sales offer | Kills the pay-to-remove narrative | [Mugshots.com charges](https://thecrimereport.org/2018/05/18/california-sues-mugshots-com-over-removal-fees/) |
| Methodology frozen and version-controlled **before** first scoring run | The fact that decides the defamation case | [Suzuki v. Consumers Union](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html) |
| Labels state the measured variable, not a superlative | "Lowest sentiment score, Reddit, Jan–Jun 2026" is a measurement; "most hated" is a claim about the world | [Milkovich](https://supreme.justia.com/cases/federal/us/497/1/) |
| Plain-text company names, no logos | Nominative fair use limit | [New Kids on the Block](https://digitalcommons.law.ggu.edu/cgi/viewcontent.cgi?article=1631&context=ggulrev) |

## 6. Defamation

*Milkovich v. Lorain Journal*, 497 U.S. 1 (1990), killed the blanket opinion defence: a statement is actionable if it implies a provably false assertion of fact, however labelled ([Justia](https://supreme.justia.com/cases/federal/us/497/1/)). So the question is whether a ranking is provably false.

Two rulings say a disclosed-methodology comparative rating is not. In *Aviation Charter v. Aviation Research Group/US*, 416 F.3d 864 (8th Cir. 2005), a safety rating built from public databases was "a subjective interpretation of multiple objective data points" ([FindLaw](https://caselaw.findlaw.com/us-8th-circuit/1147137.html)).

In *ZL Technologies v. Gartner*, 709 F. Supp. 2d 789 (N.D. Cal. 2010), a $132M claim over Magic Quadrant placement was dismissed because "the general tenor of the MQ Report negates the impression that Gartner is asserting an objective fact" ([CourtListener](https://www.courtlistener.com/opinion/2540667/zl-technologies-inc-v-gartner-inc/)). The mechanism in both is disclosed, visibly subjective methodology.

The cautionary case is *Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003): summary judgment for the publisher was reversed because a jury could find the test course had been altered ([FindLaw](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html)). Method-tampering, not the verdict, is what reaches a jury.

**Operational rule:** freeze the methodology before seeing results, version-control it, log every scoring change with a timestamp, and never adjust it after seeing where a company landed. One post-hoc tweak is the fatal fact.

⚠️ **Estonia is a materially worse flag than the US caselaw suggests.** In *Delfi AS v. Estonia* [GC], no. 64569/09 (2015), the ECtHR found no Article 10 violation where Estonian courts held a news portal liable for anonymous reader comments it merely hosted, even though it removed them on notice ([Columbia GFoE](https://globalfreedomofexpression.columbia.edu/cases/delfi-as-v-estonia/)).

Empact Partners OÜ is an Estonian entity, and UGC Ranks does not merely host: it selects, ranks, and republishes comments with our own characterization on top. **INFERENCE:** worse than Delfi's posture, with no EU analogue to the US §230 shield that protected a republisher in [*Barrett v. Rosenthal*](https://caselaw.findlaw.com/court/ca-supreme-court/1282926.html).

UK-domiciled brands face a higher bar: s.1(2) of the Defamation Act 2013 requires a for-profit claimant to show serious financial loss ([legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2013/26/section/1)). Whether s.9 bars a US brand suing an Estonian publisher is **NOT VERIFIED**.

## 7. Nominative fair use and logos

*New Kids on the Block v. News America Publishing*, 971 F.2d 302 (9th Cir. 1992), permits referring to a marked product where it is not readily identifiable otherwise, only so much of the mark as is necessary is used, and nothing suggests sponsorship ([discussion](https://digitalcommons.law.ggu.edu/cgi/viewcontent.cgi?article=1631&context=ggulrev)).

Limb two is where logos fail. Plain-text word marks pass routinely; stylized logos, brand colors, and taglines do not. **Rule: plain-text company names only, no logos on a negative-ranking page, plus an explicit disclaimer of affiliation.** The EU referential-use provision in Art. 14(1)(c) EUTMR is **NOT VERIFIED** here.

## 8. Litigation backdrop

Reddit is litigating, and winning on contract rather than copyright. **Reddit v. Anthropic** (filed June 2025) was remanded to California state court on March 30, 2026, the court holding the contract, unjust-enrichment, trespass, and UCL claims contain "extra elements" and are not preempted by the Copyright Act ([Crowell & Moring](https://www.crowell.com/en/insights/client-alerts/northern-district-of-california-court-holds-state-tort-and-contract-claims-not-preempted-by-federal-copyright-act-remands-reddit-v-anthropic-to-state-court), [Loeb](https://www.loeb.com/en/insights/publications/2026/04/reddit-inc-v-anthropic-pbc)).

Reddit brought no copyright claim there. It sued on its terms of use, the theory that reaches derived data and aggregate scores.

In **Reddit v. Perplexity, SerpApi, Oxylabs and AWMProxy** (S.D.N.Y., filed October 22, 2025), the DMCA §1201 circumvention claims survived dismissal around August 1, 2026, while unfair competition and unjust enrichment were dismissed as preempted ([Law.com](https://www.law.com/newyorklawjournal/2026/07/31/reddits-dmca-claims-against-perplexity-serpapi-survive-ai-scraping-challenge/)).

That case is about proxy rotation and block circumvention at scale. **Hard rule: never route around a Reddit block, never rotate IPs to evade rate limits, never strip Reddit content out of SERPs.** That conduct turns a contract dispute into a §1201 claim.

Reddit locked down robots.txt in 2024 and restricted the Internet Archive to its homepage in 2025 ([report](https://www.yahoo.com/news/articles/reddit-blocking-internet-archive-halt-092725165.html)). The direction of travel is one way, and it is not toward us.

---

[← Back to README](README.md) · [Data acquisition and storage](02-data-acquisition.md) · [Phase 1 category list](data/phase1-categories.csv)
