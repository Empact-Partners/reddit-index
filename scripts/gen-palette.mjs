#!/usr/bin/env node
/**
 * Repair `data/categories.csv` so every colour satisfies C1-C7 when the
 * constraints are evaluated on the QUANTISED 8-bit hex.
 *
 * Why this exists. decisions/0008 generates the palette by satisfying C1-C7 in
 * continuous OKLCH and then writing an 8-bit hex. Recomputing the constraints
 * from the stored hex, five of the twenty rows fail — by between 0.00003 and
 * 0.0006, i.e. by rounding:
 *
 *   project-management    #EB367F   C7 chroma 0.22004 > 0.22
 *   hr                    #9E8242   C6 L 0.6193 < 0.62 · C7 chroma 0.08969 < 0.09
 *   password-managers     #C5CA86   C7 chroma 0.08907 < 0.09
 *   help-desk             #79D4E4   C5 ΔE 0.1297 to Lucky Green < 0.13
 *   business-intelligence #4C7AFF   C6 L 0.6198 < 0.62
 *
 * 16-design-system.md §8 makes "every colour in categories.csv re-verified
 * against its generation constraints" a blocking build gate. So either the data
 * moves or the gate gets an epsilon — and an epsilon that exists only to excuse
 * the data it checks is a gate that has never failed anything.
 *
 * The repair is deliberately minimal: hold the fifteen passing rows fixed,
 * search the 8-bit neighbourhood of each failing hex, and take the LEGAL
 * candidate closest to the original that does not reduce the palette's minimum
 * pairwise separation. Nothing here re-runs the farthest-point optimisation, so
 * the palette a designer already approved is preserved to within a rounding step.
 *
 * Also adds two columns the CSV never carried:
 *   dE_orange        — C5's third leg was unverifiable from the shipped file
 *   min_pairwise_dE  — so the published ΔE figure can be checked against data
 *
 * Usage:  node scripts/gen-palette.mjs [--check]
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  checkConstraints, deltaE, contrast, hexToOklch, hexToRgb, rgbToHex,
  minPairwise, round, SPACE_BLACK, SNOWBELT, LUCKY_GREEN, SUGAR_GRAPE, REDDIT_ORANGE,
} from './color.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CSV = path.join(ROOT, 'data', 'categories.csv');
const CHECK = process.argv.includes('--check');

// ── read ────────────────────────────────────────────────────────────────────
const raw = fs.readFileSync(CSV, 'utf8').trim().split('\n');
const header = raw[0].split(',');
const rows = raw.slice(1).map((line) => {
  const cells = line.split(',');
  return Object.fromEntries(header.map((h, i) => [h, cells[i]]));
});
if (rows.length !== 20) throw new Error(`expected 20 category rows, found ${rows.length}`);

const violations = rows.map((r) => ({ slug: r.slug, hex: r.hex, v: checkConstraints(r.hex) }));
const failing = violations.filter((x) => x.v.length);

console.log(`categories.csv — ${rows.length} rows, ${failing.length} failing C1-C7 on the stored hex\n`);
for (const f of failing) console.log(`  ${f.slug.padEnd(22)} ${f.hex}  ${f.v.join(' · ')}`);

if (CHECK) {
  if (failing.length) {
    console.error(`\nFAIL: ${failing.length} row(s) violate their own generation constraints.`);
    process.exit(1);
  }
  console.log('\nOK: every colour satisfies C1-C7 evaluated on the quantised hex.');
  process.exit(0);
}

// ── repair ──────────────────────────────────────────────────────────────────
const failingSlugs = new Set(failing.map((f) => f.slug));
const baseline = minPairwise(rows.map((r) => r.hex));
console.log(`\nbaseline min pairwise ΔE_OKLab = ${baseline.min.toFixed(4)} ` +
  `(${rows[baseline.pair[0]].slug} / ${rows[baseline.pair[1]].slug})`);

// The floor the repair must not drop below. Nothing may make the palette LESS
// separated than it already is.
const FLOOR = baseline.min;
const RADIUS = 10; // 8-bit steps per channel; the failures are sub-step in OKLCH

let repaired = 0;
for (const row of rows) {
  if (!failingSlugs.has(row.slug)) continue;
  const [r0, g0, b0] = hexToRgb(row.hex);
  const others = rows.filter((o) => o.slug !== row.slug).map((o) => o.hex);

  let best = null;
  for (let dr = -RADIUS; dr <= RADIUS; dr++)
    for (let dg = -RADIUS; dg <= RADIUS; dg++)
      for (let db = -RADIUS; db <= RADIUS; db++) {
        const r = r0 + dr, g = g0 + dg, b = b0 + db;
        if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) continue;
        const hex = rgbToHex([r, g, b]);
        if (checkConstraints(hex).length) continue;
        const sep = Math.min(...others.map((o) => deltaE(hex, o)));
        if (sep < FLOOR) continue;
        // closest legal colour to the original, then most separated
        const move = deltaE(hex, row.hex);
        if (!best || move < best.move - 1e-12 || (Math.abs(move - best.move) < 1e-12 && sep > best.sep))
          best = { hex, move, sep };
      }

  if (!best) throw new Error(`no legal colour within ${RADIUS} 8-bit steps of ${row.slug} ${row.hex}`);
  const [L, C, H] = hexToOklch(best.hex);
  console.log(`  repair ${row.slug.padEnd(22)} ${row.hex} -> ${best.hex}  ` +
    `ΔE moved ${best.move.toFixed(4)}  L ${L.toFixed(3)} C ${C.toFixed(3)} H ${H.toFixed(1)}°`);
  row.hex = best.hex;
  repaired++;
}

// ── recompute every derived column from the (possibly new) hex ──────────────
const finalHexes = rows.map((r) => r.hex);
const finalMin = minPairwise(finalHexes);

for (let i = 0; i < rows.length; i++) {
  const row = rows[i];
  const [L, C, H] = hexToOklch(row.hex);
  row.oklch = `oklch(${round(L, 3).toFixed(3)} ${round(C, 3).toFixed(3)} ${round(H, 1)})`;
  row.contrast_space_black = round(contrast(row.hex, SPACE_BLACK), 2);
  row.contrast_snowbelt = round(contrast(row.hex, SNOWBELT), 2);
  row.dE_loved = round(deltaE(row.hex, LUCKY_GREEN), 4);
  row.dE_hated = round(deltaE(row.hex, SUGAR_GRAPE), 4);
  row.dE_orange = round(deltaE(row.hex, REDDIT_ORANGE), 4);
  row.dE_nearest_category = round(
    Math.min(...finalHexes.filter((_, j) => j !== i).map((o) => deltaE(row.hex, o))), 4);
  row.min_pairwise_dE = round(finalMin.min, 4);
}

const outHeader = [...header];
for (const c of ['dE_orange', 'min_pairwise_dE'])
  if (!outHeader.includes(c)) outHeader.splice(outHeader.indexOf('dE_nearest_category') + 1, 0, c);

const out = [outHeader.join(','), ...rows.map((r) => outHeader.map((h) => r[h]).join(','))].join('\n') + '\n';
fs.writeFileSync(CSV, out);

const stillFailing = rows.filter((r) => checkConstraints(r.hex).length);
console.log(`\nrepaired ${repaired} row(s); ${stillFailing.length} still failing`);
console.log(`min pairwise ΔE_OKLab = ${finalMin.min.toFixed(4)} ` +
  `(${rows[finalMin.pair[0]].slug} / ${rows[finalMin.pair[1]].slug})`);
console.log(`thinnest ΔE to Reddit orange = ${Math.min(...rows.map((r) => r.dE_orange)).toFixed(4)}`);
console.log(`wrote ${CSV}`);
if (stillFailing.length) process.exit(1);
