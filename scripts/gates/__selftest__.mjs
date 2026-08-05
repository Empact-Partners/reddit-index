#!/usr/bin/env node
/**
 * "Prove it by breaking one and watching it fail, then revert."
 *
 * A gate that has never been observed failing has not been tested — it has been
 * written. This copies the repo and the build output into a temp directory,
 * injects one violation per gate, and asserts each one exits non-zero. Nothing
 * in the working tree is touched, so there is no break-and-revert step to
 * forget halfway through.
 *
 * Run: node scripts/gates/__selftest__.mjs   (after a build)
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { ROOT, requireBuild } from './_util.mjs';

requireBuild();

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ri-gates-'));
const COPY = ['data', 'lib', 'app', 'components', 'scripts', 'package.json'];

for (const c of COPY) {
  fs.cpSync(path.join(ROOT, c), path.join(tmp, c), { recursive: true });
}
// Only the build artefacts the gates read.
for (const sub of [
  path.join('.next', 'static'),
  path.join('.next', 'server', 'app'),
]) {
  fs.cpSync(path.join(ROOT, sub), path.join(tmp, sub), { recursive: true });
}
fs.copyFileSync(
  path.join(ROOT, '.next', 'prerender-manifest.json'),
  path.join(tmp, '.next', 'prerender-manifest.json'));

const firstCss = () => {
  const dir = path.join(tmp, '.next', 'static');
  const found = [];
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (p.endsWith('.css')) found.push(p);
    }
  })(dir);
  return found[0];
};

const anyHtml = () =>
  path.join(tmp, '.next', 'server', 'app', 'crm.html');

/** gate, what we break, how */
const CASES = [
  ['category-constraints', 'a hand-edited hex', () => {
    const p = path.join(tmp, 'data', 'categories.csv');
    fs.writeFileSync(p, fs.readFileSync(p, 'utf8').replace('#F8AAC1', '#FF6600'));
  }],
  ['icons', 'an icon name that does not exist', () => {
    const p = path.join(tmp, 'data', 'categories.csv');
    fs.writeFileSync(p, fs.readFileSync(p, 'utf8').replace('contact-round', 'not-an-icon'));
  }],
  ['contrast', 'a token that can no longer carry text', () => {
    const p = path.join(tmp, 'app', 'globals.css');
    fs.writeFileSync(p, fs.readFileSync(p, 'utf8').replace('--green-deep:  #267856', '--green-deep:  #9FE7C4'));
  }],
  ['fonts', 'a substituted font file', () => {
    fs.writeFileSync(path.join(tmp, 'app', '_fonts', 'Syne-Medium.woff2'), 'not a font');
  }],
  ['trade-dress', 'Reddit orange written as an oklch literal', () => {
    const p = firstCss();
    fs.appendFileSync(p, '\n.x{color:oklch(0.660 0.229 35.4)}\n');
  }],
  ['css-rules', 'a fade-out mask over the quoted text', () => {
    const p = firstCss();
    fs.appendFileSync(p, '\n.mention-body{mask-image:linear-gradient(#000,transparent)}\n');
  }],
  ['footer-slot4', 'a page that stopped rendering the notice', () => {
    const p = anyHtml();
    const html = fs.readFileSync(p, 'utf8');
    fs.writeFileSync(p, html.replace(/Not affiliated with[^<]*/, 'Nothing to see here'));
  }],
  ['slugs', 'a banned /brand/ route shape', () => {
    const p = path.join(tmp, '.next', 'prerender-manifest.json');
    const m = JSON.parse(fs.readFileSync(p, 'utf8'));
    m.routes['/brand/hubspot'] = m.routes['/crm'] ?? {};
    fs.writeFileSync(p, JSON.stringify(m));
  }],
];

let failures = 0;
console.log(`gate self-test — ${CASES.length} gates, one injected violation each\n`);

for (const [gate, what, breakIt] of CASES) {
  // Fresh copy of the two things a case might mutate.
  const snapshot = new Map();
  for (const rel of ['data/categories.csv', 'app/globals.css', '.next/prerender-manifest.json',
                     'app/_fonts/Syne-Medium.woff2']) {
    const p = path.join(tmp, rel);
    if (fs.existsSync(p)) snapshot.set(p, fs.readFileSync(p));
  }
  const css = firstCss();
  const cssBefore = fs.readFileSync(css);
  const html = anyHtml();
  const htmlBefore = fs.existsSync(html) ? fs.readFileSync(html) : null;

  breakIt();

  const r = spawnSync(process.execPath, [path.join(ROOT, 'scripts', 'gates', `${gate}.mjs`)], {
    encoding: 'utf8',
    env: { ...process.env, GATE_ROOT: tmp },
  });

  if (r.status === 0) {
    console.log(`  \x1b[31mFAIL\x1b[0m  ${gate.padEnd(22)} did NOT fail on ${what}`);
    failures++;
  } else {
    const why = (r.stderr || r.stdout || '').split('\n').find((l) => l.trim().startsWith('  ')) ?? '';
    console.log(`  ok    ${gate.padEnd(22)} caught ${what}\n        ${why.trim().slice(0, 96)}`);
  }

  // restore
  for (const [p, buf] of snapshot) fs.writeFileSync(p, buf);
  fs.writeFileSync(css, cssBefore);
  if (htmlBefore) fs.writeFileSync(html, htmlBefore);
}

fs.rmSync(tmp, { recursive: true, force: true });

if (failures) {
  console.error(`\n\x1b[31m${failures} gate(s) did not fail when violated.\x1b[0m ` +
    `An unenforced rule drifts.\n`);
  process.exit(1);
}
console.log(`\nall ${CASES.length} gates fail when violated\n`);
