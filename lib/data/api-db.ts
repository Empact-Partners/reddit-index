import "server-only";
import postgres from "postgres";
import type { Cursor, ThreadsQuery } from "@/lib/api/v1";

/**
 * THE READ API'S ONLY DATABASE CONNECTION (decision 0040), and it can only call two functions.
 *
 * lib/data/site-db.ts serves the pages and reads schema `site` only. The API is the one place a caller asks for
 * mentions themselves, so it connects as a different role, `ri_api` (migration 0039): EXECUTE on api.threads and
 * api.brands, no table, no other schema, a 15 second statement timeout. Each function checks the key's hash,
 * caps the page at 500 rows of 280-character excerpts, and returns ONE json value. scripts/gates/bounded-reads.mjs
 * fails the build if a query here names a table, or if any other file reads DATABASE_URL_API.
 */

const DATABASE_URL_API = process.env.DATABASE_URL_API;

let sql: ReturnType<typeof postgres> | null = null;
function db() {
  if (!DATABASE_URL_API) throw new Error("DATABASE_URL_API is not set: ops/api_role.py --vercel sets it");
  // The session pooler, one connection a process, let go quickly: the same reasons as site-db.ts.
  sql ??= postgres(DATABASE_URL_API, {
    prepare: false,
    max: 1,
    idle_timeout: 10,
    connect_timeout: 15,
    ssl: "require",
    onnotice: () => {},
  });
  return sql;
}

async function withRetry<T>(fn: () => Promise<T>, tries = 2): Promise<T> {
  let last: unknown;
  for (let i = 0; i < tries; i++) {
    try {
      return await fn();
    } catch (e) {
      last = e;
      const msg = String((e as { message?: string })?.message ?? e);
      if (!/CONNECTION_CLOSED|CONNECTION_ENDED|ECONNRESET|ETIMEDOUT|socket|terminat/i.test(msg) || i === tries - 1) throw e;
      await new Promise((r) => setTimeout(r, 800));
    }
  }
  throw last;
}

export type ApiError = { error: string };

export type ThreadRow = {
  doc_id: string;
  brand: string;
  sentiment: "negative" | "neutral" | "positive" | "abstain" | "unlabelled";
  subreddit: string | null;
  thread_url: string | null;
  thread_title: string | null;
  doc_type: "comment" | "post";
  permalink: string;
  excerpt: string | null;
  reddit_score: number | null;
  posted_at: string;
};

export type ThreadsPage = {
  brand: { slug: string; name: string };
  sentiment: string;
  since: string | null;
  limit: number;
  rows: ThreadRow[];
  next: Cursor | null;
  scanned: number;
  complete: boolean;
};

export type BrandRow = { slug: string; name: string; mentions: number | null; negative: number | null };

export async function threads(keyHash: string, q: ThreadsQuery): Promise<ThreadsPage | ApiError> {
  const a = q.after;
  const rows = await withRetry(() => db()`
    select api.threads(${keyHash}::text, ${q.brand}::text, ${q.sentiment}::text, ${q.since}::timestamptz,
                       ${q.limit}::integer, ${a?.rank ?? null}::integer, ${a?.score ?? null}::integer,
                       ${a?.created ?? null}::timestamptz, ${a?.doc ?? null}::text) as r`);
  return rows[0]?.r as ThreadsPage | ApiError;
}

export async function brands(keyHash: string, q: string | null): Promise<{ brands: BrandRow[] } | ApiError> {
  const rows = await withRetry(() => db()`select api.brands(${keyHash}::text, ${q}::text) as r`);
  return rows[0]?.r as { brands: BrandRow[] } | ApiError;
}
