import { IndexBoard } from "@/components/board/index-board";
import type { BoardData, Scope } from "@/lib/data/board-shapes";

/**
 * The index. "Reddit Index" at the top, the controls, the boards — and NOTHING
 * else. No hero sentence, no methodology callout, no disclaimers, no footer.
 * That bareness is the owner's explicit spec, not an omission.
 */
export function IndexPage({ data, scope }: { data: BoardData; scope: Scope }) {
  return (
    <div className="pt-14 pb-[var(--section)]">
      <h1
        className="tracking-tight"
        style={{ fontSize: "var(--fs-display)", color: "var(--sherpa-blue)" }}
      >
        Reddit Index
      </h1>
      <IndexBoard data={data} initialScope={scope} />
    </div>
  );
}
