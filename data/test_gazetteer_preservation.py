#!/usr/bin/env python3
"""A generator that rebuilds a shared file must preserve what it did not generate.

This is the third time the same bug shape has cost this project real time:

  2026-08-22  discover_v2 rewrote category-subreddits.csv from a fixed column list and would
              have wiped 1,741 is_core slots        -> test_csv_preservation.py
  2026-08-24  enumerate_brands --only rebuilt brand-seed-expand.csv from just the requested
              categories, deleting 6,132 rows       -> test_seed_csv_preservation.py
  2026-08-24  gen_brands rebuilt brands.csv AND brand-aliases.csv from its own seed files and
              DELETED 989 roster-import brands mid-collection. resolve.py reads its gazetteer
              from those files, so the sweep spent an hour silently discarding every mention
              of the never-replied companies the whole wave exists to find.

The third one had a sting: a first fix restored the brands but not their surface forms, which
leaves a brand in the gazetteer and completely unmatchable — indistinguishable, in the data,
from still being missing. So this asserts BOTH files and the link between them, and it asserts
each refusal by RUNNING the generator into it, not by grepping for the message.

The fixture itself then cost something. Until 2026-08-24 it built its scratch copy with
`cp -R <data dir>`: 1.7 GB including the 525 MB .discover-v2 cache, 113.6 s per run against a
20 s house budget — and it copied brand-seed-expand.csv while the live pipeline was mid-write
to it. A torn input silently moves the before/after baseline this whole file is built on. So
the copy is now exactly the seven files gen_brands.py opens; every one is proven not to have
moved while it was being copied; and anything that could not be proven prints as `skip`, never
as `ok`. `skip` is not a pass — it exits non-zero-safe but is counted and reported separately.

  python3 data/test_gazetteer_preservation.py
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []
SKIPS = []

# Exactly what gen_brands.py opens — read off its source, not guessed:
#   reads   categories.csv, brand-gazetteer-seed.csv, brand-seed-new.csv, brand-seed-expand.csv
#   reads + rewrites  brands.csv, brand-aliases.csv
# Nothing else in data/ is involved, and the .discover-v2 cache least of all.
# "the fixture copies every file gen_brands.py names" below re-derives this from the source,
# so adding a read to gen_brands.py without adding it here is a FAIL, not a silent miss.
NEEDED = ("gen_brands.py", "categories.csv", "brand-gazetteer-seed.csv",
          "brand-seed-new.csv", "brand-seed-expand.csv",
          "brands.csv", "brand-aliases.csv")
MAX_COPY_BYTES = 32 * 1024 * 1024

ALIAS_COLS = ["brand_slug", "alias", "alias_type", "surface_class",
              "min_corroborating", "bare_disabled"]

# the sources gen_brands.py generates. Everything else in brands.csv arrives by another path
# (import_roster.py) and is exactly what the carry-forward exists to protect.
OWNED = {"gazetteer", "seed-brands", "fleet-enum", "fleet-enum-2026-08",
         "fleet-expand-2026-08", "fleet-expand-2026-08-widen"}


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def skip(name, why):
    """A check that could NOT be evaluated. Never printed as ok, never counted as passing."""
    print("  skip " + name + f"  [{why}]")
    SKIPS.append(name)


def sig(path):
    """Size + mtime, the two things a concurrent writer moves."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_size, st.st_mtime_ns)


def copy_set(dst, tries=4):
    """Copy the seven files into dst. Returns the names that would not hold still.

    The live pipeline writes brand-seed-expand.csv while this runs. Every claim in this file
    is a before/after row count, so a half-written input moves the baseline without saying so.
    Preference is to RE-COPY until the file is provably unchanged across the copy; only if it
    never settles does the caller skip the assertions that read it.
    """
    os.makedirs(dst, exist_ok=True)
    unstable = []
    for name in NEEDED:
        src = os.path.join(HERE, name)
        for _ in range(tries):
            before = sig(src)
            if before is None:
                break                       # absent is a stable state; the seed files are optional
            shutil.copy2(src, os.path.join(dst, name))
            if sig(src) == before:
                break                       # size and mtime both unmoved across the read
        else:
            unstable.append(name)
    return unstable


def copied_bytes(d):
    return sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))


def run_gen(d):
    return subprocess.run([sys.executable, os.path.join(d, "gen_brands.py")],
                          capture_output=True, text=True, cwd=d)


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


print("Gazetteer preservation\n")

tmp = tempfile.mkdtemp(prefix="gazetteer-fixture-")
try:
    work = os.path.join(tmp, "data")
    unstable = copy_set(work)

    def blocked(*names):
        return [n for n in names if n in unstable]

    # 0. the copy holds the seven files and NOTHING else. The incident that made this fixture
    #    unrunnable beside a live pipeline was copying the whole directory instead: 1.7 GB and
    #    113.6 s, and it read two CSVs the pipeline was mid-write to. A whole-directory copy
    #    fails here on the first stray name, long before it fails on size.
    extra = sorted(set(os.listdir(work)) - set(NEEDED))
    size = copied_bytes(work)
    check("the working copy holds only what gen_brands.py opens",
          not extra and size <= MAX_COPY_BYTES,
          f"{len(extra)} extra, e.g. {extra[:4]}; {size / 1e6:.1f} MB copied "
          f"against a {MAX_COPY_BYTES / 1e6:.0f} MB cap")

    if blocked("gen_brands.py"):
        for n in ("the fixture copies every file gen_brands.py names",
                  "gen_brands declares OWNED_SOURCES",
                  "roster-import is NOT claimed as owned",
                  "it refuses rather than shrinking",
                  "it also refuses a carried brand with no surface form"):
            skip(n, "gen_brands.py changed while being copied")
        src = ""
    else:
        src = open(os.path.join(work, "gen_brands.py")).read()

        # the copy set is derived from the source, so it cannot quietly go stale
        opened = sorted(set(re.findall(
            r"os\.path\.join\(\s*HERE\s*,\s*[\"']([^\"']+)[\"']\s*\)", src)))
        missed = [f for f in opened if f not in NEEDED]
        check("the fixture copies every file gen_brands.py names", not missed,
              f"gen_brands opens {missed}, which the fixture never copied")

        # 1. the generator declares which sources it owns, and roster-import is NOT one of them
        check("gen_brands declares OWNED_SOURCES", "OWNED_SOURCES" in src)
        check("roster-import is NOT claimed as owned",
              "OWNED_SOURCES" in src
              and "roster-import" not in src.split("OWNED_SOURCES")[1].split("}")[0])
        check("it refuses rather than shrinking", "refusing to write" in src)
        check("it also refuses a carried brand with no surface form",
              "no surface" in src or "unmatchable" in src)

    # 2. the two files agree with each other: every brand has at least one surface form.
    #    Read from the proven-stable copy, so sections 2, 3 and 4 all see ONE snapshot.
    b_block = blocked("brands.csv", "brand-aliases.csv")
    if b_block:
        for n in ("every brand in brands.csv has a surface form",
                  "no surface form points at a missing brand"):
            skip(n, f"{', '.join(b_block)} changed while being copied")
        brands = []
    else:
        brands = rows(os.path.join(work, "brands.csv"))
        aliases = rows(os.path.join(work, "brand-aliases.csv"))
        bslugs = {r["slug"] for r in brands}
        aslugs = {r["brand_slug"] for r in aliases}
        orphan = sorted(bslugs - aslugs)
        check("every brand in brands.csv has a surface form", not orphan,
              f"{len(orphan)} unmatchable, e.g. {orphan[:5]}")
        stray = sorted(aslugs - bslugs)
        check("no surface form points at a missing brand", not stray,
              f"{len(stray)} stray, e.g. {stray[:5]}")

    # 3. the sources this generator does NOT own are still present, in real numbers
    if blocked("brands.csv"):
        for n in ("unowned brands survive in the live file",
                  "the roster import specifically is present"):
            skip(n, "brands.csv changed while being copied")
    else:
        unowned = [r for r in brands if r["source"] not in OWNED]
        check("unowned brands survive in the live file", len(unowned) > 2000, f"{len(unowned)}")
        ro = [r for r in unowned if r["source"] == "roster-import-2026-08"]
        check("the roster import specifically is present", len(ro) > 2000, f"{len(ro)}")

    # 4. THE REGRESSION: re-running the generator must not lose any of them.
    #    Run it for real against the copy and diff. Any moved input makes the BASELINE wrong,
    #    not just the inputs, so every assertion here is skipped rather than guessed at.
    rerun_checks = ("a re-run exits 0",
                    "a re-run keeps every unowned brand",
                    "a re-run does not shed surface forms",
                    "a re-run leaves no brand unmatchable",
                    "it says what it carried")
    carried_n = None
    if unstable:
        for n in rerun_checks:
            skip(n, f"{', '.join(unstable)} changed while being copied")
    else:
        before_b = len([r for r in rows(os.path.join(work, "brands.csv"))
                        if r["source"] not in OWNED])
        before_a = len(rows(os.path.join(work, "brand-aliases.csv")))

        r = run_gen(work)
        check("a re-run exits 0", r.returncode == 0, (r.stderr or "")[-200:])

        if r.returncode == 0:
            after_rows = rows(os.path.join(work, "brands.csv"))
            after_b = len([x for x in after_rows if x["source"] not in OWNED])
            after_a = rows(os.path.join(work, "brand-aliases.csv"))
            check("a re-run keeps every unowned brand", after_b >= before_b,
                  f"{before_b} -> {after_b}")
            check("a re-run does not shed surface forms", len(after_a) >= before_a,
                  f"{before_a} -> {len(after_a)}")
            ab = {x["slug"] for x in after_rows}
            aa = {x["brand_slug"] for x in after_a}
            check("a re-run leaves no brand unmatchable", not (ab - aa),
                  f"{len(ab - aa)} orphaned by the re-run")
            check("it says what it carried", "carried forward" in (r.stdout or ""))
            mm = re.search(r"carried forward (\d+) brands", r.stdout or "")
            carried_n = int(mm.group(1)) if mm else 0
        else:
            for n in rerun_checks[1:]:
                skip(n, "the re-run did not complete")

    # 5. the three refusals, exercised rather than grepped. Each runs the real generator into
    #    a copy that has been damaged in exactly the way the 2026-08-24 incident (and its first
    #    botched fix) damaged the live files, and requires a non-zero exit naming the reason.
    #    A refusal that only exists as a string in the source is not a refusal.
    refusals = ("a missing alias file is refused, not written through",
                "carried brands left with no surface form are refused",
                "an unowned count that would shrink is refused")

    def fixture(tag, damage):
        d = os.path.join(tmp, tag)
        u = copy_set(d)
        if u:
            return None, f"{', '.join(u)} changed while being copied"
        damage(d)
        return run_gen(d), None

    def drop_alias_file(d):
        os.remove(os.path.join(d, "brand-aliases.csv"))

    def empty_alias_file(d):
        with open(os.path.join(d, "brand-aliases.csv"), "w", newline="") as f:
            csv.DictWriter(f, fieldnames=ALIAS_COLS).writeheader()

    def shadow_an_owned_slug(d):
        """Give an unowned brand a slug the generator itself produces.

        carry-forward skips a previous row whose slug the generator already emits, so this
        row cannot come back — which is precisely the shape the shrink guard must catch.
        """
        p = os.path.join(d, "brands.csv")
        existing = rows(p)
        donor = next(x for x in existing if x["source"] in OWNED)
        ghost = dict(donor)
        ghost["brand"] = donor["brand"] + " (roster ghost)"
        ghost["source"] = "roster-import-2026-08"
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(existing[0].keys()))
            w.writeheader()
            w.writerows(existing + [ghost])

    if unstable:
        for n in refusals:
            skip(n, f"{', '.join(unstable)} changed while being copied")
    elif carried_n == 0:
        # nothing is being carried, so nothing can be dropped: these would pass vacuously
        for n in refusals[:2]:
            skip(n, "no unowned brands are being carried, the refusal cannot be reached")
    else:
        for name, damage, needle in (
            (refusals[0], drop_alias_file, "brand-aliases.csv is missing"),
            (refusals[1], empty_alias_file, "no surface"),
            (refusals[2], shadow_an_owned_slug, "would drop"),
        ):
            res, why = fixture(name.split()[1] + str(refusals.index(name)), damage)
            if res is None:
                skip(name, why)
                continue
            out = (res.stderr or "") + (res.stdout or "")
            check(name, res.returncode != 0 and needle in out,
                  f"rc={res.returncode}, said {out.strip().splitlines()[-1:]}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if SKIPS:
    print(f"{len(SKIPS)} SKIPPED (not evaluated): {', '.join(SKIPS)}")
if FAILS:
    print(f"{len(FAILS)} FAILURES")
    sys.exit(1)
if SKIPS:
    # not a pass for those: the live pipeline was mid-write and the baseline could not be trusted
    print(f"gazetteer preservation holds for what was evaluated — {len(SKIPS)} were NOT, "
          f"re-run when the pipeline is idle")
else:
    print("gazetteer preservation holds")
