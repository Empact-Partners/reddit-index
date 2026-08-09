#!/usr/bin/env node
/**
 * TRADE DRESS. The gate 09-design.md and 16-design-system.md §8 both name, plus
 * the leg they do not: a colour-space scan.
 *
 * The literal string scan (`ff4500`, `orange`, `snoo`, `reddit-sans`) is what
 * the documents specify, and on its own it is blind to the thing it exists to
 * catch. Tailwind emits orange as `oklch(0.705 0.213 47.604)` — no substring
 * matches, and the colour is still Reddit orange. So every colour literal in
 * the built CSS is converted to OKLCH and rejected on hue.
 *
 * The ban is not just #FF4500. It is "every orange, amber and warm red near
 * it", because "a near-miss reads as a deliberate near-miss".
 */
import fs from 'node:fs';
import path from 'node:path';
import { hexToOklch, hexToOklab, rgbToHex } from '../color.mjs';

const REDDIT_LAB = hexToOklab('#FF4500');
import { ROOT, builtCss, allSvg, walk, fail, pass, requireBuild } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
requireBuild(root);

const LITERALS = [
  /ff4500/i,
  /\borange\b/i,
  /\bamber\b/i,
  /snoo/i,
  /reddit[-_ ]?sans/i,
  /rgb\(\s*255\s*,\s*69\s*,\s*0\s*\)/i,
];

const violations = [];

// ── 1. literal strings, over built CSS, every SVG, and the font manifest ────
const cssFiles = builtCss(root);
const svgFiles = allSvg(root);
const fontManifest = path.join(root, 'app', '_fonts', 'MANIFEST.json');
const scanTargets = [...cssFiles, ...svgFiles, ...(fs.existsSync(fontManifest) ? [fontManifest] : [])];

for (const f of scanTargets) {
  const text = fs.readFileSync(f, 'utf8');
  for (const re of LITERALS) {
    const m = text.match(re);
    if (m) {
      const i = text.indexOf(m[0]);
      violations.push(`${path.relative(root, f)}: banned literal ${JSON.stringify(m[0])} — …${text.slice(Math.max(0, i - 40), i + 40).replace(/\s+/g, ' ')}…`);
    }
  }
}

// ── 2. colour space, over built CSS ────────────────────────────────────────
// AMENDED 2026-08-09 on Vlad's ruling that the hated boards go warm: the flat
// 10-85° hue ban would outlaw the site's own sentiment colour. What trade
// dress actually protects is proximity to REDDIT'S orange, so the test is now
// perceptual distance: anything within dE_OKLab 0.14 of #FF4500 fails. The
// shipped warm tones sit at dE 0.189 (#F5A83C) and 0.214 (#8F5100) — inside
// the palette by a measured margin, and a drift toward #FF4500 still fails.
const COLOUR = /#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\([^)]+\)|oklch\([^)]+\)|hsl a?\([^)]+\)/g;

function toHex(literal) {
  const s = literal.trim();
  if (s.startsWith('#')) {
    const h = s.slice(1);
    return h.length === 3 ? `#${h[0]}${h[0]}${h[1]}${h[1]}${h[2]}${h[2]}` : s;
  }
  const rgb = s.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/);
  if (rgb) return rgbToHex([+rgb[1], +rgb[2], +rgb[3]].map((v) => Math.round(v)));
  return null; // oklch/hsl handled below
}

function oklchLiteral(s) {
  const m = s.match(/^oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)/);
  if (!m) return null;
  const L = m[1].endsWith('%') ? parseFloat(m[1]) / 100 : parseFloat(m[1]);
  return { L, C: parseFloat(m[2]), H: parseFloat(m[3]) };
}

for (const f of cssFiles) {
  const text = fs.readFileSync(f, 'utf8');
  for (const lit of text.match(COLOUR) ?? []) {
    let L, C, H;
    const direct = oklchLiteral(lit);
    if (direct) ({ L, C, H } = direct);
    else {
      const hex = toHex(lit);
      if (!hex) continue;
      [L, C, H] = hexToOklch(hex);
    }
    const rad = (H * Math.PI) / 180;
    const lab = [L, C * Math.cos(rad), C * Math.sin(rad)];
    const dE = Math.hypot(lab[0] - REDDIT_LAB[0], lab[1] - REDDIT_LAB[1], lab[2] - REDDIT_LAB[2]);
    // Two rings: anything genuinely close to #FF4500 fails whatever its hue;
    // inside the warm 10-85° band the required distance widens to 0.16, which
    // is what keeps a warm sentiment tone honest without outlawing the pinks
    // (hue ~2-8°) that were always legal.
    const warm = C >= 0.05 && H >= 10 && H <= 85;
    const min = warm ? 0.16 : 0.08;
    if (dE < min) {
      violations.push(
        `${path.relative(root, f)}: ${lit} is oklch(${L.toFixed(3)} ${C.toFixed(3)} ${H.toFixed(1)}) — ` +
        `dE ${dE.toFixed(3)} from Reddit's #FF4500 (minimum ${min}${warm ? ', warm band' : ''})`);
    }
  }
}

// ── 3. every @font-face points at our own self-hosted files ────────────────
for (const f of cssFiles) {
  const text = fs.readFileSync(f, 'utf8');
  for (const m of text.matchAll(/@font-face[^}]*src\s*:\s*([^;}]+)/g)) {
    for (const url of m[1].matchAll(/url\(([^)]+)\)/g)) {
      const u = url[1].replace(/["']/g, '');
      // Self-hosted means "served from our own build output". Turbopack emits
      // the path relative to the stylesheet (`../media/…`); both that and the
      // absolute form are ours. Anything with a scheme or a host is not.
      const selfHosted = u.startsWith('/_next/static/media/') || u.startsWith('../media/')
        || u.startsWith('./media/');
      if (!selfHosted) {
        violations.push(
          `${path.relative(root, f)}: @font-face src ${u} is not self-hosted. ` +
          `09-design.md bans a CDN or any fallback that could resolve near Reddit Sans.`);
      }
    }
  }
}

// ── 4. every SVG on disk carries a dated by-eye attestation ────────────────
// 09-design.md's pre-deploy check includes "every SVG in the asset directory has
// been checked by eye against Reddit's mark". A human step cannot be automated,
// but it CAN be made non-skippable: the allowlist records that it happened.
const allowlistPath = path.join(root, 'scripts', 'gates', 'svg-allowlist.json');
const allowlist = fs.existsSync(allowlistPath)
  ? JSON.parse(fs.readFileSync(allowlistPath, 'utf8'))
  : {};
for (const f of svgFiles) {
  const rel = path.relative(root, f);
  if (!allowlist[rel]) {
    violations.push(
      `${rel} has no entry in scripts/gates/svg-allowlist.json. ` +
      `Every SVG must be checked by eye against Reddit's mark and the check recorded.`);
  }
}

if (violations.length) {
  fail('trade dress', [
    `${violations.length} violation(s):`,
    ...violations,
    '',
    '09-design.md: Reddit orange, Snoo in any form, Reddit Sans or a lookalike, and any',
    'speech-bubble mark are banned outright. Trade dress stacked on top of the name turns a',
    'survivable dispute into an easy one (01-legal.md).',
  ]);
}

pass('trade dress',
  `${cssFiles.length} css + ${svgFiles.length} svg scanned for literals, colour space, fonts`);
