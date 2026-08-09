import { IndexBoard } from "@/components/board/index-board";
import type { BoardData, Scope } from "@/lib/data/board-shapes";

/**
 * The index. A bold Sherpa masthead — "Reddit" carries the Virtual Goal
 * highlighter swash — then the controls band, then the boards. Nothing else.
 * That bareness is the owner's explicit spec, not an omission.
 */
export function IndexPage({ data, scope }: { data: BoardData; scope: Scope }) {
  return (
    <div className="pb-[var(--section)]">
      <header className="bleed masthead">
        <h1>
          <span className="swash">Reddit</span> Brand Index
        </h1>
      </header>
      <IndexBoard data={data} initialScope={scope} />
    </div>
  );
}
