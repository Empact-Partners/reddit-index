import { revalidatePath } from "next/cache";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * The publish endpoint: the ONLY way a page on this site changes between code deploys.
 *
 * The daily sweep works out which pages' data changed (site.brand_stats.page_hash against served_hash) and
 * posts their paths here. revalidatePath expires each one immediately; the next request renders it from the
 * `site` schema. The sweep then fetches every path it named and reads the page's fingerprint back, so "the
 * page was updated" is proven by the served page, never by this route answering 200.
 *
 * Until October 2026 this called revalidateTag against tags no page carried, did nothing, and returned 200;
 * delete-sync stamped its takedown receipts on that 200.
 *
 * Bearer-gated. It reads no data: it cannot be used to make the site query anything.
 */

const MAX_PATHS = 500;
/** "/", "/slug/" (or "/slug"), and the three generated files. Nothing else is a page here. */
const PAGE = /^\/(?:[a-z0-9]+(?:-[a-z0-9]+)*\/?)?$/;
const FILES = new Set(["/sitemap.xml", "/llms.txt", "/freshness.json"]);

export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "revalidation is not configured" }, { status: 503 });
  }
  if (request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let paths: string[];
  try {
    const body = (await request.json()) as { paths?: unknown };
    paths = Array.isArray(body.paths) ? body.paths.filter((p): p is string => typeof p === "string") : [];
  } catch {
    return NextResponse.json({ error: "expected {\"paths\": [...]}" }, { status: 400 });
  }
  if (paths.length === 0) {
    return NextResponse.json({ error: "no paths" }, { status: 400 });
  }
  if (paths.length > MAX_PATHS) {
    return NextResponse.json({ error: `at most ${MAX_PATHS} paths a call` }, { status: 400 });
  }
  const bad = paths.filter((p) => !(PAGE.test(p) || FILES.has(p)));
  if (bad.length) {
    return NextResponse.json({ error: "not a page on this site", bad: bad.slice(0, 10) }, { status: 400 });
  }

  // revalidatePath drops a trailing slash itself, so "/hubspot/" and "/hubspot" name the same page.
  for (const p of paths) revalidatePath(p);
  console.log(`[revalidate] ${paths.length} paths` + (paths.length <= 20 ? `: ${paths.join(" ")}` : ""));

  return NextResponse.json({ revalidated: paths.length, at: new Date().toISOString() });
}
