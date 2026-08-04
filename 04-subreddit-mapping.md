# Category → Subreddit Mapping

## Bottom line

- Reddit brand signal is **not** proportional to subscriber count. [r/PasswordManagers](https://www.reddit.com/r/PasswordManagers/) (54,639 subs) yields more rankable brand comparison than [r/marketing](https://www.reddit.com/r/marketing/) (1,958,653 subs), because r/marketing's rules delete exactly that content.
- r/marketing produces **~2 surviving posts/day** against [r/SaaS](https://www.reddit.com/r/SaaS/)'s **122 to ~350**, depending on the counting method. Either end leaves the gap intact: it is a moderation artifact, not audience absence.
- Rule posture is the primary mapping variable. A sub that bans product mentions is a dead source no matter how many people are in it. Map to rule-permissive subs, not big ones.
- Spread, not volume, decides rankability. Eligibility gates on `n_eff ≥ 400` ([07-index-methodology.md](07-index-methodology.md)), and mentions packed into one mega-thread barely move `n_eff`.
- Traps confirmed live: [r/figma](https://www.reddit.com/r/figma/) is a Japanese action-figure sub, search stem-matches ("Descript" → "description"), and `search_reddit` with `type='sr'` returns nothing under app-only OAuth.
- 🔴 **ERP** and **Help Desk/Support** cannot be ranked honestly. They ship labelled "insufficient Reddit signal to rank," not ranked anyway.
- **12 of the 50 Phase 1 categories are mapped; 38 are still `pending`.** Machine-readable in [data/subreddit-map.csv](data/subreddit-map.csv) (131 rows, 12 categories, `rule_posture` and `is_vendor_owned_sub`) and [data/phase1-categories.csv](data/phase1-categories.csv).

## Verified general subs

All counts pulled 2026-08-04 via `get_subreddit_info`. Volume is extrapolated from the 10 newest posts in each `new` feed, so it measures **surviving** posts after moderation, not submissions.

| Sub | Subscribers | ~Posts/day | Read |
|---|---|---|---|
| [r/Entrepreneur](https://www.reddit.com/r/Entrepreneur/) | 5,248,886 | ~6 | Huge, near-silent |
| [r/productivity](https://www.reddit.com/r/productivity/) | 4,231,779 | ~13 | Rule-suppressed |
| [r/webdev](https://www.reddit.com/r/webdev/) | 3,291,845 | ~13 | Rule-suppressed |
| [r/smallbusiness](https://www.reddit.com/r/smallbusiness/) | 2,515,668 | ~160 | Mentions deleted |
| [r/marketing](https://www.reddit.com/r/marketing/) | 1,958,653 | **~2** | Effectively closed |
| [r/sysadmin](https://www.reddit.com/r/sysadmin/) | 1,307,063 | ~32 | 🟢 Permissive |
| [r/Accounting](https://www.reddit.com/r/Accounting/) | 1,272,842 | ~95 | 🟢 Live |
| [r/selfhosted](https://www.reddit.com/r/selfhosted/) | 812,909 | ~42 | 🟢 Live |
| [r/SaaS](https://www.reddit.com/r/SaaS/) | 771,351 | **~350** | 🟢 Highest volume |
| [r/devops](https://www.reddit.com/r/devops/) | 505,306 | ~8 | Thin |
| [r/ExperiencedDevs](https://www.reddit.com/r/ExperiencedDevs/) | 408,343 | ~3 | Thin |
| [r/msp](https://www.reddit.com/r/msp/) | 245,249 | ~3 | Karma-gated |
| [r/projectmanagement](https://www.reddit.com/r/projectmanagement/) | 235,409 | ~2.5 | Thin, on-topic |
| [r/humanresources](https://www.reddit.com/r/humanresources/) | 234,776 | ~14 | 🟢 Live |
| [r/NoteTaking](https://www.reddit.com/r/NoteTaking/) | 63,318 | ~5 | Small, on-topic |
| [r/CustomerService](https://www.reddit.com/r/CustomerService/) | 56,709 | ~6 | 🔴 Misrouted |

⚠️ **Volume depends on method.** A second measurement the same day, spanning the last 100 posts in `/new`, gave r/SaaS **122/day** against the ~350 above, plus r/sysadmin 25, r/webdev 20, r/devops 6, r/projectmanagement 3, r/marketing 2 ([02-data-acquisition.md](02-data-acquisition.md)).

Five of those six agree within roughly 1.4×. Only r/SaaS diverges, by nearly 3×, because the 10-newest extrapolation counts posts that have not yet cleared moderation removal. The ordering is stable under both methods, so the mapping calls below hold. Quote the range, never one figure as measured fact.

## The map: 12 assessed categories

Subscriber counts verified individually 2026-08-04. Full row-per-subreddit form in [data/subreddit-map.csv](data/subreddit-map.csv).

| Category | Subreddits (subscribers) | Verdict |
|---|---|---|
| **CRM** | CRM 55,258 · sales 594,293 · salesforce 113,701 · techsales 61,611 · SaaS 771,351 · smallbusiness · Entrepreneur · EntrepreneurRideAlong 717,181 · hubspot 22,276 · gohighlevel 22,997 · Dynamics365 15,274 · Zoho 12,656 · Netsuite 26,757 | 🟢 Rich |
| **Project Mgmt** | projectmanagement 235,409 · pmp 127,324 · agile 86,940 · scrum 45,282 · Notion 466,660 · jira 16,789 · clickup 20,100 · trello 13,038 · Asana 7,610 · productivity · devops · ExperiencedDevs | 🟢 Rich |
| **Marketing Automation** | marketing 1,958,653 · DigitalMarketing 444,279 · PPC 276,512 · SEO 501,557 · Emailmarketing 121,644 · ecommerce 664,181 · shopify 368,664 · copywriting 259,811 · hubspot · gohighlevel · salesforce · Klaviyo 7,906 | 🟡 Rich but rule-suppressed |
| **Accounting** | Accounting 1,272,842 · tax 471,648 · BusinessIntelligence 239,162 (restricted) · CPA 125,475 · Bookkeeping 82,702 · QuickBooks 40,925 · Payroll 34,153 · Netsuite · ERP 18,180 · smallbusiness · Entrepreneur | 🟢 Rich |
| **HR / HRIS** | AskHR 1,845,104 · humanresources 234,776 · recruiting 210,024 · Payroll 34,153 · smallbusiness · Entrepreneur · Accounting | 🟢 Rich (r/recruitinghell, r/talentacquisition counts NOT VERIFIED) |
| **Help Desk / Support** | sysadmin 1,307,063 · msp 245,249 · ITManagers 77,186 · CustomerService 56,709 · CustomerSuccess 53,226 · servicenow 37,616 · helpdesk 17,828 · Zendesk 5,995 · SaaS · shopify | 🔴 Thin + misrouted |
| **Email Marketing** | ecommerce 664,181 · SEO · DigitalMarketing · shopify 368,664 · copywriting 259,811 · Emailmarketing 121,644 · marketing · MailChimp 11,411 · Klaviyo 7,906 · SaaS | 🟡 Rich, DTC-skewed |
| **Design / Prototyping** | webdev 3,291,845 · graphic_design 2,915,697 · web_design 974,146 · UXDesign 245,262 · UI_Design 236,904 · FigmaDesign 154,567 · userexperience 147,493 · canva 97,460 · webflow 42,290 · Adobe 41,119 | 🟡 Rich, monoculture |
| **Video Editing** | NewTubers 713,161 · VideoEditing 521,861 · videography 451,620 · AfterEffects 344,668 · davinciresolve 224,963 · editors 193,209 · premiere 184,965 · CapCut 98,513 · finalcutpro 41,381 · Adobe | 🟡 Rich for NLEs, thin for SaaS video |
| **Password Mgrs / Security** | privacy 1,652,252 · cybersecurity 1,499,209 · selfhosted 812,909 · netsec 568,416 · sysadmin · msp · Bitwarden 119,758 · ITManagers · 1Password 56,814 · PasswordManagers 54,639 · ProtonPass 35,219 · KeePass 23,021 | 🟢 Richest |
| **ERP** | BusinessIntelligence 239,162 · supplychain 112,776 · manufacturing 100,336 · SAP 60,630 · Netsuite 26,757 · Odoo 19,483 · ERP 18,180 · Dynamics365 15,274 · Accounting · smallbusiness | 🔴 Thin |
| **Note-taking / KM** | productivity 4,231,779 · Notion 466,660 · ObsidianMD 350,650 · PKMS 76,430 · OneNote 75,635 · NoteTaking 63,318 · Zettelkasten 39,054 · Evernote 27,159 · logseq 19,678 · Anytype 14,127 · selfhosted | 🟢 Rich |

## The rules that kill brand signal

Rule text pulled 2026-08-04 via the Reddit API `get_subreddit_rules`. This is the highest-value section: rule posture predicts yield better than any size metric.

| Sub | Rule that suppresses brand signal | Effect |
|---|---|---|
| [r/smallbusiness](https://www.reddit.com/r/smallbusiness/about/rules) | Rule 2, as of June 2026: product mentions removed from new posts or comments if they appear **directly or indirectly promotional**. Rule 5 bans market-research posts. | 🔴 2.5M subs actively deleting brand mentions |
| [r/marketing](https://www.reddit.com/r/marketing/about/rules) | "Zero tolerance policy to Advertising, Self-Promotion & Spam" (permanent ban), AI-content permaban, 30-day account + 300-karma posting gate | 🔴 Explains ~2 posts/day |
| [r/Entrepreneur](https://www.reddit.com/r/Entrepreneur/about/rules) | "Do not use this community to sell, promote… No dropping URLs." | 🔴 6 posts/day at 5.2M subs |
| [r/SaaS](https://www.reddit.com/r/SaaS/about/rules) | Promotion capped at max 1 mention or 3 links per 60 days; disclosure mandatory; violation = ban + URL blacklist | 🟡 Organic talk survives |
| [r/sysadmin](https://www.reddit.com/r/sysadmin/about/rules) | No advertising, but "Vendors are free to discuss their product in the context of an existing discussion" | 🟢 Why it stays high-signal |
| [r/msp](https://www.reddit.com/r/msp/about/rules) | Vendor promotion confined to the Weekly Promo thread; **50 in-sub comment karma** required to post | 🟡 Organic threads fine, thin |
| [r/ecommerce](https://www.reddit.com/r/ecommerce/about/rules) | No external links, described as the most strictly enforced rule | 🟡 Mentions survive, links do not |
| [r/productivity](https://www.reddit.com/r/productivity/about/rules) | "Self-promotion is not allowed here in any form, even if asked for recommendations" + no listicles | 🔴 Kills the thread type we need |
| [r/webdev](https://www.reddit.com/r/webdev/about/rules) | No commercial promotion; project sharing on Saturdays only | 🟡 13 posts/day at 3.3M subs |

⚠️ Rule posture drifts. r/smallbusiness changed in June 2026 and cut a top-five source down to noise. Re-pull rules before every ingest cycle and write the result to the `rule_posture` column, or the map silently rots.

## Traps, verified live

**Name collision.** [r/figma](https://www.reddit.com/r/figma/) (14,737) is a Japanese action-figure subreddit. The design tool sub is [r/FigmaDesign](https://www.reddit.com/r/FigmaDesign/) (154,567). Never resolve a subreddit by lowercasing a product name.

**Stem matching.** Reddit search stems query terms. "Descript" in [r/VideoEditing](https://www.reddit.com/r/VideoEditing/) returned 15 results, roughly 8 of which matched the word "description". Short brand names need a post-search exact-token filter.

**Discovery is broken.** `search_reddit` with `type='sr'` returned zero results for every query tried (CRM, marketing automation, accounting, HR) under app-only OAuth. Candidate names must be supplied manually.

## Empirical signal tests

Seven scoped searches, `sort=relevance`, `t=all`. These are the calibration set: any new category should be tested this way before it is mapped.

| Query | Results | Evidence |
|---|---|---|
| "HubSpot" in r/CRM | 100 + cursor, densely opinionated | ["Zoho vs Hubspot vs Salesforce"](https://reddit.com/r/CRM/comments/1ne8y3d/zoho_vs_hubspot_vs_salesforce/) (63 comments) · ["I hate Hubspot"](https://reddit.com/r/CRM/comments/1mcr4d4/i_hate_hubspot_its_like_blunt_force_trauma_to_the/) (37 / 66) |
| "Bitwarden" in r/PasswordManagers | 100 + cursor, near-100% on-topic | ["Bitwarden BAD NEWS"](https://reddit.com/r/PasswordManagers/comments/1te4lcp/bitwarden_bad_news/) (192 / 147) · ["password manager tier list"](https://reddit.com/r/PasswordManagers/comments/1up6rfa/techlore_just_dropped_a_password_manager_tier_list/) (148 / 117) |
| "Workday" in r/humanresources | 25 + cursor, head-to-head | ["[CA] Paylocity v UKG v Workday"](https://reddit.com/r/humanresources/comments/1ujw5dy/ca_paylocity_v_ukg_v_workday/) (80 comments) |
| "NetSuite" in r/Accounting | 25 + cursor | ["QBO is too small, Netsuite is too expensive. What's a middle ground?"](https://reddit.com/r/Accounting/comments/1ojgbg5/qbo_is_too_small_netsuite_is_too_expensive_whats/) (71 comments) |
| "ClickUp" in r/projectmanagement | 25 + cursor | ["Project management tools ranked + comparison table (2026 update)"](https://reddit.com/r/projectmanagement/comments/1r7dr5i/project_management_tools_ranked_comparison_table/) (143 comments) |
| "Klaviyo" in r/Emailmarketing | 15 + cursor, all on-topic | ["Cheaper Alternatives to Klaviyo"](https://reddit.com/r/Emailmarketing/comments/1msuvn1/cheaper_alternatives_to_klaviyo/) (59 comments) |
| "Zendesk" in r/msp · "Odoo" in r/ERP · "Descript" in r/VideoEditing | 🔴 Failed | Zendesk hits are 2016–2019 (stale). Odoo: 15 total, top thread from 2023, most under 30 comments. Descript: majority false positives |

**The mechanical pass mark.** At least 25 results with a live `after` cursor; a top thread under three years old; and 50+ comments naming three or more brands spread across **at least three threads in two or more subreddits**, never concentrated in one.

The spread clause is not fussiness. Eligibility gates on `n_eff ≥ 400`, where `n_eff = n / DEFF` and `DEFF = 1 + (m̄ − 1)·ICC` ([07-index-methodology.md](07-index-methodology.md)). Mentions inside one thread are correlated, so a single 500-comment recommendation thread inflates raw `n` while `n_eff` barely moves. Spread survives the design-effect correction; volume alone does not.

## Vendor-owned and single-product subreddits

Single-product subs (r/hubspot, r/Notion, r/Bitwarden, r/1Password, r/clickup, r/QuickBooks, r/Zendesk, and similar) self-select for users already invested in the product. Whether each is officially vendor-run is **NOT VERIFIED** and does not change the hazard — self-selection produces the bias regardless of who holds the mod queue.

**Specification decision** (a design choice, not a measured result): flag every such sub with `is_vendor_owned_sub=yes` in [data/subreddit-map.csv](data/subreddit-map.csv). Exclude those rows from loved/hated sentiment scoring and from the consolidated ranking table.

They stay eligible for one thing: brand-page evidence, displayed with a visible "from the product's own subreddit" label so a reader can discount it. Criticism inside a product's own sub is the strongest negative signal available; praise there is worthless.

## Honesty flags

🔴 here means the category failed the signal test badly enough that no brand in it is likely to clear `n_eff ≥ 400` on spread-corrected mentions. Marked as inference: the verdict comes from probe results, not from a computed `n_eff`. Such a category ships as a page saying so, never as a ranking.

🔴 **ERP.** Thin across every mapped sub. "Odoo" in r/ERP returned 15 results total, top thread from 2023, most under 30 comments. Labelled "insufficient Reddit signal to rank."

🔴 **Help Desk / Support.** Misrouted. r/CustomerService (56,709) is a retail-horror-story sub, not a software sub, and r/msp results for Zendesk are 2016–2019. Labelled "insufficient Reddit signal to rank."

🟡 **Design / Prototyping.** Ranks Figma against everything credibly. Cannot separate ranks 4–10 — the sub cluster is a Figma monoculture. Publish a top-3 with the tail marked unranked.

🟡 **Video Editing.** Ranks NLEs (Premiere, Resolve, Final Cut, CapCut) but not SaaS video tools. Publish the NLE ranking, exclude the SaaS video segment.

⚠️ A "insufficient Reddit signal to rank" page is a shippable outcome and must be built as a real template. The failure mode is ranking a category anyway because the page exists and the outreach list wants it.

## Mapping the remaining 38 Phase 1 categories

Twelve of the 50 Phase 1 categories are mapped and signal-tested above. The other **38 carry `subreddit_map_status=pending`** in [data/phase1-categories.csv](data/phase1-categories.csv). Run this procedure per category, in order, and write the outcome back to both CSVs in the same commit.

1. **Enumerate candidates by hand.** Automated discovery is unavailable. Draw from three sources: the general subs table above, one sub per known brand in [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv), and the practitioner sub for the buyer's job function.
2. **Resolve each name via `get_subreddit_info`.** Confirm subscriber count and description. This is the step that catches r/figma. Never accept a name unread.
3. **Pull rules via `get_subreddit_rules`.** Classify posture as permissive, capped, or prohibitive into `rule_posture`. Prohibitive subs are dropped regardless of size.
4. **Measure surviving volume** from the 10 newest posts. Under ~5/day, the sub is supporting evidence only, never a category's primary source.
5. **Run the empirical signal test** on the category's two largest brands against the pass mark above. Record how the hits spread across threads and subreddits, not just the totals: spread is what the design-effect correction consumes.
6. **Flag single-product subs** as `is_vendor_owned_sub=yes` before the category ships.
7. **Assign the verdict**: rich, rule-suppressed, or thin. Thin routes to the "insufficient Reddit signal to rank" template.
8. **Write the result back.** Add one row per subreddit to [data/subreddit-map.csv](data/subreddit-map.csv) and flip that category's `subreddit_map_status` to `mapped` in [data/phase1-categories.csv](data/phase1-categories.csv), together. Two files disagreeing on what is mapped is how this map rots unnoticed.

Categories are cheap to declare unrankable and expensive to publish wrongly. When steps 4 and 5 disagree, the signal test wins.

---

[← Back to README](README.md) · [Category taxonomy](03-taxonomy.md) · [Data acquisition and the API ceiling](02-data-acquisition.md) · [Index methodology and the eligibility gate](07-index-methodology.md)
