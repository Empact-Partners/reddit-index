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
  removals_max?: unknown;
  removals_rows?: unknown;
} | undefined;

export type CorpusRevision = {
  mentions_max?: unknown;
  mentions_rows?: unknown;
  sentiment_max?: unknown;
  sentiment_rows?: unknown;
  removals_max?: unknown;
  removals_rows?: unknown;
} | undefined;

const ts = (v: unknown): number | null => {
  if (v === null || v === undefined) return null;
  const t = new Date(v as string).getTime();
  return Number.isNaN(t) ? null : t;
};
const num = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v);

/**
 * What this build must do about the rail it is about to read. Three tiers, by consequence:
 *
 *   LEGAL  a takedown the rail may still show. delete-sync records every removal in the `removals` ledger
 *          before it purges (decisions/0002, a legal condition, never skipped); a purge after the rail was built
 *          means a deleted card may still be on a page. Judged from the LEDGER, never from the net mention count:
 *          a review of PR #3 showed five takedowns inside a window that also collected 910 mentions read as +905,
 *          "only added". NOTHING overrides this tier — not RAIL_ALLOW_STALE, not anything.
 *   BLOCK  the rail cannot be trusted and a person may knowingly override it (RAIL_ALLOW_STALE=1): it was never
 *          refreshed, the revision could not be read, a LABEL changed (cards would disagree with the scores beside
 *          them), or the rail was built over an EMPTY corpus that now has mentions (every page would render with
 *          no cards — not a lag, a broken site).
 *   WARN   mentions were only added: the newest cards lag until the next publish. Cosmetic. A comment-only push
 *          was refused over exactly this on 2026-09-22 (910 mentions added), which is why it is not a block.
 *
 * Why labels need no content hash: every writer of mention_sentiment in this repo appends (INSERT ... ON CONFLICT
 * DO NOTHING — classify_api, classify_daily, classify_daemon, load, backfill_labels) and nothing UPDATEs it, so a
 * relabel is always a new row and always moves the count. An in-place relabel would take a hand-written UPDATE.
 */
export type RailVerdict = { legal: string[]; block: string[]; warn: string[] };

export function railVerdict(meta: RailMeta, rev: CorpusRevision): RailVerdict {
  if (!meta) return { legal: [], block: ["the rail has never recorded a refresh"], warn: [] };
  if (!rev) return { legal: [], block: ["the corpus revision could not be read"], warn: [] };

  const legal: string[] = [];
  const block: string[] = [];
  const warn: string[] = [];

  // --- LEGAL: the takedown ledger moved past what the rail knew ---------------------------------------
  const rLive = num(rev.removals_rows), rBuilt = num(meta.removals_rows);
  const rMarkLive = ts(rev.removals_max), rMarkBuilt = ts(meta.removals_max);
  if (rLive !== null && rBuilt === null && rLive > 0) {
    legal.push("takedowns exist and the rail recorded none of them — it may be showing deleted cards");
  } else if (rLive !== null && rBuilt !== null && rLive > rBuilt) {
    legal.push(`${rLive - rBuilt} takedown(s) purged since the rail was built — it may be showing deleted cards`);
  } else if (rMarkLive !== null && (rMarkBuilt === null || rMarkLive > rMarkBuilt)) {
    legal.push("a takedown newer than the rail was purged — it may be showing a deleted card");
  }
  // the net count still speaks when it FALLS: a deletion that bypassed the ledger is still a deletion
  const mLive = num(rev.mentions_rows), mBuilt = num(meta.mentions_rows);
  if (mLive !== null && mBuilt !== null && mLive < mBuilt) {
    legal.push(`mentions fell from ${mBuilt} to ${mLive} — deletions the rail would still show`);
  }

  // --- BLOCK: labels disagree with scores, or the rail is empty against a full corpus --------------------
  const labelLive = ts(rev.sentiment_max), labelBuilt = ts(meta.sentiment_max);
  if (labelLive !== null && labelBuilt === null && num(meta.sentiment_rows) !== 0) {
    block.push("labels exist and the rail recorded none");
  } else if (labelLive !== null && labelBuilt !== null && labelLive > labelBuilt) {
    block.push("a label newer than the rail was built for");
  }
  const labelRowsLive = num(rev.sentiment_rows), labelRowsBuilt = num(meta.sentiment_rows);
  if (labelRowsLive !== null && labelRowsBuilt !== null && labelRowsLive !== labelRowsBuilt) {
    block.push(`labels moved from ${labelRowsBuilt} to ${labelRowsLive} since the rail was built`);
  }
  if (mBuilt === 0 && mLive !== null && mLive > 0) {
    block.push(`the rail was built over an empty corpus and ${mLive} mention(s) now exist — every page would render with no cards`);
  } else if (mBuilt === null && ts(rev.mentions_max) !== null) {
    block.push("mentions exist and the rail recorded no count for them");
  }

  // --- WARN: only added -------------------------------------------------------------------------------
  if (mLive !== null && mBuilt !== null && mBuilt > 0 && mLive > mBuilt) {
    warn.push(`${mLive - mBuilt} mention(s) arrived since the rail was built — some newest cards lag until the next publish`);
  } else if (!legal.length && !block.length) {
    const markLive = ts(rev.mentions_max), markBuilt = ts(meta.mentions_max);
    if (markLive !== null && markBuilt !== null && markLive > markBuilt) {
      warn.push("a mention newer than the rail was built for — some newest cards lag until the next publish");
    }
  }
  return { legal, block, warn };
}

/** Every reason to refuse the build, legal first; kept for callers that only need the refusal. */
export function staleReasons(meta: RailMeta, rev: CorpusRevision): string[] {
  const v = railVerdict(meta, rev);
  return [...v.legal, ...v.block];
}
