import Link from "next/link";
import { num } from "@/lib/format";
import { ScoreChip } from "./score-chip";
import { CategoryChip } from "@/components/category/category-identity";
import type { BrandScore } from "@/lib/data/types";
import type { CategorySlug } from "@/lib/generated/categories";

/**
 * THE BOARD. Two columns that are two truncated views of ONE ordering.
 *
 * decisions/0006 collapsed the old two-index design into a single published
 * metric, and the arithmetic consequence is load-bearing: Most Loved is that
 * ordering descending, Most Hated is the same ordering ascending, so
 * **a company cannot appear on both**. Under one ordering it is impossible.
 *
 * With N eligible companies, each list takes at most floor(N/2) — otherwise
 * "top 10 each" over 9 companies renders the same names twice under opposite
 * headings, which is the one thing 0006 forbids. The page states the actual
 * counts rather than implying a round number.
 *
 * Below 768px the board STACKS: full Most Loved, then full Most Hated, each
 * keeping its heading, its accent and its full score chips. It never becomes
 * two narrow columns.
 */
export function splitBoard(scores: BrandScore[], perList: number) {
  const eligible = scores.filter((s) => s.eligible && s.redditLoveScore !== null);
  const ordered = [...eligible].sort(
    (a, b) => (b.redditLoveScore ?? 0) - (a.redditLoveScore ?? 0),
  );
  const cap = Math.min(perList, Math.floor(ordered.length / 2));
  return {
    loved: ordered.slice(0, cap),
    hated: cap === 0 ? [] : ordered.slice(-cap).reverse(),
    total: ordered.length,
    cap,
  };
}

function BoardColumn({
  heading,
  rows,
  tone,
  showCategory,
}: {
  heading: string;
  rows: BrandScore[];
  tone: "loved" | "hated";
  showCategory: boolean;
}) {
  return (
    <section>
      {/* The superlative NEVER stands alone: every row below carries the
          measured variable in a score chip. decisions/0005 condition 1. */}
      <h2 style={{ fontSize: "var(--fs-h3)" }}>{heading}</h2>
      <ol className="mt-6 list-none p-0 m-0 grid gap-6">
        {rows.map((s, i) => (
          <li key={s.brandSlug} className="grid gap-2">
            <p className="flex flex-wrap items-baseline gap-3">
              <span style={{ fontSize: "var(--fs-micro)" }}>
                {tone === "loved" ? i + 1 : `#${s.rankDesc}`}
              </span>
              <Link
                href={`/${s.brandSlug}/`}
                style={{ fontSize: "var(--fs-body)" }}
                className="underline underline-offset-4"
              >
                {s.brandName}
              </Link>
              <span style={{ fontSize: "var(--fs-small)" }}>
                {num(s.n)} mentions
              </span>
              {showCategory && <CategoryChip slug={s.categorySlug as CategorySlug} />}
            </p>
            <ScoreChip
              score={s.redditLoveScore as number}
              ciLow={s.ciLow as number}
              ciHigh={s.ciHigh as number}
              opinionatedMentions={s.nOp}
              nEff={s.nEff}
              windowStart={s.windowStart}
              windowEnd={s.windowEnd}
              tone={tone}
            />
          </li>
        ))}
      </ol>
    </section>
  );
}

export function LovedHatedBoard({
  scores,
  perList,
  showCategory = false,
}: {
  scores: BrandScore[];
  perList: number;
  showCategory?: boolean;
}) {
  const { loved, hated, total, cap } = splitBoard(scores, perList);

  if (cap === 0) {
    return (
      <p style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
        {total === 0
          ? "No company here has cleared the eligibility gate yet, so no board is published. Every company found is listed below with the test it missed."
          : `Only ${total} company has cleared the eligibility gate. A board needs at least two, one at each end of the ordering, so none is published yet.`}
      </p>
    );
  }

  return (
    <>
      <p style={{ fontSize: "var(--fs-small)" }}>
        {total} companies qualify. Each list shows {cap} of them, drawn from
        opposite ends of one ordering, so no company appears on both.
      </p>
      <div className="mt-8 grid gap-12 md:grid-cols-2">
        <BoardColumn heading="Most Loved" rows={loved} tone="loved" showCategory={showCategory} />
        <BoardColumn heading="Most Hated" rows={hated} tone="hated" showCategory={showCategory} />
      </div>
    </>
  );
}
