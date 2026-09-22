/**
 * The rail-staleness decision (migration 0005), including every case Codex's review of PR #2 found the
 * first version getting wrong. The one that matters most: a RESCORE. The commonest publish in this repo
 * changes no mention at all — collect, classify, score, publish re-labels existing rows and the rail
 * carries the label — so a guard watching only the newest mention's timestamp passes a stale rail on the
 * most ordinary day there is.
 */
import { describe, it, expect } from "vitest";
import { staleReasons, railVerdict } from "@/lib/data/rail-freshness";

const T1 = "2026-09-21T07:57:12Z";
const T2 = "2026-09-22T09:00:00Z";

const current = {
  refreshed_at: T1,
  mentions_max: T1, mentions_rows: 1_240_014,
  sentiment_max: T1, sentiment_rows: 481_373,
  removals_max: T1, removals_rows: 2_001,
};
const corpus = { mentions_max: T1, mentions_rows: 1_240_014, sentiment_max: T1, sentiment_rows: 481_373,
                 removals_max: T1, removals_rows: 2_001 };

describe("staleReasons", () => {
  it("passes a rail built for exactly this corpus", () => {
    expect(staleReasons(current, corpus)).toEqual([]);
  });

  it("catches a RESCORE that touched no mention at all", () => {
    // the failure the single-signal version shipped: same mentions, same count, new labels
    const r = staleReasons(current, { ...corpus, sentiment_max: T2, sentiment_rows: 500_000 });
    expect(r.length).toBeGreaterThan(0);
    expect(r.join(" ")).toMatch(/label/);
  });

  it("WARNS, and does not block, when mentions were only added (production, 2026-09-22)", () => {
    // the exact state that blocked a comment-only push: a collection added 910 mentions after the last publish
    const v = railVerdict(current, { ...corpus, mentions_max: T2, mentions_rows: 1_240_924 });
    expect(v.block).toEqual([]);
    expect(v.warn.join(" ")).toMatch(/910 mention\(s\) arrived/);
  });

  it("refuses a net deletion as a takedown", () => {
    expect(railVerdict(current, { ...corpus, mentions_rows: 1_239_000 }).legal).toEqual([
      "mentions fell from 1240014 to 1239000 — deletions the rail would still show",
    ]);
  });

  it("refuses a takedown HIDDEN inside a window that also added mentions (review of PR #3)", () => {
    // five purged, 910 collected: the net count rises, the ledger does not lie
    const v = railVerdict(current, { ...corpus, mentions_rows: 1_240_919, mentions_max: T2,
                                     removals_rows: 2_006, removals_max: T2 });
    expect(v.legal.join(" ")).toMatch(/5 takedown\(s\) purged/);
  });

  it("refuses a takedown whose count is unchanged but whose ledger mark moved", () => {
    expect(railVerdict(current, { ...corpus, removals_max: T2 }).legal.length).toBe(1);
  });

  it("BLOCKS new labels even when no mention changed", () => {
    const v = railVerdict(current, { ...corpus, sentiment_rows: 481_374 });
    expect(v.block.join(" ")).toMatch(/labels moved/);
  });

  it("catches a rail that has never been refreshed", () => {
    expect(staleReasons(undefined, corpus)).toEqual(["the rail has never recorded a refresh"]);
  });

  it("a rail recorded before the ledger existed still judges takedowns, and refuses if any exist", () => {
    const { removals_max, removals_rows, ...preLedger } = current;
    void removals_max; void removals_rows;
    expect(railVerdict(preLedger, corpus).legal.length).toBe(1);
  });

  it("refuses to judge when the corpus revision could not be read", () => {
    expect(staleReasons(current, undefined)).toEqual(["the corpus revision could not be read"]);
  });

  it("blocks an EMPTY rail under a non-empty corpus — every page would have no cards (not a lag)", () => {
    const emptyRail = { refreshed_at: T1, mentions_max: null, mentions_rows: 0,
                        sentiment_max: null, sentiment_rows: 0, removals_max: T1, removals_rows: 2_001 };
    const v = railVerdict(emptyRail, corpus);
    expect(v.block.join(" ")).toMatch(/built over an empty corpus/);
    expect(v.warn).toEqual([]);
  });

  it("passes an honest first run: an empty rail over an empty corpus", () => {
    expect(staleReasons(
      { refreshed_at: T1, mentions_max: null, mentions_rows: 0, sentiment_max: null, sentiment_rows: 0,
        removals_max: null, removals_rows: 0 },
      { mentions_max: null, mentions_rows: 0, sentiment_max: null, sentiment_rows: 0,
        removals_max: null, removals_rows: 0 },
    )).toEqual([]);
  });

  it("does not call a rail stale for being AHEAD of the corpus", () => {
    // the refresh records its marks BEFORE it rebuilds, so the rail may legitimately carry a row the
    // recorded mark predates. Only the corpus being ahead is staleness.
    expect(staleReasons({ ...current, mentions_max: T2 }, corpus)).toEqual([]);
  });

  it("reads string counts from the driver as numbers, not as text", () => {
    // postgres returns bigint as a string; "1240014" !== 1240014 would fail every build
    expect(staleReasons({ ...current, mentions_rows: "1240014", sentiment_rows: "481373", removals_rows: "2001" },
                        corpus)).toEqual([]);
  });
});
