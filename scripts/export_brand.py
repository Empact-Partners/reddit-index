#!/usr/bin/env python3
"""Export everything the Reddit Index holds on one brand into plain files a teammate can open (CSV + JSON + README).

Vlad, 2026-10-01: the index is semi-retired, but its data stays useful to the people running a partner's Reddit work;
give them the brand's slice in the partner repo. Read-only: SELECTs on the published views through the Supabase
management API (token: ~/.claude/.supabase-empact.token, Vlad's Mac). Authors are left out on purpose (nobody needs
them to read a thread, and the partner repo can be shared with the partner).

  python3 scripts/export_brand.py --slug contabo --out ~/Projects/empact-partners-repos/partner-contabo/reddit/reddit-index \
      [--labels <a report's data/labelled.jsonl>]

--labels: a research report's own per-item sentiment (labelled.jsonl, items keyed "<thread>:post" / "<thread>:<comment>").
The index stopped scoring sentiment on 25 Aug 2026; where a report labelled the same item later, its label is used and
the row says so (sentiment_source). Joined by Reddit id in code, never by a model.
"""
import argparse, collections, csv, datetime, json, pathlib, urllib.request

REF = "nrsyqcttpijxhwtdtoct"   # the reddit-index Supabase project
LABEL = {0: "neutral", 1: "positive", 2: "negative", 3: "abstain"}


def token() -> str:
    raw = (pathlib.Path.home() / ".claude/.supabase-empact.token").read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        d = json.loads(raw)
        return d.get("token") or d.get("access_token")
    return raw


def q(sql: str) -> list[dict]:
    assert sql.lstrip().lower().startswith(("select", "with")), "read-only"
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{REF}/database/query", method="POST",
                                 data=json.dumps({"query": sql}).encode(),
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0 (reddit-index export_brand)"})
    return json.load(urllib.request.urlopen(req, timeout=180))


def day(ts) -> str:
    return (ts or "")[:10]


def report_labels(path: str | None) -> dict:
    """item key "<thread36>:post" or "<thread36>:<comment36>" -> {sentiment, relevant, citing_answers, archived, locked}"""
    out = {}
    if not path:
        return out
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        lab = r.get("lab") or {}
        out[r["item_id"]] = {"sentiment": lab.get("sentiment"), "relevant": lab.get("relevant"),
                             "citing_answers": r.get("citing_answers") or 0, "archived": r.get("archived"),
                             "locked": r.get("locked"), "thread_id": r.get("thread_id")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels")
    a = ap.parse_args()
    slug = a.slug.replace("'", "")
    brand = q(f"select id, slug, name from published.brands where slug='{slug}'")
    if not brand:
        raise SystemExit(f"{slug} is not in the index")
    b = brand[0]
    bid = int(b["id"])
    mentions = q(f"""
        select m.doc_id, m.doc_type, m.thread_id, m.created_utc, m.permalink, m.score, m.body, m.matched_form, m.label,
               s.name subreddit, t.link_title, t.permalink thread_link, t.created_utc thread_created, t.num_comments,
               t.archived, ms.is_comparative, ms.is_recommendation, ms.evidence_span
        from published.mentions m
        left join published.subreddits s on s.id = m.subreddit_id
        left join published.threads t on t.id = m.thread_id
        left join public.mention_sentiment ms on ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
        where m.brand_id = {bid} order by m.created_utc desc""")
    subs = {r["name"]: r for r in q(f"""select s.name, s.subscribers from published.subreddits s
        where s.id in (select distinct subreddit_id from published.mentions where brand_id = {bid})""")}
    scores = q(f"""select c.slug category, c.name category_name, sc.week_start, sc.reddit_love_score, sc.pos, sc.neg, sc.neu,
        sc.n, sc.n_threads, sc.n_subreddits, sc.window_start, sc.window_end, sc.computed_at
        from published.brand_category_scores sc join published.categories c on c.id = sc.category_id
        where sc.brand_id = {bid} order by sc.week_start, c.slug""")
    rev = q("select mentions_max, sentiment_max from published.corpus_revision")[0]
    labels = report_labels(a.labels)

    out = pathlib.Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in mentions:
        t36 = (m["thread_id"] or "").removeprefix("t3_")
        key = f"{t36}:post" if m["doc_type"] == 2 else f"{t36}:{m['doc_id'].removeprefix('t1_')}"
        rep = labels.get(key)
        if m["label"] is not None:
            sent, src = LABEL.get(m["label"], ""), "index"
        elif rep and rep["relevant"] is False:
            sent, src = "not about the brand", "report"
        elif rep and rep["sentiment"]:
            sent, src = rep["sentiment"], "report"
        else:
            sent, src = "not scored", ""
        rows.append({"date": day(m["created_utc"]), "subreddit": m["subreddit"], "thread_title": m["link_title"],
                     "thread_link": m["thread_link"], "mention_link": m["permalink"],
                     "type": "post" if m["doc_type"] == 2 else "comment", "sentiment": sent, "sentiment_source": src,
                     "comparative": m["is_comparative"], "recommendation": m["is_recommendation"],
                     "upvotes": m["score"], "matched": m["matched_form"], "text": (m["body"] or "").strip(),
                     "_thread": m["thread_id"], "_thread_created": day(m["thread_created"]),
                     "_comments": m["num_comments"], "_archived": m["archived"],
                     "_cited": (labels.get(f"{t36}:post") or {}).get("citing_answers") or max(
                         [v["citing_answers"] for k, v in labels.items() if k.startswith(t36 + ":")] or [0])})
    cols = ["date", "subreddit", "thread_title", "thread_link", "mention_link", "type", "sentiment", "sentiment_source",
            "comparative", "recommendation", "upvotes", "matched", "text"]
    with (out / "mentions.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    by_thread = collections.OrderedDict()
    for r in rows:
        t = by_thread.setdefault(r["_thread"], {"thread_title": r["thread_title"], "subreddit": r["subreddit"],
                                                "thread_link": r["thread_link"], "thread_created": r["_thread_created"],
                                                "comments": r["_comments"], "archived": r["_archived"],
                                                "ai_engine_citations": r["_cited"], "mentions": 0, "positive": 0,
                                                "negative": 0, "neutral": 0, "mixed": 0, "not_scored": 0,
                                                "last_mention": r["date"]})
        t["mentions"] += 1
        s = r["sentiment"]
        k = s if s in ("positive", "negative", "neutral", "mixed") else "not_scored" if s in ("not scored", "abstain") else None
        if k:
            t[k] += 1
        t["last_mention"] = max(t["last_mention"], r["date"])
    for t in by_thread.values():
        p, n = t["positive"], t["negative"]
        t["lean"] = ("negative" if n > p else "positive" if p > n else "even" if p else
                     "neutral" if t["neutral"] or t["mixed"] else "not scored")
    tcols = ["thread_title", "subreddit", "thread_link", "thread_created", "comments", "archived", "ai_engine_citations",
             "mentions", "positive", "negative", "neutral", "mixed", "not_scored", "lean", "last_mention"]
    threads = sorted(by_thread.values(), key=lambda t: t["last_mention"], reverse=True)   # newest first within a tie
    threads.sort(key=lambda t: (-int(t["ai_engine_citations"] or 0), -t["mentions"]))
    with (out / "threads.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=tcols)
        w.writeheader()
        w.writerows(threads)

    by_sub = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        c = by_sub[r["subreddit"]]
        c["mentions"] += 1
        c[r["sentiment"]] += 1
    sub_rows = []
    for name, c in by_sub.items():
        sub_rows.append({"subreddit": name, "mentions": c["mentions"],
                         "threads": len({r["_thread"] for r in rows if r["subreddit"] == name}),
                         "positive": c["positive"], "negative": c["negative"], "neutral": c["neutral"] + c["mixed"],
                         "not_scored": c["not scored"] + c["abstain"],
                         "last_mention": max(r["date"] for r in rows if r["subreddit"] == name),
                         "subscribers": (subs.get(name) or {}).get("subscribers")})
    # the index's rule_posture is left out: it reads "permissive" for subs that ban promotion (r/de_EDV, 2026-10-01)
    sub_rows.sort(key=lambda s: -s["mentions"])
    with (out / "subreddits.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sub_rows[0]))
        w.writeheader()
        w.writerows(sub_rows)

    summary = {"brand": b["name"], "slug": b["slug"], "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "page": f"https://redditindex.com/{b['slug']}/", "mentions": len(rows), "threads": len(by_thread),
               "subreddits": len(sub_rows), "first_mention": min(r["date"] for r in rows), "last_mention": max(r["date"] for r in rows),
               "sentiment": dict(collections.Counter(r["sentiment"] for r in rows)),
               "sentiment_source": dict(collections.Counter(r["sentiment_source"] or "none" for r in rows)),
               "index_sentiment_scored_until": day(rev["sentiment_max"]), "index_mentions_collected_until": day(rev["mentions_max"]),
               "scores": scores}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "scores"}, indent=1, default=str))


if __name__ == "__main__":
    main()
