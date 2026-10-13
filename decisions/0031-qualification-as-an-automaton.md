# 0031 — Post qualification runs on an automaton, with the same answers

Date: 2026-10-13. Status: accepted (the commission: full speed under the shared Reddit app).

## Context

Every post the collector lists is first qualified (`worker/daily.py` `content_qualify`): does its title or text
carry a brand form (a low-ambiguity brand name or a domain) or one of its category's nouns. The brand-form test was
one regular expression, `(?<![a-z0-9])form|form|...|form(?![a-z0-9])` with case ignored, over 16,253 forms: 218 KB
of alternation.

Measured on 13 Oct, on 2,000 real posts from 20 subreddits and 1,800 real comment texts:

| | regex | automaton |
|---|---|---|
| per post (`content_qualify`) | 45.8 ms | 0.03 ms |
| per text (the brand-form test alone) | 16.1 ms | 0.004 ms |
| posts qualified, of 2,000 | 1,480 | 1,480, the same posts |
| texts matched, of 1,800 | 383 | 383, the same texts |

The pilot of decision 0029 spent 628 of its 1,602 seconds of collection matching. A daytime pass lists about 25,000
posts: about 19 minutes of a 300-minute pass went to this test.

The regex's two boundary checks sit outside the alternation, so they bound only its first form and its last; every
other form matched anywhere, inside a word too ("portant" in "important", "soci" in "social"). That is what has
qualified posts since August, and every yield the collector was judged on was measured with it.

## Decision

`worker/harvest.py` `build_alias_re` returns an `AliasMatcher`: an Aho-Corasick automaton over the same forms, case
ignored, a form found anywhere in the text. Its `search` returns True or None, so `content_qualify` and every other
caller are unchanged. Without the automaton package (it is in the sweep image) the regex is built as before.

The one difference: the regex's last form (one of the shortest, chosen by the order of a Python set, so not the same
form from one run to the next) needed no letter or digit after it; it is now found inside a word like every other
form. On the 3,800 texts measured, no answer changed.

Not changed: which posts qualify, the category nouns, the resolver that decides what a mention is. Whether
qualification should become whole-word (it would qualify about a third as many texts) is a separate decision with its
own measurement, and matters little once comments come from the comment listing (decision 0029).

## How it is judged

The collect stage's `seconds.matching` on the next passes, against 628 seconds for 300 calls in the 0029 pilot.
