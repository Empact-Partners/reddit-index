import { IndexBoard } from "@/components/board/index-board";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";
import type { BoardData, Scope } from "@/lib/data/board-shapes";

/**
 * The index. The masthead is layout chrome now; this page is controls +
 * boards and nothing else — the bareness is the owner's explicit spec.
 * The h1 is sr-only: the visible identity is the masthead band.
 */
export function IndexPage({ data, scope }: { data: BoardData; scope: Scope }) {
  const scopeName = scope === "all"
    ? "All Categories"
    : CATEGORY_BY_SLUG[scope as CategorySlug].name;
  return (
    <div className="pb-[var(--section)]">
      <h1 className="sr-only">Reddit Brand Index — {scopeName}</h1>
      <IndexBoard data={data} initialScope={scope} />
    </div>
  );
}
