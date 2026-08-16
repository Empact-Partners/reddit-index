import { Fragment } from "react";
import Link from "next/link";
import { num } from "@/lib/format";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";
import { PER_LIST, type BoardRow } from "@/lib/data/board-shapes";

/**
 * Full category names, always. The abbreviation map that used to live here
 * ("Backup & Storage" -> trimmed tails) existed because the two half-width
 * cards could not fit a real name on one line, and the fallback was a
 * horizontal scrollbar inside each card. Vlad, 2026-08-16: no horizontal
 * scroll on Most Loved / Most Hated, and the category name must be fully
 * visible. The cards are now given the width instead (see .board-grid).
 */
function categoryLabel(slug: CategorySlug): string {
  return CATEGORY_BY_SLUG[slug].name;
}

/**
 * One board. A real <table>, two metric columns — Reddit Love Score (centred,
 * one-line header) and mentions — plus a category chip in the All Categories
 * scope. The receipts live on the company pages.
 *
 * In the consolidated (neutral) view every row is colour-coded by which end of
 * the ordering it belongs to: the loved half carries the green wash, the hated
 * half the warm wash, and the top/bottom ten sit a rung deeper. The split is
 * the same ceil/floor as splitScope, so the two views can never disagree about
 * which side a brand is on.
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
  const consolidated = total !== undefined;
  const truncated = consolidated && rows.length < (total as number);
  const lovedN = Math.min(PER_LIST, Math.ceil(rows.length / 2));

  function rank(i: number): number {
    const t = rows[i]?.trueRank;
    if (t !== undefined) return t;   // search hit: its position on the real board
    if (!consolidated) return i + 1; // split view: rank within this list
    if (!truncated || i < PER_LIST) return i + 1;
    return (total as number) - (rows.length - i) + 1; // bottom block: absolute
  }

  function endAttrs(i: number) {
    if (!consolidated) return {};
    const isLoved = truncated ? i < PER_LIST : i < lovedN;
    const fromBottom = rows.length - 1 - i;
    const strong = isLoved ? i < 10 : fromBottom < 10;
    return {
      "data-end": isLoved ? "loved" : "hated",
      ...(strong ? { "data-strong": "" } : {}),
    };
  }

  return (
    <div className="board-table-wrap">
      <table className="rank-table" data-tone={tone}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" aria-label="Rank">#</th>
            <th scope="col">Brand</th>
            <th scope="col" className="col-score">
              Reddit <span aria-hidden="true">❤️</span><span className="sr-only">Love</span> Score
            </th>
            <th scope="col" className="col-mentions">Mentions</th>
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
              <tr {...endAttrs(i)}>
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
                      {categoryLabel(r.categorySlug)}
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
