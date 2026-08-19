/**
 * The company-page score for brands BELOW their category's ranking bar.
 *
 * Ruled 2026-08-19 (decisions/0011): every company page shows a Reddit ❤️
 * Score. A brand that meets its category's bar shows the board score exactly
 * as before (same number the board ranks it by). A brand below the bar shows
 * a score computed with the SAME estimator over ALL of its collected
 * opinionated mentions — the Positive and Negative tiles on its own page —
 * and stays unranked. No new method, no new constant: this is score.py's
 * published formula (p_tilde = posterior Beta, the published number is the
 * 0.10 quantile) with score.py's v2 leave-one-out pooled category prior
 * (PRIOR_K = 10, PRIOR_P0_SMOOTH = 10), applied to the page's own counts
 * instead of the scoring-window subset.
 *
 * Numerics are a line-for-line port of worker/score.py (_betacf, betainc,
 * beta_quantile) so a Python recompute lands on the same integer.
 */

export const PRIOR_K = 10;
export const PRIOR_P0_SMOOTH = 10;
export const PRIOR_POOL_MIN = 30;
export const SCORE_QUANTILE = 0.10;

// Lanczos approximation of ln Γ(x) (g = 7, n = 9). Accurate to ~1e-15 for the
// arguments used here (all > 0.5); Python's math.lgamma agrees to the digits
// that survive round(100 * q).
const LANCZOS: readonly [number, number, number, number, number, number, number, number, number] = [
  0.99999999999980993, 676.5203681218851, -1259.1392167224028,
  771.32342877765313, -176.61502916214059, 12.507343278686905,
  -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
];
export function lgamma(x: number): number {
  if (x < 0.5) {
    return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
  }
  x -= 1;
  let a: number = LANCZOS[0];
  const t = x + 7.5;
  for (let i = 1; i < 9; i++) a += (LANCZOS[i] as number) / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
}

function betacf(a: number, b: number, x: number, itmax = 200, eps = 3e-14): number {
  const qab = a + b, qap = a + 1.0, qam = a - 1.0;
  let c = 1.0;
  let d = 1.0 - qab * x / qap;
  if (Math.abs(d) < 1e-300) d = 1e-300;
  d = 1.0 / d;
  let h = d;
  for (let m = 1; m <= itmax; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1.0 + aa * d;
    if (Math.abs(d) < 1e-300) d = 1e-300;
    c = 1.0 + aa / c;
    if (Math.abs(c) < 1e-300) c = 1e-300;
    d = 1.0 / d;
    h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1.0 + aa * d;
    if (Math.abs(d) < 1e-300) d = 1e-300;
    c = 1.0 + aa / c;
    if (Math.abs(c) < 1e-300) c = 1e-300;
    d = 1.0 / d;
    const delta = d * c;
    h *= delta;
    if (Math.abs(delta - 1.0) < eps) break;
  }
  return h;
}

/** Regularised incomplete beta I_x(a,b) — the Beta CDF. */
export function betainc(a: number, b: number, x: number): number {
  if (x <= 0) return 0.0;
  if (x >= 1) return 1.0;
  const lbeta = lgamma(a + b) - lgamma(a) - lgamma(b)
    + a * Math.log(x) + b * Math.log(1.0 - x);
  if (x < (a + 1.0) / (a + b + 2.0)) return Math.exp(lbeta) * betacf(a, b, x) / a;
  return 1.0 - Math.exp(lbeta) * betacf(b, a, 1.0 - x) / b;
}

/** Inverse Beta CDF by bisection — deterministic, same 100 halvings as score.py. */
export function betaQuantile(a: number, b: number, q: number): number {
  let lo = 0.0, hi = 1.0;
  for (let i = 0; i < 100; i++) {
    const mid = (lo + hi) / 2.0;
    if (betainc(a, b, mid) < q) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2.0;
}

/**
 * score.py::fit_prior_pooled — the category's pooled positive rate, leaving
 * out the brand being scored, by mention mass. `counts` = [pos, nOp] per
 * OTHER brand in the category (the caller excludes the brand).
 */
export function fitPriorPooled(counts: Array<[number, number]>): {
  alpha0: number; beta0: number; fallback: boolean;
} {
  let op = 0, on = 0;
  for (const [p, n] of counts) { op += p; on += n; }
  const p0 = (op + PRIOR_P0_SMOOTH / 2) / (on + PRIOR_P0_SMOOTH);
  return { alpha0: PRIOR_K * p0, beta0: PRIOR_K * (1 - p0), fallback: on < PRIOR_POOL_MIN };
}

/** The published number: round(100 × the 0.10 posterior quantile). Null with no opinion. */
export function pageScore(pos: number, neg: number, alpha0: number, beta0: number): number | null {
  const nOp = pos + neg;
  if (nOp <= 0) return null;
  return Math.round(100 * betaQuantile(pos + alpha0, neg + beta0, SCORE_QUANTILE));
}
