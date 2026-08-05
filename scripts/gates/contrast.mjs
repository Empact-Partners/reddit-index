#!/usr/bin/env node
/**
 * Re-MEASURE every token pair. 16-design-system.md §8 is specific about this:
 * "Token pairs re-measured, not trusted from this document."
 *
 * The gate asserts the CONSTRAINT (>= 4.5:1 for body text, >= 3:1 for non-text),
 * never equality with a figure printed in a document — the stored contrast
 * numbers in the repo drift by ~0.02 from a fresh computation because they came
 * from a different linearisation constant, and a gate that demands equality
 * would fail on arithmetic rather than on design.
 *
 * Values are read out of app/globals.css, so a token edited there is checked
 * there rather than against a copy.
 */
import fs from 'node:fs';
import path from 'node:path';
import { contrast } from '../color.mjs';
import { ROOT, fail, pass } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
const css = fs.readFileSync(path.join(root, 'app', 'globals.css'), 'utf8');

function token(name) {
  const m = css.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})`));
  if (!m) fail('contrast', `token --${name} is not defined as a hex in app/globals.css`);
  return m[1];
}

const T = {
  sherpa: token('sherpa-blue'),
  green: token('lucky-green'),
  goal: token('virtual-goal'),
  grape: token('sugar-grape'),
  black: token('space-black'),
  snow: token('snowbelt'),
  greenDeep: token('green-deep'),
  grapeDeep: token('grape-deep'),
  grapeLight: token('grape-light'),
};

// [label, fg, bg, minimum, why]
const PAIRS = [
  ['body text on page',            T.black,      T.snow,   4.5, 'WCAG 1.4.3'],
  ['structure on page',            T.sherpa,     T.snow,   4.5, 'nav, headings'],
  ['loved ink on page',            T.greenDeep,  T.snow,   4.5, 'loved text and icons'],
  ['hated ink on page',            T.grapeDeep,  T.snow,   4.5, 'hated text and icons'],
  ['text on loved fill',           T.black,      T.green,  4.5, 'score chip, sentiment chip'],
  ['text on hated fill',           T.black,      T.grape,  4.5, 'score chip, sentiment chip'],
  ['footer text on Sherpa',        T.snow,       T.sherpa, 4.5, 'slot 4 must be readable'],
  ['hated accent on Sherpa',       T.grapeLight, T.sherpa, 4.5, 'the only on-dark accent'],
  ['focus ring on page',           T.grape,      T.snow,   3.0, 'WCAG 1.4.11 non-text'],
  ['focus ring on Sherpa',         T.goal,       T.sherpa, 3.0, 'WCAG 1.4.11 non-text'],
];

const bad = [];
const lines = [];
for (const [label, fg, bg, min, why] of PAIRS) {
  const r = contrast(fg, bg);
  lines.push(`${label.padEnd(26)} ${fg} on ${bg}  ${r.toFixed(2)}:1  (needs ${min}, ${why})`);
  if (r < min) bad.push(`${label}: ${r.toFixed(2)}:1 below the required ${min}:1  — ${why}`);
}

// The two colours the documents call out as unusable for text. If either ever
// clears 4.5 the palette has been edited, and the sentiment scale with it.
for (const [name, hex] of [['Lucky Green', T.green], ['Sugar Grape', T.grape]]) {
  const r = contrast(hex, T.snow);
  if (r >= 4.5) bad.push(`${name} now reads ${r.toFixed(2)}:1 on Snowbelt — the derived ink tokens exist because it did not`);
}

if (bad.length) fail('contrast', [...bad, '', ...lines]);
pass('contrast', `${PAIRS.length} token pairs re-measured`);
