import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * The publish endpoint. Bearer-gated, and the ONLY way the pipeline touches the
 * site — 08-architecture.md §4 keeps this separate from the deploy hook, which
 * is for code and schema changes only.
 *
 * The caller DIFFS: step 9 of the daily pass compares freshly computed scores
 * against the previous run and sends only the tags whose published result
 * changed. The slug set is logged on every call, because §4 is explicit that a
 * day sending thousands of tags is a defect in the diff rather than a busy news
 * day, and you cannot notice that without the log.
 */
export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "revalidation is not configured" }, { status: 503 });
  }
  if (request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let tags: string[];
  try {
    const body = (await request.json()) as { tags?: unknown };
    tags = Array.isArray(body.tags) ? body.tags.filter((t): t is string => typeof t === "string") : [];
  } catch {
    return NextResponse.json({ error: "expected {\"tags\": [...]}" }, { status: 400 });
  }
  if (tags.length === 0) {
    return NextResponse.json({ error: "no tags" }, { status: 400 });
  }

  console.log(`[revalidate] ${tags.length} tags: ${tags.join(", ")}`);
  for (const tag of tags) revalidateTag(tag, "max");

  return NextResponse.json({ revalidated: tags.length, tags, at: new Date().toISOString() });
}
