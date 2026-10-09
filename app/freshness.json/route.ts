import { getMeta } from "@/lib/data/site-db";

// Emitted once and cached. The daily sweep expires this path at the end of every successful run, which is
// the only time its content changes.
export const dynamic = "force-static";
// A timer, not an expiry (decision 0022): revalidatePath does not reach a route handler's built response, so
// this file served the last deploy's date for days (9 Oct: Oct 8 04:20 after three "successful" expiries).
// One row of site.meta at most once every five minutes, whatever the traffic.
export const revalidate = 300;

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
