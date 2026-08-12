#!/usr/bin/env python3
"""Entity resolution: rules only, no classifier, nothing guessed.

Aho-Corasick over a per-surface-form alias table with word-boundary enforcement.
URLs matched before prose, code blocks and `>` quotes stripped first.

  low    → accept on word-boundary match
  medium → accept on ≥1 corroborating signal
  high   → EXCLUDED OUTRIGHT, because τ and the low-margin band both require a
           trained classifier and a gold set that do not exist. That means bare
           `monday` and bare `Close` do not resolve at all, and the recall loss
           is published rather than hidden.

This is 05-entity-resolution.md's five-stage pipeline minus stage 3 (the
classifier that needs the gold set) and stage 4's LLM adjudication tail.
"""
import csv, json, os, re, sys

try:
    import ahocorasick
except ImportError:
    print("pip install pyahocorasick", file=sys.stderr)
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


# ── preprocessing ───────────────────────────────────────────────────────────
# Strip before matching: fenced code blocks, inline code, and `>` quote blocks.
# 13-algorithm.md §5 and 06-sentiment.md §5 both require it.

_CODE_BLOCK = re.compile(r'```[\s\S]*?```|`[^`]+`')
_QUOTE_BLOCK = re.compile(r'^>.*$', re.MULTILINE)

VERB_FRAME = re.compile(
    r"\b(use|using|used|switch(?:ed)? to|migrat(?:e|ed|ing) to|mov(?:e|ed|ing) (?:off|from|to)|"
    r"on|running|adopted|implemented|rolled out|ditch(?:ed)?|dropped|left|paying for|"
    r"signed up for|trial(?:l)?ed|evaluated|we\'re on|deployed)\s+\S{0,3}$", re.I)


def preprocess(text):
    text = _CODE_BLOCK.sub(' ', text)
    text = _QUOTE_BLOCK.sub(' ', text)
    return text

def normalize(text):
    """NFKC, casefold, collapse whitespace, strip possessives. Keep offsets."""
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    text = text.casefold()
    text = re.sub(r"['']s\b", '', text)  # Notion's → Notion
    text = re.sub(r'\s+', ' ', text)
    return text


# ── alias table ─────────────────────────────────────────────────────────────

def load_aliases():
    """Returns list of (alias_lower, brand_slug, surface_class, min_corroborating, bare_disabled)"""
    rows = []
    for r in csv.DictReader(open(os.path.join(REPO, "data", "brand-aliases.csv"))):
        rows.append((
            r["alias"].lower(),
            r["brand_slug"],
            r["surface_class"],
            int(r["min_corroborating"]),
            r["bare_disabled"] == "True",
        ))
    return rows

def load_brands():
    return {r["slug"]: r for r in csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}

def load_stop_contexts():
    out = {}
    for r in csv.DictReader(open(os.path.join(REPO, "data", "brands.csv"))):
        stops = [s.strip() for s in (r["stop_contexts"] or "").split(";") if s.strip()]
        if stops:
            out[r["slug"]] = stops
    return out

def load_domains():
    out = {}
    for r in csv.DictReader(open(os.path.join(REPO, "data", "brands.csv"))):
        doms = [d.strip() for d in (r["domains"] or "").split(";") if d.strip()]
        if doms:
            out[r["slug"]] = doms
    return out


# ── build the automaton ─────────────────────────────────────────────────────

def build_automaton(aliases):
    """One Aho-Corasick automaton over all surface forms. Linear in text length.

    A surface form can map to MULTIPLE brands (e.g. `hubspot` → HubSpot CRM
    AND HubSpot Marketing Hub). The automaton stores a LIST of matches per key
    so none is silently dropped.
    """
    A = ahocorasick.Automaton()
    for alias, brand_slug, cls, min_c, disabled in aliases:
        if disabled:
            continue
        existing = A.get(alias, [])
        existing.append((alias, brand_slug, cls, min_c))
        A.add_word(alias, existing)
    A.make_automaton()
    return A


# ── word boundary check ────────────────────────────────────────────────────

_WORD_CHAR = re.compile(r'[a-z0-9]')

def is_word_boundary(text, start, end):
    """Word-boundary enforcement: `stripe` inside `pinstripe` is not a match."""
    if start > 0 and _WORD_CHAR.match(text[start - 1]):
        return False
    if end < len(text) and _WORD_CHAR.match(text[end]):
        return False
    return True


# ── corroborating signals ──────────────────────────────────────────────────

def check_domain(text, brand_slug, domains):
    """Signal 1: the strongest. A domain URL in the same document is auto-accept."""
    for d in domains.get(brand_slug, []):
        if d.lower() in text:
            return True
    return False

def check_cooccurrence(text, pos, brand_slug, all_hits):
    """Signal 2: a confirmed SAFE brand within 400 chars."""
    window = 400
    for other in all_hits:
        if other["brand_slug"] == brand_slug:
            continue
        if other["class"] != "SAFE":
            continue
        if abs(other["pos"] - pos) < window:
            return True
    return False

def check_stop_context(text, pos, brand_slug, stops):
    """A hit on a stop context is a hard reject."""
    window = text[max(0, pos - 80):pos + 80].lower()
    for stop in stops.get(brand_slug, []):
        if stop in window:
            return True
    return False


# ── the pipeline ────────────────────────────────────────────────────────────

class Resolver:
    def __init__(self):
        self.aliases = load_aliases()
        self.brands = load_brands()
        self.stops = load_stop_contexts()
        self.domains = load_domains()
        self.automaton = build_automaton(self.aliases)

    def has_alias(self, text):
        """Recall-only qualification scan: ANY boundary-valid automaton hit.

        No entity gating, no stop-contexts — this decides whether a thread is
        worth one tree fetch, not whether a mention exists. A false qualify
        costs one request; a false reject drops the thread forever. Extraction
        still runs the full resolve() with entity gating, so a junk-qualified
        thread yields zero mention rows.
        """
        norm = normalize(preprocess(text))
        for end_idx, matches in self.automaton.iter(norm):
            alias = matches[0][0]
            if is_word_boundary(norm, end_idx - len(alias) + 1, end_idx + 1):
                return True
        return False

    def resolve(self, text, subreddit=None, thread_title=None):
        """Returns list of {brand_slug, alias, pos, conf, rule_fired}"""
        clean = preprocess(text)
        norm = normalize(clean)

        # Phase 1: domain scan first — strongest signal
        domain_hits = set()
        for brand_slug, doms in self.domains.items():
            for d in doms:
                if d.lower() in norm:
                    domain_hits.add(brand_slug)

        # Phase 2: Aho-Corasick
        raw_hits = []
        for end_idx, matches in self.automaton.iter(norm):
            for (alias, brand_slug, cls, min_c) in matches:
                start = end_idx - len(alias) + 1
                if not is_word_boundary(norm, start, end_idx + 1):
                    continue
                raw_hits.append({
                    "brand_slug": brand_slug,
                    "alias": alias,
                    "pos": start,
                    "class": cls,
                    "min_corroborating": min_c,
                })

        # Phase 3: resolve each hit
        accepted = []
        seen = set()
        for hit in raw_hits:
            key = (hit["brand_slug"], hit["pos"])
            if key in seen:
                continue
            seen.add(key)

            slug = hit["brand_slug"]
            cls = hit["class"]

            # Domain auto-accept is the strongest signal (05 §4 rank 1).
            # It overrides stop contexts AND ambiguity class, because a
            # document containing `close.com` is about the product even if
            # "close the deal" appears in the same sentence.
            if slug in domain_hits:
                accepted.append({
                    "brand_slug": slug,
                    "alias": hit["alias"],
                    "pos": hit["pos"],
                    "conf": 0.98,
                    "rule_fired": "domain_autoaccept",
                })
                continue

            # Stop contexts veto a BARE token, never a qualified form.
            # "Close the deal quickly using Close CRM" matched `Close CRM`, which
            # is unambiguous, and the veto was firing on `close the deal` sitting
            # in the same sentence. A qualified form carries its own evidence.
            qualified = (" " in hit["alias"]) or ("." in hit["alias"])
            if not qualified and check_stop_context(norm, hit["pos"], slug, self.stops):
                continue

            # SAFE: accept
            if cls == "SAFE":
                accepted.append({
                    "brand_slug": slug,
                    "alias": hit["alias"],
                    "pos": hit["pos"],
                    "conf": 0.95,
                    "rule_fired": "safe_word_boundary",
                })
                continue

            # AMBIGUOUS with domain already handled above
            if slug in domain_hits:
                accepted.append({
                    "brand_slug": slug,
                    "alias": hit["alias"],
                    "pos": hit["pos"],
                    "conf": 0.98,
                    "rule_fired": "domain_autoaccept",
                })
                continue

            # AMBIGUOUS: need ≥1 corroborating signal
            if cls == "AMBIGUOUS":
                signals = 0
                if check_cooccurrence(norm, hit["pos"], slug, raw_hits):
                    signals += 1
                # Subreddit prior: if the sub is in a category's seed list
                cat_nouns = _category_nouns_for_brand(slug)
                if any(n in (thread_title or "").lower() for n in cat_nouns):
                    signals += 1
                if any(n in norm[max(0, hit["pos"] - 120):hit["pos"] + 120] for n in cat_nouns):
                    signals += 1
                if VERB_FRAME.search(norm[max(0, hit["pos"] - 40):hit["pos"]]):
                    signals += 1
                if signals >= 1:
                    accepted.append({
                        "brand_slug": slug,
                        "alias": hit["alias"],
                        "pos": hit["pos"],
                        "conf": 0.85,
                        "rule_fired": f"ambiguous_corroborated_{signals}",
                    })
                continue

            # HOSTILE: the frozen rule is >= 2 corroborating signals, and a
            # stop-context veto has already run above. 05 §5: a bare
            # high-ambiguity token "default-rejects unless two corroborating
            # signals fire". Bare forms that no stop-context list can rescue
            # (`close`, `make`, `square`) never reach here at all — they carry
            # bare_disabled and are absent from the automaton.
            if cls == "HOSTILE":
                signals = 0
                if check_cooccurrence(norm, hit["pos"], slug, raw_hits):
                    signals += 1
                cat_nouns = _category_nouns_for_brand(slug)
                if any(n in (thread_title or "").lower() for n in cat_nouns):
                    signals += 1
                if any(n in norm[max(0, hit["pos"] - 120):hit["pos"] + 120]
                       for n in cat_nouns):
                    signals += 1
                if VERB_FRAME.search(norm[max(0, hit["pos"] - 40):hit["pos"]]):
                    signals += 1
                if signals >= 2:
                    accepted.append({
                        "brand_slug": slug,
                        "alias": hit["alias"],
                        "pos": hit["pos"],
                        "conf": 0.78,
                        "rule_fired": f"hostile_corroborated_{signals}",
                    })
            continue

        # A surface form shared by two brands resolves to ONE of them. "HubSpot"
        # is the canonical name of `hubspot` and an alias of
        # `hubspot-marketing-hub`; accepting both counts the company twice and
        # inflates every figure downstream. The canonical name wins, because an
        # alias inheriting a parent's evidence is exactly what 05 §5 forbids.
        canonical = {b["slug"]: b["brand"].lower() for b in self.brands.values()} \
            if isinstance(next(iter(self.brands.values()), {}), dict) else {}
        by_pos = {}
        for a in accepted:
            key = (a["pos"], a["alias"])
            prev = by_pos.get(key)
            if prev is None:
                by_pos[key] = a
                continue
            a_is_canon = canonical.get(a["brand_slug"]) == a["alias"].lower()
            p_is_canon = canonical.get(prev["brand_slug"]) == prev["alias"].lower()
            if a_is_canon and not p_is_canon:
                by_pos[key] = a
            elif a_is_canon == p_is_canon and a["conf"] > prev["conf"]:
                by_pos[key] = a

        # Then one mention per brand per document: a comment naming a brand
        # three times is ONE observation (13-algorithm.md §6).
        final = {}
        for a in by_pos.values():
            prev = final.get(a["brand_slug"])
            if not prev or a["conf"] > prev["conf"]:
                final[a["brand_slug"]] = a
        return list(final.values())


def _category_nouns_for_brand(brand_slug):
    """Quick lookup of what category a brand lives in, for the subreddit prior."""
    # Import here to avoid circular — the harvest module has the vocabulary
    try:
        from harvest import CATEGORY_NOUNS
        brands = load_brands()
        b = brands.get(brand_slug)
        if b:
            return CATEGORY_NOUNS.get(b["primary_category_slug"], [])
    except Exception:
        pass
    return []


# ── CLI for testing ─────────────────────────────────────────────────────────

def main():
    r = Resolver()
    tests = [
        ("I switched from HubSpot to Pipedrive last month", "sales", "Best CRM?"),
        ("Monday morning we deployed the new monday.com board", "projectmanagement", "PM tools"),
        ("Close the deal quickly using Close CRM", "sales", "CRM roundup"),
        ("We use Notion for everything at work", "productivity", "Note taking apps"),
        ("The SAP of the tree was flowing in r/worldbuilding", "worldbuilding", "Fantasy stories"),
        ("Monday is my least favorite day", "nfl", "Game day thread"),
    ]
    for text, sub, title in tests:
        hits = r.resolve(text, subreddit=sub, thread_title=title)
        brands = [h["brand_slug"] for h in hits]
        print(f"  {text[:60]:<62} -> {brands}")

    # Regression: the two documented false matches must NOT resolve
    assert not r.resolve("Monday the weekday in r/nfl", "nfl", "Game day"), "Monday weekday should not resolve"
    assert not r.resolve("The SAP flows through the tree", "worldbuilding", "Fantasy"), "SAP fluid should not resolve"
    print("\n  regression tests passed")


if __name__ == "__main__":
    main()
