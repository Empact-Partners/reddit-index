import type { MetadataRoute } from "next";
import { getRegistry } from "@/lib/routing";
import { SITE_URL } from "@/lib/env";

// The ONE data route in this app that did not pin itself to build time. Without
// it the sitemap is rendered by a function and only CDN-cached, so every cache
// expiry re-runs getRegistry() -> getSnapshot() — the whole-corpus read — and
// /sitemap.xml is the single most-probed path on any live domain. Measured
// 2026-09-17: `x-vercel-cache: HIT` but NO `x-nextjs-prerender` header, unlike
// every other route here. Pinned so it is emitted once per build, like the pages
// it lists. See the note on `revalidate` in app/[slug]/page.tsx.
export const dynamic = "force-static";

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
