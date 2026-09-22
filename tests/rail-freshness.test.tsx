/**
 * The rail-staleness decision (migration 0005), including every case Codex's review of PR #2 found the
 * first version getting wrong. The one that matters most: a RESCORE. The commonest publish in this repo
 * changes no mention at all — collect, classify, score, publish re-labels existing rows and the rail
 * carries the label — so a guard watching only the newest mention's timestamp passes a stale rail on the
 * most ordinary day there is.
 */
import { describe, it, expect } from "vitest";
import { staleReasons } from "@/lib/data/rail-freshness";

const T1 = "2026-09-21T07:57:12Z";
const T2 = "2026-09-22T09:00:00Z";

const current = {
  refreshed_at: T1,
  mentions_max: T1, mentions_rows: 1_240_014,
  sentiment_max: T1, sentiment_rows: 481_373,
};
const corpus = { mentions_max: T1, mentions_rows: 1_240_014, sentiment_max: T1, sentiment_rows: 481_373 };

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

  it("catches a new mention", () => {
    expect(staleReasons(current, { ...corpus, mentions_max: T2, mentions_rows: 1_240_015 }).length)
      .toBeGreaterThan(0);
  });

  it("catches a DELETION, which moves a count without moving a maximum", () => {
    expect(staleReasons(current, { ...corpus, mentions_rows: 1_239_000 })).toEqual([
      "mentions moved from 1240014 to 1239000 since the rail was built",
    ]);
  });

  it("catches a rail that has never been refreshed", () => {
    expect(staleReasons(undefined, corpus)).toEqual(["the rail has never recorded a refresh"]);
  });

  it("refuses to judge when the corpus revision could not be read", () => {
    expect(staleReasons(current, undefined)).toEqual(["the corpus revision could not be read"]);
  });

  it("catches an empty rail under a non-empty corpus (the null bypass)", () => {
    const emptyRail = { refreshed_at: T1, mentions_max: null, mentions_rows: 0,
                        sentiment_max: null, sentiment_rows: 0 };
    const r = staleReasons(emptyRail, corpus);
    expect(r.join(" ")).toMatch(/mentions exist and the rail recorded none/);
    expect(r.join(" ")).toMatch(/labels exist and the rail recorded none/);
  });

  it("passes an honest first run: an empty rail over an empty corpus", () => {
    expect(staleReasons(
      { refreshed_at: T1, mentions_max: null, mentions_rows: 0, sentiment_max: null, sentiment_rows: 0 },
      { mentions_max: null, mentions_rows: 0, sentiment_max: null, sentiment_rows: 0 },
    )).toEqual([]);
  });

  it("does not call a rail stale for being AHEAD of the corpus", () => {
    // the refresh records its marks BEFORE it rebuilds, so the rail may legitimately carry a row the
    // recorded mark predates. Only the corpus being ahead is staleness.
    expect(staleReasons({ ...current, mentions_max: T2 }, corpus)).toEqual([]);
  });

  it("reads string counts from the driver as numbers, not as text", () => {
    // postgres returns bigint as a string; "1240014" !== 1240014 would fail every build
    expect(staleReasons({ ...current, mentions_rows: "1240014", sentiment_rows: "481373" },
                        corpus)).toEqual([]);
  });
});
