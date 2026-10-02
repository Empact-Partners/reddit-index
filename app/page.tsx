import type { Metadata } from "next";
import { getIndexRows, getMeta } from "@/lib/data/site-db";
import { buildBoards } from "@/lib/data/boards";
import { buildSearchIndex } from "@/lib/data/search-index";
import { IndexPage } from "@/components/pages/index-page";

export const dynamic = "force-static";
// NEVER a number. A time-based revalidate makes a page regenerate on a timer, on a request, and from
// 5 August to 17 September 2026 each such regeneration re-read the whole corpus: 3.80 billion rows to the
// site's database user, 97% of the organisation's egress (docs/investigation-2026-10.md).
//
// A page now changes in exactly one way: the daily sweep computes that its data changed and calls
// /api/revalidate with its path. The next request renders it from the `site` schema (a few short rows) and
// the result is cached until the sweep names it again. scripts/gates/bounded-reads.mjs fails the build on a
// numeric revalidate.
export const revalidate = false;

export async function generateMetadata(): Promise<Metadata> {
  // The fingerprint the sweep reads back to prove the served index is the current one.
  const meta = await getMeta();
  return { other: { "ri-hash": meta.boardsHash } };
}

export default async function Home() {
  const rows = await getIndexRows();
  return <IndexPage data={buildBoards(rows)} scope="all" search={buildSearchIndex(rows)} />;
}
