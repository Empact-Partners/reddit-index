import Link from "next/link";
import { getSnapshot } from "@/lib/data/snapshot";
import { num } from "@/lib/format";
import { LovedHatedBoard } from "@/components/data/board";
import { ExposureConfoundLine, MethodologyCallout } from "@/components/data/disclosures";
import { EvidenceTable } from "@/components/data/states";
import { CategoryTile } from "@/components/category/category-identity";

export const dynamic = "force-static";
export const revalidate = 86400;

/**
 * The pooled board: up to 100 companies at each end of the ONE published
 * ordering, capped at five per category, category as the third column.
 *
 * The two lists are drawn from opposite ends of a single ordering, so they are
 * disjoint by construction (decisions/0006). Where fewer than 200 companies
 * qualify, each list takes at most floor(N/2), and the page states the actual
 * counts rather than implying a round number.
 */
function poolCappedPerCategory(scores: ReturnType<typeof allScores>, cap = 5) {
  const seen = new Map<string, number>();
  const out = [];
  for (const s of scores) {
    const c = seen.get(s.categorySlug) ?? 0;
    if (c >= cap) continue;
    seen.set(s.categorySlug, c + 1);
    out.push(s);
  }
  return out;
}

function allScores(cats: Awaited<ReturnType<typeof getSnapshot>>["categories"]) {
  return cats.filter((c) => c.rankable).flatMap((c) => c.scores);
}

export default async function Home() {
  const snap = await getSnapshot();
  const scores = allScores(snap.categories);
  const eligible = scores
    .filter((s) => s.eligible && s.redditLoveScore !== null)
    .sort((a, b) => (b.redditLoveScore ?? 0) - (a.redditLoveScore ?? 0));
  const pooled = poolCappedPerCategory(eligible, 5);
  const rankable = snap.categories.filter((c) => c.rankable).length;
  const totalMentions = snap.categories.reduce(
    (a, c) => a + c.scores.reduce((b, s) => b + s.n, 0), 0);

  return (
    <>
      {/* One sentence stating what is measured and over what window. No
          marketing copy — 00-concept.md is explicit about that. */}
      <section className="pt-[var(--section)]">
        <h1 style={{ fontSize: "var(--fs-display)", maxWidth: "18ch" }}>
          What Reddit says about software
        </h1>
        <p className="mt-8" style={{ fontSize: "var(--fs-lead)", maxWidth: "62ch" }}>
          Every opinion below was written by a Reddit user about a named
          product, classified one mention at a time, and counted. {num(totalMentions)}{" "}
          mentions collected across {snap.categories.length} categories,{" "}
          {rankable} of which currently carry enough independent evidence to be
          ranked at all.
        </p>
      </section>

      <MethodologyCallout />
      <ExposureConfoundLine />

      <section className="mt-[var(--section)]">
        {pooled.length === 0 ? (
          <>
            <h2 style={{ fontSize: "var(--fs-h2)" }}>No pooled board yet</h2>
            <p className="mt-6" style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
              No company has cleared its category&apos;s eligibility gate, so
              there is nothing to rank and no board is published. That is a
              correct outcome, not a missing feature: a position published on
              thin evidence is a claim the data cannot carry. Everything
              collected so far is on the category pages below, with the test
              each company missed named beside it.
            </p>
          </>
        ) : (
          <>
            <h2 style={{ fontSize: "var(--fs-h2)" }}>Most Loved and Most Hated</h2>
            <p className="mt-4" style={{ fontSize: "var(--fs-small)", maxWidth: "66ch" }}>
              Both lists come from one ordering read from opposite ends, so no
              company appears on both. At most five companies per category, so
              one busy category cannot fill the page.
            </p>
            <div className="mt-8">
              <LovedHatedBoard scores={pooled} perList={100} showCategory />
            </div>
          </>
        )}
      </section>

      {eligible.length > 0 && (
        <section className="mt-[var(--section)]">
          <h2 style={{ fontSize: "var(--fs-h3)" }}>Every ranked company</h2>
          <p className="mt-4" style={{ fontSize: "var(--fs-small)" }}>
            Default sort: Reddit Love Score, descending.
          </p>
          <EvidenceTable scores={eligible} />
        </section>
      )}

      {/* All 20 categories, ranked and unrankable both listed. Hiding the ones
          that cannot be ranked reads as cherry-picking. */}
      <section className="mt-[var(--section)]">
        <h2 style={{ fontSize: "var(--fs-h3)" }}>Categories</h2>
        <ul className="mt-8 grid gap-6 list-none p-0 m-0 sm:grid-cols-2 lg:grid-cols-3">
          {snap.categories.map((c) => (
            <li key={c.slug} className="cat-card-rule pt-4" data-category={c.slug}>
              <Link href={`/${c.slug}/`} className="flex items-start gap-3">
                <CategoryTile slug={c.slug} />
                <span>
                  <span className="block underline underline-offset-4"
                        style={{ fontSize: "var(--fs-body)" }}>
                    {c.name}
                  </span>
                  <span className="block mt-1" style={{ fontSize: "var(--fs-small)" }}>
                    {num(c.scores.length)} companies ·{" "}
                    {c.rankable ? `${c.tier} tier` : "cannot be ranked"}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
