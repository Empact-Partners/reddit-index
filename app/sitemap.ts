import type { MetadataRoute } from "next";
import { getRegistry } from "@/lib/routing";
import { getMeta } from "@/lib/data/site-db";
import { SITE_URL } from "@/lib/env";

// Emitted once and cached; the daily sweep expires it only when the SET of pages changes. Without the pin
// the sitemap is rendered by a function on every cache expiry, and /sitemap.xml is the single most-probed
// path on any live domain. It reads the slug list (short rows), never the corpus.
export const dynamic = "force-static";

/**
 * Built from the SAME registry that mints the routes, so the sitemap can never list a page that 404s or
 * miss one that exists.
 *
 * Priorities are the crawl order that matters for this site: the index and the category boards are the
 * product, company pages are the long tail.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [reg, meta] = await Promise.all([getRegistry(), getMeta()]);
  // The date the data was last refreshed, not the date this file happened to be generated.
  const now = meta.lastSuccessAt ? new Date(meta.lastSuccessAt) : new Date();
  return [
    { url: `${SITE_URL}/`, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/methodology/`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    ...reg.categories.map((slug) => ({
      url: `${SITE_URL}/${slug}/`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
    ...reg.companies.map((slug) => ({
      url: `${SITE_URL}/${slug}/`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
  ];
}
