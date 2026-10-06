import { getMeta } from "@/lib/data/site-db";

// Emitted once and cached. The daily sweep expires this path at the end of every successful run, which is
// the only time its content changes.
export const dynamic = "force-static";

/**
 * When the data was last refreshed. The footer on every page reads this, so the date is current everywhere
 * without regenerating 6,000 pages a day to change one line.
 */
export async function GET() {
  const meta = await getMeta();
  return Response.json(
    { refreshedAt: meta.lastSuccessAt, newestMention: meta.newestMention },
    { headers: { "cache-control": "public, max-age=300" } },
  );
}
