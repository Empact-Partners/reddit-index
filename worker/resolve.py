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

# A bare one- or two-character token is never a brand reference in casual
# prose — it is "or", "me", "as", "re", "am". The gazetteer's English-word
# gate only screened dictionary words of length 3-12, so two-letter forms were
# never examined and shipped as SAFE with min_corroborating=0. Once the sweep
# actually started reading comments (it had been extracting none), those five
# aliases alone produced 35,000 of 42,000 mentions in the pilot category.
# Enforced HERE as well as in the data, because a regenerated gazetteer must
# not be able to reintroduce the class.
MIN_BARE_LEN = 3


def _english_words():
    """The system dictionary, lowercased. Absent on a bare container, in which
    case the guard below simply does not fire (the length rule still does)."""
    words = set()
    try:
        with open("/usr/share/dict/words") as f:
            for w in f:
                w = w.strip().lower()
                if len(w) >= 2:
                    words.add(w)
    except FileNotFoundError:
        pass
    return words


_ENGLISH = _english_words()
# Deliberately NOT treated as ordinary words: short forms that are overwhelmingly
# product references in software talk even though a dictionary lists them.
_TECH_EXEMPT = {"aws", "sap", "ibm", "gcp", "sas", "php", "sql", "vim", "git",
                "npm", "aix", "erp", "crm", "api", "ios", "mac", "pdf"}

# Generic tech nouns that a dictionary does not list but which are never a
# brand reference on their own. "APP" ships as a SAFE alias of Astro Pixel
# Processor and matched 2,699 times in three subreddits.
_GENERIC = {"app", "apps", "tool", "tools", "bot", "bots", "web", "site",
            "cloud", "data", "code", "stack", "server", "client", "agent",
            "studio", "suite", "platform", "dashboard", "console", "portal"}


def _is_plain_english(alias):
    """True when a SINGLE-token alias is an ordinary English word — 'pieces',
    'piece', 'edge'. Such a form must never be accepted bare: it is what
    produced 'Pieces for Developers' from the word pieces. The alias stays in
    the automaton but is forced to require corroboration, so a real reference
    (near a domain or another confirmed brand) still resolves.

    MULTI-WORD forms are deliberately exempt even when every token is a
    dictionary word: "adobe acrobat", "affinity photo" and "amazon ses" are
    ordinary words in sequence and are unmistakably brand references — the
    same reasoning that already exempts qualified forms from the stop-context
    veto. An earlier version of this guard classified them as English and
    would have thrown away every multi-word brand in the gazetteer.
    """
    toks = [t for t in re.split(r"[^a-z0-9]+", alias.lower()) if t]
    if len(toks) != 1 or any(t in _TECH_EXEMPT for t in toks):
        return False
    if toks[0] in _GENERIC:
        return True
    if not _ENGLISH:
        return False

    def known(t):
        # the system dictionary lists singulars, so 'pieces' misses while
        # 'piece' hits — an alias that is a plain plural is just as ordinary
        if t in _ENGLISH:
            return True
        for suf, base in (("s", ""), ("es", ""), ("ies", "y")):
            if t.endswith(suf) and len(t) > len(suf) + 1:
                if t[: -len(suf)] + base in _ENGLISH:
                    return True
        return False

    return all(known(t) for t in toks)


_dom_claims = None


def _domain_identifies(domain, slug, all_domains):
    """Can this domain, seen in a comment, prove THIS brand is being discussed?

    Domain hits are the strongest signal in resolve() — conf 0.98, and they
    override stop contexts and ambiguity class alike. The gazetteer feeds them
    two systematic falsehoods:

    1. SHARED domains. 206 domain strings are claimed by more than one brand;
       microsoft.com by seventeen, aws.amazon.com by sixteen, zoho.com by
       fifteen. One microsoft.com URL was auto-accepting all seventeen.
       A domain that points at several brands identifies none of them.
    2. MULTI-TENANT hosts. github.com is listed as a domain of `fooocus`, an
       image tool hosted there, so every GitHub link in every subreddit
       credited Fooocus (1,144 hits in three subs). A brand only owns a
       domain when the registrable label is recognisably its own name.

    Losing a domain signal costs little — the brand's own name still matches
    through the normal gated path. Accepting a false one costs everything,
    because nothing downstream re-examines a 0.98 auto-accept.
    """
    global _dom_claims
    if _dom_claims is None:
        _dom_claims = {}
        for s, doms in all_domains.items():
            for dd in doms:
                if dd:
                    _dom_claims.setdefault(dd.strip().lower(), set()).add(s)
    d = domain.strip().lower()
    if len(_dom_claims.get(d, ())) > 1:
        return False
    parts = [p for p in d.split(".") if p]
    if len(parts) < 2:
        return False
    # registrable label: the one before the public suffix, allowing for a
    # two-part suffix such as .co.uk / .com.au
    label = parts[-3] if (len(parts) >= 3 and len(parts[-2]) <= 3
                          and parts[-2] in ("co", "com", "org", "net", "ac")) else parts[-2]
    brand_toks = set(re.split(r"[^a-z0-9]+", slug.lower())) - {""}
    if label in brand_toks:
        return True
    flat = "".join(slug.lower().split("-"))
    if label == flat or flat == label:
        return True
    # get<brand>.com / try<brand>.io / <brand>hq.com: the label must CONTAIN a
    # whole brand token of real length. Deliberately not a prefix test —
    # "huggingface" and "huggingchat" share six characters and are different
    # companies, and that fallback let a tenant claim its host.
    return any(len(t) >= 5 and t in label for t in brand_toks)


def build_automaton(aliases):
    """One Aho-Corasick automaton over all surface forms. Linear in text length.

    A surface form can map to MULTIPLE brands (e.g. `hubspot` → HubSpot CRM
    AND HubSpot Marketing Hub). The automaton stores a LIST of matches per key
    so none is silently dropped.
    """
    A = ahocorasick.Automaton()
    for alias, brand_slug, cls, min_c, disabled in aliases:
        if disabled or len(alias.strip()) < MIN_BARE_LEN:
            continue
        if cls == "SAFE" and _is_plain_english(alias):
            # an ordinary English word is never self-evidently a brand
            cls, min_c = "AMBIGUOUS", max(int(min_c or 0), 1)
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
        # Domain lookup as an automaton, not a scan. The scan it replaces was
        # `for slug, doms in self.domains.items(): for d in doms: d.lower() in norm`
        # — 6,123 substring searches plus 6,123 .lower() calls PER COMMENT,
        # measured at 136 ms/comment, i.e. ~40 s of CPU for one 300-comment
        # tree. Same semantics exactly: plain substring containment, no word
        # boundary (a domain inside a URL must still match).
        # Canonical name per brand, built once — this dict comprehension over
        # 6,040 brands used to run inside resolve() on every comment.
        self._canonical = {b["slug"]: b["brand"].lower()
                           for b in self.brands.values() if isinstance(b, dict)}
        self._domain_ac = None
        pairs = [(d.lower(), slug) for slug, doms in self.domains.items()
                 for d in doms if d and _domain_identifies(d, slug, self.domains)]
        if pairs:
            A = ahocorasick.Automaton()
            for d, slug in pairs:
                cur = A.get(d, None)
                if cur is None:
                    A.add_word(d, [slug])
                elif slug not in cur:
                    cur.append(slug)
            A.make_automaton()
            self._domain_ac = A

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
        if self._domain_ac is not None:
            for _end, slugs in self._domain_ac.iter(norm):
                domain_hits.update(slugs)

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
        canonical = self._canonical
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


_NOUNS_BY_BRAND = None


def _category_nouns_for_brand(brand_slug):
    """Quick lookup of what category a brand lives in, for the subreddit prior.

    Built ONCE. This used to call load_brands() — a full re-parse of the
    6,040-row brands.csv — on every invocation, which profiled as 16.5M csv
    row reads across 6,000 comments and was the single largest cost in the
    whole pipeline.
    """
    global _NOUNS_BY_BRAND
    if _NOUNS_BY_BRAND is None:
        try:
            from harvest import CATEGORY_NOUNS
            _NOUNS_BY_BRAND = {
                slug: CATEGORY_NOUNS.get(b["primary_category_slug"], [])
                for slug, b in load_brands().items()}
        except Exception:
            _NOUNS_BY_BRAND = {}
    return _NOUNS_BY_BRAND.get(brand_slug, [])


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
