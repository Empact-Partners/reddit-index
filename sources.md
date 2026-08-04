# Sources

Every external source cited across this repo, grouped. **160 unique URLs**, all fetched or verified on **2026-08-04** unless the entry says otherwise.

## Bottom line

- The whole legal argument rests on **four Reddit documents**. They are short. Read them yourself rather than trusting the summaries here.
- Reddit terms carry revision dates that matter: **Data API Terms last revised 2026-07-20**, **Developer Terms last revised 2026-03-24**. Both changed within months of this research. Re-check before building.
- Reddit thread URLs are cited as **evidence of signal density**, not as data. They are public permalinks. Some will 404 over time as content is deleted, which is itself the reason [01-legal.md](01-legal.md) requires a delete-sync job.
- Where a claim could not be traced to a primary source it is marked **NOT VERIFIED** in place. Those are listed under Limits in the [README](README.md).

## The load-bearing four

Everything in [01-legal.md](01-legal.md) and [decisions/0002](decisions/0002-display-full-mentions.md) reduces to these:

| Document | Why it decides the project |
|---|---|
| [Data API Terms](https://redditinc.com/policies/data-api-terms) | §3.1 commercial use needs a separate agreement · §4.1 no Reddit marks in the app name · §6 deletion reaches derived data |
| [Developer Terms](https://redditinc.com/policies/developer-terms) | §4.1 no use "by or on behalf of a business" · §5.2 mandatory attribution · §3.3 delete-sync |
| [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) | Names "companies that help brands monitor trends associated with their brands" as a licensee category |
| [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) | Permits suspending "associated accounts, bots, domains, or subreddits" — the blast-radius clause |

## All sources

### Reddit — terms, policies and documentation

| Source | Cited in |
|---|---|
| [PRAW docs](https://praw.readthedocs.io/en/stable/code_overview/other/listinggenerator.html) | [02-data-acquisition.md](02-data-acquisition.md) |
| [data-api-terms](https://redditinc.com/policies/data-api-terms) | [00-concept.md](00-concept.md) |
| [Developer Platform: Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) | [01-legal.md](01-legal.md) |
| [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) | [02-data-acquisition.md](02-data-acquisition.md), [08-architecture.md](08-architecture.md) |
| [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) | [01-legal.md](01-legal.md), [decisions/0002-display-full-mentions.md](decisions/0002-display-full-mentions.md) |
| [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) | [01-legal.md](01-legal.md), [05-entity-resolution.md](05-entity-resolution.md), [decisions/0002-display-full-mentions.md](decisions/0002-display-full-mentions.md) |
| [Data API Terms §3.2](https://www.redditinc.com/policies/data-api-terms) | [01-legal.md](01-legal.md) |
| [Developer Terms §4.2](https://www.redditinc.com/policies/developer-terms) | [01-legal.md](01-legal.md), [08-architecture.md](08-architecture.md) |

### Reddit — threads and subreddits cited as evidence

| Source | Cited in |
|---|---|
| ["QBO is too small, Netsuite is too expensive. What's a middle ground?"](https://reddit.com/r/Accounting/comments/1ojgbg5/qbo_is_too_small_netsuite_is_too_expensive_whats/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| ["I hate Hubspot"](https://reddit.com/r/CRM/comments/1mcr4d4/i_hate_hubspot_its_like_blunt_force_trauma_to_the/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| ["Zoho vs Hubspot vs Salesforce"](https://reddit.com/r/CRM/comments/1ne8y3d/zoho_vs_hubspot_vs_salesforce/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| ["Cheaper Alternatives to Klaviyo"](https://reddit.com/r/Emailmarketing/comments/1msuvn1/cheaper_alternatives_to_klaviyo/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| ["Bitwarden BAD NEWS"](https://reddit.com/r/PasswordManagers/comments/1te4lcp/bitwarden_bad_news/) | [04-subreddit-mapping.md](04-subreddit-mapping.md), [12-phasing.md](12-phasing.md) |
| ["password manager tier list"](https://reddit.com/r/PasswordManagers/comments/1up6rfa/techlore_just_dropped_a_password_manager_tier_list/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| ["Project management tools ranked + comparison table (2026 update)"](https://reddit.com/r/projectmanagement/comments/1r7dr5i/project_management_tools_ranked_comparison_table/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/Accounting](https://www.reddit.com/r/Accounting/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/CustomerService](https://www.reddit.com/r/CustomerService/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/Entrepreneur](https://www.reddit.com/r/Entrepreneur/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/Entrepreneur](https://www.reddit.com/r/Entrepreneur/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/ExperiencedDevs](https://www.reddit.com/r/ExperiencedDevs/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/FigmaDesign](https://www.reddit.com/r/FigmaDesign/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/NoteTaking](https://www.reddit.com/r/NoteTaking/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/PasswordManagers](https://www.reddit.com/r/PasswordManagers/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/SaaS](https://www.reddit.com/r/SaaS/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/SaaS](https://www.reddit.com/r/SaaS/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/VideoEditing](https://www.reddit.com/r/VideoEditing/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/devops](https://www.reddit.com/r/devops/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/ecommerce](https://www.reddit.com/r/ecommerce/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/figma](https://www.reddit.com/r/figma/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/humanresources](https://www.reddit.com/r/humanresources/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/marketing](https://www.reddit.com/r/marketing/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/marketing](https://www.reddit.com/r/marketing/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/msp](https://www.reddit.com/r/msp/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/msp](https://www.reddit.com/r/msp/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/productivity](https://www.reddit.com/r/productivity/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/productivity](https://www.reddit.com/r/productivity/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/projectmanagement](https://www.reddit.com/r/projectmanagement/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/redditdev](https://www.reddit.com/r/redditdev/comments/30a7ap/does_reddit_api_limit_total_listings_returned_to/) | [02-data-acquisition.md](02-data-acquisition.md) |
| [r/selfhosted](https://www.reddit.com/r/selfhosted/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/smallbusiness](https://www.reddit.com/r/smallbusiness/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/smallbusiness](https://www.reddit.com/r/smallbusiness/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/sysadmin](https://www.reddit.com/r/sysadmin/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/sysadmin](https://www.reddit.com/r/sysadmin/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/webdev](https://www.reddit.com/r/webdev/) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |
| [r/webdev](https://www.reddit.com/r/webdev/about/rules) | [04-subreddit-mapping.md](04-subreddit-mapping.md) |

### Litigation and case law

| Source | Cited in |
|---|---|
| [*Barrett v. Rosenthal*](https://caselaw.findlaw.com/court/ca-supreme-court/1282926.html) | [01-legal.md](01-legal.md) |
| [Suzuki v. Consumers Union](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html) | [01-legal.md](01-legal.md) |
| [FindLaw](https://caselaw.findlaw.com/us-8th-circuit/1147137.html) | [01-legal.md](01-legal.md) |
| [New Kids on the Block](https://digitalcommons.law.ggu.edu/cgi/viewcontent.cgi?article=1631&context=ggulrev) | [01-legal.md](01-legal.md) |
| [Columbia GFoE](https://globalfreedomofexpression.columbia.edu/cases/delfi-as-v-estonia/) | [01-legal.md](01-legal.md) |
| [Milkovich](https://supreme.justia.com/cases/federal/us/497/1/) | [01-legal.md](01-legal.md) |
| [Mugshots.com charges](https://thecrimereport.org/2018/05/18/california-sues-mugshots-com-over-removal-fees/) | [01-legal.md](01-legal.md) |
| [ZL Technologies v. Gartner](https://www.courtlistener.com/opinion/2540667/zl-technologies-inc-v-gartner-inc/) | [00-concept.md](00-concept.md), [01-legal.md](01-legal.md) |
| [Crowell & Moring](https://www.crowell.com/en/insights/client-alerts/northern-district-of-california-court-holds-state-tort-and-contract-claims-not-preempted-by-federal-copyright-act-remands-reddit-v-anthropic-to-state-court) | [01-legal.md](01-legal.md) |
| [EDPB Guidelines 1/2024](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202401_legitimateinterest_en.pdf) | [01-legal.md](01-legal.md) |
| [Law.com](https://www.law.com/newyorklawjournal/2026/07/31/reddits-dmca-claims-against-perplexity-serpapi-survive-ai-scraping-challenge/) | [01-legal.md](01-legal.md) |
| [legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2013/26/section/1) | [01-legal.md](01-legal.md) |
| [Loeb](https://www.loeb.com/en/insights/publications/2026/04/reddit-inc-v-anthropic-pbc) | [01-legal.md](01-legal.md) |
| [`reddit.co`](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html) | [decisions/0001-name-reddit-index.md](decisions/0001-name-reddit-index.md) |
| [Reddit v. Carey, WIPO D2020-1834](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) | [00-concept.md](00-concept.md), [01-legal.md](01-legal.md), [decisions/0001-name-reddit-index.md](decisions/0001-name-reddit-index.md) |

### Data archives and vendors

| Source | Cited in |
|---|---|
| [2026-06 torrent](https://academictorrents.com/details/3bac8bd352bbb74bbb23df4273cf3da5d66ee5a5) | [02-data-acquisition.md](02-data-acquisition.md) |
| [2026-01](https://academictorrents.com/details/8412b89151101d88c915334c45d9c223169a1a60) | [02-data-acquisition.md](02-data-acquisition.md) |
| [Apify actors](https://apify.com/automation-lab/reddit-scraper) | [02-data-acquisition.md](02-data-acquisition.md) |
| [Bright Data datasets](https://brightdata.com/products/datasets/reddit) | [02-data-acquisition.md](02-data-acquisition.md) |
| [Actions limits](https://docs.github.com/en/actions/reference/limits) | [08-architecture.md](08-architecture.md) |
| [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) | [02-data-acquisition.md](02-data-acquisition.md) |
| [download_links.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md) | [02-data-acquisition.md](02-data-acquisition.md) |
| [tweeteval leaderboard](https://github.com/cardiffnlp/tweeteval) | [06-sentiment.md](06-sentiment.md) |
| [pushshift/Reddit-Bot-Detector](https://github.com/pushshift/Reddit-Bot-Detector) | [06-sentiment.md](06-sentiment.md) |
| [Reddit v. SerpApi, Reddit v. Perplexity](https://www.coronium.io/blog/is-web-scraping-legal-2026) | [10-seo-aeo.md](10-seo-aeo.md) |

### Methodology — academic and statistical

| Source | Cited in |
|---|---|
| [task page](http://noisy-text.github.io/2017/emerging-rare-entities.html) | [05-entity-resolution.md](05-entity-resolution.md) |
| [Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/) | [07-index-methodology.md](07-index-methodology.md) |
| [EMNLP 2021](https://aclanthology.org/2021.emnlp-main.322/) | [06-sentiment.md](06-sentiment.md) |
| [GLiNER NAACL 2024](https://aclanthology.org/2024.naacl-long.300.pdf) | [05-entity-resolution.md](05-entity-resolution.md) |
| [COLING 2025](https://aclanthology.org/2025.coling-main.217/) | [06-sentiment.md](06-sentiment.md) |
| [arXiv 2208.01368](https://arxiv.org/abs/2208.01368) | [06-sentiment.md](06-sentiment.md) |
| [arXiv 2606.02255](https://arxiv.org/abs/2606.02255) | [06-sentiment.md](06-sentiment.md) |
| [arXiv 2408.01257v2](https://arxiv.org/html/2408.01257v2) | [06-sentiment.md](06-sentiment.md) |
| [arXiv 2412.12564v3](https://arxiv.org/html/2412.12564v3) | [06-sentiment.md](06-sentiment.md) |
| [ReFinED](https://arxiv.org/pdf/2207.04108) | [05-entity-resolution.md](05-entity-resolution.md) |
| [ELEVANT](https://arxiv.org/pdf/2305.14937) | [05-entity-resolution.md](05-entity-resolution.md) |
| [ELLEN](https://arxiv.org/pdf/2403.17385) | [05-entity-resolution.md](05-entity-resolution.md) |
| [arXiv 2405.18061](https://arxiv.org/pdf/2405.18061) | [06-sentiment.md](06-sentiment.md) |
| [arXiv 2408.13202](https://arxiv.org/pdf/2408.13202) | [06-sentiment.md](06-sentiment.md) |
| [arXiv 2601.16800](https://arxiv.org/pdf/2601.16800) | [06-sentiment.md](06-sentiment.md) |
| [bi-encoder](https://arxiv.org/pdf/2602.18487) | [05-entity-resolution.md](05-entity-resolution.md) |
| [SemEval-2026 DimABSA](https://arxiv.org/pdf/2604.07066) | [06-sentiment.md](06-sentiment.md) |
| [binomial proportion CI](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval) | [07-index-methodology.md](07-index-methodology.md) |
| [model card](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest) | [06-sentiment.md](06-sentiment.md) |
| [model card](https://huggingface.co/siebert/sentiment-roberta-large-english) | [06-sentiment.md](06-sentiment.md) |
| [Cacioppo, Gardner & Berntson, 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2) | [07-index-methodology.md](07-index-methodology.md), [decisions/0004-two-axis-index.md](decisions/0004-two-axis-index.md) |
| [evanmiller.org](https://www.evanmiller.org/how-not-to-sort-by-average-rating.html) | [07-index-methodology.md](07-index-methodology.md) |
| [Computers 14(3):95](https://www.mdpi.com/2073-431X/14/3/95) | [06-sentiment.md](06-sentiment.md) |
| [overview](https://www.researchgate.net/publication/258110327_Overview_of_RepLab_2013_Evaluating_Online_Reputation_Monitoring_Systems) | [05-entity-resolution.md](05-entity-resolution.md) |
| [Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466) | [07-index-methodology.md](07-index-methodology.md), [decisions/0004-two-axis-index.md](decisions/0004-two-axis-index.md) |
| [Zarantonello et al.](https://www.sciencedirect.com/science/article/abs/pii/S0148296319302590) | [07-index-methodology.md](07-index-methodology.md), [decisions/0004-two-axis-index.md](decisions/0004-two-axis-index.md) |
| [ScienceDirect S1877050925014280](https://www.sciencedirect.com/science/article/pii/S1877050925014280) | [06-sentiment.md](06-sentiment.md) |
| [API call](https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Linear&language=en&format=json&limit=10) | [05-entity-resolution.md](05-entity-resolution.md) |
| [API call](https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Vercel&language=en&format=json&limit=5) | [05-entity-resolution.md](05-entity-resolution.md) |
| [database download](https://www.wikidata.org/wiki/Wikidata:Database_download) | [05-entity-resolution.md](05-entity-resolution.md) |

### Ranking and rating precedents

| Source | Cited in |
|---|---|
| [IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV) | [07-index-methodology.md](07-index-methodology.md) |
| [Metacritic](https://metacritichelp.zendesk.com/hc/en-us/articles/14478499933079-How-do-you-compute-METASCORES) | [07-index-methodology.md](07-index-methodology.md) |
| [free public scorecard](https://securityscorecard.com/free-account-public-scorecard/) | [11-outreach-play.md](11-outreach-play.md) |
| [SecurityScorecard free tier](https://securityscorecard.com/pricing-packages/free/) | [11-outreach-play.md](11-outreach-play.md) |
| [ACSI](https://theacsi.com/solutions/acsi-logo-licensing) | [11-outreach-play.md](11-outreach-play.md) |
| [HubSpot Website Grader](https://www.hubspot.com/blog/bid/2411/100-000-Website-Hopefuls-Try-To-Make-The-Grade-In-Internet-Marketing) | [11-outreach-play.md](11-outreach-play.md) |
| [U.S. Chamber of Commerce, Principles for Fair and Accurate Security Ra](https://www.uschamber.com/security/cybersecurity/principles-for-fair-and-accurate-security-ratings) | [11-outreach-play.md](11-outreach-play.md) |
| [YouGov BrandIndex Lite](https://yougov.com/business/products/brandindex-lite) | [00-concept.md](00-concept.md) |

### Taxonomy — G2, Capterra, public classifications

| Source | Cited in |
|---|---|
| [G2 badge docs](https://documentation.g2.com/docs/g2-badges) | [11-outreach-play.md](11-outreach-play.md) |
| [G2](https://documentation.g2.com/docs/research-scoring-methodologies) | [07-index-methodology.md](07-index-methodology.md) |
| [G2 ToU](https://legal.g2.com/terms-of-use) | [05-entity-resolution.md](05-entity-resolution.md) |
| [content usage](https://sell.g2.com/content-usage-guidelines) | [05-entity-resolution.md](05-entity-resolution.md) |
| [capterra.com/categories/](https://www.capterra.com/categories/) | [03-taxonomy.md](03-taxonomy.md), [decisions/0003-g2-taxonomy-spine.md](decisions/0003-g2-taxonomy-spine.md) |
| [Terms of Use](https://www.capterra.com/legal/terms-of-use/) | [03-taxonomy.md](03-taxonomy.md), [data/README.md](data/README.md), [decisions/0003-g2-taxonomy-spine.md](decisions/0003-g2-taxonomy-spine.md) |
| [robots.txt](https://www.capterra.com/robots.txt) | [03-taxonomy.md](03-taxonomy.md), [decisions/0003-g2-taxonomy-spine.md](decisions/0003-g2-taxonomy-spine.md) |
| [NAICS 513210](https://www.census.gov/naics/?input=513210&year=2022&details=513210) | [03-taxonomy.md](03-taxonomy.md) |
| [g2.com/categories](https://www.g2.com/categories) | [03-taxonomy.md](03-taxonomy.md) |

### SEO, AI citation and search

| Source | Cited in |
|---|---|
| [Ahrefs, 16.975M URLs](https://ahrefs.com/blog/do-ai-assistants-prefer-to-cite-fresh-content/) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Ahrefs, May 2026](https://ahrefs.com/blog/llmstxt-study/) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Ahrefs](https://ahrefs.com/blog/schema-ai-citations/) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Google, Nov 2024](https://developers.google.com/search/blog/2024/11/site-reputation-abuse) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Google](https://developers.google.com/search/docs/appearance/ai-features) | [10-seo-aeo.md](10-seo-aeo.md) |
| [carousel docs](https://developers.google.com/search/docs/appearance/structured-data/carousel) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Google review snippet docs](https://developers.google.com/search/docs/appearance/structured-data/review-snippet) | [10-seo-aeo.md](10-seo-aeo.md), [11-outreach-play.md](11-outreach-play.md) |
| [crawl budget docs](https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Google spam policies](https://developers.google.com/search/docs/essentials/spam-policies) | [10-seo-aeo.md](10-seo-aeo.md), [11-outreach-play.md](11-outreach-play.md) |
| [Search Engine Land](https://searchengineland.com/reddit-sues-perplexity-serpapi-scraping-google-463681) | [02-data-acquisition.md](02-data-acquisition.md) |
| [SE Ranking](https://seranking.com/blog/google-may-2026-core-update-analysis/) | [00-concept.md](00-concept.md), [10-seo-aeo.md](10-seo-aeo.md) |
| [SE Ranking, 30K keywords / 22,729 AIOs, 2025-12-01](https://seranking.com/blog/review-platforms-in-ai-overviews/) | [10-seo-aeo.md](10-seo-aeo.md) |
| [eMarketer](https://www.emarketer.com/content/reddit-weekly-search-activity-jumps-30-yoy-boosting-ad-intent-user-reach) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Ahrefs data summary](https://www.quattr.com/blog/takeaway-from-ahrefs-ai-search-study) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Semrush 3-month study](https://www.semrush.com/blog/most-cited-domains-ai/) | [10-seo-aeo.md](10-seo-aeo.md), [11-outreach-play.md](11-outreach-play.md) |
| [TechTarget](https://www.techtarget.com/whatis/feature/Reddit-pricing-API-charge-explained) | [02-data-acquisition.md](02-data-acquisition.md) |

### Infrastructure and model pricing

| Source | Cited in |
|---|---|
| [ClickHouse](https://clickhouse.com/pricing) | [08-architecture.md](08-architecture.md) |
| [BigQuery](https://cloud.google.com/bigquery/pricing) | [08-architecture.md](08-architecture.md) |
| [R2 pricing](https://developers.cloudflare.com/r2/pricing/) | [08-architecture.md](08-architecture.md) |
| [OpenAI](https://developers.openai.com/api/docs/pricing) | [06-sentiment.md](06-sentiment.md) |
| [DuckDB news](https://duckdb.org/news/) | [08-architecture.md](08-architecture.md) |
| [Vantage](https://instances.vantage.sh/aws/ec2/g5.xlarge) | [06-sentiment.md](06-sentiment.md) |
| [Anthropic](https://platform.claude.com/docs/en/pricing) | [06-sentiment.md](06-sentiment.md) |
| [Supabase compute & disk](https://supabase.com/docs/guides/platform/compute-and-disk) | [08-architecture.md](08-architecture.md) |
| [Supabase pricing](https://supabase.com/pricing) | [08-architecture.md](08-architecture.md) |
| [Vercel limits](https://vercel.com/docs/limits) | [08-architecture.md](08-architecture.md) |

### Prior art and market

| Source | Cited in |
|---|---|
| [ApeWisdom](https://apewisdom.io/api/) | [00-concept.md](00-concept.md) |
| [apewisdom.io/methodology](https://apewisdom.io/methodology/) | [00-concept.md](00-concept.md) |
| [pricing](https://brandfetch.com/developers/pricing) | [05-entity-resolution.md](05-entity-resolution.md) |
| [gummysearch.com](https://gummysearch.com/) | [00-concept.md](00-concept.md) |
| [octolens.com](https://octolens.com/reddit-monitoring) | [05-entity-resolution.md](05-entity-resolution.md) |
| [CNBC](https://www.cnbc.com/2026/07/22/reddit-stock-google-ai-content-deal.html) | [02-data-acquisition.md](02-data-acquisition.md) |
| [PRNewswire](https://www.prnewswire.com/news-releases/g2-to-acquire-capterra-software-advice-and-getapp-from-gartner-302673901.html) | [00-concept.md](00-concept.md) |
| [Profound Index](https://www.tryprofound.com/profound-index) | [00-concept.md](00-concept.md) |
| [report](https://www.yahoo.com/news/articles/reddit-blocking-internet-archive-halt-092725165.html) | [01-legal.md](01-legal.md) |

### Outreach and GTM evidence

| Source | Cited in |
|---|---|
| [datavlab guide](https://datavlab.ai/post/inter-annotator-agreement-llm-evaluation-guide) | [06-sentiment.md](06-sentiment.md) |
| [2026 write-up](https://dev.to/agenthustler/crunchbase-api-in-2026-free-tier-gone-what-startup-data-hunters-do-now-1177) | [05-entity-resolution.md](05-entity-resolution.md) |
| [Anagram](https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026) | [10-seo-aeo.md](10-seo-aeo.md) |
| [Conbersa, vendor source](https://www.conbersa.ai/learn/reddit-bot-detection-2026) | [06-sentiment.md](06-sentiment.md) |
| [Gong cold email stats](https://www.gong.io/blog/cold-email-stats) | [11-outreach-play.md](11-outreach-play.md) |
| [Gong's benchmark is 344 emails per meeting](https://www.gong.io/blog/does-cold-email-even-work-any-more-heres-what-the-data-says) | [11-outreach-play.md](11-outreach-play.md) |
| [Leapd](https://www.leapd.ai/blog/ai-visibility/how-chatgpt-google-ai-overviews-and-perplexity-source-information-in-2026) | [10-seo-aeo.md](10-seo-aeo.md) |
| [reporteroutreach.com, aggregating Digitaloft / Reboot / BuzzStream](https://www.reporteroutreach.com/blog/digital-pr-statistics) | [11-outreach-play.md](11-outreach-play.md) |
---

## How to re-verify

Reddit's terms pages are the only ones that change often enough to matter. Both carry a "Last Revised" line at the top:

```
https://redditinc.com/policies/data-api-terms
https://redditinc.com/policies/developer-terms
```

If either date has moved past those in the table above, re-read [01-legal.md](01-legal.md) against the new text before doing anything else.

---

[← Back to README](README.md) · [Method](method.md) · [Legal position](01-legal.md)
