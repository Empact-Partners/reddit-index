/**
 * Is the materialised rail the rail this corpus deserves?
 *
 * Migration 0005 moved the mention rail out of the build (86,909 ms -> 562 ms) and introduced exactly
 * one new way to be wrong: a publish that changes the corpus and skips the refresh builds a site whose
 * cards are older than the numbers beside them, silently. This is the decision that refuses that build.
 *
 * It is a pure function on two rows so it can be tested, because the first version of it was wrong in
 * four ways that only a test finds. It compared ONE signal — the newest mention's timestamp — which
 * answers "did new mentions arrive" and nothing else. The commonest publish in this repo changes no
 * mention at all: collect, classify, score, publish re-LABELS existing rows, and the rail carries the
 * label. A rescored corpus under an unchanged newest-mention mark is precisely the stale rail this
 * exists to catch, and the single-signal version waved it through.
 *
 * FOUR signals, therefore, and the counts matter as much as the marks: a deletion, an edited body and
 * a backfill of an older document into a brand's underfilled rail each move a count without moving a
 * maximum.
 */

export type RailMeta = {
  refreshed_at?: unknown;
  mentions_max?: unknown;
  mentions_rows?: unknown;
  sentiment_max?: unknown;
  sentiment_rows?: unknown;
} | undefined;

export type CorpusRevision = {
  mentions_max?: unknown;
  mentions_rows?: unknown;
  sentiment_max?: unknown;
  sentiment_rows?: unknown;
} | undefined;

const ts = (v: unknown): number | null => {
  if (v === null || v === undefined) return null;
  const t = new Date(v as string).getTime();
  return Number.isNaN(t) ? null : t;
};
const num = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v);

/**
 * Every reason this rail is stale. Empty means it is current, and the build may proceed.
 */
export function staleReasons(meta: RailMeta, rev: CorpusRevision): string[] {
  if (!meta) return ["the rail has never recorded a refresh"];
  if (!rev) return ["the corpus revision could not be read"];

  const out: string[] = [];

  // A mark that exists in the corpus and not in the rail's record is stale: the rail was built over
  // nothing of that kind while the corpus holds some. Both absent is an honest empty corpus, and passes.
  for (const [what, live, built] of [
    ["a mention newer", ts(rev.mentions_max), ts(meta.mentions_max)],
    ["a label newer", ts(rev.sentiment_max), ts(meta.sentiment_max)],
  ] as const) {
    if (live === null) continue;
    if (built === null) out.push(`${what.split(" ")[1] === "mention" ? "mentions exist" : "labels exist"} and the rail recorded none`);
    else if (live > built) out.push(`${what} than the rail was built for`);
  }

  // A count that moved in EITHER direction is stale — a deletion is as much a change as an arrival.
  for (const [what, live, built] of [
    ["mentions", num(rev.mentions_rows), num(meta.mentions_rows)],
    ["labels", num(rev.sentiment_rows), num(meta.sentiment_rows)],
  ] as const) {
    if (live === null || built === null) continue;
    if (live !== built) out.push(`${what} moved from ${built} to ${live} since the rail was built`);
  }
  return out;
}
