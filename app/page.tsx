import { getSnapshot } from "@/lib/data/snapshot";
import { buildBoards } from "@/lib/data/boards";
import { buildSearchIndex } from "@/lib/data/search-index";
import { IndexPage } from "@/components/pages/index-page";

export const dynamic = "force-static";
// NOT `86400`. A time-based revalidate turns every prerendered route into ISR,
// and an ISR regeneration runs in a cold Vercel lambda where `getSnapshot()` is
// memoised per PROCESS — so refreshing ONE page re-reads the WHOLE corpus
// (~67 MB on the wire: every thread title, the full-table mention aggregate,
// every brand and score). Measured 2026-09-17 on nrsyqcttpijxhwtdtoct: ~800 of
// those loads a day, ~54 GB/day, which is 97% of the org's 805 GB Supabase
// egress for Sep 3-17 against a 250 GB Pro allowance.
//
// The regenerations never even landed. The corpus aggregate takes 12-65s and
// hits the statement timeout (333 timeouts, 154 broken pipes on 2026-09-17
// alone), so the lambda dies, the page stays stale, and the NEXT request
// retries it — /hubspot/ sat 21.8 days stale while paying this bill on every
// hit. Nothing was gained and the whole corpus was paid for repeatedly.
//
// `false` is what this repo already documents: worker/publish.py — "Publish =
// rebuild. The site is fully static: every route is prerendered from one
// database read at build time, so new data reaches redditindex.com only when
// Vercel builds again." Data freshness comes from that rebuild, never from a
// runtime read. The /api/revalidate tag path cannot substitute: there is no
// `unstable_cache`, no `cacheTag` and no tagged `fetch` anywhere in the app,
// so `revalidateTag` has always been a no-op against these Postgres reads.
export const revalidate = false;

export default async function Home() {
  const snap = await getSnapshot();
  return <IndexPage data={buildBoards(snap)} scope="all" search={buildSearchIndex(snap)} />;
}
