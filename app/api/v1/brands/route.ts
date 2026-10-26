import { brands } from "@/lib/data/api-db";
import { bearerKey, errorResponse, hashKey, NO_STORE, parseBrandsQuery } from "@/lib/api/v1";

export const dynamic = "force-dynamic";

/**
 * GET /api/v1/brands/?q=<text>
 * Authorization: Bearer <key>
 *
 * The slugs /api/v1/threads takes: every published brand (slug, name, mentions, negative), or the ones whose slug
 * or name contains `q`. The counts are the site's own (site.brand_stats), null for a brand with no page yet.
 * Decision 0040.
 */
export async function GET(request: Request) {
  const key = bearerKey(request.headers.get("authorization"));
  if (!key) return errorResponse("unauthorized");

  const parsed = parseBrandsQuery(new URL(request.url).searchParams);
  if (!parsed.ok) return Response.json({ error: "bad_request", message: parsed.message }, { status: 400, headers: NO_STORE });

  let r: Awaited<ReturnType<typeof brands>>;
  try {
    r = await brands(hashKey(key), parsed.value.q);
  } catch (e) {
    console.error("[api/v1/brands]", String((e as { message?: string })?.message ?? e).slice(0, 300));
    return Response.json({ error: "unavailable", message: "the index's database did not answer; try again in a minute" },
      { status: 503, headers: NO_STORE });
  }
  if (!r) return errorResponse("unavailable", 503);
  if ("error" in r) return errorResponse(r.error);

  return Response.json(r, { headers: NO_STORE });
}
