import { Fragment } from "react";
import Link from "next/link";
import { num } from "@/lib/format";
import { CATEGORY_BY_SLUG } from "@/lib/generated/categories";
import { PER_LIST, type BoardRow } from "@/lib/data/board-shapes";

/**
 * One board. A real <table>, two metric columns — Reddit Love Score and
 * mentions — plus a category chip in the All Categories scope. Nothing else:
 * no CI, no n_eff, no badges. The receipts live on the company pages.
 *
 * The category swatch is the bare .cat-chip span, NOT the CategoryChip
 * component: no nested link inside the row, and no lucide icon set dragged
 * into the client bundle.
 */
export function BoardTable({
  rows,
  tone,
  showCategory,
  caption,
  total,
}: {
  rows: BoardRow[];
  tone: "loved" | "hated" | "neutral";
  showCategory: boolean;
  caption: string;
  /** Consolidated view only: the uncapped scope size, so absolute positions
   *  survive truncation and the gap says what it skipped. */
  total?: number;
}) {
  const truncated = total !== undefined && rows.length < total;

  function rank(i: number): number {
    if (total === undefined) return i + 1; // split view: rank within this list
    if (!truncated || i < PER_LIST) return i + 1;
    return total - (rows.length - i) + 1; // bottom block: absolute position
  }

  return (
    <div className="table-scroll">
      <table className="rank-table" data-tone={tone}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" aria-label="Rank">#</th>
            <th scope="col">Brand</th>
            <th scope="col">Reddit Love Score</th>
            <th scope="col">Mentions</th>
            {showCategory && <th scope="col">Category</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <Fragment key={`${r.brandSlug}:${r.categorySlug}`}>
              {truncated && i === PER_LIST && (
                <tr className="rank-gap">
                  <td colSpan={showCategory ? 5 : 4}>
                    positions {PER_LIST + 1}–{num((total as number) - PER_LIST)} not shown
                  </td>
                </tr>
              )}
              <tr>
                <td className="col-rank">{rank(i)}</td>
                <td className="col-brand">
                  <Link href={`/${r.brandSlug}/`} className="underline underline-offset-4">
                    {r.brandName}
                  </Link>
                </td>
                <td className="col-score">{r.score}</td>
                <td className="col-mentions">{num(r.mentions)}</td>
                {showCategory && (
                  <td className="col-category">
                    <span className="cat-chip" data-category={r.categorySlug}>
                      {CATEGORY_BY_SLUG[r.categorySlug].name}
                    </span>
                  </td>
                )}
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
