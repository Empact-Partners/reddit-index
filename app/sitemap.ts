import type { MetadataRoute } from "next";
import { getRegistry } from "@/lib/routing";
import { getMeta } from "@/lib/data/site-db";
import { SITE_URL } from "@/lib/env";

// Cached and rebuilt at most once an hour (decision 0022), never per request: /sitemap.xml is the single most-probed
// path on any live domain. It reads the slug list (short rows), never the corpus. The sweep's expiry never reached
// it, so until 9 Oct it listed the page set of the last deploy (6,441 URLs for 6,065 company pages).
export const dynamic = "force-static";
export const revalidate = 3600;

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
