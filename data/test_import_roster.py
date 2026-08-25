#!/usr/bin/env python3
"""Gate fixtures for import_roster.py — each asserts a KNOWN-BAD input is handled.

Same doctrine as the outreach repo's 02b: a gate that has never failed a bad input is
decoration.

INCIDENT (2026-08-24, DNS): this fixture used to make two REAL DNS lookups — google.com and
a deliberately nonexistent domain — to exercise G4. An audit instrumented socket across all
thirteen fixtures: twelve made zero calls, this one made two, so `must('a live domain
resolves', ...)` went red on any box with no network. That is the expensive kind of red: a
suite that fails because the wifi dropped teaches people to ignore the suite, and the next
real failure gets ignored with it. The thing under test was never DNS — it is
import_roster's handling of what the resolver says. So the resolver is now driven from a
deterministic stand-in at the lowest honest seam (socket.getaddrinfo, which resolve_domain
reads at call time), both outcomes are forced, and a tripwire is installed BEFORE the module
is imported so any real lookup — from the import, from this file, from a future edit — is
recorded and fails a check rather than reaching the network.

INCIDENT (2026-08-24, round 4 — the reason merge() is now DRIVEN): an auditor gutted
import_roster.merge() — deleting the ambiguity strictness rule, G5, the reserved-slug
pre-check and the G1 dedupe — and this file printed "26/26 fixtures passed", exit 0. Each
of the four also escaped on its own. The cause was a copy: four checks ran against
`strictness()`, a re-implementation of merge()'s rule written inline HERE, so they measured
this file rather than production and could not move no matter what merge() did. Two of them
could not go red for ANY edit to either repo ('Kit' took the length branch either way;
max('high', anything) is 'high' either way), and the G5 check compared a list comprehension
written one line above it against a literal. The same shape hid two missing wirings:
reserved_slugs() was tested as a helper while its CALL SITE was not (deleting the rewrite
from merge() left the suite green, so the publish-time `next build` collision this module
exists to prevent would have shipped), and G1 dedupe had no check at all.

So merge() is now RUN, on a synthetic roster in a sandbox: HERE/RI/DRAFT are rebound to a
tempdir on a freshly loaded module instance, the real categories.csv + routing registry are
copied in so the reserved namespace is production's, and every assertion below reads what
merge() actually wrote — the appended seed rows, the rejects file, the summary line. No
rule of merge()'s is restated in this file.

Runs fully offline: no fleet, no DB, no DNS, and it never touches the live data/ files —
the live brand-seed-expand.csv is APPENDED to by merge(), so a fixture that ran merge()
in place would corrupt the running sweep's input.

  python3 data/test_import_roster.py
"""
import ast, contextlib, csv, importlib.util, io, json, os, shutil, socket, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

# ─── offline tripwire ────────────────────────────────────────────────────────────────────
# Installed before import_roster is imported, so it covers import time too. Every name the
# system resolver is normally reached through raises here; REAL_LOOKUPS is asserted empty at
# the end of the run, which is what makes "this fixture is offline" a CHECK and not a claim
# in a docstring (the previous version made exactly that claim, and it was false).
REAL_LOOKUPS = []


def _tripwire(*a, **kw):
    REAL_LOOKUPS.append(a[0] if a else None)
    raise AssertionError(f'fixture attempted a real network lookup: {a[:1]!r}')


for _fn in ('getaddrinfo', 'gethostbyname', 'gethostbyname_ex', 'gethostbyaddr',
            'create_connection'):
    setattr(socket, _fn, _tripwire)

from import_roster import (reserved_slugs, english_words, resolve_domain, is_english_word,
                           category_nouns)
from gen_brands import slugify

FAILS, N = [], 0
def must(name, cond, detail=""):
    global N
    N += 1
    if not cond: FAILS.append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


class FakeResolver:
    """A resolver whose answers are decided here, not by the network.

    Keyed on the hostname, so a resolve_domain that stopped passing its argument through
    (asking about a hardcoded host, say) reads as a failure rather than a pass.
    """
    LIVE = {'acme-live.test'}

    def __init__(self, error=None, live=None):
        self.calls = []
        self.live = set(self.LIVE if live is None else live)
        self.error = error or socket.gaierror(-2, 'Name or service not known')

    def getaddrinfo(self, host, port, *a, **kw):
        self.calls.append((host, port))
        if host in self.live:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '',
                     ('192.0.2.1', port))]
        raise self.error


@contextlib.contextmanager
def resolver(fake):
    """Swap the stand-in in for the duration, then put the tripwire back."""
    socket.getaddrinfo = fake.getaddrinfo
    try:
        yield fake
    finally:
        socket.getaddrinfo = _tripwire


print("import_roster gate fixtures\n")
res = reserved_slugs()

# flat-namespace pre-check: the publish-time build bomb
must("category slugs are reserved (a company slugging to 'crm' must be caught)", "crm" in res)
# every tier, and DOTTED framework paths specifically: the tokens are pulled out of
# registry.mjs with a character-class regex, and a class that forgets the dot silently keeps
# only the undotted half of the tier. There is no count check here on purpose — categories.csv
# alone carries 151 slugs, so `len(res) > 100` was true no matter how much of the registry
# the parse dropped, which is what "reserved set is the full union" used to assert.
must("framework paths are reserved, dotted ones included ('api', 'robots.txt', 'sitemap.xml')",
     {"api", "_next", "robots.txt", "sitemap.xml", "llms.txt"} <= res,
     str({"api", "_next", "robots.txt", "sitemap.xml", "llms.txt"} - res))
must("site routes are reserved ('search', 'methodology')", {"search","methodology"} <= res)
must("reserved slugs come from more than one source (categories are not the whole set)",
     len(res - {r['slug'] for r in csv.DictReader(open(os.path.join(HERE, 'categories.csv')))}) > 0)

# slugify fallback (the Орфограммка class of bug)
def slug_or(name, dom):
    """slugify(), but its SystemExit reads as a FAIL line rather than killing the fixture
    with the other 30-odd checks unevaluated — run_all_fixtures classes that as CRASH, and
    a CRASH is deliberately not a FAIL."""
    try:
        return slugify(name, dom)
    except SystemExit as e:
        return f'<SystemExit: {e}>'


must("a non-Latin name falls back to its domain label",
     slug_or("Орфограммка", "orfogrammka.ru") == "orfogrammka",
     slug_or("Орфограммка", "orfogrammka.ru"))
must("a normal name still slugs normally", slug_or("Acme Corp", "acme.com") == "acme-corp")
try:
    slugify("!!!", "")
    must("a name with no Latin and no domain refuses loudly", False, "did not raise")
except SystemExit:
    must("a name with no Latin and no domain refuses loudly", True)

# ─── merge(), driven on a synthetic roster in a sandbox ───────────────────────────────────
# Everything below this line reads what merge() WROTE. The dictionary is supplied (WORDS)
# so that the strictness checks measure the guard rather than /usr/share/dict/words —
# blanking the dictionary used to be enough to turn the old 'Close' check red while the rule
# it named stayed deleted.
WORDS = {'close', 'front'}          # deliberately NOT 'kit', 'klaviyo', 'crm', 'search'

ROSTER = [
    {'company': 'Close',           'domain': 'close-app.test',   'sells': 'sales crm'},
    {'company': 'Kit',             'domain': 'kit-app.test',     'sells': 'crm'},
    {'company': 'Front',           'domain': 'front-app.test',   'sells': 'shared inbox'},
    {'company': 'Klaviyo',         'domain': 'klaviyo-app.test', 'sells': 'crm'},
    {'company': 'CRM',             'domain': 'crm-app.test',     'sells': 'crm'},
    {'company': 'Pipeline',        'domain': 'pipeline-app.test','sells': 'crm'},
    {'company': 'Search',          'domain': 'search-inc.test',  'sells': 'crm'},
    {'company': 'Dedupe Slug Co',  'domain': 'dedupeslug.test',  'sells': 'crm'},
    {'company': 'Distinctname Co', 'domain': 'dupedomain.test',  'sells': 'crm'},
]
DRAFTS = [
    {'domain': 'close-app.test',   'aliases': ['Close CRM'], 'ambiguity': 'low',
     'stop_contexts': ['close the deal', 'unrelated phrase'], 'note': 'ordinary verb'},
    {'domain': 'kit-app.test',     'aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'short'},
    {'domain': 'front-app.test',   'aliases': [], 'ambiguity': 'high',
     'stop_contexts': ['front of the queue'], 'note': 'ordinary noun'},
    {'domain': 'klaviyo-app.test', 'aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'coinage'},
    {'domain': 'crm-app.test',     'aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'named after its category'},
    {'domain': 'pipeline-app.test','aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'named after one of its category nouns'},
    {'domain': 'search-inc.test',  'aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'site route'},
    {'domain': 'dedupeslug.test',  'aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'slug already in the gazetteer'},
    {'domain': 'dupedomain.test',  'aliases': [], 'ambiguity': 'low',
     'stop_contexts': [], 'note': 'domain already in the gazetteer'},
]
# the gazetteer G1 dedupes against: one slug the reserved rewrite must dodge INTO ('crm'),
# one that makes the rewritten form unresolvable ('search-software'), and one of each
# dedupe key (slug, domain).
BRANDS = ('brand,slug,domains\n'
          'Cee Are Em,crm,ceearem.example\n'
          'Search Software Inc,search-software,searchsoftware.example\n'
          'Dedupe Slug Co Ltd,dedupe-slug-co,otherslug.example\n'
          'Someone Else,someone-else,dupedomain.test\n')
SEED_HEADER = ('brand,primary_category_slug,also_in_category_slugs,aliases,ambiguity_class,'
               'ambiguity_note,domains,stop_contexts,bare_disabled_forms,source\n')


def build_sandbox(tmp):
    """A data/ dir merge() can be pointed at, so nothing it writes lands on the live run."""
    sb = os.path.join(tmp, 'data')
    os.makedirs(os.path.join(sb, '.roster-import', 'gazetteer'))
    os.makedirs(os.path.join(tmp, 'lib', 'routing'))
    # the REAL sources of truth for the reserved namespace: the call site has to be tested
    # against the set production reserves, not a convenient one invented here.
    shutil.copy(os.path.join(HERE, 'categories.csv'), sb)
    shutil.copy(os.path.join(HERE, '..', 'lib', 'routing', 'registry.mjs'),
                os.path.join(tmp, 'lib', 'routing'))
    open(os.path.join(sb, 'brands.csv'), 'w').write(BRANDS)
    open(os.path.join(sb, 'brand-seed-expand.csv'), 'w').write(SEED_HEADER)
    ri = os.path.join(sb, '.roster-import')
    json.dump(ROSTER, open(os.path.join(ri, 'roster.json'), 'w'))
    json.dump([{'domain': r['domain'], 'category_slug': 'crm'} for r in ROSTER],
              open(os.path.join(ri, 'mapping.json'), 'w'))
    json.dump([{'slug': 'crm'}], open(os.path.join(ri, 'categories_ref.json'), 'w'))
    json.dump(DRAFTS, open(os.path.join(ri, 'gazetteer', 'g_000.json'), 'w'))
    return sb


def sandboxed(sb):
    """import_roster bound to the sandbox — same file, its own module instance."""
    spec = importlib.util.spec_from_file_location('import_roster_sandboxed',
                                                  os.path.join(HERE, 'import_roster.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.HERE = sb
    m.RI = os.path.join(sb, '.roster-import')
    m.DRAFT = os.path.join(m.RI, 'gazetteer')
    m.english_words = lambda: WORDS
    return m


with tempfile.TemporaryDirectory() as tmp:
    sb = build_sandbox(tmp)
    mod = sandboxed(sb)
    summary = io.StringIO()
    with resolver(FakeResolver(live={r['domain'] for r in ROSTER})), \
            contextlib.redirect_stdout(summary):
        mod.merge()
    summary = summary.getvalue()
    added = {r['brand']: r for r in csv.DictReader(open(os.path.join(sb,
                                                                    'brand-seed-expand.csv')))}
    rejects = json.load(open(os.path.join(sb, '.roster-import', 'import_rejects.json')))

def col(brand, field, default='<absent>'):
    return added[brand][field] if brand in added else default

# ambiguity strictness: the rule that protects existing boards. Each of these four is a
# DIFFERENT branch of it — an English word, a short name, the floor never lowering a fleet
# 'high', and the rule not firing on a name it has no business touching.
must("merge() lifts an English-word name out of low ('Close' enters as medium)",
     col('Close', 'ambiguity_class') == 'medium', col('Close', 'ambiguity_class'))
must("merge() lifts a 3-char name out of low ('Kit', which is not in the word list)",
     col('Kit', 'ambiguity_class') == 'medium', col('Kit', 'ambiguity_class'))
must("merge() never weakens a fleet 'high' ('Front' is both a word and high)",
     col('Front', 'ambiguity_class') == 'high', col('Front', 'ambiguity_class'))
must("merge() leaves a distinctive coinage at low ('Klaviyo')",
     col('Klaviyo', 'ambiguity_class') == 'low', col('Klaviyo', 'ambiguity_class'))

# G5: a stop-context that does not contain the bare token is dropped before it is written
must("merge() drops a stop-context that lacks the bare token, keeps the one that has it (G5)",
     col('Close', 'stop_contexts') == 'close the deal', col('Close', 'stop_contexts'))

# the reserved-slug pre-check, at its CALL SITE — not the helper. 'CRM' slugs to 'crm',
# which is a category slug AND already a gazetteer slug: without the rewrite it is either
# rejected or swallowed by G1, and the company silently disappears.
must("a company slugging onto a reserved slug is disambiguated and still imported ('CRM')",
     'CRM' in added, sorted(added))
must("a reserved slug whose '-software' form is also taken is rejected, by that name",
     rejects == [['search-inc.test', 'slug collision unresolvable: search-software']],
     str(rejects))
must("'Search' is not imported under the reserved route slug", 'Search' not in added)

# G1 dedupe — had no check at all until round 4
must("a company whose SLUG is already in brands.csv is deduped (G1)",
     'Dedupe Slug Co' not in added, sorted(added))
must("a company whose DOMAIN is already in brands.csv is deduped (G1), under any slug",
     'Distinctname Co' not in added, sorted(added))
must("the dedupes are counted in the summary, not silently dropped",
     'deduped-vs-gazetteer 2' in summary, summary.strip().splitlines()[-2:])
must("merge() appended exactly the rows it should, and no others",
     set(added) == {'Close', 'Kit', 'Front', 'Klaviyo', 'CRM', 'Pipeline'}, sorted(added))

# G3 bare-form disable, also at its call site
must("an English-word bare form is disabled in the written row ('close')",
     'close' in col('Close', 'bare_disabled_forms').split(';'),
     col('Close', 'bare_disabled_forms'))
# 'pipeline' and not 'crm': 'crm' is ALSO an existing gazetteer slug, so the vs-existing
# collision guard disables it too and the check stayed green with the noun rule deleted.
must("a brand named after one of its category's nouns has its bare form disabled ('pipeline')",
     'pipeline' in col('Pipeline', 'bare_disabled_forms').split(';'),
     col('Pipeline', 'bare_disabled_forms'))

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

# ─── G4: both resolver outcomes, decided here rather than by the network ──────────────────
with resolver(FakeResolver()) as fake:
    live = resolve_domain('acme-live.test')
    dead = resolve_domain('this-domain-should-not-exist-9c3f1a.example')
must("a domain the resolver answers for resolves (G4)", live is True, repr(live))
must("a domain the resolver refuses does not resolve (G4)", dead is False, repr(dead))
must("resolve_domain asks about the domain it was handed, on the HTTPS port",
     fake.calls == [('acme-live.test', 443),
                    ('this-domain-should-not-exist-9c3f1a.example', 443)],
     str(fake.calls))

# A transient resolver error must come back as False, never as an exception: merge() maps
# resolve_domain across a ThreadPoolExecutor and then RETRIES the falses. A raise there
# propagates out of ex.map and kills the whole G4 pass mid-import.
with resolver(FakeResolver(error=socket.timeout('timed out'))):
    try:
        transient = resolve_domain('acme-flaky.test')
    except BaseException as e:
        transient = f'raised {type(e).__name__}'
must("a transient resolver error is False, not a raise (the retry pass depends on it)",
     transient is False, repr(transient))

# ─── the seam is the ONLY way out: a future direct socket call must be caught here ────────
TREE = ast.parse(open(os.path.join(HERE, 'import_roster.py')).read())
RESOLVER_CALLS = {'getaddrinfo', 'gethostbyname', 'gethostbyname_ex', 'gethostbyaddr',
                  'create_connection', 'connect', 'connect_ex', 'urlopen', 'urlretrieve'}

OWNER = {}
def _own(node, fn):
    for ch in ast.iter_child_nodes(node):
        nf = ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
        OWNER[ch] = nf
        _own(ch, nf)
_own(TREE, '<module>')

def _callee(node):
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)

net = [(_callee(n), OWNER.get(n, '<module>'), n.lineno)
       for n in ast.walk(TREE) if isinstance(n, ast.Call) and _callee(n) in RESOLVER_CALLS]
must("every resolver call in import_roster.py lives in resolve_domain (one seam, not two)",
     net and all(fn == 'resolve_domain' for _, fn, _ in net), str(net))
must("that seam is not vacuous — resolve_domain really calls the system resolver",
     any(c == 'getaddrinfo' and fn == 'resolve_domain' for c, fn, _ in net), str(net))

# and the seam has to be WIRED: a resolve_domain nobody calls is a guard that is not there
merge_fn = next(n for n in ast.walk(TREE)
                if isinstance(n, ast.FunctionDef) and n.name == 'merge')
mapped = [(m.args[0].id if m.args and isinstance(m.args[0], ast.Name) else 'not-a-name')
          for m in ast.walk(merge_fn)
          if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute)
          and m.func.attr == 'map']
must("G4 in merge() runs through resolve_domain, first pass AND retry",
     len(mapped) == 2 and set(mapped) == {'resolve_domain'}, str(mapped))

# ─── the verdict of this suite must not depend on the wifi ───────────────────────────────
must("the fixture reached the network zero times", not REAL_LOOKUPS, str(REAL_LOOKUPS[:3]))

print(f"\n{N - len(FAILS)}/{N} fixtures passed")
sys.exit(1 if FAILS else 0)
