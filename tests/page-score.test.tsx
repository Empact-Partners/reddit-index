import { describe, it, expect } from "vitest";
import fixtures from "./fixtures-page-score.json";
import { fitPriorPooled, pageScore, betainc, betaQuantile } from "@/lib/data/page-score";

/**
 * Parity with worker/score.py. The fixtures were produced by the Python
 * estimator (fit_prior_pooled + beta_quantile at SCORE_QUANTILE) — the TS port
 * must land on the same prior and the same integer for every case, or the
 * number on a company page would not be the number a Python recompute gives.
 */
describe("page-score parity with worker/score.py", () => {
  for (const f of fixtures as Array<{
    others: Array<[number, number]>; pos: number; neg: number;
    alpha0: number; beta0: number; fallback: boolean; score: number;
  }>) {
    it(`pos=${f.pos} neg=${f.neg} others=${JSON.stringify(f.others)} -> ${f.score}`, () => {
      const { alpha0, beta0, fallback } = fitPriorPooled(f.others);
      expect(alpha0).toBeCloseTo(f.alpha0, 9);
      expect(beta0).toBeCloseTo(f.beta0, 9);
      expect(fallback).toBe(f.fallback);
      expect(pageScore(f.pos, f.neg, alpha0, beta0)).toBe(f.score);
    });
  }
  // 2026-08-25: this used to assert null. A brand Reddit discusses without
  // praising or damning it now scores at the CATEGORY BASELINE — with pos = neg
  // = 0 the posterior is the prior, so the same quantile call answers "we know
  // nothing beyond this category", which is the truth. Nothing is invented.
  // The null case moved up a level: snapshot.ts returns null when there is no
  // LABELLED mention at all, because "discussed neutrally" and "never mentioned"
  // are different facts that used to render identically.
  it("no opinion -> the category baseline, not null", () => {
    const s = pageScore(0, 0, 5, 5);
    expect(s).not.toBeNull();
    expect(s).toBe(30);
  });
  // The property that makes this safe: a neutral brand can never outrank an
  // evidenced one, because every score is the same lower-bound quantile.
  it("a neutral brand sits between damned and praised", () => {
    const neutral = pageScore(0, 0, 5, 5)!;
    expect(pageScore(0, 10, 5, 5)!).toBeLessThan(neutral);
    expect(pageScore(10, 0, 5, 5)!).toBeGreaterThan(neutral);
    expect(pageScore(1, 0, 5, 5)!).toBeGreaterThan(neutral);
  });
  it("betainc is a CDF", () => {
    expect(betainc(2, 3, 0)).toBe(0);
    expect(betainc(2, 3, 1)).toBe(1);
    expect(betainc(2, 2, 0.5)).toBeCloseTo(0.5, 12);
    expect(betaQuantile(2, 2, 0.5)).toBeCloseTo(0.5, 9);
  });
});
