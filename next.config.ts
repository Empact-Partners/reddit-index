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
  // The snapshot is memoised PER PROCESS, and Next prerenders in several
  // worker processes, so the first page each worker touches pays the whole
  // corpus query. At 345k labelled mentions that first page exceeds the 60s
  // default and the build fails on pages that are individually trivial
  // (/tidio, /tilda...). The pages are not slow; the one-time fetch behind
  // them is. Every later page in that worker is served from the memo.
  staticPageGenerationTimeout: 300,
  // ...and cap the worker count for the same reason. Each worker opens its
  // own connection to the Supabase TRANSACTION pooler and runs the full
  // corpus query; at default parallelism the pooler drops connections
  // mid-query (CONNECTION_CLOSED on /customshow, /big-agi — different pages
  // each run, which is the signature of load, not of a bad page). Fewer
  // workers is strictly faster here than retrying a build that dies at 90%.
  experimental: { cpus: 2 },
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
