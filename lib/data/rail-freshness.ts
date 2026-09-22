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
 * What this build must do about the rail it is about to read.
 *
 * Not all drift is the same, and treating it as the same blocked a comment-only push within hours of shipping:
 * a collection had added 910 mentions since the last publish, and every code push after that refused to build
 * until someone published. That is the "the site cannot be rebuilt at all" failure this repo has paid for
 * before. So each kind of drift gets the verdict its consequence deserves:
 *
 *   BLOCK  the rail has never been refreshed, or the corpus revision could not be read;
 *   BLOCK  a LABEL changed (a rescore or new classifications) — every card would show a label that disagrees
 *          with the score beside it, which is the case the review of PR #2 found the first guard missing;
 *   BLOCK  mentions were DELETED — delete-sync propagates takedowns (decisions/0002, a legal condition, never
 *          skipped). The live rail this replaced dropped a deleted mention on the next build; a stale
 *          materialised rail would keep showing it, so a shrinking corpus is never "just a warning";
 *   WARN   mentions were only ADDED — some brands' newest cards lag until the next publish. Cosmetic, fixed by
 *          the next publish, and never worth refusing a code deploy over.
 */
export type RailVerdict = { block: string[]; warn: string[] };

export function railVerdict(meta: RailMeta, rev: CorpusRevision): RailVerdict {
  if (!meta) return { block: ["the rail has never recorded a refresh"], warn: [] };
  if (!rev) return { block: ["the corpus revision could not be read"], warn: [] };

  const block: string[] = [];
  const warn: string[] = [];

  // labels: any movement at all is a disagreement between cards and scores
  const labelLive = ts(rev.sentiment_max), labelBuilt = ts(meta.sentiment_max);
  if (labelLive !== null && labelBuilt === null) block.push("labels exist and the rail recorded none");
  else if (labelLive !== null && labelBuilt !== null && labelLive > labelBuilt) block.push("a label newer than the rail was built for");
  const labelRowsLive = num(rev.sentiment_rows), labelRowsBuilt = num(meta.sentiment_rows);
  if (labelRowsLive !== null && labelRowsBuilt !== null && labelRowsLive !== labelRowsBuilt) {
    block.push(`labels moved from ${labelRowsBuilt} to ${labelRowsLive} since the rail was built`);
  }

  // mentions: fewer is a takedown the rail would keep showing; more is a rail that lags
  const mLive = num(rev.mentions_rows), mBuilt = num(meta.mentions_rows);
  if (mLive !== null && mBuilt !== null && mLive < mBuilt) {
    block.push(`mentions fell from ${mBuilt} to ${mLive} — deletions the rail would still show`);
  } else if (mLive !== null && mBuilt !== null && mLive > mBuilt) {
    warn.push(`${mLive - mBuilt} mention(s) arrived since the rail was built — some newest cards lag until the next publish`);
  }
  const markLive = ts(rev.mentions_max), markBuilt = ts(meta.mentions_max);
  if (markLive !== null && markBuilt === null) block.push("mentions exist and the rail recorded none");
  else if (markLive !== null && markBuilt !== null && markLive > markBuilt && !warn.length) {
    warn.push("a mention newer than the rail was built for — some newest cards lag until the next publish");
  }
  return { block, warn };
}

/** Every reason to refuse the build; kept for callers that only need the refusal. */
export function staleReasons(meta: RailMeta, rev: CorpusRevision): string[] {
  return railVerdict(meta, rev).block;
}
