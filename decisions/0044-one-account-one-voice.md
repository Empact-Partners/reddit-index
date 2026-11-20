# 0044: One account, one voice; Stock Analysis matched only by name (2026-11-20)

**Trigger.** QuantConnect's CEO, replying to our Reddit Reputation email on 18 Nov 2026: "the #1 app in your home page
is the author writing all the posts himself" (PHPRunner) and "Stock analysis is only positive, with unrelated links".
Both true. Issues #106 and #107.

**1. The score counts accounts, not posts.** PHPRunner was #1 on Most Loved: 153 of its 172 opinionated mentions came
from one account, its author. On 20 Nov about twenty brands among the top 40 of the pooled board drew more than 60%
of their mentions from one account (EngageBay 96%, SocialRails 99%, Qoblex 99%). The 5% author floor existed but,
since 2.2.0, gates only the precision claim. Rather than a new visibility gate with an arbitrary cut-off, the score now
counts each account once: positive when most of its opinionated mentions of the brand are positive, negative when
most are negative, a tie neither; a mention whose author is gone is its own voice. `site.refresh_brand` stores
`voice_pos`/`voice_neg` (migration 0042) and `worker/site_score.py` scores, ranks and sets `page_n_op` from them, so the
pooled board's bar of 10 is ten accounts. The tiles still count every mention. This is the floor's intent ("one
prolific voice carried across many threads") applied in the arithmetic, the same way decision 0011 handled thin
evidence in the estimator instead of hiding brands.

**2. Stock Analysis.** The canonical name is the ordinary phrase, and `gen_brands.py` makes every multi-word form SAFE,
so none of its eight stop contexts ever ran. The row now carries `bare_disabled_forms = stock analysis` (decision 0018's
mechanism). And its web address is pasted as a chart or data source in threads about other stocks: new
`data/link-citation-brands.csv` lists brands for which a domain seen only inside a link is a citation, not a mention
(`worker/resolve.py`, `names_outside_links`). Stored mentions were judged again with `ops/reresolve_brand.py`: 306 of
348 no longer resolve and are in `mention_rejections`; 42 name the site in their text and stay.

Not done here: other brands whose multi-word name is an ordinary phrase (Actual Budget, Lunch Money) are unchecked.
