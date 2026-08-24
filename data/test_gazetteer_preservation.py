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
from still being missing. So this asserts BOTH files and the link between them.

  python3 data/test_gazetteer_preservation.py
"""
import csv
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def gen():
    spec = importlib.util.spec_from_file_location("gb", os.path.join(HERE, "gen_brands.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


print("Gazetteer preservation\n")
m = gen()

# 1. the generator declares which sources it owns, and roster-import is NOT one of them
src = open(os.path.join(HERE, "gen_brands.py")).read()
check("gen_brands declares OWNED_SOURCES", "OWNED_SOURCES" in src)
check("roster-import is NOT claimed as owned",
      "roster-import" not in src.split("OWNED_SOURCES")[1].split("}")[0])
check("it refuses rather than shrinking", "refusing to write" in src)
check("it also refuses a carried brand with no surface form",
      "no surface" in src or "unmatchable" in src)

# 2. the live files agree with each other: every brand has at least one surface form
brands = list(csv.DictReader(open(os.path.join(HERE, "brands.csv"))))
aliases = list(csv.DictReader(open(os.path.join(HERE, "brand-aliases.csv"))))
bslugs = {r["slug"] for r in brands}
aslugs = {r["brand_slug"] for r in aliases}
orphan = sorted(bslugs - aslugs)
check("every brand in brands.csv has a surface form", not orphan,
      f"{len(orphan)} unmatchable, e.g. {orphan[:5]}")
stray = sorted(aslugs - bslugs)
check("no surface form points at a missing brand", not stray,
      f"{len(stray)} stray, e.g. {stray[:5]}")

# 3. the sources this generator does NOT own are still present, in real numbers
owned = {"gazetteer", "seed-brands", "fleet-enum", "fleet-enum-2026-08",
         "fleet-expand-2026-08", "fleet-expand-2026-08-widen"}
unowned = [r for r in brands if r["source"] not in owned]
check("unowned brands survive in the live file", len(unowned) > 2000, f"{len(unowned)}")
ro = [r for r in unowned if r["source"] == "roster-import-2026-08"]
check("the roster import specifically is present", len(ro) > 2000, f"{len(ro)}")

# 4. THE REGRESSION: re-running the generator must not lose any of them.
#    Run it for real in a copy of the data dir and diff.
with tempfile.TemporaryDirectory() as tmp:
    work = os.path.join(tmp, "data")
    subprocess.run(["cp", "-R", HERE, work], check=True, capture_output=True)
    for junk in ("__pycache__",):
        p = os.path.join(work, junk)
        if os.path.isdir(p):
            subprocess.run(["rm", "-rf", p], check=False, capture_output=True)

    before_b = len([r for r in csv.DictReader(open(os.path.join(work, "brands.csv")))
                    if r["source"] not in owned])
    before_a = len(list(csv.DictReader(open(os.path.join(work, "brand-aliases.csv")))))

    r = subprocess.run([sys.executable, os.path.join(work, "gen_brands.py")],
                       capture_output=True, text=True, cwd=os.path.dirname(work))
    check("a re-run exits 0", r.returncode == 0, (r.stderr or "")[-200:])

    if r.returncode == 0:
        after_rows = list(csv.DictReader(open(os.path.join(work, "brands.csv"))))
        after_b = len([x for x in after_rows if x["source"] not in owned])
        after_a = list(csv.DictReader(open(os.path.join(work, "brand-aliases.csv"))))
        check("a re-run keeps every unowned brand", after_b >= before_b,
              f"{before_b} -> {after_b}")
        check("a re-run does not shed surface forms", len(after_a) >= before_a,
              f"{before_a} -> {len(after_a)}")
        ab = {x["slug"] for x in after_rows}
        aa = {x["brand_slug"] for x in after_a}
        check("a re-run leaves no brand unmatchable", not (ab - aa),
              f"{len(ab - aa)} orphaned by the re-run")
        check("it says what it carried", "carried forward" in (r.stdout or ""))

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES")
    sys.exit(1)
print("gazetteer preservation holds")
