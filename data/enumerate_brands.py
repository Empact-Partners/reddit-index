#!/usr/bin/env python3
"""Enumerate brands for the new categories on the Codex fleet, then validate.

Three phases, all disk-idempotent (re-running fills gaps only):
  1. ENUMERATE — one fleet job per category (gpt-5.6-sol): real, currently
     shipping products with domains, casual-writing aliases, an ambiguity
     class for the bare name, and stop-contexts for the ambiguous ones.
  2. REVIEW — an adversarial pass on a DIFFERENT model (gpt-5.6-terra):
     kill hallucinated products, wrong-category rows, missed ambiguity.
  3. VALIDATE + MERGE — deterministic gates, then write data/brand-seed-new.csv.

The gates are what make a generated list trustworthy; the models only draft.
  G1 dedupe vs brands.csv and within the run (slug or domain collision ->
     merged into also_in, never a second row)
  G2 an alias that is an English word is forced AMBIGUOUS at minimum, or
     bare-disabled when the model called it low
  G3 an alias claimed by two brands loses its bare form for both
  G4 domains must RESOLVE (socket.getaddrinfo; a wrong domain is auto-accept
     poison) — non-resolving domains dropped and journaled
  G5 a stop-context must contain the bare token
  G6 >= 4 brands per category post-gates, or the category is flagged

Usage:
    python3 data/enumerate_brands.py            # all three phases
    python3 data/enumerate_brands.py --phase 1  # enumeration only

Expansion mode (depth-plan P1a — uncapped rosters over ALL categories):
    python3 data/enumerate_brands.py --expand --only crm,vpn   # pilot
    python3 data/enumerate_brands.py --expand                  # all 100
Expansion enumerates ADDITIONAL brands beyond the per-category known list
(brands.csv is the exclusion set), runs in data/.brand-expand/, and writes
data/brand-seed-expand.csv — same contract, same review, same gates.
"""
import argparse, csv, json, os, re, sys, time, socket
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "worker"))
sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
from codex_fleet import CodexFleet  # noqa: E402

RUN = os.path.join(HERE, ".brand-enum")  # main() repoints this in --expand mode
os.makedirs(RUN, exist_ok=True)
SERVER = "local-mac"
MAX_INFLIGHT = 40

fleet = CodexFleet()

# "existing" = a category that already HAS brands (the original 20), not one
# merely present in categories.csv — that file now carries all 100 rows.
EXISTING_SLUGS = {r["primary_category_slug"] for r in
                  csv.DictReader(open(os.path.join(HERE, "brands.csv")))}


def load_words():
    """Common-English word set for G2. macOS ships /usr/share/dict/words."""
    words = set()
    try:
        for w in open("/usr/share/dict/words"):
            w = w.strip().lower()
            if 2 < len(w) <= 12:
                words.add(w)
    except FileNotFoundError:
        pass
    return words


def taxonomy():
    return list(csv.DictReader(open(os.path.join(HERE, "taxonomy-100.csv"))))


def new_categories():
    return [r for r in taxonomy() if r["slug"] not in EXISTING_SLUGS]


def fleet_running():
    try:
        h = fleet.health()
        for e in (h if isinstance(h, list) else [h]):
            inner = e.get("health") or e
            if not e.get("ok", True):
                return None
            n = inner.get("running")
            if isinstance(n, int):
                return n + (inner.get("queued") or 0)
    except Exception:
        return None
    return None


def wait_for_slot():
    while True:
        n = fleet_running()
        if n is not None and n < MAX_INFLIGHT:
            return
        time.sleep(20 if n is None else 8)


def journal(rec):
    with open(os.path.join(RUN, "journal.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def parse_out(fp):
    try:
        raw = open(fp).read()
        m = re.search(r"\[.*\]", raw, re.S)
        return json.loads(m.group(0) if m else raw)
    except Exception:
        return None


ENUM_PROMPT = """You are compiling a brand gazetteer for the software category "{name}".

List 12-25 REAL software products/services in this category that are actively
discussed on Reddit by the people who buy or use them. Include the obvious
market leaders AND the tools Reddit actually loves or hates. Only products
that exist and ship today — omit rather than guess. No generic terms, no
features, no companies that merely have an adjacent product.

For each product return an object:
  name           canonical product name as written by its maker
  domains        its primary domain(s), lowercase, no scheme (e.g. "notion.so")
  aliases        OTHER surface forms people actually type in casual Reddit
                 comments (abbreviations, old names, common shorthand).
                 NOT the canonical name again. Empty list if none.
  ambiguity      how confusable the BARE name is with ordinary English or
                 other common meanings, one of: "low" (unmistakable, e.g.
                 "QuickBooks"), "medium" (needs context, e.g. "Notion"),
                 "high" (a common word/name, e.g. "Monday", "Bear")
  stop_contexts  ONLY when ambiguity is medium or high: 5-12 short phrases
                 where the bare word appears in its ORDINARY sense on Reddit
                 (e.g. for "Bear": "bear market", "polar bear"). Else [].
  note           one line on the ambiguity call.

Write ONLY a JSON array of these objects to the file {out_fp} (create it).
Do not print the JSON to the console. Do not write any other file."""

EXPAND_PROMPT = """You are deepening a brand gazetteer for the software category "{name}".

The gazetteer already covers these products — do NOT repeat any of them:
{known}

List up to {target} MORE real software products/services in this category that
Reddit actually discusses: the mid-market tools, the niche and vertical
players, the open-source alternatives, the regional leaders, the products a
practitioner subreddit compares against the big names, the tools people
migrate to and from. Only products that exist and ship today. If the category
genuinely has fewer than {target} more, return fewer — omit rather than guess
or pad. No generic terms, no features, no companies that merely have an
adjacent product.

For each product return an object:
  name           canonical product name as written by its maker
  domains        its primary domain(s), lowercase, no scheme (e.g. "notion.so")
  aliases        OTHER surface forms people actually type in casual Reddit
                 comments (abbreviations, old names, common shorthand).
                 NOT the canonical name again. Empty list if none.
  ambiguity      how confusable the BARE name is with ordinary English or
                 other common meanings, one of: "low" (unmistakable, e.g.
                 "QuickBooks"), "medium" (needs context, e.g. "Notion"),
                 "high" (a common word/name, e.g. "Monday", "Bear")
  stop_contexts  ONLY when ambiguity is medium or high: 5-12 short phrases
                 where the bare word appears in its ORDINARY sense on Reddit
                 (e.g. for "Bear": "bear market", "polar bear"). Else [].
  note           one line on the ambiguity call.

Write ONLY a JSON array of these objects to the file {out_fp} (create it).
Do not print the JSON to the console. Do not write any other file."""

REVIEW_PROMPT = """Review this draft brand list for the software category "{name}".
For each entry judge: (a) is this a REAL, currently shipping product (not
hallucinated, not discontinued, not a feature)? (b) is this category a
correct primary or plausible secondary category for it? (c) is the ambiguity
class right for the BARE name ("low" only if the bare token could hardly
mean anything else in casual text)?

Draft:
{draft}

Write ONLY a JSON object to the file {out_fp} (create it): keys are the
product names from the draft, values are objects
  {{"real": bool, "category_ok": bool, "ambiguity": "low"|"medium"|"high"}}.
Judge every entry. Do not print JSON to the console."""


def run_fleet_phase(jobs, label, round_deadline=None, job_timeout=600):
    """jobs: list of (job_id, task, out_fp). Disk-idempotent, 3 rounds.

    round_deadline scales with fan-out width: a fixed 720s over ~95 deep sol
    jobs would expire mid-run and round 2 would RESUBMIT still-running jobs —
    duplicate submissions are disk-safe but burn quota for nothing.

    job_timeout: deep-roster sol jobs run past the 600s default (the first
    100-category run lost 54/95 jobs to exactly that), so expand-mode
    enumeration passes 1500.
    """
    if round_deadline is None:
        round_deadline = max(720, 60 * len(jobs))
    for rnd in range(1, 4):
        pending = [(jid, task, fp) for jid, task, fp in jobs if parse_out(fp) is None]
        if not pending:
            break
        print(f"{label} round {rnd}: {len(pending)} jobs", flush=True)
        for jid, task, fp in pending:
            if os.path.exists(fp):
                os.remove(fp)
            wait_for_slot()
            journal({"phase": label, "job": jid, "round": rnd, "t": time.time()})
            for attempt in range(5):
                try:
                    model = "gpt-5.6-sol" if label == "enum" else "gpt-5.6-terra"
                    r = fleet.submit(task, server=SERVER, mode="workspace-write",
                                     model=model, workspace=RUN, timeout=job_timeout,
                                     reasoning_effort="medium")
                    journal({"phase": label, "job": jid, "job_id": r["job_id"]})
                    break
                except Exception:
                    time.sleep(10 * (attempt + 1))
        deadline = time.time() + round_deadline
        last_done, last_change = -1, time.time()
        while time.time() < deadline:
            left = [1 for _, _, fp in pending if parse_out(fp) is None]
            done = len(jobs) - len([1 for _, _, fp in jobs if parse_out(fp) is None])
            print(f"  {done}/{len(jobs)} {label} done", flush=True)
            if not left:
                break
            if done != last_done:
                last_done, last_change = done, time.time()
            elif time.time() - last_change > 180 and (fleet_running() or 0) == 0:
                # every remaining job is dead (timeout/error) — stop idling out
                # the deadline and let the next round resubmit them now
                print(f"  {label}: fleet idle, no progress 180s -> next round",
                      flush=True)
                break
            time.sleep(25)


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def resolve_domain(d):
    try:
        socket.getaddrinfo(d, 443, proto=socket.IPPROTO_TCP)
        return True
    except Exception:
        return False


def main():
    global RUN
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=0, help="0 = all")
    ap.add_argument("--expand", action="store_true",
                    help="depth expansion: ALL categories, known brands excluded")
    ap.add_argument("--only", default="",
                    help="comma-separated category slugs (expansion pilot)")
    ap.add_argument("--target", type=int, default=60,
                    help="expansion: max ADDITIONAL brands requested per category")
    args = ap.parse_args()

    if args.expand:
        RUN = os.path.join(HERE, ".brand-expand")
        os.makedirs(RUN, exist_ok=True)
        cats = taxonomy()
        if args.only:
            keep = {s.strip() for s in args.only.split(",") if s.strip()}
            cats = [c for c in cats if c["slug"] in keep]
        # Per-category known names (primary + also_in) — the exclusion list.
        known_by_cat = {}
        for r in csv.DictReader(open(os.path.join(HERE, "brands.csv"))):
            slugs = {r["primary_category_slug"]}
            slugs.update(c for c in (r.get("also_in_category_slugs") or "").split(";") if c)
            for cs in slugs:
                known_by_cat.setdefault(cs, []).append(r["brand"])
        print(f"expansion over {len(cats)} categories", flush=True)
    else:
        cats = new_categories()
        print(f"{len(cats)} new categories", flush=True)

    # ── phase 1: enumerate ──────────────────────────────────────────────────
    enum_jobs = []
    for c in cats:
        fp = os.path.join(RUN, f"out_{c['slug']}.json")
        if args.expand:
            known = ", ".join(sorted(known_by_cat.get(c["slug"], []))) or "(none yet)"
            task = EXPAND_PROMPT.format(name=c["category"], known=known,
                                        target=args.target, out_fp=fp)
        else:
            task = ENUM_PROMPT.format(name=c["category"], out_fp=fp)
        enum_jobs.append((c["slug"], task, fp))
    if args.phase in (0, 1):
        run_fleet_phase(enum_jobs, "enum",
                        job_timeout=1500 if args.expand else 600)
    if args.phase == 1:
        return 0

    # ── phase 2: adversarial review ─────────────────────────────────────────
    review_jobs = []
    for c in cats:
        src = parse_out(os.path.join(RUN, f"out_{c['slug']}.json"))
        if not src:
            continue
        fp = os.path.join(RUN, f"review_{c['slug']}.json")
        draft = json.dumps([{"name": b.get("name"), "domains": b.get("domains"),
                             "ambiguity": b.get("ambiguity")} for b in src], indent=1)
        review_jobs.append((c["slug"], REVIEW_PROMPT.format(
            name=c["category"], draft=draft, out_fp=fp), fp))
    if args.phase in (0, 2):
        run_fleet_phase(review_jobs, "review")
    if args.phase == 2:
        return 0

    # ── phase 3: deterministic gates + merge ────────────────────────────────
    words = load_words()
    existing = list(csv.DictReader(open(os.path.join(HERE, "brands.csv"))))
    existing_slugs = {r["slug"]: r for r in existing}
    existing_domains = {}
    for r in existing:
        for d in (r["domains"] or "").split(";"):
            if d:
                existing_domains[d.strip().lower()] = r["slug"]

    rows, alias_claims, rejects = {}, {}, []
    also_in = {}  # existing brand slug -> set of extra categories

    def reject(cat, name, why):
        rejects.append({"category": cat, "brand": name, "why": why})

    # first pass: collect + per-brand gates
    for c in cats:
        slug_c = c["slug"]
        src = parse_out(os.path.join(RUN, f"out_{slug_c}.json")) or []
        review = parse_out(os.path.join(RUN, f"review_{slug_c}.json")) or {}
        for b in src:
            name = (b.get("name") or "").strip()
            if not name:
                continue
            v = review.get(name, {})
            if v and (v.get("real") is False or v.get("category_ok") is False):
                reject(slug_c, name, "review: " + json.dumps(v))
                continue
            amb = str(b.get("ambiguity") or "medium").lower()
            if amb not in ("low", "medium", "high"):
                amb = "medium"
            rv = str(v.get("ambiguity") or "").lower()
            order = {"low": 0, "medium": 1, "high": 2}
            if rv in order and order[rv] > order[amb]:
                amb = rv  # the reviewer only ever RAISES ambiguity
            bslug = slugify(name)
            domains = []
            for d in (b.get("domains") or []):
                d = str(d).strip().lower().replace("https://", "").replace("http://", "").strip("/")
                if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", d):
                    reject(slug_c, name, f"domain syntax: {d}")
                    continue
                domains.append(d)
            # G2: english-word bare name forces >= medium
            if name.lower() in words and amb == "low":
                amb = "medium"
            # G1: dedupe vs existing
            hit = existing_slugs.get(bslug)
            if not hit:
                for d in domains:
                    if d in existing_domains:
                        hit = existing_slugs[existing_domains[d]]
                        break
            if hit:
                also_in.setdefault(hit["slug"], set()).add(slug_c)
                continue
            if bslug in rows:
                rows[bslug]["cats"].add(slug_c)
                continue
            aliases = []
            for a in (b.get("aliases") or []):
                a = str(a).strip()
                if a and a.lower() != name.lower():
                    aliases.append(a)
            stops = [s.strip() for s in (b.get("stop_contexts") or [])
                     if name.lower().split()[0] in str(s).lower()]
            rows[bslug] = {
                "name": name, "slug": bslug, "cats": {slug_c}, "amb": amb,
                "aliases": aliases, "domains": domains, "stops": stops,
                "note": str(b.get("note") or "")[:200],
            }
            for form in [name] + aliases:
                alias_claims.setdefault(form.lower(), set()).add(bslug)

    # G3: cross-brand alias collision -> bare form disabled for all claimants
    bare_disabled = {}
    for form, claimants in alias_claims.items():
        if len(claimants) > 1:
            for bslug in claimants:
                bare_disabled.setdefault(bslug, set()).add(form)

    # G2b: single-english-word alias forms get bare-disabled
    for bslug, r in rows.items():
        for form in [r["name"]] + r["aliases"]:
            f = form.lower()
            if " " not in f and "." not in f and f in words:
                bare_disabled.setdefault(bslug, set()).add(f)

    # G4: domains must resolve (concurrent — pure DNS, no credits)
    all_domains = sorted({d for r in rows.values() for d in r["domains"]})
    with ThreadPoolExecutor(max_workers=32) as ex:
        ok = dict(zip(all_domains, ex.map(resolve_domain, all_domains)))
    for r in rows.values():
        kept = [d for d in r["domains"] if ok.get(d)]
        for d in r["domains"]:
            if not ok.get(d):
                reject(next(iter(r["cats"])), r["name"], f"domain does not resolve: {d}")
        r["domains"] = kept

    # G6: per-category floor
    by_cat = {}
    for r in rows.values():
        for cs in r["cats"]:
            by_cat.setdefault(cs, []).append(r)
    for c in cats:
        n = len(by_cat.get(c["slug"], []))
        if n < 4:
            print(f"  !! {c['slug']}: only {n} brands post-gates", flush=True)

    # write the seed CSV (same contract either mode)
    out_fp = os.path.join(HERE, "brand-seed-expand.csv" if args.expand
                          else "brand-seed-new.csv")
    source_tag = "fleet-expand-2026-08" if args.expand else "fleet-enum-2026-08"
    with open(out_fp + ".tmp", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["brand", "primary_category_slug", "also_in_category_slugs",
                    "aliases", "ambiguity_class", "ambiguity_note", "domains",
                    "stop_contexts", "bare_disabled_forms", "source"])
        for bslug in sorted(rows):
            r = rows[bslug]
            cats_sorted = sorted(r["cats"])
            w.writerow([
                r["name"], cats_sorted[0], ";".join(cats_sorted[1:]),
                ";".join(r["aliases"]), r["amb"], r["note"],
                ";".join(r["domains"]), ";".join(r["stops"]),
                ";".join(sorted(bare_disabled.get(bslug, set()))),
                source_tag,
            ])
        # Existing brands seen in ANOTHER category's list: emit a widen-only
        # row (gen_brands treats an already-known brand as also_in-widening,
        # never a duplicate). This is how cross-category membership deepens.
        for eslug in sorted(also_in):
            er = existing_slugs[eslug]
            have = {er["primary_category_slug"]}
            have.update(c for c in (er.get("also_in_category_slugs") or "").split(";") if c)
            extra = sorted(c for c in also_in[eslug] if c not in have)
            if extra:
                w.writerow([er["brand"], er["primary_category_slug"],
                            ";".join(extra), "", er["ambiguity_class"], "",
                            "", "", "", source_tag + "-widen"])
    os.replace(out_fp + ".tmp", out_fp)

    json.dump({"rejects": rejects,
               "also_in": {k: sorted(v) for k, v in also_in.items()}},
              open(os.path.join(RUN, "gates-report.json"), "w"), indent=1)
    print(f"\n{len(rows)} new brands -> {out_fp}")
    print(f"{len(rejects)} rejects, {len(also_in)} existing brands gain categories "
          f"(.brand-enum/gates-report.json)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
