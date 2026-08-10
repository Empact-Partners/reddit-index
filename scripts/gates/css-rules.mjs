#!/usr/bin/env node
/**
 * The design law nobody wrote down as a gate, checked against the BUILT CSS.
 *
 * These are not stylistic preferences. Each one is a rule some document states
 * as a requirement, and each one is the kind of rule that regresses silently
 * because a component library shipped a sensible default:
 *
 *   · no ellipsis / line-clamp / mask anywhere — the mention body is quoted in
 *     full, and "no read more, no fade-out mask" is the whole point
 *   · no box-shadow, no linear-gradient fills — "no gradients, no shadows,
 *     hard edges" is inherited from the Empact guide unchanged
 *   · --cat appears only under the five selectors allowed to carry category
 *     colour, which is what makes "category colour never touches a score
 *     surface" mechanically checkable
 *   · pill radius only on sentiment and score chips — the 6px square is what
 *     separates a category tile from a verdict
 *   · never `outline: none`
 *   · every transition <= 150ms, and a prefers-reduced-motion block exists
 */
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, builtCss, walk, fail, pass, requireBuild } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
requireBuild(root);

const files = builtCss(root);
if (files.length === 0) fail('css law', 'no built CSS found under .next/static');

const problems = [];
let sawReducedMotion = false;

const CAT_ALLOWED = ['.cat-tile', '.cat-chip', '.cat-header-rule', '.breadcrumb-cat', '.cat-card-rule', '.brand-mark'];

for (const f of files) {
  const css = fs.readFileSync(f, 'utf8');
  const rel = path.relative(root, f);

  if (/prefers-reduced-motion/.test(css)) sawReducedMotion = true;

  for (const [re, why] of [
    [/text-overflow\s*:\s*ellipsis/gi, 'text-overflow: ellipsis — nothing on this site truncates'],
    [/-webkit-line-clamp\s*:\s*(?!none)/gi, '-webkit-line-clamp — the mention body is never clamped'],
    [/(?<!-)mask-image\s*:\s*(?!none)/gi, 'mask-image — no fade-out mask over quoted text'],
    [/(?<!repeating-)linear-gradient/gi, 'linear-gradient fill — only the repeating hatch pattern is allowed'],
    [/outline\s*:\s*(none|0)\b/gi, 'outline: none — focus is never removed'],
  ]) {
    for (const m of css.matchAll(re)) {
      const i = m.index ?? 0;
      problems.push(`${rel}: ${why}\n      …${css.slice(Math.max(0, i - 60), i + 60).replace(/\s+/g, ' ')}…`);
    }
  }

  // box-shadow: the framework reset (`none`) and Tailwind's var-only composition
  // are inert. What is banned is an AUTHORED shadow with a real value.
  for (const m of css.matchAll(/box-shadow\s*:\s*([^;}]+)/gi)) {
    const value = m[1].trim();
    if (/^none$/i.test(value)) continue;
    if (/^(var\(--tw-[a-z-]+\)[,\s]*)+$/i.test(value)) continue;
    problems.push(`${rel}: authored box-shadow "${value.slice(0, 60)}" — the guide is hard edges, no shadows`);
  }

  // radial-gradient is legal only for the dotted pattern module.
  for (const m of css.matchAll(/radial-gradient/gi)) {
    const i = m.index ?? 0;
    const context = css.slice(Math.max(0, i - 200), i);
    if (!/\.pattern-dotted/.test(context)) {
      problems.push(`${rel}: radial-gradient outside .pattern-dotted`);
    }
  }

  // --cat may be READ only under the allowed selectors. The generated
  // [data-category="…"] rules DEFINE it, which is a different thing.
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*var\(--cat\)[^{}]*)\}/g)) {
    const selector = m[1].trim();
    if (!CAT_ALLOWED.some((s) => selector.includes(s))) {
      problems.push(
        `${rel}: category colour used outside its allowlist — selector "${selector.slice(0, 90)}"\n` +
        `      allowed: ${CAT_ALLOWED.join(', ')}. Category colour never touches a score surface.`);
    }
  }

  // Pill radius only on sentiment/score chips.
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*border-radius\s*:\s*(?:999px|9999px|calc\(infinity[^;]*|50%)[^{}]*)\}/g)) {
    const selector = m[1].trim();
    const ok = /score-chip|sentiment-chip|--radius-chip|:root|\.cat-chip::before/.test(selector) ||
      /--radius-chip/.test(m[2]);
    if (!ok) {
      problems.push(`${rel}: pill radius on "${selector.slice(0, 90)}" — pills are sentiment surfaces only`);
    }
  }

  for (const m of css.matchAll(/transition(?:-duration)?\s*:[^;{}]*?(\d*\.?\d+)(m?s)\b/g)) {
    const ms = m[2] === 's' ? parseFloat(m[1]) * 1000 : parseFloat(m[1]);
    if (ms > 150.5) {
      problems.push(`${rel}: transition ${m[1]}${m[2]} exceeds the 150ms ceiling`);
    }
  }
}

if (!sawReducedMotion) {
  problems.push('no prefers-reduced-motion block in any built stylesheet');
}

// Source-level grep for utilities that survive the theme wipe.
for (const f of [...walk(path.join(root, 'app'), /\.(tsx|css)$/),
                 ...walk(path.join(root, 'components'), /\.tsx$/)]) {
  const src = fs.readFileSync(f, 'utf8');
  for (const [re, why] of [
    [/\brounded-full\b/g, 'rounded-full is a static utility that survives --radius-*: initial'],
    [/\bshadow-(sm|md|lg|xl|2xl)\b/g, 'a shadow utility'],
    [/\bbg-(gradient|linear)-/g, 'a gradient utility'],
  ]) {
    if (re.test(src)) problems.push(`${path.relative(root, f)}: ${why}`);
  }
}

if (problems.length) fail('css law', [`${problems.length} violation(s):`, ...problems]);
pass('css law', `${files.length} stylesheet(s) checked`);
