import { createHash } from "node:crypto";

/**
 * The read API's request rules (decision 0040): what a request may ask for, checked before anything reaches the
 * database, and the cursor a page hands back. Pure functions, so the tests can hold every rule without a database.
 */

export const DEFAULT_LIMIT = 100;
/** The page cap. api.threads applies the same cap, so a caller that skips this module still cannot exceed it. */
export const MAX_LIMIT = 500;

export const SENTIMENTS = ["negative", "neutral", "positive", "all"] as const;
export type SentimentFilter = (typeof SENTIMENTS)[number];

/** The position after which the next page starts: the last row's sort values (api.threads' order). */
export type Cursor = { rank: number; score: number; created: string; doc: string };

export type ThreadsQuery = {
  brand: string;
  sentiment: SentimentFilter;
  since: string | null;
  limit: number;
  after: Cursor | null;
};

export type Parsed<T> = { ok: true; value: T } | { ok: false; message: string };

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DATE = /^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const DOC_ID = /^t[13]_[a-z0-9]+$/;
const KEY = /^[A-Za-z0-9_-]{16,128}$/;

/** The key from `Authorization: Bearer <key>`, or null when the header is absent or not that shape. */
export function bearerKey(header: string | null): string | null {
  const k = header?.match(/^Bearer\s+(\S+)\s*$/i)?.[1];
  return k && KEY.test(k) ? k : null;
}

/** sha256 of the key, lowercase hex: what api.api_keys stores (ops/api_keys.py key_hash). */
export function hashKey(key: string): string {
  return createHash("sha256").update(key, "utf8").digest("hex");
}

export function encodeCursor(c: Cursor): string {
  return Buffer.from(JSON.stringify([c.rank, c.score, c.created, c.doc]), "utf8").toString("base64url");
}

export function decodeCursor(s: string): Cursor | null {
  try {
    const v = JSON.parse(Buffer.from(s, "base64url").toString("utf8"));
    if (!Array.isArray(v) || v.length !== 4) return null;
    const [rank, score, created, doc] = v;
    if (rank !== 0 && rank !== 1) return null;
    if (!Number.isInteger(score) || Math.abs(score) > 2 ** 31) return null;
    if (typeof created !== "string" || !Number.isFinite(Date.parse(created))) return null;
    if (typeof doc !== "string" || !DOC_ID.test(doc)) return null;
    return { rank, score, created, doc };
  } catch {
    return null;
  }
}

export function parseThreadsQuery(p: URLSearchParams): Parsed<ThreadsQuery> {
  const brand = (p.get("brand") ?? "").trim().toLowerCase();
  if (!brand) return { ok: false, message: "brand is required: a slug from /api/v1/brands/, e.g. brand=contabo" };
  if (brand.length > 120 || !SLUG.test(brand)) return { ok: false, message: "brand must be a slug, e.g. brand=contabo" };

  const sentiment = (p.get("sentiment") ?? "negative").trim().toLowerCase();
  if (!(SENTIMENTS as readonly string[]).includes(sentiment)) {
    return { ok: false, message: `sentiment must be one of ${SENTIMENTS.join(", ")}` };
  }

  let since: string | null = null;
  const rawSince = p.get("since");
  if (rawSince !== null && rawSince.trim() !== "") {
    const t = rawSince.trim();
    const ms = DATE.test(t) ? Date.parse(t.length === 10 ? `${t}T00:00:00Z` : t) : NaN;
    if (!Number.isFinite(ms)) return { ok: false, message: "since must be a date, e.g. since=2026-09-01" };
    since = new Date(ms).toISOString();
  }

  let limit = DEFAULT_LIMIT;
  const rawLimit = p.get("limit");
  if (rawLimit !== null && rawLimit.trim() !== "") {
    if (!/^\d{1,6}$/.test(rawLimit.trim()) || Number(rawLimit) < 1) {
      return { ok: false, message: `limit must be a whole number from 1 to ${MAX_LIMIT}` };
    }
    limit = Math.min(Number(rawLimit), MAX_LIMIT);
  }

  let after: Cursor | null = null;
  const rawCursor = p.get("cursor");
  if (rawCursor !== null && rawCursor.trim() !== "") {
    after = decodeCursor(rawCursor.trim());
    if (!after) return { ok: false, message: "cursor is not one this API gave out: pass `next` from the previous page" };
  }

  return { ok: true, value: { brand, sentiment: sentiment as SentimentFilter, since, limit, after } };
}

export function parseBrandsQuery(p: URLSearchParams): Parsed<{ q: string | null }> {
  const q = (p.get("q") ?? "").trim();
  if (q.length > 100) return { ok: false, message: "q is at most 100 characters" };
  return { ok: true, value: { q: q || null } };
}

/** The database's refusals, as HTTP. */
export const ERROR_STATUS: Record<string, number> = {
  unauthorized: 401,
  rate_limited: 429,
  unknown_brand: 404,
  bad_sentiment: 400,
  bad_cursor: 400,
  unavailable: 503,
};

export const ERROR_MESSAGE: Record<string, string> = {
  unauthorized: "the key is missing, unknown or revoked: send Authorization: Bearer <key>",
  rate_limited: "this key has made 300 calls today (UTC); it works again at 00:00 UTC",
  unknown_brand: "no published brand has that slug: find it with /api/v1/brands/?q=<name>",
  bad_sentiment: "sentiment must be one of negative, neutral, positive, all",
  bad_cursor: "cursor is not one this API gave out",
  unavailable: "the index's database did not answer; try again in a minute",
};

export function errorResponse(error: string, status?: number): Response {
  return Response.json(
    { error, message: ERROR_MESSAGE[error] ?? error },
    { status: status ?? ERROR_STATUS[error] ?? 500, headers: NO_STORE },
  );
}

/** Every answer is per key and per moment: never cached by Vercel or anything between. */
export const NO_STORE = { "Cache-Control": "no-store" };
