import "server-only";
import postgres from "postgres";
import { CATEGORIES, type CategorySlug } from "@/lib/generated/categories";
import { METHODOLOGY_VERSION } from "@/lib/format";
import type { BrandScore, CategoryView, CompanyView, FailedTest, Snapshot } from "./types";
import type { Mention, Sentiment } from "@/components/data/mention-card";

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

async function loadSnapshot(): Promise<Snapshot> {
  const t0 = Date.now();
  const s = db();

  const [catRows, brandRows, scoreRows, subCounts, mentionRows, mentionAgg] = await Promise.all([
    s`select id, slug, name, threshold_tier, precision_target_pp, n_min, base_rate_c, status
      from published.categories`,
    s`select id, slug, name, primary_category_id from published.brands`,
    s`select * from published.brand_category_scores
      where week_start = (select max(week_start) from published.brand_category_scores)`,
    s`select cs.category_id, count(*)::int as n
      from published.category_subreddits cs where cs.is_scoring group by 1`,
    // Newest first, 500 per brand. The dashboard paginates 10 per page, so
    // 500 is fifty pages — far past what anyone scrolls. The old rail of 2000
    // was set when the biggest brand had a few hundred mentions; at 158k
    // mentions and climbing it pulled ~135k full comment bodies through the
    // pooler in one statement and the build started dying with
    // CONNECTION_CLOSED while the collector and classifier used the same
    // instance. This is a build-memory and transport bound, not a display one.
    // A LATERAL per brand, not a global window: row_number() over the whole
    // table sorted every mention in the corpus to keep the newest 2000 of
    // each, which stopped fitting inside the statement timeout once the
    // depth sweep pushed the table past ~200k rows (the build failed on
    // /jamf-pro with 57014). The lateral walks the (brand_id, created_utc
    // desc) index and touches at most 2000 rows per brand. Same result set.
    s`select t.*, b.slug as brand_slug, b.name as brand_name, sr.name as subreddit
      from published.brands b
      cross join lateral (
        select m.* from published.mentions m
        where m.brand_id = b.id
        order by m.created_utc desc
        limit 500
      ) t
      join published.subreddits sr on sr.id = t.subreddit_id`,
    // The dashboard aggregates: TRUE totals over the whole table, per
    // (brand x subreddit x label) — the stat tiles and the subreddit ledger
    // must describe everything collected, not the 100 cards shown.
    s`select m.brand_id, sr.name as subreddit, m.label,
             count(*)::int as n, max(m.created_utc) as newest
      from published.mentions m
      join published.subreddits sr on sr.id = m.subreddit_id
      group by 1, 2, 3`,
  ]);

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
  type Agg = { pos: number; neg: number; neu: number; subs: Map<string, {
    pos: number; neg: number; neu: number; total: number; newest: string }> };
  const aggByBrand = new Map<string, Agg>();
  for (const r of mentionAgg) {
    const bid = String(r.brand_id);
    const a = aggByBrand.get(bid) ?? { pos: 0, neg: 0, neu: 0, subs: new Map() };
    const label = r.label === null || r.label === undefined ? 3 : Number(r.label);
    const bucket = label === 1 ? "pos" : label === 2 ? "neg" : "neu";
    const n = Number(r.n);
    a[bucket] += n;
    const sub = String(r.subreddit);
    const st = a.subs.get(sub) ?? { pos: 0, neg: 0, neu: 0, total: 0, newest: "" };
    st[bucket] += n;
    st.total += n;
    const newest = new Date(r.newest as string).toISOString();
    if (newest > st.newest) st.newest = newest;
    a.subs.set(sub, st);
    aggByBrand.set(bid, a);
  }

  const companies = new Map<string, CompanyView>();
  for (const b of brandRows) {
    const slug = String(b.slug);
    const mine = scores.filter((x) => x.brandSlug === slug);
    const primary = b.primary_category_id ? catById.get(String(b.primary_category_id)) : null;
    const agg = aggByBrand.get(String(b.id)) ?? { pos: 0, neg: 0, neu: 0, subs: new Map() };
    companies.set(slug, {
      slug,
      name: String(b.name),
      primaryCategorySlug: (primary?.slug ?? null) as CategorySlug | null,
      primaryThreshold: primary
        ? (categories.find((c) => c.slug === primary.slug)?.threshold ?? 3)
        : 3,
      scores: mine,
      mentions: [],
      totalMentions: agg.pos + agg.neg + agg.neu,
      sentimentTotals: { pos: agg.pos, neg: agg.neg, neu: agg.neu },
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
