import type { NextConfig } from "next";
import { IS_PROVISIONAL } from "./lib/site-stage";

const nextConfig: NextConfig = {
  // decisions/0007: `/crm/` is the canonical form, and every route in the flat
  // namespace is one segment deep. `/crm` 308s to it rather than serving twice.
  trailingSlash: true,
  // Makes `<Link href="/category/crm">` a TYPE ERROR. decisions/0007 bans that
  // shape outright; this is the cheapest place to enforce it.
  typedRoutes: true,
  reactStrictMode: true,
  outputFileTracingExcludes: { "*": ["worker/**", "data/**", "supabase/**"] },
  async headers() {
    // Three independent noindex layers because they fail differently: a header,
    // a meta tag, and robots.txt. All three read one constant.
    return IS_PROVISIONAL
      ? [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }]
      : [];
  },
};

export default nextConfig;
