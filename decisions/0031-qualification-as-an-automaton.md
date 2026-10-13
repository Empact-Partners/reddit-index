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

`worker/harvest.py` `build_alias_re` returns an `AliasMatcher`: an Aho-Corasick automaton over the same forms, a form
found anywhere in the text, letters compared as re.IGNORECASE compares them (`re_i_fold`: the Turkish capital I with
dot becomes i before lowercasing, and Python's own table of extra equivalents, dotless i, long s, final sigma and a few
Greek and Cyrillic variants, maps each group to one letter). Its `search` returns True or None, so `content_qualify`
and every other caller are unchanged. Without the automaton package (it is in the sweep image) the regex is built as
before. Forms that are all empty give a matcher that matches nothing.

The one difference: the regex's first form (a longest one) needed no letter or digit before it and its last (a
shortest one) none after it, and which forms those were the order of a Python set decided, run by run. Both are now
found inside a word like every other form. On the texts measured, no answer changed.

Not changed: which posts qualify, the category nouns, the resolver that decides what a mention is. Whether
qualification should become whole-word (it would qualify about a third as many texts) is a separate decision with its
own measurement, and matters little once comments come from the comment listing (decision 0029).

## Review

An independent read by GLM-5.3 (clean clone, read-only) found the first version's claim of the same answers false in
two places, both taken: str.lower() is not re.IGNORECASE ("İubenda" matched the regex and not the automaton; 481
forms start with i), and the regex's first form lost its boundary as well as its last. Also taken: an automaton built
from forms that are all blank cannot be searched. After the fix, every character of the Basic Multilingual Plane
compared with every ASCII letter and digit gives re.IGNORECASE's answer (0 disagreements in 2.4 million), and the
2,000 posts and 1,200 comment texts still give the same answers.

## How it is judged

The collect stage's `seconds.matching` on the next passes, against 628 seconds for 300 calls in the 0029 pilot.
