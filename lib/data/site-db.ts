import "server-only";
import postgres from "postgres";
import { cache } from "react";
import type { CompanyView, IndexRow, SiteMeta, SubredditStat } from "./types";
import type { Mention, Sentiment } from "@/components/data/mention-card";
import type { CategorySlug } from "@/lib/generated/categories";

/**
 * THE ONLY FILE THAT TALKS TO THE DATABASE, and it can only see the `site` schema.
 *
 * Until October 2026 every build, and for six weeks every page regeneration, loaded the whole corpus:
 * an aggregate over 1.4 million mentions, every thread title and the full card rail. 3.80 billion rows
 * went to the site's database user, 97% of the organisation's egress (docs/investigation-2026-10.md).
 *
 * Now the numbers and the card list for each company are computed inside Postgres, once, when that
 * company's data changes (supabase/migrations/0007, `site.refresh_brand`). A page reads ONE row and its
 * own cards. Three things keep it that way:
 *
 *   1. The role in DATABASE_URL_SITE (`ri_site`) has SELECT on schema `site` and nothing else, and a
 *      5 second statement timeout. A query against the corpus is a permission error, not a bill.
 *   2. scripts/gates/bounded-reads.mjs fails the build if any other file opens a database connection,
 *      or if a query here names a relation outside `site`.
 *   3. Every query here returns one row (a company, the meta row) or one JSON value (the index rows),
 *      so there is no row set for the pooler to hand back half of.
 */

const DATABASE_URL_SITE = process.env.DATABASE_URL_SITE;

let sql: ReturnType<typeof postgres> | null = null;
function db() {
  if (!DATABASE_URL_SITE) {
    throw new Error(
      "DATABASE_URL_SITE is not set. The site reads through the `ri_site` Postgres role on the Supabase " +
      "session pooler (port 5432). ops/site_role.py creates the login and sets this variable on Vercel.",
    );
  }
  sql ??= postgres(DATABASE_URL_SITE, {
    // The SESSION pooler (port 5432). The transaction pooler (6543) hangs under this site's load: measured
    // 2026-10-02, 40 concurrent index reads completed 7 and then nothing reached the database again, in a
    // build and in a bare script alike; the same reads through 5432 took 3.5 s. In session mode every open
    // connection holds a database connection (60 in total on this instance), so a process keeps ONE and
    // lets it go quickly. Renders are short and the sweep fetches four pages at a time.
    prepare: false,
    max: 1,
    idle_timeout: 10,
    connect_timeout: 15,
    ssl: "require",
    onnotice: () => {},
  });
  return sql;
}

/** A dropped pooler connection is retried; anything else (a missing grant, a timeout) is a real answer. */
async function withRetry<T>(fn: () => Promise<T>, tries = 3): Promise<T> {
  let last: unknown;
  for (let i = 0; i < tries; i++) {
    try {
      return await fn();
    } catch (e) {
      last = e;
      const msg = String((e as { message?: string })?.message ?? e);
      const transient = /CONNECTION_CLOSED|CONNECTION_ENDED|ECONNRESET|ETIMEDOUT|socket|terminat/i.test(msg);
      if (!transient || i === tries - 1) throw e;
      await new Promise((r) => setTimeout(r, 800 * 2 ** i));
    }
  }
  throw last;
}

const SENTIMENT: Record<number, Sentiment> = { 0: "neu", 1: "pos", 2: "neg", 3: "abstain" };

type CardRow = {
  subreddit: string; doc_type: number; author: string; created_utc: string; permalink: string;
  body: string; matched_form: string | null; label: number | null; thread_title: string | null;
};

export type CompanyPageData = {
  company: CompanyView;
  boardRank: number | null;
  boardSize: number;
  /** Fingerprint of everything on the page. The sweep fetches the page and reads this back to prove
   *  the served page is the current one. */
  pageHash: string;
};

/**
 * One company page: its row and its cards, in one round trip. `cache` makes generateMetadata and the
 * page share the read within a request; it is not a cross-request cache.
 */
export const getCompany = cache(async (slug: string): Promise<CompanyPageData | null> => {
  const rows = await withRetry(() => db()`
    select s.slug, s.name, s.primary_category_slug, s.pos, s.neg, s.neu, s.unlabelled, s.posts, s.comments,
           s.total_mentions, s.oldest_mention, s.subreddit_stats, s.page_score, s.page_n_op,
           s.board_rank, s.board_size, s.page_hash,
           (select coalesce(json_agg(json_build_object(
                     'subreddit', c.subreddit, 'doc_type', c.doc_type, 'author', c.author,
                     'created_utc', c.created_utc, 'permalink', c.permalink, 'body', c.body,
                     'matched_form', c.matched_form, 'label', c.label, 'thread_title', c.thread_title)
                   order by c.created_utc desc, c.doc_id desc), '[]'::json)
              from site.rail_card c
             where c.brand_slug = s.slug) as cards,
           (select coalesce(json_agg(json_build_object(
                     'subreddit', w.subreddit, 'doc_type', w.doc_type, 'author', w.author,
                     'created_utc', w.created_utc, 'permalink', w.permalink, 'body', w.body,
                     'matched_form', w.matched_form, 'sentiment', w.sentiment, 'thread_title', w.thread_title)
                   order by w.created_utc desc, w.doc_id desc), '[]'::json)
              from site.watch_shown w
             where w.brand_slug = s.slug) as watch
    from site.brand_stats s
    where s.slug = ${slug}`);
  const r = rows[0];
  if (!r) return null;

  const name = String(r.name);
  const mentions: Mention[] = (r.cards as CardRow[]).map((c) => ({
    brandName: name,
    brandSlug: slug,
    subreddit: String(c.subreddit),
    author: String(c.author),
    createdUtc: new Date(c.created_utc).toISOString(),
    sentiment: SENTIMENT[Number(c.label ?? 3)] ?? "abstain",
    docType: Number(c.doc_type) === 2 ? "post_body" : "comment",
    matchedForm: String(c.matched_form ?? ""),
    // The question a COMMENT answers. A post's title is already the first line of its own body.
    threadTitle: Number(c.doc_type) === 2 ? null : (c.thread_title || null),
    body: String(c.body),
    // site.rail_card only returns permalinks with Reddit's comment shape, so this cannot mint a bad link
    permalink: String(c.permalink).startsWith("http") ? String(c.permalink) : `https://www.reddit.com${c.permalink}`,
  }));

  // decisions/0020: the closer watch's mentions, in their own section, counted in nothing. Its sentiment is the
  // watch's own reading (positive, negative, neutral or mixed), shown as the nearest of the card's three words.
  const WATCH: Record<string, Sentiment> = { positive: "pos", negative: "neg", neutral: "neu", mixed: "neu" };
  const watchMentions: Mention[] = ((r.watch ?? []) as Array<CardRow & { sentiment: string | null }>).map((c) => ({
    brandName: name,
    brandSlug: slug,
    subreddit: String(c.subreddit),
    author: String(c.author),
    createdUtc: new Date(c.created_utc).toISOString(),
    sentiment: WATCH[String(c.sentiment ?? "")] ?? "abstain",
    docType: Number(c.doc_type) === 2 ? "post_body" : "comment",
    matchedForm: String(c.matched_form ?? ""),
    threadTitle: Number(c.doc_type) === 2 ? null : (c.thread_title || null),
    body: String(c.body),
    // site.refresh_watch keeps only Reddit's permalink shape
    permalink: String(c.permalink),
  }));

  const company: CompanyView = {
    slug,
    name,
    primaryCategorySlug: (r.primary_category_slug ?? null) as CategorySlug | null,
    pageScore: r.page_score === null ? null : Number(r.page_score),
    pageNOp: Number(r.page_n_op),
    mentions,
    totalMentions: Number(r.total_mentions),
    sentimentTotals: { pos: Number(r.pos), neg: Number(r.neg), neu: Number(r.neu) },
    docTypeTotals: { posts: Number(r.posts), comments: Number(r.comments) },
    unlabelled: Number(r.unlabelled),
    oldestMention: r.oldest_mention ? new Date(r.oldest_mention as string).toISOString() : null,
    railSize: mentions.length,
    subredditStats: r.subreddit_stats as SubredditStat[],
    watchMentions,
  };
  return {
    company,
    boardRank: r.board_rank === null ? null : Number(r.board_rank),
    boardSize: Number(r.board_size),
    pageHash: String(r.page_hash),
  };
});

/** The one row about the whole site: when the data was last refreshed, and what the index pages hash to. */
export const getMeta = cache(async (): Promise<SiteMeta> => {
  const rows = await withRetry(() => db()`
    select last_success_at, newest_mention, boards_hash, slugs_hash from site.meta`);
  const r = rows[0];
  return {
    lastSuccessAt: r?.last_success_at ? new Date(r.last_success_at as string).toISOString() : null,
    newestMention: r?.newest_mention ? new Date(r.newest_mention as string).toISOString() : null,
    boardsHash: String(r?.boards_hash ?? ""),
    slugsHash: String(r?.slugs_hash ?? ""),
  };
});

/**
 * Every company that has a page, six short fields each: what the boards, the search box, the sitemap and
 * llms.txt are built from. About 6,000 rows, under half a megabyte, returned as ONE JSON value.
 *
 * All 152 index pages (home and each category) embed the same boards, so the rows are remembered per
 * process under the hash the database publishes for them: a build worker, or a lambda regenerating
 * several index pages, reads them once. The key is the content hash, so a remembered copy cannot be stale.
 */
let indexMemo: { hash: string; at: number; index: Promise<{ hash: string; rows: IndexRow[] }> } | null = null;

/**
 * The rows AND the fingerprint they were read under, in one statement (one snapshot): a board page embeds the
 * hash of the rows it rendered, never a hash read a moment earlier or later (review 2026-10-04). A render reads
 * its metadata and its body within milliseconds, so an index remembered for under a minute is reused without
 * asking the database; after that, a one-row read of site.meta decides whether the remembered rows still hold.
 */
export async function getIndex(): Promise<{ hash: string; rows: IndexRow[] }> {
  if (indexMemo && Date.now() - indexMemo.at < 60_000) return indexMemo.index;
  const meta = await getMeta();
  // The PROMISE is remembered, not the result: eighty pages rendering at once in a build worker share one read.
  if (indexMemo && meta.boardsHash && indexMemo.hash === meta.boardsHash) {
    indexMemo.at = Date.now();
    return indexMemo.index;
  }
  const load = (async () => {
    const res = await withRetry(() => db()`
      select (select boards_hash from site.meta) as hash,
             coalesce(json_agg(json_build_array(
               slug, name, primary_category_slug, page_score, page_n_op, total_mentions)), '[]'::json) as rows
      from site.brand_stats`);
    const raw = (res[0]?.rows ?? []) as Array<[string, string, string | null, number | null, number, number]>;
    return {
      hash: String(res[0]?.hash ?? ""),
      rows: raw.map(([slug, name, cat, score, nOp, mentions]): IndexRow => ({
        slug, name, categorySlug: (cat ?? null) as CategorySlug | null, score, nOp, mentions,
      })),
    };
  })();
  const memo = { hash: meta.boardsHash, at: Date.now(), index: load };
  indexMemo = memo;
  // remembered under the hash the rows were actually read with; a failed read is not remembered
  load.then((ix) => { if (indexMemo === memo) memo.hash = ix.hash; })
    .catch(() => { if (indexMemo === memo) indexMemo = null; });
  return load;
}

export async function getIndexRows(): Promise<IndexRow[]> {
  return (await getIndex()).rows;
}

/** decisions/0020: the companies the closer watch covers (Empact Partners' Reddit clients), for /methodology. */
export async function getWatchedBrands(): Promise<Array<{ slug: string; name: string; since: string; hasPage: boolean }>> {
  if (!DATABASE_URL_SITE) return [];
  const rows = await withRetry(() => db()`
    select coalesce(json_agg(json_build_object(
             'slug', w.slug, 'name', w.name, 'since', w.since,
             'hasPage', exists (select 1 from site.brand_stats s where s.slug = w.slug))
           order by lower(w.name)), '[]'::json) as rows
    from site.watched_brand w`);
  return (rows[0]?.rows ?? []) as Array<{ slug: string; name: string; since: string; hasPage: boolean }>;
}

export type MethodologyParamRow = {
  version: string; scope: string; key: string; value: unknown; rationale: string; git_commit: string;
};

/** The frozen constants, straight from the append-only table, so /methodology cannot drift from the code. */
export async function getMethodologyParamRows(version: string): Promise<MethodologyParamRow[]> {
  if (!DATABASE_URL_SITE) return [];
  const rows = await withRetry(() => db()`
    select coalesce(json_agg(json_build_object(
             'version', version, 'scope', scope, 'key', key, 'value', value,
             'rationale', rationale, 'git_commit', git_commit) order by scope, key), '[]'::json) as rows
    from site.methodology_params
    where version = ${version}`);
  return (rows[0]?.rows ?? []) as MethodologyParamRow[];
}
