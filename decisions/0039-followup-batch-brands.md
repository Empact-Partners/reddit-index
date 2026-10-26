# 0039 — The follow-up batch's brands in the index

Date: 2026-10-26. Status: accepted. Decided by Vlad Shvets (the partner-development follow-up batch, 22 to 26 Oct
2026), executed by Claude (session 5 of the batch). Follows decision 0018's route for adding brands.

## Context

The follow-up emails of the partner-development batch link each company's Reddit Index page. 55 companies in the
batch manifest (`index_need: add_brand`) had no brand in the index; 7 more (Gratifii, Sofy, Act-On, Feathery, Lago,
Leadspace, Referral Rock) are brands without a page yet. On the evening of 26 Oct Vlad re-scoped Pomelo to Zepz:
Zepz acquired Pomelo's product in January 2026 and paused it, so Pomelo is not added and Zepz's two brands,
WorldRemit and Sendwave, are. That makes 56 new brands.

## What changes

| | |
|---|---|
| Brands | 56 rows appended to `data/brand-seed-expand.csv`, `source = empact-followups-2026-10`; `gen_brands.py` adds 56 brands and 141 surface forms and changes no existing row |
| Categories | none added: every brand sits in one of the 159 (0018: a 160th needs `parent_id`) |
| Review | every row by hand, against each company's own site (the pages the batch's research read on 26 Oct); the changes and the hard calls in `data/phase-b/brand-review-log-0039.csv` |
| Load | `worker/load.py --seed --only-changed origin/main` from the branch before the merge, 26 Oct 2026: 56 brands, 141 aliases; brands 10,745 in all; parity 56 of 56 by slug and primary category |
| Backfill | `ops/schedule.json` `backfill.categories` gains the 42 primary categories of the new and the 7 page-less brands, ordered by the batch's send queue (earliest first). About 295 core subreddits that no earlier backfill swept; the 8 partner categories of 0018 stay first and are done |

## How the rows were made

0018's route, with one change: the rows were drafted by Claude while reading each company's site summary, not by a
lab, because the hand review needs that same read and the batch needed the brands loaded before the night of 26 Oct.
No paid API was used: the site pages were the ones the batch's research had already read.

## Calls worth knowing

- **Affinity CRM** (`affinity-crm`, affinity.co) is its own brand. `/affinity` is Affinity the photo and design app
  (Serif/Canva) and keeps its row untouched; a seed row named "Affinity" would only have widened it again (gen_brands
  keys rows on `brand.lower()`). The CRM disables the bare word and stops on Affinity Photo, Designer, Publisher,
  Serif and Canva.
- **Spike.sh** beside Spike (spikenow.com), **Kore** (kore.co) beside Kore.ai: the new rows add no bare form the
  existing brands own.
- **Ordinary words** (Sentiment, Gleam, Cello, Wonka, Kore): bare form disabled, matched by domain and qualified forms.
  **Rare words with another meaning** (Velaro the train, Vinify the verb, Parafin the misspelling, Corebook the RPG
  rulebook, Zelt the tent): HOSTILE with stop contexts. Togal, Yoti, ClassLink, Ekster: AMBIGUOUS.
- **No fitting category**: Baabuk (wool footwear) and Ekster (wallets) are in ecommerce as direct-to-consumer stores;
  brightwheel (childcare) in lms; Alpha Progression (a consumer gym app) in fitness-business-management; Funded
  Trading Plus (a prop trading firm) in crypto-trading. Their boards rank them beside software they do not compete
  with; the batch's email session knows.

## The brands

| Brand | Slug | Primary category | Bare form |
|---|---|---|---|
| Lasso Moderation | `lasso-moderation` | community-platforms | SAFE |
| TestingBot | `testingbot` | software-test-automation | SAFE |
| Aftershoot | `aftershoot` | photo-editing | SAFE |
| Botcopy | `botcopy` | ai-agent-platforms | SAFE |
| FitBudd | `fitbudd` | fitness-business-management | SAFE |
| Gleam | `gleam` | affiliate-referral-marketing | HOSTILE |
| Optimal Workshop | `optimal-workshop` | survey-tools | SAFE |
| Payhip | `payhip` | ecommerce | SAFE |
| Sentiment | `sentiment` | help-desk | HOSTILE |
| Spike.sh | `spike-sh` | observability | SAFE |
| SweetProcess | `sweetprocess` | wikis | SAFE |
| Aiosell | `aiosell` | hotel-management | SAFE |
| Parafin | `parafin` | loan-management | HOSTILE |
| Plutio | `plutio` | invoicing | SAFE |
| Synsona | `synsona` | marketing-automation | SAFE |
| Testlify | `testlify` | recruiting | SAFE |
| Togal | `togal` | construction | AMBIGUOUS |
| Adzact | `adzact` | marketing-automation | SAFE |
| Affinity CRM | `affinity-crm` | crm | SAFE |
| Amlyze | `amlyze` | aml-financial-crime | SAFE |
| Baabuk | `baabuk` | ecommerce | SAFE |
| Blended Tech | `blended-tech` | inventory | SAFE |
| BoomPop | `boompop` | event-management | SAFE |
| Cello | `cello` | affiliate-referral-marketing | HOSTILE |
| Chamaileon | `chamaileon` | email-marketing | SAFE |
| ClassLink | `classlink` | identity | AMBIGUOUS |
| Corebook | `corebook` | digital-asset-management | HOSTILE |
| Crimsoni | `crimsoni` | writing-assistants | SAFE |
| DemandFarm | `demandfarm` | crm | SAFE |
| Ditto Music | `ditto-music` | music-production | SAFE |
| Dyspatch | `dyspatch` | email-marketing | SAFE |
| Ekster | `ekster` | ecommerce | AMBIGUOUS |
| Funded Trading Plus | `funded-trading-plus` | crypto-trading | SAFE |
| EmailGenius | `emailgenius` | email-marketing | SAFE |
| HashLedger | `hashledger` | accounting | SAFE |
| HumanFirst | `humanfirst` | llm-operations | SAFE |
| Idomoo | `idomoo` | ai-video | SAFE |
| Kore | `kore` | help-desk | HOSTILE |
| Mailizio | `mailizio` | email-marketing | SAFE |
| brightwheel | `brightwheel` | lms | SAFE |
| Personizely | `personizely` | feature-flags | SAFE |
| WorldRemit | `worldremit` | payment-processing | SAFE |
| Sendwave | `sendwave` | payment-processing | SAFE |
| PullFlow | `pullflow` | ai-coding | SAFE |
| Reevo | `reevo` | crm | SAFE |
| Sharadar | `sharadar` | investment-research | SAFE |
| UXarmy | `uxarmy` | survey-tools | SAFE |
| Velaro | `velaro` | live-chat | HOSTILE |
| Vinify | `vinify` | inventory | HOSTILE |
| Voiseed | `voiseed` | voice-ai | SAFE |
| Wonka | `wonka` | recruiting | HOSTILE |
| Yoti | `yoti` | identity | AMBIGUOUS |
| Zelt | `zelt` | hr | HOSTILE |
| Alpha Progression | `alpha-progression` | fitness-business-management | SAFE |
| Dedalus Labs | `dedalus-labs` | cloud-hosting | SAFE |
| Vablet | `vablet` | sales-enablement | SAFE |

## Not changed

The sweep's code, the night window, the 1.9 GB line (0035), the weekly full-backup day (0038: no backfill pass on
Wed 28 Oct). The tracker's mentions stay out of `public.mentions` (0018).
