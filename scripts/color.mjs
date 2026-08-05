/**
 * Colour maths — the single implementation, shared by the palette generator and
 * the build gate that checks it. Zero dependencies so it runs identically on
 * Vercel, in CI, and locally.
 *
 * decisions/0008 states its constraints in OKLCH and OKLab. Nothing here trusts
 * a figure written in a document: every value is recomputed from the stored hex.
 * That distinction matters — `data/categories.csv` carries an `oklch` column
 * that is the optimiser's PRE-QUANTISATION target, not the OKLCH of the 8-bit
 * hex beside it, and five rows drifted across a constraint boundary in between.
 */

/** sRGB 8-bit channel -> linear light. */
export const srgbToLinear = (c) => {
  const x = c / 255;
  return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
};

/** linear light -> sRGB 8-bit channel, clamped. */
export const linearToSrgb = (x) => {
  const v = x <= 0.0031308 ? x * 12.92 : 1.055 * x ** (1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(v * 255)));
};

export function hexToRgb(hex) {
  const h = hex.replace('#', '').trim();
  if (!/^[0-9a-fA-F]{6}$/.test(h)) throw new Error(`not a 6-digit hex: ${hex}`);
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

export const rgbToHex = ([r, g, b]) =>
  '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('').toUpperCase();

/** linear sRGB -> OKLab (Ottosson). */
export function linearRgbToOklab([R, G, B]) {
  const l = 0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B;
  const m = 0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B;
  const s = 0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B;
  const cbrt = (v) => (v >= 0 ? Math.cbrt(v) : -Math.cbrt(-v));
  const l_ = cbrt(l), m_ = cbrt(m), s_ = cbrt(s);
  return [
    0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
    1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
    0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
  ];
}

export const hexToOklab = (hex) => linearRgbToOklab(hexToRgb(hex).map(srgbToLinear));

/** OKLCH from a hex: [L, C, H] with H in degrees [0, 360). */
export function hexToOklch(hex) {
  const [L, a, b] = hexToOklab(hex);
  const C = Math.hypot(a, b);
  const H = ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
  return [L, C, H];
}

/** Euclidean distance in OKLab — the ΔE decisions/0008 uses throughout. */
export function deltaE(hexA, hexB) {
  const A = hexToOklab(hexA), B = hexToOklab(hexB);
  return Math.hypot(A[0] - B[0], A[1] - B[1], A[2] - B[2]);
}

/** WCAG 2.2 relative luminance. */
export function relativeLuminance(hex) {
  const [R, G, B] = hexToRgb(hex).map(srgbToLinear);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

/** WCAG 2.2 contrast ratio, 1..21. */
export function contrast(hexA, hexB) {
  const a = relativeLuminance(hexA), b = relativeLuminance(hexB);
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

// ── The fixed points ────────────────────────────────────────────────────────
export const SPACE_BLACK = '#171616';
export const SNOWBELT = '#EEF1ED';
export const SHERPA_BLUE = '#02454F';
export const LUCKY_GREEN = '#40C890';   // loved
export const SUGAR_GRAPE = '#A155FF';   // hated
export const REDDIT_ORANGE = '#FF4500'; // banned outright

/**
 * C1-C7 from decisions/0008, evaluated on the QUANTISED hex.
 * Returns [] when the colour is legal, otherwise one string per violation.
 */
export function checkConstraints(hex) {
  const [L, C, H] = hexToOklch(hex);
  const v = [];
  const c1 = contrast(hex, SPACE_BLACK);
  if (c1 < 4.5) v.push(`C1 Space Black contrast ${c1.toFixed(2)} < 4.5`);
  if (H >= 10 && H <= 85) v.push(`C2 hue ${H.toFixed(1)}° inside the banned orange band 10-85°`);
  if (H >= 132 && H <= 192) v.push(`C3 hue ${H.toFixed(1)}° inside the banned green band 132-192°`);
  if (H >= 269 && H <= 330) v.push(`C4 hue ${H.toFixed(1)}° inside the banned purple band 269-330°`);
  const dG = deltaE(hex, LUCKY_GREEN), dP = deltaE(hex, SUGAR_GRAPE), dO = deltaE(hex, REDDIT_ORANGE);
  const dMin = Math.min(dG, dP, dO);
  if (dMin < 0.13)
    v.push(`C5 OKLab distance ${dMin.toFixed(4)} < 0.13 (green ${dG.toFixed(4)}, grape ${dP.toFixed(4)}, orange ${dO.toFixed(4)})`);
  if (L < 0.62 || L > 0.82) v.push(`C6 lightness ${L.toFixed(4)} outside [0.62, 0.82]`);
  if (C < 0.09 || C > 0.22) v.push(`C7 chroma ${C.toFixed(5)} outside [0.09, 0.22]`);
  return v;
}

/** Smallest ΔE between any two colours in the set. */
export function minPairwise(hexes) {
  let best = Infinity, pair = null;
  for (let i = 0; i < hexes.length; i++)
    for (let j = i + 1; j < hexes.length; j++) {
      const d = deltaE(hexes[i], hexes[j]);
      if (d < best) { best = d; pair = [i, j]; }
    }
  return { min: best, pair };
}

export const round = (x, n) => Number(x.toFixed(n));
