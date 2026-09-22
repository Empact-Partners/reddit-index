import "server-only";
import postgres from "postgres";
import { CATEGORIES, type CategorySlug } from "@/lib/generated/categories";
import { METHODOLOGY_VERSION } from "@/lib/format";
import { fitPriorPooled, pageScore as computePageScore } from "@/lib/data/page-score";
import type { BrandScore, CategoryView, CompanyView, FailedTest, Snapshot } from "./types";
import type { Mention, Sentiment } from "@/components/data/mention-card";
import { railVerdict } from "./rail-freshness";

/**
 * ONE fetch per build worker, not one per page.
 *
 * 08-architecture.md §4 calls this "the single biggest lever" on build time: a
 * 5,000-page build that queries per page is 5,000 round trips, and the same
 * build that queries once is four. The memo is deliberately build-phase-only —
 * at runtime a warm lambda would otherwise serve a frozen snapshot forever.
 *
 * Mentions are NOT in the eager snapshot. They are the one unbounded table, and
 * loading every one of them into a module-scoped map is exactly the mistake
 * §2 warns about, one layer up.
 */

const SITE_READER_URL = process.env.DATABASE_URL_READONLY;

let sql: ReturnType<typeof postgres> | null = null;
function db() {
  if (!SITE_READER_URL) {
    throw new Error(
      "DATABASE_URL_READONLY is not set. The reader path uses a dedicated " +
      "site_reader Postgres role through Supavisor TRANSACTION mode on port 6543 " +
      "(08-architecture.md §5) — the site ships no anon key at all.",
    );
  }
  sql ??= postgres(SITE_READER_URL, {
    // Mandatory on 6543: transaction mode cannot hold a prepared statement
    // across a checkout, and connections error without this.
    prepare: false,
    max: 10,           // §5: "Cap the build's pool at ~10"
    idle_timeout: 20,
    connect_timeout: 15,
    ssl: "require",
    onnotice: () => {},
  });
  return sql;
}

const SENTIMENT: Record<number, Sentiment> = { 0: "neu", 1: "pos", 2: "neg", 3: "abstain" };

let snapshotPromise: Promise<Snapshot> | null = null;

export function getSnapshot(): Promise<Snapshot> {
  if (process.env.NEXT_PHASE === "phase-production-build") {
    return (snapshotPromise ??= loadSnapshot());
  }
  return (snapshotPromise ??= loadSnapshot());
}

/**
 * Retry the whole snapshot fetch on a transport failure.
 *
 * `next build` prerenders in several worker processes and each runs this
 * query; the Supabase TRANSACTION pooler drops a connection under that load
 * and the build dies at 90% on an arbitrary page (CONNECTION_CLOSED on
 * /customshow one run, /big-agi the next — a different page each time, which
 * is the signature of load rather than of bad data). The query is a pure
 * read, so retrying it is free and safe.
 */
async function withRetry<T>(fn: () => Promise<T>, tries = 4): Promise<T> {
  let last: unknown;
  for (let i = 0; i < tries; i++) {
    try {
      return await fn();
    } catch (e) {
      last = e;
      const msg = String((e as { message?: string })?.message ?? e);
      const transient = /CONNECTION_CLOSED|ECONNRESET|ETIMEDOUT|socket|terminat|statement timeout|57014|PARTIAL_RESULT/i.test(msg);
      if (!transient || i === tries - 1) throw e;
      await new Promise((r) => setTimeout(r, 1500 * 2 ** i));
    }
  }
  throw last;
}

async function loadSnapshot(): Promise<Snapshot> {
  return withRetry(() => loadSnapshotOnce());
}

async function loadSnapshotOnce(): Promise<Snapshot> {
  const t0 = Date.now();
  const s = db();

  // THE CARDS AND THE PROOF THAT THEY ARE CURRENT COME FROM ONE SNAPSHOT. Read on separate pooled connections,
  // a refresh committing mid-load could pair the OLD rail's cards with the NEW rail's metadata, and the guard
  // would certify cards it never saw (round 2 of PR #3's review). One repeatable-read transaction makes the
  // three reads see the same database state; it runs beside the 11.9s aggregate, so it costs nothing.
  const railRead = s.begin("isolation level repeatable read read only", async (tx) => {
    const cards = await tx`select brand_slug, brand_name, subreddit, doc_id, doc_type, thread_id,
             author, created_utc, permalink, body, matched_form, label
      from published.mention_rail`;
    const meta = await tx`select refreshed_at, rail_rows, mentions_max, mentions_rows, sentiment_max, sentiment_rows,
             removals_max, removals_rows
      from published.mention_rail_meta`;
    const rev = await tx`select mentions_rows, mentions_max, sentiment_rows, sentiment_max,
             removals_rows, removals_max, removals_pending
      from published.corpus_revision`;
    return [cards, meta, rev] as const;
  });

  const [catRows, brandRows, scoreRows, subCounts, [mentionRows, railMeta, corpusRevision], mentionAgg,
         threadRows] = await Promise.all([
    s`select id, slug, name, threshold_tier, precision_target_pp, n_min, base_rate_c, status
      from published.categories`,
    s`select id, slug, name, primary_category_id from published.brands`,
    s`select * from published.brand_category_scores
      where week_start = (select max(week_start) from published.brand_category_scores)`,
    s`select cs.category_id, count(*)::int as n
      from published.category_subreddits cs where cs.is_scoring group by 1`,
    // THE RAIL IS PRECOMPUTED (migration 0005). It used to be a LATERAL per brand over
    // published.mentions: the newest 80 comments and 40 posts for each of 10,511 brands (doc_type 1 is a comment, 2 is a post —
    // the comment this replaced had that pair the wrong way round). That is
    // correct and it was unaffordable — `mentions` is partitioned by month, so finding one brand's
    // newest rows merges across all 49 partitions, about a million index probes. Measured on
    // production 2026-09-22 with 0004's indexes valid on every partition: 86,909 ms and 2,786,173
    // shared buffers, TWICE per build (next.config.ts caps the build at 2 workers and each worker
    // runs this whole function), against a 300s per-page timeout — and growing on both axes, one
    // more partition every month and more brands every sweep.
    //
    // The same 161,660 rows now come from a materialised view refreshed once at publish time:
    // 562 ms and 16,704 buffers, proven row-for-row identical to the query above (0 rows in either
    // EXCEPT direction). The view carries only the eleven columns this function reads — score,
    // intensity, stage, subreddit_id and brand_id were being read from disk and shipped for nothing.
    //
    // The rails are still 80 + 40 per document type, and everything the comment below argued about
    // why still holds; it moved into the view's definition, it did not go away.
    railRead,
    // The dashboard aggregates: TRUE totals over the whole table, per
    // (brand x subreddit x doc_type x label) — the stat tiles, the type
    // filter counts and the subreddit ledger must describe everything
    // collected, not the cards shown. `oldest` is here so the page can say
    // how far back collection reaches without an ascending scan (measured at
    // 35s and back into statement-timeout territory).
    s`select m.brand_id, sr.name as subreddit, m.doc_type, m.label,
             count(*)::int as n, max(m.created_utc) as newest,
             min(m.created_utc) as oldest
      from published.mentions m
      join published.subreddits sr on sr.id = m.subreddit_id
      group by 1, 2, 3, 4`,
    // Thread titles, flat. A post card without its headline reads exactly like
    // a comment, which is half of why the index looked comment-only. Joining
    // threads INSIDE the rail lateral measured 12-27s; as its own query it is
    // 0.24s and the map is built in JS.
    s`select id, link_title from published.threads`,
  ]);

  // A PARTIAL READ MUST RETRY, NOT KILL THE BUILD. Under prerender load the
  // Supabase transaction pooler can hand back a row set containing an undefined
  // entry, and `new Map(rows.map(...))` then throws
  // "TypeError: Iterator value undefined is not an entry object" — an opaque
  // message that does NOT match withRetry's transient pattern, so the retry this
  // file already implements never fires and the whole build dies. Three
  // consecutive production builds failed exactly this way on 2026-08-25 while
  // the collection pipeline was writing, and the live site silently stopped
  // taking new data. The read is pure, so retrying is free — the comment above
  // withRetry already argues this for the connection-drop case.
  // Array.from(), NOT rows.some(). The row set comes back SPARSE — it has holes,
  // not nulls — and `map` preserves holes, so `new Map()` iterates them as
  // undefined and throws. Array.prototype.some SKIPS holes, so the first version
  // of this guard walked straight past the very thing it was written to catch and
  // the build failed again at the same line. Array.from materialises a hole as
  // undefined, which is what makes it visible.
  //   [1, , 3].some(r => r == null)              -> false
  //   Array.from([1, , 3]).some(r => r == null)  -> true
  const bad = ([["categories", catRows], ["brands", brandRows],
                ["scores", scoreRows], ["subCounts", subCounts],
                ["mentions", mentionRows], ["mentionAgg", mentionAgg],
                ["threads", threadRows], ["railMeta", railMeta], ["corpusRevision", corpusRevision]] as [string, unknown[]][])
    .filter(([name, rows]) => !Array.isArray(rows)
                          || Array.from(rows).some((r) => r == null)
                          // the guard's two single-row reads must each return their row: an empty answer is
                          // an incomplete read to retry, never evidence that nothing needs guarding
                          || ((name === "railMeta" || name === "corpusRevision") && rows.length !== 1));
  if (bad.length) {
    throw new Error(
      `PARTIAL_RESULT: ${bad.map(([n]) => n).join(", ")} came back with a null row — ` +
      `the pooler returned an incomplete set. Retrying rather than building a ` +
      `site that is missing rows.`);
  }

  // THE RAIL MUST BE THE RAIL THIS DATA DESERVES.
  //
  // The rail is materialised now (migration 0005), which buys 86,909 ms -> 562 ms and costs exactly
  // one new way to be wrong: a publish that changes the corpus and never refreshes the view would
  // build a site whose cards are older than its numbers, and nothing would say so.
  //
  // FOUR signals, not one. A high-water mark on created_utc answers only "did new mentions arrive",
  // and the commonest publish in this repo changes no mention at all: collect -> classify -> score ->
  // publish re-LABELS existing rows, and the rail carries the label. The counts close the other doors
  // — a deletion, an edited body, or a backfill of an older document into a brand's underfilled rail
  // each move a count without moving a maximum. Any signal AHEAD of what the rail recorded is stale.
  //
  // A null mark with a non-empty corpus is stale too: the rail was built over nothing and the corpus
  // is not nothing. Both empty is the honest first run, and it passes.
  const meta = railMeta[0];
  const rev = corpusRevision[0];
  const verdict = railVerdict(meta, rev);
  // A takedown the rail may still show is refused unconditionally: RAIL_ALLOW_STALE is a knowing override of a
  // consistency problem, and a legal condition is not a consistency problem (review of PR #3).
  if (verdict.legal.length) {
    throw new Error(
      `RAIL_TAKEDOWN: ${verdict.legal.join("; ")}. A deleted card must not be served. Run ` +
      "`select public.refresh_mention_rail();` (worker/publish.py does this) and build again. This is not overridable.");
  }
  const stale = verdict.block;
  for (const w of verdict.warn) console.warn(`[snapshot] rail lags the corpus: ${w} (refreshed ${meta?.refreshed_at ?? "never"})`);
  if (stale.length) {
    const fix = "run `select public.refresh_mention_rail();` (worker/publish.py does this) and build again";
    const detail = `${stale.join("; ")} (rail refreshed ${meta?.refreshed_at ?? "never"})`;
    if (process.env.RAIL_ALLOW_STALE === "1") {
      console.warn(`[snapshot] STALE RAIL, building anyway because RAIL_ALLOW_STALE=1: ${detail}. ${fix}`);
    } else {
      throw new Error(
        `STALE_RAIL: ${detail}. The cards on every page would be older than the scores beside them. ` +
        `${fix}. To ship anyway, set RAIL_ALLOW_STALE=1.`);
    }
  }
  console.log(
    `[snapshot] rail: ${mentionRows.length} rows, refreshed ${meta?.refreshed_at ?? "never"}` +
    `; corpus ${rev?.mentions_rows ?? "?"} mentions, ${rev?.sentiment_rows ?? "?"} labels` +
    `; loaded in ${Date.now() - t0}ms`);

  const catById = new Map(catRows.map((c) => [String(c.id), c]));
  const brandById = new Map(brandRows.map((b) => [String(b.id), b]));
  const scoringByCat = new Map(subCounts.map((r) => [String(r.category_id), Number(r.n)]));

  const scores: BrandScore[] = scoreRows.map((r) => {
    const b = brandById.get(String(r.brand_id));
    const c = catById.get(String(r.category_id));
    return {
      brandSlug: String(b?.slug ?? ""),
      brandName: String(b?.name ?? ""),
      categorySlug: String(c?.slug ?? "") as CategorySlug,
      redditLoveScore: r.reddit_love_score === null ? null : Number(r.reddit_love_score),
      n: Number(r.n),
      nOp: Number(r.n_op),
      nEff: Number(r.n_eff ?? 0),
      deff: Number(r.deff ?? 1),
      pos: Number(r.pos), neg: Number(r.neg), neu: Number(r.neu), abstain: Number(r.abstain),
      neutralShare: Number(r.neutral_share ?? 0),
      abstainShare: Number(r.abstain_share ?? 0),
      polarization: r.polarization === null ? null : Number(r.polarization),
      ciLow: r.ci_low === null ? null : Math.round(Number(r.ci_low) * 100),
      ciHigh: r.ci_high === null ? null : Math.round(Number(r.ci_high) * 100),
      nAuthors: Number(r.n_authors ?? 0),
      nSubreddits: Number(r.n_subreddits ?? 0),
      nThreads: Number(r.n_threads ?? 0),
      maxThreadShare: Number(r.max_thread_share ?? 0),
      maxAuthorShare: Number(r.max_author_share ?? 0),
      maxSubredditShare: Number(r.max_subreddit_share ?? 0),
      rankDesc: r.rank_desc === null ? null : Number(r.rank_desc),
      rankAsc: r.rank_asc === null ? null : Number(r.rank_asc),
      tiedWith: [],
      eligible: Boolean(r.eligible),
      failedTest: (r.failed_test ?? null) as FailedTest | null,
      failedObserved: r.failed_observed ?? null,
      failedRequired: r.failed_required ?? null,
      windowStart: String(r.window_start ?? "").slice(0, 10),
      windowEnd: String(r.window_end ?? "").slice(0, 10),
    };
  });

  const categories: CategoryView[] = CATEGORIES.map((meta) => {
    const row = catRows.find((c) => c.slug === meta.slug);
    const id = row ? String(row.id) : null;
    const scoring = id ? (scoringByCat.get(id) ?? 0) : 0;
    const mine = scores.filter((x) => x.categorySlug === meta.slug);
    return {
      slug: meta.slug,
      name: meta.name,
      tier: meta.tier,
      precisionPp: meta.precisionPp,
      nMin: meta.nMin,
      // 14-category-tests.md's viability test: five scoring subreddits.
      rankable: scoring >= 5,
      scoringSubreddits: scoring,
      requiredSubreddits: 5,
      baseRate: row?.base_rate_c === null || row?.base_rate_c === undefined
        ? null : Number(row.base_rate_c),
      lastUpdated: null,
      // filled below, once every category's scores are known
      threshold: 3,
      scores: mine.sort((a, b) => (b.redditLoveScore ?? -1) - (a.redditLoveScore ?? -1)),
    };
  });

  // Each category's publication bar, from its OWN evidence distribution
  // (see buildThresholds in boards.ts). Computed here so every consumer —
  // boards, category pages, company pages — applies one number.
  for (const c of categories) {
    const ops = c.scores.filter((x) => x.redditLoveScore !== null && x.nOp > 0)
      .map((x) => x.nOp).sort((a, b) => a - b);
    if (!ops.length) { c.threshold = 3; continue; }
    const mid = Math.floor(ops.length / 2);
    const lo = ops[mid - 1] ?? ops[mid] ?? 3;
    const hi = ops[mid] ?? 3;
    const median = ops.length % 2 ? hi : Math.round((lo + hi) / 2);
    c.threshold = Math.max(3, Math.min(30, median));
  }

  // Aggregate rows -> per-brand sentiment totals + subreddit ledger.
  // Labels: 0 neu, 1 pos, 2 neg, 3 abstain; null (unclassified yet) and
  // abstain both fold into neu for DISPLAY — the dashboard's "Neutral" is
  // "carried no verdict", which is what a reader means by it.
  type Agg = { pos: number; neg: number; neu: number;
    unlabelled: number; posts: number; comments: number; oldest: string;
    subs: Map<string, {
    pos: number; neg: number; neu: number; total: number; newest: string }> };
  const aggByBrand = new Map<string, Agg>();
  for (const r of mentionAgg) {
    const bid = String(r.brand_id);
    const a = aggByBrand.get(bid) ?? { pos: 0, neg: 0, neu: 0, unlabelled: 0,
                                       posts: 0, comments: 0, oldest: "",
                                       subs: new Map() };
    const raw = r.label;
    const label = raw === null || raw === undefined ? 3 : Number(raw);
    const bucket = label === 1 ? "pos" : label === 2 ? "neg" : "neu";
    const n = Number(r.n);
    a[bucket] += n;
    // Counted separately from "neutral": a mention nothing has classified yet
    // is not a reader's neutral, and 11.5% of the corpus is in that state at
    // any time while the classifier catches up with the collector.
    if (raw === null || raw === undefined) a.unlabelled += n;
    if (Number(r.doc_type) === 2) a.posts += n; else a.comments += n;
    const sub = String(r.subreddit);
    const st = a.subs.get(sub) ?? { pos: 0, neg: 0, neu: 0, total: 0, newest: "" };
    st[bucket] += n;
    st.total += n;
    const newest = new Date(r.newest as string).toISOString();
    if (newest > st.newest) st.newest = newest;
    const oldest = new Date(r.oldest as string).toISOString();
    if (!a.oldest || oldest < a.oldest) a.oldest = oldest;
    a.subs.set(sub, st);
    aggByBrand.set(bid, a);
  }

  const titleByThread = new Map<string, string>(
    threadRows.map((t) => [String(t.id), String(t.link_title ?? "")]),
  );

  // decisions/0011 — the page score for below-bar brands. Per PRIMARY
  // category, every brand votes its all-collected opinionated counts into the
  // pooled prior (score.py's fit_prior_pooled, leave-one-out by mention mass).
  const countsByCat = new Map<string, Array<[string, number, number]>>();
  for (const b of brandRows) {
    const agg = aggByBrand.get(String(b.id));
    const cat = b.primary_category_id ? String(b.primary_category_id) : "";
    if (!agg || !cat) continue;
    const arr = countsByCat.get(cat) ?? [];
    arr.push([String(b.slug), agg.pos, agg.pos + agg.neg]);
    countsByCat.set(cat, arr);
  }
  const pageScoreFor = (slug: string, catId: string, pos: number, neg: number,
                        neu = 0): number | null => {
    // No opinion but SOME labelled mention -> the prior, i.e. the category
    // baseline. No labelled mention at all -> still a dash. The distinction is
    // the point: "discussed neutrally" and "never mentioned" are different facts
    // and used to render identically.
    if (pos + neg <= 0 && neu <= 0) return null;
    const others = (countsByCat.get(catId) ?? []).filter((x) => x[0] !== slug)
      .map((x) => [x[1], x[2]] as [number, number]);
    const { alpha0, beta0 } = fitPriorPooled(others);
    return computePageScore(pos, neg, alpha0, beta0);
  };

  const companies = new Map<string, CompanyView>();
  for (const b of brandRows) {
    const slug = String(b.slug);
    const mine = scores.filter((x) => x.brandSlug === slug);
    const primary = b.primary_category_id ? catById.get(String(b.primary_category_id)) : null;
    const agg = aggByBrand.get(String(b.id)) ?? { pos: 0, neg: 0, neu: 0,
      unlabelled: 0, posts: 0, comments: 0, oldest: "", subs: new Map() };
    companies.set(slug, {
      slug,
      name: String(b.name),
      primaryCategorySlug: (primary?.slug ?? null) as CategorySlug | null,
      primaryThreshold: primary
        ? (categories.find((c) => c.slug === primary.slug)?.threshold ?? 3)
        : 3,
      scores: mine,
      pageScore: pageScoreFor(slug, b.primary_category_id ? String(b.primary_category_id) : "",
                              agg.pos, agg.neg, agg.neu),
      pageNOp: agg.pos + agg.neg,
      mentions: [],
      totalMentions: agg.pos + agg.neg + agg.neu,
      sentimentTotals: { pos: agg.pos, neg: agg.neg, neu: agg.neu },
      docTypeTotals: { posts: agg.posts, comments: agg.comments },
      unlabelled: agg.unlabelled,
      oldestMention: agg.oldest || null,
      railSize: 0,        // filled once the rail is built, below
      subredditStats: [...agg.subs.entries()]
        .map(([subreddit, st]) => ({ subreddit, total: st.total, pos: st.pos,
                                     neg: st.neg, neu: st.neu, newest: st.newest }))
        .sort((a2, b2) => b2.total - a2.total),
    });
  }

  for (const r of mentionRows) {
    const c = companies.get(String(r.brand_slug));
    if (!c) continue;
    const m: Mention = {
      brandName: String(r.brand_name),
      brandSlug: String(r.brand_slug),
      subreddit: String(r.subreddit),
      author: String(r.author),
      createdUtc: new Date(r.created_utc as string).toISOString(),
      sentiment: SENTIMENT[Number(r.label ?? 3)] ?? "abstain",
      docType: Number(r.doc_type) === 2 ? "post_body" : "comment",
      matchedForm: String(r.matched_form ?? ""),
      // The thread this document belongs to — the question a COMMENT answers.
      // Never sent for a post: a post's title is already the first line of its
      // own body, the card ignores this field for posts, and every byte here
      // ships to the browser inside the island's props.
      threadTitle: Number(r.doc_type) === 2
        ? null
        : titleByThread.get(String(r.thread_id ?? "")) || null,
      body: String(r.body),
      permalink: String(r.permalink).startsWith("http")
        ? String(r.permalink)
        : `https://www.reddit.com${r.permalink}`,
    };
    // The gate item, asserted at BUILD time rather than eyeballed: a permalink
    // that does not have Reddit's comment shape never reaches a page.
    if (!/^https:\/\/www\.reddit\.com\/r\/[A-Za-z0-9_]+\/comments\/[a-z0-9]+/.test(m.permalink)) {
      throw new Error(`Mention permalink is not a Reddit comment URL: ${m.permalink}`);
    }
    if (m.author === "[deleted]") continue;
    c.mentions.push(m);
  }

  // The rail is a WINDOW, not the corpus. Recording its size is what lets the
  // page say so instead of implying that 250 cards are 34,000 mentions.
  for (const c of companies.values()) c.railSize = c.mentions.length;

  console.log(
    `[snapshot] ${categories.length} categories / ${companies.size} companies / ` +
    `${scores.length} score rows / ${mentionRows.length} mentions in ${Date.now() - t0}ms`,
  );

  return {
    categories,
    companies,
    methodologyVersion: METHODOLOGY_VERSION,
    generatedAt: new Date().toISOString(),
  };
}
