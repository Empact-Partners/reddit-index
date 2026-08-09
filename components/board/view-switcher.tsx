"use client";

/**
 * Two boards <-> one list. A segmented control: two buttons, aria-pressed,
 * 6px radius (pill shapes are sentiment-only), active leg filled Sherpa Blue.
 */
export type BoardView = "boards" | "list";

export function ViewSwitcher({
  value,
  onChange,
}: {
  value: BoardView;
  onChange: (next: BoardView) => void;
}) {
  return (
    <div className="seg" role="group" aria-label="View">
      <button
        type="button"
        aria-pressed={value === "boards"}
        onClick={() => onChange("boards")}
      >
        Loved | Hated
      </button>
      <button
        type="button"
        aria-pressed={value === "list"}
        onClick={() => onChange("list")}
      >
        One list
      </button>
    </div>
  );
}
