import Link from "next/link";
import { num } from "@/lib/format";
import { CategoryTile } from "@/components/category/category-identity";
import { LovedHatedBoard } from "@/components/data/board";
import {
  ExposureConfoundLine, MethodologyCallout, CategoryTierLine,
} from "@/components/data/disclosures";
import {
  InsufficientSignalPanel, BelowThresholdBlock, EvidenceTable,
} from "@/components/data/states";
import { Breadcrumbs } from "@/components/site/breadcrumbs";
import type { CategoryView, Snapshot } from "@/lib/data/types";

/**
 * A category page, in the order 09-design.md specifies:
 *   breadcrumb -> H1 on the linear band -> methodology callout ->
 *   exposure-confound line -> the two-column board -> the full table ->
 *   the below-threshold block -> related categories.
 *
 * If the category cannot be ranked, the insufficient-signal panel REPLACES the
 * board entirely. Never alongside a partial ranking, never a 404.
 */
export function CategoryPage({
  category, snapshot,
}: {
  category: CategoryView;
  snapshot: Snapshot;
}) {
  const eligible = category.scores.filter((s) => s.eligible);
  const below = category.scores.filter((s) => !s.eligible);
  const alternatives = snapshot.categories
    .filter((c) => c.rankable && c.slug !== category.slug)
    .slice(0, 2)
    .map((c) => ({ slug: c.slug, name: c.name }));

  return (
    <>
      <Breadcrumbs trail={[{ href: "/", label: "Home" }]} current={category.name} />

      <header className="pattern-linear cat-header-rule mt-8 pt-8" data-category={category.slug}>
        <div className="flex items-center gap-4">
          <CategoryTile slug={category.slug} />
          <h1 style={{ fontSize: "var(--fs-h1)" }}>{category.name}</h1>
        </div>
      </header>

      <MethodologyCallout tier={category.tier} precisionPp={category.precisionPp} />
      <ExposureConfoundLine />
      <CategoryTierLine category={category} />

      <div className="mt-[var(--section)]">
        {!category.rankable ? (
          <InsufficientSignalPanel category={category} alternatives={alternatives} />
        ) : (
          <>
            <LovedHatedBoard scores={category.scores} perList={10} />

            <section className="mt-[var(--section)]">
              <h2 style={{ fontSize: "var(--fs-h3)" }}>Every company found</h2>
              <p className="mt-4" style={{ fontSize: "var(--fs-small)" }}>
                Sorted by Reddit Love Score, descending — that ordering is the
                consolidated view. {num(eligible.length)} of{" "}
                {num(category.scores.length)} companies carry a position.
              </p>
              <EvidenceTable scores={category.scores} />
            </section>

            <BelowThresholdBlock scores={below} />
          </>
        )}
      </div>

      <section className="mt-[var(--section)]">
        <h2 style={{ fontSize: "var(--fs-h4)" }}>Other categories</h2>
        <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 list-none p-0">
          {snapshot.categories
            .filter((c) => c.slug !== category.slug)
            .map((c) => (
              <li key={c.slug}>
                <Link href={`/${c.slug}/`} className="underline underline-offset-4"
                      style={{ fontSize: "var(--fs-small)" }}>
                  {c.name}
                </Link>
              </li>
            ))}
        </ul>
      </section>
    </>
  );
}
