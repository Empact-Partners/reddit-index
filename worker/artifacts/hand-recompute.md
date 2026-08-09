# Hand recomputation — hubspot in crm

Every number below can be checked without running anything. The sample is
20 mentions chosen by a documented seed (20260806) over the doc_id ordering, so
regenerating it produces exactly these twenty.


> This verifies the ESTIMATOR'S ARITHMETIC on a 20-mention subset. It is not
> an estimate of hubspot: the published figure below runs over the whole
> in-window corpus.


## The twenty mentions

| # | label | subreddit | author | matched | permalink |
|---|---|---|---|---|---|
| 1 | neutral | r/CRM | u/BasicsOnly | `hubspot` | https://www.reddit.com/r/CRM/comments/1l45o7l/anyone_here_whos_moved_from_hubspot_to_attio/mwamb82/ |
| 2 | neutral | r/CRM | u/mujhekyamaitoaurathu | `hubspot` | https://www.reddit.com/r/CRM/comments/1uqf9cb/crm_for_small_business/p00wbnr/ |
| 3 | neutral | r/CRM | u/Top-Wish-5520 | `hubspot` | https://www.reddit.com/r/CRM/comments/1sw7f9p/we_spent_800_month_on_clay_apollo_and_hubspot_and/omh9qvh/ |
| 4 | positive | r/sales | u/TheGrowthMentor | `hubspot` | https://www.reddit.com/r/sales/comments/1lkjral/what_crm_should_we_use/n04txft/ |
| 5 | positive | r/CRM | u/Marcelc | `hubspot` | https://www.reddit.com/r/CRM/comments/1ne8y3d/zoho_vs_hubspot_vs_salesforce/ndqik7c/ |
| 6 | positive | r/sales | u/Choice_Breakfast435 | `hubspot` | https://www.reddit.com/r/sales/comments/1lkjral/what_crm_should_we_use/mzwr5o8/ |
| 7 | positive | r/CRM | u/Adorable-Reindeer280 | `hubspot` | https://www.reddit.com/r/CRM/comments/1tvlwhb/best_startup_crm_for_2050_person_teams_were/oq7n787/ |
| 8 | negative | r/CRM | u/Ok_Low_5480 | `hubspot` | https://www.reddit.com/r/CRM/comments/1l45o7l/anyone_here_whos_moved_from_hubspot_to_attio/mwad6ii/ |
| 9 | positive | r/CRM | u/Ok-Prompt3555 | `hubspot` | https://www.reddit.com/r/CRM/comments/1oo696l/dynamics_365_sales_to_hubspot_migration/nn8b7pu/ |
| 10 | positive | r/sales | u/Fit_Height_8490 | `hubspot` | https://www.reddit.com/r/sales/comments/1sa191f/hubspot_mm_ae_worth_it/odsjfy9/ |
| 11 | negative | r/CRM | u/OriginalARG | `hubspot` | https://www.reddit.com/r/CRM/comments/1lvqqs8/help_me_avoid_800mo_hubspot_increase_pipedrive/ |
| 12 | positive | r/sales | u/Desperate-Purpose342 | `hubspot` | https://www.reddit.com/r/sales/comments/1r2svmv/i_am_using_a_crm_and_i_feel_like_its_just_a/o4z4zy1/ |
| 13 | positive | r/revops | u/cmullins70 | `hubspot` | https://www.reddit.com/r/revops/comments/1mvanz8/hubspot_alternatives/nuv5hhs/ |
| 14 | negative | r/CRM | u/Mammoth_Savings3855 | `hubspot` | https://www.reddit.com/r/CRM/comments/1tk3b2l/need_help_choosing_and_setting_up_a_crm_for_my/ |
| 15 | negative | r/CRM | u/GoodLifeExperience | `hubspot` | https://www.reddit.com/r/CRM/comments/1o1yxhz/hubspot_to_ghl_feedback/nlta5y0/ |
| 16 | negative | r/CRM | u/Quick-Performer-4670 | `hubspot` | https://www.reddit.com/r/CRM/comments/1eytc08/attio_vs_folk_which_crm_can_grow_with_my_business/nrcmr1a/ |
| 17 | negative | r/CRM | u/CurlyAce84 | `hubspot` | https://www.reddit.com/r/CRM/comments/1mwudbb/want_to_build_landing_pagesfunnel_hubspot_or_ghl/na09eq7/ |
| 18 | neutral | r/CRM | u/Wrong-Mood9032 | `hubspot` | https://www.reddit.com/r/CRM/comments/1tfkgso/help_new_in_hubspot/ |
| 19 | neutral | r/CRM | u/TheGrowthMentor | `hubspot` | https://www.reddit.com/r/CRM/comments/1k5qroz/zoho_vs_hubspot/mon68hm/ |
| 20 | positive | r/CRM | u/South-Reference-8865 | `hubspot` | https://www.reddit.com/r/CRM/comments/1q57eah/top_crm_enrichment_tools_for_enterprise/ny3hb5b/ |

## The arithmetic, longhand
```
x_pos  = 9
x_neg  = 6
neu    = 5     (counted and published, never in the denominator)
abstain= 0
N_op   = 9 + 6 = 15

category prior, fitted leave-one-out over every other crm brand with N_op >= 30
  alpha0 = 13.701
  beta0  = 6.299

p_tilde = (x_pos + alpha0) / (N_op + alpha0 + beta0)
        = (9 + 13.701) / (15 + 13.701 + 6.299)
        = 22.7010 / 35.0000
        = 0.648600
Reddit Love Score = round(100 * 0.648600) = 65
```

## Three independent computations of the same number

| route | value |
|---|---|
| longhand, above | **65** |
| worker/score.py, same inputs | **65** |
| Postgres, independent code path | **65** |

Paste-able check: `=ROUND(100*(9+13.701)/(15+13.701+6.299),0)`

## The published figure, for contrast

- whole in-window corpus: n = 1115, N_op = 805, n_eff = 400.2
- eligible: **False**
- failed test: **n_eff** — 400 observed against 600 required
