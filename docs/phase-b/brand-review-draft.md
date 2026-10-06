# Phase B brand rows: review draft (started 2026-10-06 02:05 UTC, during gate night 3: reading only)

Source: `Empact-Partners/reddit-mentions` `data/index-package/brand-seed-rows.csv` (179 rows: 118 low, 39 medium,
22 high ambiguity). The handoff asks every high and medium row to be read before loading. First pass, to finish
against `data/brand-seed-expand.csv`'s matching rules (what `bare_disabled_forms` and case-exact aliases do) before
anything is loaded:

| Row | Problem | Fix to apply |
|---|---|---|
| CNA | bare "CNA" is Certified Nursing Assistant on Reddit | bare disabled; aliases "CNA Insurance", "CNA Financial"; domain cna.com |
| PEX | bare "PEX" is plumbing pipe | bare disabled; alias "PEX Card"; domain pexcard.com |
| Cargo (website-builders) | "cargo" is Rust's tool and shipping | bare disabled; aliases "Cargo.site", "Cargo Collective" |
| Engine (expense-management) | "engine" is a common noun | bare disabled; aliases "Engine.com", "Hotel Engine" |
| SAP Concur | "concur" is a verb | bare "Concur" disabled; aliases "SAP Concur", "Concur Expense"; domain concur.com |
| BILL Spend & Expense | "bill" | bare disabled; aliases "BILL Spend & Expense", "Bill.com" |
| wecantrack | alias "We Can Track" matches plain English | drop that alias; keep "wecantrack", "WeCanTrack" (case-exact) |
| Affluent | adjective | bare disabled; alias "Affluent.io" |
| Noon, Ribbon (recruiting) | common words | bare disabled; aliases "Noon AI", "Ribbon AI"; domains noon.ai, ribbon.ai |
| Canny | adjective; a feedback board, check its category | bare disabled; alias "Canny.io" |
| Lorikeet | a bird | bare disabled; alias "Lorikeet AI"; domain to verify |
| Seismic | sales enablement, not help-desk; common word | wrong category: drop, or move only if a sales-enablement category exists |
| Coalition, Cowbell, Thimble, Vouch, AXIS, Nationwide | common words | bare disabled; "<name> Insurance" / "<name> Cyber" / "AXIS Capital" aliases; domains coalitioninc.com, cowbell.insure, thimble.com, vouch.us, axiscapital.com, nationwide.com |
| Great American, American Specialty, Remote People, Prime Insurance | ordinary phrases | bare disabled; full company names ("Great American Insurance", "American Specialty Insurance", "RemotePeople") and domains |
| Overture (artist-booking) | common word, no domain, no alias | drop unless a domain is verified |
| LEARN Behavioral | "learn" | match only the full name |
| Specialty Insurance, SystemOne | ordinary phrases (handoff) | case-exact with context, or domain and distinctive forms only |
| Lingo (lingoapp.com) | not lingo-dev | bare "lingo" disabled for both |

To decide in decision 0018: Framer's primary category (design today; website-builders proposed), with the slug
frozen and its score history kept.
