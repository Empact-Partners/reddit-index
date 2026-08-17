import type { MetadataRoute } from "next";
import { getRegistry } from "@/lib/routing";
import { SITE_URL } from "@/lib/env";

/**
 * Built from the SAME registry that mints the routes, so the sitemap can
 * never list a page that 404s or miss one that exists. robots.ts has
 * advertised /sitemap.xml since day one — until now nothing emitted it, which
 * would have shipped a robots file pointing at a 404 the moment the site
 * went public.
 *
 * Priorities are the crawl order that matters for this site: the index and
 * the category boards are the product, company pages are the long tail.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const reg = await getRegistry();
  const now = new Date();
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
