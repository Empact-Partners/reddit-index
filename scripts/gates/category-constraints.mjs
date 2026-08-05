#!/usr/bin/env node
/**
 * Every colour in data/categories.csv, re-verified against C1-C7 from
 * decisions/0008 — recomputed from the STORED HEX, never trusted from the
 * `oklch` column beside it, which is the optimiser's pre-quantisation target.
 * Five rows drifted across a constraint boundary in exactly that gap.
 *
 * Also asserts the generated TypeScript still matches the CSV that produced it,
 * so "regenerate, never hand-edit" is enforced rather than requested.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { checkConstraints, minPairwise, deltaE, REDDIT_ORANGE } from '../color.mjs';
import { ROOT, fail, pass } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
const csvPath = path.join(root, 'data', 'categories.csv');
const raw = fs.readFileSync(csvPath);
const sha = crypto.createHash('sha256').update(raw).digest('hex');

const gen = fs.readFileSync(path.join(root, 'lib', 'generated', 'categories.ts'), 'utf8');
const declared = gen.match(/CATEGORIES_SOURCE_SHA256 = "([0-9a-f]{64})"/)?.[1];
if (declared !== sha) {
  fail('category constraints', [
    'data/categories.csv does not match the module generated from it.',
    `  csv sha256        ${sha}`,
    `  generated sha256  ${declared ?? '(absent)'}`,
    'Run `pnpm gen`. Editing a hex by hand voids every generation constraint silently.',
  ]);
}

const lines = raw.toString('utf8').trim().split('\n');
const header = lines[0].split(',');
const rows = lines.slice(1).map((l) => {
  const c = l.split(',');
  return Object.fromEntries(header.map((h, i) => [h, c[i]]));
});

const bad = [];
for (const r of rows) {
  const v = checkConstraints(r.hex);
  if (v.length) bad.push(`${String(r.slug).padEnd(24)} ${r.hex}  ${v.join(' · ')}`);
}
if (bad.length) {
  fail('category constraints', [
    `${bad.length} of ${rows.length} colours violate their own generation constraints:`,
    ...bad,
    '',
    'Re-run `node scripts/gen-palette.mjs`. A colour drifting toward green or purple is a build',
    'failure, not a taste question (decisions/0008).',
  ]);
}

const { min, pair } = minPairwise(rows.map((r) => r.hex));
const stored = Number(rows[0].min_pairwise_dE);
if (!Number.isFinite(stored) || Math.abs(stored - min) > 0.0002) {
  fail('category constraints', [
    `min pairwise ΔE_OKLab recomputes to ${min.toFixed(4)} (${rows[pair[0]].slug} / ${rows[pair[1]].slug})`,
    `but the CSV publishes ${rows[0].min_pairwise_dE}. Data and its published figure cannot drift.`,
  ]);
}

const thinnestOrange = Math.min(...rows.map((r) => deltaE(r.hex, REDDIT_ORANGE)));
if (thinnestOrange < 0.13) {
  fail('category constraints',
    `a category colour sits only ΔE ${thinnestOrange.toFixed(4)} from Reddit orange (C5 needs ≥ 0.13)`);
}

pass('category constraints',
  `${rows.length} colours · min pairwise ΔE ${min.toFixed(4)} · nearest orange ΔE ${thinnestOrange.toFixed(4)}`);
