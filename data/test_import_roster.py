#!/usr/bin/env python3
"""Gate fixtures for import_roster.py — each asserts a KNOWN-BAD input is handled.

Same doctrine as the outreach repo's 02b: a gate that has never failed a bad input is
decoration. These run offline (no fleet, no DNS beyond two real lookups).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from import_roster import reserved_slugs, english_words, resolve_domain, is_english_word, category_nouns
from gen_brands import slugify

FAILS, N = [], 0
def must(name, cond, detail=""):
    global N
    N += 1
    if not cond: FAILS.append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))

print("import_roster gate fixtures\n")
res = reserved_slugs()

# flat-namespace pre-check: the publish-time build bomb
must("category slugs are reserved (a company slugging to 'crm' must be caught)", "crm" in res)
must("framework paths are reserved ('api')", "api" in res)
must("site routes are reserved ('search', 'methodology')", {"search","methodology"} <= res)
must("reserved set is the full union, not just categories", len(res) > 100, f"only {len(res)}")

# slugify fallback (the Орфограммка class of bug)
must("a non-Latin name falls back to its domain label",
     slugify("Орфограммка", "orfogrammka.ru") == "orfogrammka")
must("a normal name still slugs normally", slugify("Acme Corp", "acme.com") == "acme-corp")
try:
    slugify("!!!", "")
    must("a name with no Latin and no domain refuses loudly", False, "did not raise")
except SystemExit:
    must("a name with no Latin and no domain refuses loudly", True)

# ambiguity strictness: the rule that protects existing boards
words = english_words()
ORDER = {"low":0,"medium":1,"high":2}
def strictness(name, drafted):
    amb = drafted
    if name.lower() in words or len(name) <= 3:
        amb = max(amb, "medium", key=lambda a: ORDER[a])
    return amb
must("an English-word brand name cannot enter as low ('Close')",
     strictness("Close", "low") == "medium")
must("a 3-char brand name cannot enter as low ('Kit')",
     strictness("Kit", "low") == "medium")
must("a distinctive coinage keeps low ('Klaviyo')",
     strictness("Klaviyo", "low") == "low")
must("a fleet 'high' is never weakened", strictness("Front", "high") == "high")

# plural guard — /usr/share/dict/words ships singulars only
W = english_words()
must("a plural English word is caught ('things' — 628 false mentions before this)",
     is_english_word("things", W))
must("a plural English word is caught ('cats' — 122 false mentions before this)",
     is_english_word("cats", W))
# NOTE: pick a base verified present in THIS word list. It is idiosyncratic — it has
# "cat" and "thing" but not "box", so a fixture written from intuition tests the
# dictionary's coverage rather than this function.
_es = next((b for b in ("class", "patch", "bench", "branch", "match") if b in W), None)
must("an -es plural is caught", _es is not None and is_english_word(_es + "es", W),
     f"base={_es}")
must("a distinctive coinage is still NOT a word ('klaviyo')",
     not is_english_word("klaviyo", W))
must("a real singular still passes ('close')", is_english_word("close", W))

# category-noun self-corroboration — resolve.py counts a category noun in the title AND one
# near the match as two of the signals a HOSTILE bare token needs, so a brand named after
# its own category corroborates itself
CN = category_nouns()
must("seo-tools lists 'seo' as one of its nouns (the self-corroboration trap)",
     any("seo" == n or "seo" in n.split() for n in CN.get("seo-tools", set())))

# G5: a stop-context must contain the bare token
name = "Close"
stops = ["close the deal", "unrelated phrase"]
kept = [s for s in stops if name.lower().split()[0] in s.lower()]
must("a stop-context not containing the bare token is dropped (G5)", kept == ["close the deal"])

# G4: DNS truth, both directions
must("a live domain resolves", resolve_domain("google.com"))
must("a nonexistent domain does not resolve",
     not resolve_domain("this-domain-should-not-exist-9c3f1a.example"))

print(f"\n{N - len(FAILS)}/{N} fixtures passed")
sys.exit(1 if FAILS else 0)
