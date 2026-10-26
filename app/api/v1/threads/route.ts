import { threads } from "@/lib/data/api-db";
import {
  bearerKey, encodeCursor, errorResponse, hashKey, NO_STORE, parseThreadsQuery,
} from "@/lib/api/v1";

export const dynamic = "force-dynamic";

/**
 * GET /api/v1/threads/?brand=<slug>&sentiment=negative&since=2026-09-01&limit=100&cursor=<next>
 * Authorization: Bearer <key>
 *
 * One brand's mentions with a sentiment (negative by default), negative first, then the Reddit score, then
 * newest. Each row: the thread's URL and title, the subreddit, the comment's or post's own permalink, a
 * 280-character verbatim excerpt around the brand's name, the sentiment, the Reddit score, when it was posted.
 * `next` is the cursor for the following page, null on the last one. Decision 0040; keys: ops/api_keys.py.
 *
 * The request is checked here before the database is asked anything; the key, the brand and the page cap are
 * checked again inside api.threads (migration 0039), which is the guard that holds.
 */
export async function GET(request: Request) {
  const key = bearerKey(request.headers.get("authorization"));
  if (!key) return errorResponse("unauthorized");

  const parsed = parseThreadsQuery(new URL(request.url).searchParams);
  if (!parsed.ok) return Response.json({ error: "bad_request", message: parsed.message }, { status: 400, headers: NO_STORE });

  let r: Awaited<ReturnType<typeof threads>>;
  try {
    r = await threads(hashKey(key), parsed.value);
  } catch (e) {
    console.error("[api/v1/threads]", String((e as { message?: string })?.message ?? e).slice(0, 300));
    return Response.json({ error: "unavailable", message: "the index's database did not answer; try again in a minute" },
      { status: 503, headers: NO_STORE });
  }
  if (!r) return errorResponse("unavailable", 503);
  if ("error" in r) return errorResponse(r.error);

  return Response.json({ ...r, next: r.next ? encodeCursor(r.next) : null }, { headers: NO_STORE });
}
