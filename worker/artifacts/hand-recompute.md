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
| 1 | negative | r/CRM | u/No_Week_5798 | `hubspot` | https://www.reddit.com/r/CRM/comments/1nphjbg/trying_to_streamline_lead_handoffs_in_hubspot_and/ |
| 2 | neutral | r/CRM | u/sardamit | `hubspot` | https://www.reddit.com/r/CRM/comments/1mzt3nu/crm_hubspot/namccxx/ |
| 3 | neutral | r/CRM | u/Narrow_Goose8822 | `hubspot` | https://www.reddit.com/r/CRM/comments/1mrrwed/how_to_get_better_at_hubspot_crm_automations/ |
| 4 | neutral | r/sales | u/Ferris80 | `hubspot` | https://www.reddit.com/r/sales/comments/173pe7l/thoughts_on_pipedrive_crm/k44yq6k/ |
| 5 | neutral | r/sales | u/guywithalpha | `hubspot` | https://www.reddit.com/r/sales/comments/1bwjgk7/good_news_the_potential_death_of_salesforce/l8g3gh8/ |
| 6 | neutral | r/CRM | u/OracleofFl | `hubspot` | https://www.reddit.com/r/CRM/comments/1n4p13n/controversial_isnt_opportunities_in_salesforce/nbnfjqq/ |
| 7 | positive | r/CRM | u/attio | `hubspot` | https://www.reddit.com/r/CRM/comments/1pd8fde/im_the_cofounder_of_attio_crm_we_just_raised_a_50/ns3a3u6/ |
| 8 | positive | r/CRM | u/dualfalchions | `hubspot` | https://www.reddit.com/r/CRM/comments/1ol784i/crm_recommendations_for_small_b2b_service/nmrt3zd/ |
| 9 | neutral | r/SalesOperations | u/Cautious_Pen_674 | `hubspot` | https://www.reddit.com/r/SalesOperations/comments/1rmmna0/crm_hubspot_side_hustle/o93iuq8/ |
| 10 | neutral | r/CRM | u/oasudoais7d987 | `hubspot` | https://www.reddit.com/r/CRM/comments/lasbqr/best_crm_w_marketing_automation_not_named/glucb32/ |
| 11 | negative | r/sales | u/andrewbermudez | `hubspot` | https://www.reddit.com/r/sales/comments/77v3ax/anyone_pissed_about_hubspot_crm_price_increases/ |
| 12 | neutral | r/CRM | u/CircuitForge | `hubspot` | https://www.reddit.com/r/CRM/comments/1g43xtz/best_voip_service_to_integrate_with_hubspot_crm/ |
| 13 | negative | r/CRM | u/guillermeo | `hubspot` | https://www.reddit.com/r/CRM/comments/1such21/after_1_year_building_a_crm_for_travel_agencies/ |
| 14 | negative | r/sales | u/EZeeZGeezy | `hubspot` | https://www.reddit.com/r/sales/comments/1bwjgk7/good_news_the_potential_death_of_salesforce/ky88993/ |
| 15 | neutral | r/CRM | u/sandilya22 | `hubspot` | https://www.reddit.com/r/CRM/comments/103rhw9/anyone_here_integrating_multiple_crms_in_their/ |
| 16 | negative | r/sales | u/Mrhood714 | `hubspot` | https://www.reddit.com/r/sales/comments/1bwjgk7/good_news_the_potential_death_of_salesforce/ky6u12t/ |
| 17 | neutral | r/sales | u/djredcent | `hubspot` | https://www.reddit.com/r/sales/comments/5njxtp/hubspot_sales_crm_and_pipedrive_users/ |
| 18 | positive | r/CRM | u/CoachAmber | `hubspot` | https://www.reddit.com/r/CRM/comments/1mrrwed/how_to_get_better_at_hubspot_crm_automations/na6c00f/ |
| 19 | negative | r/CRM | u/TaleOfACat | `hubspot` | https://www.reddit.com/r/CRM/comments/1q8z7qh/which_crm_feels_closest_to_hubspot_in_usability/ |
| 20 | negative | r/sales | u/gafana | `hubspot` | https://www.reddit.com/r/sales/comments/woh50m/good_crm_for_sales_to_replace_hubspot/ikbpb8i/ |

## The arithmetic, longhand
```
x_pos  = 3
x_neg  = 7
neu    = 10     (counted and published, never in the denominator)
abstain= 0
N_op   = 3 + 7 = 10

category prior, fitted leave-one-out over every other crm brand with N_op >= 30
  alpha0 = 121.346
  beta0  = 78.654

p_tilde = (x_pos + alpha0) / (N_op + alpha0 + beta0)
        = (3 + 121.346) / (10 + 121.346 + 78.654)
        = 124.3460 / 210.0000
        = 0.592124
Reddit Love Score = round(100 * 0.592124) = 59
```

## Three independent computations of the same number

| route | value |
|---|---|
| longhand, above | **59** |
| worker/score.py, same inputs | **59** |
| Postgres, independent code path | **59** |

Paste-able check: `=ROUND(100*(3+121.346)/(10+121.346+78.654),0)`

## The published figure, for contrast

- whole in-window corpus: n = 147, N_op = 84, n_eff = 58.0
- eligible: **False**
- failed test: **n_eff** — 58 observed against 600 required
