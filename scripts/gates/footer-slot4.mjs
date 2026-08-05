#!/usr/bin/env node
/**
 * FOOTER SLOT 4, on every rendered route, as text.
 *
 * "A page that renders without slot 4 is a bug of the same severity as a page
 * rendering the wrong score."
 *
 * The gate checks the built HTML, not the source, because the failure mode is
 * a page that stopped rendering the footer — not a component that stopped
 * containing it. And it asserts that the set of files it scanned EQUALS the
 * prerendered-route set, so a route that quietly stopped prerendering cannot
 * skip the check by simply not being there.
 *
 * app/error.tsx and app/global-error.tsx never prerender, so this gate is
 * structurally blind to them. tests/footer.test.tsx covers those two, and
 * global-error.tsx is the dangerous one: it replaces the root layout entirely.
 */
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, builtHtml, fail, pass, requireBuild } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
requireBuild(root);

const NON_AFFILIATION =
  "Not affiliated with, endorsed by, or sponsored by Reddit, Inc. 'Reddit' is a trademark of Reddit, Inc., used here descriptively.";

// HTML-escaped forms the renderer may emit for the apostrophes.
const VARIANTS = [
  NON_AFFILIATION,
  NON_AFFILIATION.replace(/'/g, '&#x27;'),
  NON_AFFILIATION.replace(/'/g, '&#39;'),
  NON_AFFILIATION.replace(/'/g, '&apos;'),
];

// Next emits its own last-resort 500 shell at `_global-error.html`, marked
// `id="__next_error__"`. It is the framework's static fallback for the case
// where the React root itself fails to render, is not a route anyone navigates
// to, and cannot be given our footer without patching Next. Our own
// app/global-error.tsx — which IS what renders when a runtime error escapes the
// root layout — does carry slot 4, and tests/footer.test.tsx asserts it,
// because this gate walks prerendered HTML and is structurally blind to every
// error boundary.
const FRAMEWORK_SHELLS = new Set(['_global-error.html']);

const files = builtHtml(root).filter((f) => !FRAMEWORK_SHELLS.has(path.basename(f)));
if (files.length === 0) {
  fail('footer slot 4', 'no prerendered HTML found under .next/server/app');
}

const missing = [];
const hidden = [];

for (const f of files) {
  const html = fs.readFileSync(f, 'utf8');
  // Strip scripts and styles first: the string appearing inside a flight payload
  // or a stylesheet is not the string appearing on the page.
  const visible = html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '');

  const idx = VARIANTS.map((v) => visible.indexOf(v)).find((i) => i >= 0);
  if (idx === undefined) {
    missing.push(path.relative(root, f));
    continue;
  }

  // Not inside an attribute value.
  const before = visible.slice(0, idx);
  const lastTagOpen = before.lastIndexOf('<');
  const lastTagClose = before.lastIndexOf('>');
  if (lastTagOpen > lastTagClose) {
    hidden.push(`${path.relative(root, f)}: the notice sits inside a tag attribute, not in text`);
  }

  // Not inside <details>, and not under aria-hidden. Both are cheap string
  // checks on the enclosing markup, and both are explicitly banned.
  const enclosing = visible.slice(Math.max(0, idx - 2000), idx);
  const openDetails = (enclosing.match(/<details\b/gi) ?? []).length;
  const closeDetails = (enclosing.match(/<\/details>/gi) ?? []).length;
  if (openDetails > closeDetails) {
    hidden.push(`${path.relative(root, f)}: the notice is inside a <details> disclosure`);
  }
  if (/aria-hidden=["']true["'][^>]*>[^<]*$/.test(enclosing.slice(-300))) {
    hidden.push(`${path.relative(root, f)}: the notice is inside an aria-hidden element`);
  }
}

// The manifest cross-check: every prerendered route must have been scanned.
const manifestPath = path.join(root, '.next', 'prerender-manifest.json');
if (fs.existsSync(manifestPath)) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const routes = Object.keys(manifest.routes ?? {});
  const scanned = new Set(files.map((f) =>
    '/' + path.relative(path.join(root, '.next', 'server', 'app'), f).replace(/\.html$/, '')));
  // Route handlers (robots.txt, sitemap.xml, the revalidate endpoint) emit no
  // HTML page and carry no footer. Everything a reader can LAND on must.
  const NON_PAGE = /\.(txt|xml|json|ico|png|svg|webmanifest)$/;
  const unscanned = routes.filter((r) => {
    if (NON_PAGE.test(r)) return false;
    if (FRAMEWORK_SHELLS.has(path.basename(r) + '.html')) return false;
    const norm = r === '/' ? '/index' : r.replace(/\/$/, '');
    return !scanned.has(norm) && !scanned.has(norm + '/index') && !scanned.has(r);
  });
  if (unscanned.length) {
    fail('footer slot 4', [
      `${unscanned.length} prerendered route(s) produced no HTML file to check:`,
      ...unscanned,
      'A route that stops prerendering must not thereby skip the footer check.',
    ]);
  }
}

if (missing.length || hidden.length) {
  fail('footer slot 4', [
    ...(missing.length ? [`${missing.length} route(s) render WITHOUT the non-affiliation notice:`, ...missing] : []),
    ...(hidden.length ? ['', 'present but not as visible text:', ...hidden] : []),
    '',
    'The notice ships verbatim, at Small size, at full opacity, as real text in the DOM,',
    'on every route including 404 and the error boundaries.',
  ]);
}

pass('footer slot 4', `present as text on all ${files.length} prerendered routes`);
