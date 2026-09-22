import type { MetadataRoute } from "next";
import { IS_PROVISIONAL } from "@/lib/site-stage";
import { SITE_URL } from "@/lib/env";

/**
 * Nothing in the spec ever defined this file — `robots.txt` appears in the repo
 * only as a reserved path in the slug precedence union. It matters here for one
 * reason: while the site is provisional it carries real Reddit users' words on
 * a public domain with no frozen methodology behind them, and the honest
 * posture is to ask not to be indexed rather than to rely on a meta tag alone.
 */
// Declared, not inferred: this file reads no database today, and the gate that keeps the
// corpus off the request path requires every route to say so in its own words.
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  if (IS_PROVISIONAL) {
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
