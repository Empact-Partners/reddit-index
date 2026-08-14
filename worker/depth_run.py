#!/usr/bin/env python3
"""Stage-3 orchestrator — docs/depth-execution-plan.md, category by category.

Drives the 90-day sweep per category (deepest boards first), then that
category's classify burn, then a global score + publish — so categories come
online WHOLE, visibly deeper, one after another. Every step is idempotent;
kill at any instant and resume with the identical command.

    nohup caffeinate -is python3 -u worker/depth_run.py --days 90 \
        > /tmp/ri-depth.log 2>&1 &
    python3 worker/depth_run.py --status          # anytime, read-only
    python3 worker/depth_run.py --list-approximate

Category order: current mention volume descending, frozen to
.cache/depth/order.json on first run (a resume days later must not reshuffle
as volumes shift mid-sweep). Override with --order slug1,slug2 or restrict
with --category slug.

Publish: the Vercel deploy hook (`deploy_hook` in ~/.claude/.reddit-index.json)
POSTed with retries. The git empty-commit fallback is behind
--allow-git-publish and refuses to run on a dirty tree — a nohup process
never commits or stashes a human session's work.
"""
import argparse, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402
import sweep  # noqa: E402

DEPTH_DIR = os.path.join(HERE, ".cache", "depth")
os.makedirs(DEPTH_DIR, exist_ok=True)
ORDER_FP = os.path.join(DEPTH_DIR, "order.json")
RUN_FP = os.path.join(DEPTH_DIR, "run.json")
CRED_FP = os.path.expanduser("~/.claude/.reddit-index.json")
BACKOFFS = [60, 300, 900]  # between listing re-passes of an incomplete category


def atomic_json(fp, obj):
    with open(fp + ".tmp", "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(fp + ".tmp", fp)


def load_run():
    try:
        return json.load(open(RUN_FP))
    except Exception:
        return {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "done": [], "classified": [], "published_through": None,
                "publish_blocked": False}


def cat_subs(mapping):
    """category_slug -> sorted [subs] (inverted scoring map)."""
    out = {}
    for sub, slugs in mapping.items():
        for s in slugs:
            out.setdefault(s, []).append(sub)
    return {s: sorted(v) for s, v in out.items()}


def category_order(conn, by_cat):
    if os.path.exists(ORDER_FP):
        return json.load(open(ORDER_FP))
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.slug, count(m.doc_id) AS n
            FROM categories c
            JOIN category_subreddits cs ON cs.category_id = c.id AND cs.is_scoring
            LEFT JOIN mentions m ON m.subreddit_id = cs.subreddit_id
            GROUP BY 1 ORDER BY n DESC, c.slug
        """)
        order = [r[0] for r in cur.fetchall() if r[0] in by_cat]
    for slug in sorted(by_cat):  # categories with no DB rows yet tail on
        if slug not in order:
            order.append(slug)
    atomic_json(ORDER_FP, order)
    return order


def deploy_hook():
    try:
        return json.load(open(CRED_FP)).get("deploy_hook") or None
    except Exception:
        return None


def publish(allow_git):
    hook = deploy_hook()
    if hook:
        err = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(hook, data=b"", method="POST")
                with urllib.request.urlopen(req, timeout=30) as f:
                    f.read()
                print("  published (deploy hook)", flush=True)
                return True
            except Exception as e:
                err = e
                time.sleep(min(120, 10 * 2 ** attempt))
        # A missed publish is cosmetic: the data is in Supabase and the next
        # category's publish (or the nightly) renders it.
        print(f"  publish hook FAILED after 5 tries: {err} — data is safe in "
              f"Supabase, next publish picks it up", flush=True)
        return False
    if not allow_git:
        print("  no deploy_hook and --allow-git-publish not set — publish skipped",
              flush=True)
        return False
    dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        print("  working tree dirty — git publish skipped (never stash a "
              "session's work from a nohup process)", flush=True)
        return False
    for cmd in (["git", "-C", REPO, "pull", "--ff-only", "--quiet"],
                ["git", "-C", REPO, "commit", "--allow-empty", "-q", "-m",
                 f"depth publish {time.strftime('%F %H:%M')}"],
                ["git", "-C", REPO, "push", "-q"]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  git publish failed at {' '.join(cmd[3:5])}: "
                  f"{(r.stderr or '').strip()[:160]}", flush=True)
            return False
    print("  published (git empty-commit)", flush=True)
    return True


def classify_burn(slug):
    """Supervised, uncapped, category-scoped. Subprocess so the burn owns
    burn.lock in its own pid and a kill here never wedges the lock."""
    r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "classify_daily.py"),
                        "--category", slug, "--cap", "0", "--loop"], cwd=HERE)
    return r.returncode == 0


def score_and_publish(run_state, allow_git):
    r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "score_db.py")],
                       cwd=HERE)
    if r.returncode != 0:
        # calibration gate refusal — a report item, never a silent retry
        print("  score_db FAILED (calibration gate?) — publish blocked, "
              "sweeping continues", flush=True)
        run_state["publish_blocked"] = True
        atomic_json(RUN_FP, run_state)
        return False
    run_state["publish_blocked"] = False
    ok = publish(allow_git)
    atomic_json(RUN_FP, run_state)
    return ok


def sweep_category(slug, subs, ctx):
    """Re-pass with backoff until every sub is complete or stuck."""
    for rnd in range(len(BACKOFFS) + 1):
        incomplete = [s for s in subs if not sweep.sub_complete(s, ctx["mode"])]
        if not incomplete:
            return True
        if rnd > 0:
            wait = BACKOFFS[min(rnd - 1, len(BACKOFFS) - 1)]
            print(f"  {slug}: {len(incomplete)} subs incomplete — retry in {wait}s",
                  flush=True)
            time.sleep(wait)
        sweep.run_subs(incomplete, ctx)
    left = [s for s in subs if not sweep.sub_complete(s, ctx["mode"])]
    if left:
        print(f"  {slug}: giving up on {len(left)} subs this pass: "
              f"{', '.join(left[:8])}", flush=True)
    return not left


def cmd_status(days, list_approx=False):
    mapping = sweep.load_scoring_map()
    by_cat = cat_subs(mapping)
    mode = sweep.make_mode(days)
    run_state = load_run()
    order = json.load(open(ORDER_FP)) if os.path.exists(ORDER_FP) else sorted(by_cat)

    if list_approx:
        approx = set()
        for sub in mapping:
            try:
                st = json.load(open(sweep.state_path(sub)))
                if st.get("coverage") == "approximate":
                    approx.add(sub)
            except Exception:
                pass
        print("\n".join(sorted(approx)) or "(none)")
        return 0

    mentions, classified, scored = {}, {}, {}
    try:
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.slug, count(*) FROM mentions m
                JOIN category_subreddits cs ON cs.subreddit_id = m.subreddit_id AND cs.is_scoring
                JOIN categories c ON c.id = cs.category_id
                WHERE m.created_utc >= now() - interval '90 days'
                GROUP BY 1""")
            mentions = dict(cur.fetchall())
            cur.execute("""
                SELECT c.slug, count(*) FROM mentions m
                JOIN mention_sentiment ms ON ms.doc_id = m.doc_id AND ms.brand_id = m.brand_id
                JOIN category_subreddits cs ON cs.subreddit_id = m.subreddit_id AND cs.is_scoring
                JOIN categories c ON c.id = cs.category_id
                WHERE m.created_utc >= now() - interval '90 days'
                GROUP BY 1""")
            classified = dict(cur.fetchall())
            cur.execute("""
                SELECT c.slug, count(*) FROM brand_category_scores b
                JOIN categories c ON c.id = b.category_id
                WHERE b.week_start = (SELECT max(week_start) FROM brand_category_scores)
                GROUP BY 1""")
            scored = dict(cur.fetchall())
        conn.close()
    except Exception as e:
        print(f"(DB unavailable — disk columns only: {e})", flush=True)

    print(f"{'category':28} {'subs':>9} {'apx':>3} {'threads':>8} "
          f"{'mentions':>9} {'classified':>10} {'scored':>6}  stage")
    for slug in order:
        subs = by_cat.get(slug, [])
        done = sum(1 for s in subs if sweep.sub_complete(s, mode))
        threads = apx = 0
        for s in subs:
            try:
                st = json.load(open(sweep.state_path(s)))
                threads += len(st.get("post_ids", []))
                apx += 1 if st.get("coverage") == "approximate" else 0
            except Exception:
                pass
        stage = ("done" if slug in run_state["done"] else
                 "classified" if slug in run_state["classified"] else
                 "sweeping" if 0 < done else "pending")
        print(f"{slug:28} {done:>4}/{len(subs):<4} {apx:>3} {threads:>8} "
              f"{mentions.get(slug, 0):>9} {classified.get(slug, 0):>10} "
              f"{scored.get(slug, 0):>6}  {stage}")
    if run_state.get("publish_blocked"):
        print("\n⚠ publish BLOCKED (calibration gate) — see /tmp/ri-depth.log")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--category", action="append", help="restrict to slug(s)")
    ap.add_argument("--order", help="comma-separated slug order override")
    ap.add_argument("--publish-every", type=int, default=1,
                    help="score+publish after every N categories")
    ap.add_argument("--allow-git-publish", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list-approximate", action="store_true")
    args = ap.parse_args()

    if args.status or args.list_approximate:
        return cmd_status(args.days, args.list_approximate)

    ctx = sweep.prepare(args.days)
    mapping = ctx["mapping"]
    by_cat = cat_subs(mapping)

    # ── pre-flight, fail loud ────────────────────────────────────────────────
    missing = sorted(s for s in mapping if s not in ctx["sub_ids"])
    if missing:
        print(f"PRE-FLIGHT FAIL: {len(missing)} scoring subs missing from the "
              f"subreddits table — run `python3 worker/load.py --seed-subs` first.\n"
              f"  {', '.join(missing[:20])}", flush=True)
        return 1
    if not deploy_hook() and not args.allow_git_publish:
        print("PRE-FLIGHT FAIL: no deploy_hook in ~/.claude/.reddit-index.json "
              "and --allow-git-publish not set. Create the Vercel deploy hook "
              "(dashboard, one click) or pass the flag.", flush=True)
        return 1

    if args.order:
        order = [s.strip() for s in args.order.split(",") if s.strip()]
        atomic_json(ORDER_FP, order)
    else:
        order = category_order(ctx["conn"], by_cat)
    if args.category:
        order = [s for s in order if s in set(args.category)]
    bad = [s for s in order if s not in by_cat]
    if bad:
        print(f"PRE-FLIGHT FAIL: slugs with no scoring subs: {bad}", flush=True)
        return 1

    run_state = load_run()
    print(f"depth run: {len(order)} categories, days={args.days}, "
          f"publish_every={args.publish_every}", flush=True)

    since_publish = 0
    for i, slug in enumerate(order, 1):
        if slug in run_state["done"]:
            continue
        # One category must never take the run down. Anything unhandled here
        # (a link that stayed down past every retry, a Supabase blip that
        # outlasted the reconnect ladder) is logged and the run moves on;
        # the category is NOT marked done, so a later pass redoes it and the
        # on-disk sweep state means it resumes rather than restarts.
        try:
            subs = by_cat[slug]
            pending = [s for s in subs if not sweep.sub_complete(s, ctx["mode"])]
            print(f"\n[{i}/{len(order)}] {slug}: {len(subs)} subs "
                  f"({len(subs) - len(pending)} already complete)", flush=True)
            complete = sweep_category(slug, subs, ctx)

            if slug not in run_state["classified"]:
                if classify_burn(slug):
                    run_state["classified"].append(slug)
                    atomic_json(RUN_FP, run_state)
                else:
                    print(f"  {slug}: classify burn failed — will publish without it, "
                          f"nightly picks up the rest", flush=True)

            if complete:
                run_state["done"].append(slug)
            else:
                print(f"  {slug}: left INCOMPLETE — not marked done, a later "
                      f"pass will finish it", flush=True)
                run_state.setdefault("incomplete", [])
                if slug not in run_state["incomplete"]:
                    run_state["incomplete"].append(slug)
            atomic_json(RUN_FP, run_state)
            since_publish += 1
            if since_publish >= args.publish_every:
                print(f"  scoring + publishing after {slug}…", flush=True)
                score_and_publish(run_state, args.allow_git_publish)
                run_state["published_through"] = slug
                atomic_json(RUN_FP, run_state)
                since_publish = 0
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  {slug}: UNHANDLED {type(e).__name__}: "
                  f"{str(e).splitlines()[0][:160]} — continuing", flush=True)
            try:
                ctx["conn"] = db.connect()
            except Exception:
                pass
            time.sleep(30)

    if since_publish:
        score_and_publish(run_state, args.allow_git_publish)

    # A second pass over anything left incomplete (subs that were mid-outage
    # the first time round). Cheap: everything already done is skipped from
    # disk state.
    leftovers = [s for s in order if s not in run_state["done"]]
    if leftovers:
        print(f"\nsecond pass over {len(leftovers)} incomplete categories", flush=True)
        for slug in leftovers:
            try:
                if sweep_category(slug, by_cat[slug], ctx):
                    classify_burn(slug)
                    if slug not in run_state["done"]:
                        run_state["done"].append(slug)
                    atomic_json(RUN_FP, run_state)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"  {slug}: second pass failed: {str(e)[:120]}", flush=True)
        score_and_publish(run_state, args.allow_git_publish)
    print("\nDEPTH RUN COMPLETE", flush=True)
    ctx["conn"].close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
