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
  it("no opinion -> no score", () => {
    expect(pageScore(0, 0, 5, 5)).toBeNull();
  });
  it("betainc is a CDF", () => {
    expect(betainc(2, 3, 0)).toBe(0);
    expect(betainc(2, 3, 1)).toBe(1);
    expect(betainc(2, 2, 0.5)).toBeCloseTo(0.5, 12);
    expect(betaQuantile(2, 2, 0.5)).toBeCloseTo(0.5, 9);
  });
});
