import { num, formatWindow } from "@/lib/format";

export type ScoreChipProps = {
  score: number;              // integer 0-100
  ciLow: number;              // 90% cluster-bootstrap lower bound, 0-100
  ciHigh: number;             // upper bound
  opinionatedMentions: number; // N_op = pos + neg. NOT raw n.
  nEff: number;
  windowStart: string;        // ISO date
  windowEnd: string;          // ISO date
  /** Never a category colour. `neutral` wherever no Most Loved / Most Hated
   *  heading sits above the chip, so it can't imply a verdict the page
   *  didn't make. */
  tone?: "loved" | "hated" | "neutral";
};

/**
 * FIVE FIELDS, FIXED ORDER, ONE LINE.
 *
 *   Reddit Love Score 21/100 · 90% CI 18–24 · 1,240 opinionated mentions · n_eff 412 · Jan–Jun 2026
 *
 * decisions/0005 accepts the labels "Most Loved" and "Most Hated" only on six
 * conditions, and the first is that "the measured variable appears next to the
 * superlative on every surface… the superlative is never alone". A chip showing
 * only the score fails the condition the whole naming decision ships under.
 *
 * So, all of these are requirements and none is a default:
 *   · Small or larger — never Micro. No figure a reader must check sits at 13px
 *   · never truncated, never an ellipsis, never a tooltip
 *   · the interval is IN the chip. "An interval a reader cannot see is an
 *     interval that does not constrain the claim."
 *   · on mobile the line WRAPS between fields; it never collapses
 *
 * The interval is rendered as `90% CI` rather than a bare `CI`: decisions/0006
 * fixes it at a 90% cluster bootstrap, and a level-less interval is ambiguous.
 */
export function ScoreChip({
  score, ciLow, ciHigh, opinionatedMentions, nEff, windowStart, windowEnd, tone = "neutral",
}: ScoreChipProps) {
  // Postgres hands back null where TypeScript promised number. A chip missing a
  // field is a broken promise to the reader, so it fails here instead.
  for (const [k, v] of Object.entries({ score, ciLow, ciHigh, opinionatedMentions, nEff })) {
    if (!Number.isFinite(v)) {
      throw new Error(`ScoreChip: ${k} is not a finite number (${v}). All five fields are mandatory — decisions/0005 condition 1.`);
    }
  }

  return (
    <p className="score-chip" data-tone={tone}>
      <span className="sr-only">Score summary. </span>
      <span className="f">
        Reddit&nbsp;Love&nbsp;Score <b>{score}</b>/100
      </span>
      <span aria-hidden="true"> · </span>
      <span className="f">
        90% CI <b>{ciLow}</b>–<b>{ciHigh}</b>
      </span>
      <span aria-hidden="true"> · </span>
      <span className="f">
        <b>{num(opinionatedMentions)}</b> opinionated mentions
      </span>
      <span aria-hidden="true"> · </span>
      <span className="f">
        n_eff <b>{num(Math.round(nEff))}</b>
      </span>
      <span aria-hidden="true"> · </span>
      <span className="f">
        <time dateTime={`${windowStart}/${windowEnd}`}>
          {formatWindow(windowStart, windowEnd)}
        </time>
      </span>
    </p>
  );
}
