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
| 1 | positive | r/revops | u/yauheniban | `hubspot` | https://www.reddit.com/r/revops/comments/1jlzq42/hubspot_vs_salesforce_vs_pipedrive_which_crm_is/mkckwxi/ |
| 2 | positive | r/revops | u/Zmchastain | `hubspot` | https://www.reddit.com/r/revops/comments/1st3vdf/can_someone_explain_why_hubspot_has_gotten_so/ohuje7c/ |
| 3 | negative | r/CRM | u/Common-Strawberry122 | `hubspot` | https://www.reddit.com/r/CRM/comments/1nmsur8/crm_for_professional_services_firm/nffawuh/ |
| 4 | positive | r/CRM | u/Superb_Buffalo8689 | `hubspot` | https://www.reddit.com/r/CRM/comments/1kmiuxq/hubspot_vs_pipedrive_vs_monday/msc76c7/ |
| 5 | neutral | r/CRM | u/Phantomsf | `hubspot` | https://www.reddit.com/r/CRM/comments/1vbii5u/we_are_finally_moving_our_business_off_of_sheets/p0trbw0/ |
| 6 | neutral | r/CRM | u/justtosubscribe | `hubspot` | https://www.reddit.com/r/CRM/comments/1nh689o/need_help_selecting_a_crm/ |
| 7 | positive | r/CRM | u/GrowthRunner1 | `hubspot` | https://www.reddit.com/r/CRM/comments/1sd6w3q/teams_leaving_pipedrive/oelqobb/ |
| 8 | neutral | r/CRM | u/Weekly-Pizza7952 | `hubspot` | https://www.reddit.com/r/CRM/comments/1qc0av5/we_spend_over_19k_a_year_on_hubspot_alternatives/o4ysnsq/ |
| 9 | negative | r/CRM | u/UpstairsOwl8062 | `hubspot` | https://www.reddit.com/r/CRM/comments/1oifys9/which_crm_to_choose/nm0yzml/ |
| 10 | neutral | r/revops | u/romeonoi | `hubspot` | https://www.reddit.com/r/revops/comments/1kymfvt/question_about_user_field_mapping_between/muz5we5/ |
| 11 | negative | r/CRM | u/Human_Learner | `hubspot` | https://www.reddit.com/r/CRM/comments/1lvqqs8/help_me_avoid_800mo_hubspot_increase_pipedrive/n29mk7j/ |
| 12 | neutral | r/CRM | u/LooceyCRM | `hubspot` | https://www.reddit.com/r/CRM/comments/1c53rjg/best_crm_tool_for_non_profits/kzs93cc/ |
| 13 | positive | r/CRM | u/Adorable-Reindeer280 | `hubspot` | https://www.reddit.com/r/CRM/comments/1tvlwhb/best_startup_crm_for_2050_person_teams_were/oq7n787/ |
| 14 | positive | r/techsales | u/Agreeable_Spare1502 | `hubspot` | https://www.reddit.com/r/techsales/comments/1u8t015/hubspot_ent_aeent_ae_roles_in_general_right_now/osimpao/ |
| 15 | positive | r/CRM | u/genemarks | `hubspot` | https://www.reddit.com/r/CRM/comments/1kjskll/zoho_vs_hubspot/msfopbx/ |
| 16 | positive | r/revops | u/SeeingWhatWorks | `hubspot` | https://www.reddit.com/r/revops/comments/1siql85/marketing_ops_professional_2_years_experience/ofo6jov/ |
| 17 | positive | r/sales | u/Confident-Staff-8792 | `hubspot` | https://www.reddit.com/r/sales/comments/1oa1v78/does_anyone_else_hate_their_crm/nk8b4wc/ |
| 18 | negative | r/sales | u/acesmat | `hubspot` | https://www.reddit.com/r/sales/comments/1lkjral/what_crm_should_we_use/ |
| 19 | positive | r/CRM | u/Shwetatechnical | `hubspot` | https://www.reddit.com/r/CRM/comments/1ljb1ct/looking_for_crm_for_my_small_business/n01bly8/ |
| 20 | neutral | r/CRM | u/Manojit_8991 | `hubspot` | https://www.reddit.com/r/CRM/comments/1b8zugj/what_is_the_best_alternative_to_hubspot_marketing/ktsroos/ |

## The arithmetic, longhand
```
x_pos  = 10
x_neg  = 4
neu    = 6     (counted and published, never in the denominator)
abstain= 0
N_op   = 10 + 4 = 14

category prior, fitted leave-one-out over every other crm brand with N_op >= 30
  alpha0 = 13.427
  beta0  = 6.573

p_tilde = (x_pos + alpha0) / (N_op + alpha0 + beta0)
        = (10 + 13.427) / (14 + 13.427 + 6.573)
        = 23.4270 / 34.0000
        = 0.689029
Reddit Love Score = round(100 * 0.689029) = 69
```

## Three independent computations of the same number

| route | value |
|---|---|
| longhand, above | **69** |
| worker/score.py, same inputs | **69** |
| Postgres, independent code path | **69** |

Paste-able check: `=ROUND(100*(10+13.427)/(14+13.427+6.573),0)`

## The published figure, for contrast

- whole in-window corpus: n = 1114, N_op = 804, n_eff = 401.0
- eligible: **False**
- failed test: **n_eff** — 401 observed against 600 required
