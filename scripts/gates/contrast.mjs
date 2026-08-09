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
  hatedFill: token('hated-fill'),
  hatedInk: token('hated-ink'),
};

// srgb interpolation is per-channel on the gamma-encoded values, which is
// exactly what color-mix(in srgb, …) computes — so the wash surfaces the
// board cards actually paint are reproducible here and get measured too.
function mix(hexA, hexB, wA) {
  const a = hexA.slice(1).match(/../g).map((h) => parseInt(h, 16));
  const b = hexB.slice(1).match(/../g).map((h) => parseInt(h, 16));
  return '#' + a.map((v, i) => Math.round(v * wA + b[i] * (1 - wA))
    .toString(16).padStart(2, '0')).join('');
}
const WHITE = '#FFFFFF';
const lovedWashHover = mix(T.green, WHITE, 0.24);
const hatedWashHover = mix(T.hatedFill, WHITE, 0.26);

// [label, fg, bg, minimum, why]
const PAIRS = [
  ['body text on page',            T.black,      T.snow,   4.5, 'WCAG 1.4.3'],
  ['structure on page',            T.sherpa,     T.snow,   4.5, 'nav, headings'],
  ['loved ink on page',            T.greenDeep,  T.snow,   4.5, 'loved text and icons'],
  ['hated ink on page',            T.hatedInk,   T.snow,   4.5, 'hated text and icons'],
  ['loved ink on deepest wash',    T.greenDeep,  lovedWashHover, 4.5, 'score text on hover rung'],
  ['hated ink on deepest wash',    T.hatedInk,   hatedWashHover, 4.5, 'score text on hover rung'],
  ['body text on deepest washes',  T.black,      hatedWashHover, 4.5, 'row text on hover rung'],
  ['text on loved fill',           T.black,      T.green,  4.5, 'board header strip, chips'],
  ['text on hated fill',           T.black,      T.hatedFill, 4.5, 'board header strip, chips'],
  ['masthead text on Sherpa',      T.snow,       T.sherpa, 4.5, 'the title band'],
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
