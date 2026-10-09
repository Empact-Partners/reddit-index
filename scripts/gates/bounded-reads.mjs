#!/usr/bin/env node
/**
 * THE SITE CAN ONLY READ SMALL PRECOMPUTED ROWS, AND ONLY WHEN IT IS TOLD A PAGE CHANGED.
 *
 * From 5 August to 17 September 2026 every route here carried a timed `revalidate`, so pages regenerated on
 * requests, and each regeneration loaded the whole corpus: 3.80 billion rows to the site's database user,
 * 97% of the organisation's egress, 873 GB against a 250 GB allowance. It was found by the bill
 * (docs/investigation-2026-10.md). The first fix made the site fully static and added `static-only.mjs`.
 *
 * The site is no longer fully static: the daily sweep expires the pages whose data changed and they are
 * rendered again on the next request. That is safe only while a render cannot reach the corpus, so this
 * gate replaces "nothing renders at runtime" with "a render reads one company's precomputed rows":
 *
 *   SOURCE
 *     1. No numeric `revalidate` anywhere. A page changes when /api/revalidate names it, never on a timer.
 *        Three generated files are the exception, named below with the shortest interval each may carry
 *        (decision 0022): revalidatePath does not reach a route handler's built response, so an expiry left
 *        them as the last deploy wrote them. Each reads a few hundred kilobytes at most, at most once per
 *        interval, whatever the traffic: under 20 MB a day for all three, against the 3.80 billion rows.
 *     2. Every page and route handler declares `dynamic = "force-static"` (the publish endpoint excepted),
 *        and every page pins `revalidate = false`.
 *     3. ONE file opens a database connection: lib/data/site-db.ts. Nothing else imports the driver or
 *        reads a DATABASE_URL.
 *     4. Every relation that file names is in schema `site`. (The database enforces this too: the role it
 *        connects as has no grant outside `site`. This check fails the build before the deploy does.)
 *     5. No `unstable_cache` and no `revalidateTag`: a second cache that revalidatePath does not clear is
 *        how a page keeps serving a comment that was taken down.
 *     6. The publish endpoint reaches no data.
 *   OUTPUT (--built)
 *     7. Nothing in the prerender manifest carries a revalidate interval, except those three, at or above
 *        their floor.
 *
 * Run: node scripts/gates/bounded-reads.mjs            (source only, no build needed)
 *      node scripts/gates/bounded-reads.mjs --built    (source + the prerender manifest)
 */
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, fail, pass, walk } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
const checkBuilt = process.argv.includes('--built');
const problems = [];

const DB_MODULE = 'lib/data/site-db.ts';
const DYNAMIC_ALLOWED = new Set(['app/api/revalidate/route.ts']);
/** The only files that may carry a timer, the path each serves, and the shortest interval allowed (seconds). */
const TIMED = {
  'app/freshness.json/route.ts': { route: '/freshness.json', floor: 300 },  // one row of site.meta
  'app/llms.txt/route.ts': { route: '/llms.txt', floor: 3600 },             // the index rows, under 0.5 MB
  'app/sitemap.ts': { route: '/sitemap.xml', floor: 3600 },                 // the slug list
};
const TIMED_ROUTES = Object.fromEntries(Object.values(TIMED).map((t) => [t.route, t.floor]));

const rel = (p) => path.relative(root, p).split(path.sep).join('/');
// Comments are not code: a note about the old `revalidate = 86400` must not fail the gate that forbids it.
const stripComments = (src) => src
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/(^|[^:])\/\/.*$/gm, '$1');

// ---- 1, 2: routes -----------------------------------------------------------------------------
const ROUTE_FILE = /^(page|route|sitemap|robots|default|template)\.(tsx?|jsx?|mjs)$/;
const routeFiles = walk(path.join(root, 'app'), ROUTE_FILE);
if (routeFiles.length === 0) fail('bounded reads', 'found no routes under app/ — the gate cannot prove anything');

for (const file of routeFiles) {
  const name = rel(file);
  const src = stripComments(fs.readFileSync(file, 'utf8'));
  const numeric = src.match(/export\s+const\s+revalidate\s*=\s*([0-9][0-9_]*)/);
  const timed = TIMED[name];
  if (timed) {
    const n = numeric ? Number(numeric[1].replaceAll('_', '')) : null;
    if (n === null) problems.push(`${name}: carries no timer — an expiry does not reach a route handler, so without one it never changes between deploys`);
    else if (n < timed.floor) problems.push(`${name}: export const revalidate = ${n} — this file may refresh at most once every ${timed.floor} s`);
  } else if (numeric) {
    problems.push(`${name}: export const revalidate = ${numeric[1]} — a number here regenerates the page on a timer, which is what cost 3.80 billion rows`);
  }
  if (DYNAMIC_ALLOWED.has(name)) continue;
  if (!/export\s+const\s+dynamic\s*=\s*["']force-static["']/.test(src)) {
    problems.push(`${name}: no \`export const dynamic = "force-static"\``);
  }
  if (/^page\.tsx?$/.test(path.basename(file)) && !/export\s+const\s+revalidate\s*=\s*false/.test(src)) {
    problems.push(`${name}: no \`export const revalidate = false\``);
  }
  if (/export\s+const\s+dynamic\s*=\s*["']force-dynamic["']/.test(src)) {
    problems.push(`${name}: force-dynamic, and it is not the publish endpoint`);
  }
}

// ---- 3, 5: one database module, no second cache -------------------------------------------------
const CODE = /\.(tsx?|jsx?|mjs)$/;
const codeFiles = ['app', 'lib', 'components'].flatMap((d) => walk(path.join(root, d), CODE));
for (const file of codeFiles) {
  const name = rel(file);
  const src = stripComments(fs.readFileSync(file, 'utf8'));
  if (name !== DB_MODULE) {
    if (/(?:from|import)\s*\(?\s*["']postgres["']/.test(src) || /["']@supabase\//.test(src) || /from\s+["']pg["']/.test(src)) {
      problems.push(`${name}: imports a database driver — only ${DB_MODULE} may open a connection`);
    }
    if (/process\.env\.DATABASE_URL/.test(src) || /process\.env\[["']DATABASE_URL/.test(src)) {
      problems.push(`${name}: reads a DATABASE_URL — only ${DB_MODULE} may`);
    }
  }
  if (/\bunstable_cache\b/.test(src)) problems.push(`${name}: unstable_cache — a second cache that revalidatePath does not clear`);
  if (/\brevalidateTag\b/.test(src)) problems.push(`${name}: revalidateTag — pages carry no tags; the publish endpoint expires paths`);
}

// ---- 4: every relation the database module names is in schema `site` ------------------------------
const dbPath = path.join(root, DB_MODULE);
if (!fs.existsSync(dbPath)) {
  problems.push(`${DB_MODULE} does not exist — the gate cannot check what the site reads`);
} else {
  const src = stripComments(fs.readFileSync(dbPath, 'utf8'));
  // the SQL lives in tagged templates: db()`...`
  const queries = [...src.matchAll(/\)\s*`([\s\S]*?)`/g)].map((m) => m[1]);
  if (queries.length === 0) problems.push(`${DB_MODULE}: found no queries to check`);
  for (const q of queries) {
    for (const m of q.matchAll(/\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_.]*)/gi)) {
      const relName = m[1].toLowerCase();
      if (!relName.startsWith('site.')) {
        problems.push(`${DB_MODULE}: a query reads \`${m[1]}\` — every relation must be in schema \`site\``);
      }
    }
    if (/\b(public|published)\s*\./i.test(q)) {
      problems.push(`${DB_MODULE}: a query names schema public/published — the corpus is behind those`);
    }
  }
  if (!/process\.env\.DATABASE_URL_SITE\b/.test(src)) {
    problems.push(`${DB_MODULE}: does not connect through DATABASE_URL_SITE (the role that can only read \`site\`)`);
  }
  if (/DATABASE_URL_READONLY/.test(src)) {
    problems.push(`${DB_MODULE}: uses DATABASE_URL_READONLY — that role can read the corpus`);
  }
}

// ---- 6: the publish endpoint touches no data ----------------------------------------------------
for (const allowed of DYNAMIC_ALLOWED) {
  const f = path.join(root, allowed);
  if (!fs.existsSync(f)) continue;
  const src = stripComments(fs.readFileSync(f, 'utf8'));
  if (/site-db|lib\/data|lib\/routing/.test(src)) {
    problems.push(`${allowed}: it is allowed to be dynamic because it reads no data, and it imports the data layer`);
  }
}

// ---- 7: output ----------------------------------------------------------------------------------
if (checkBuilt) {
  const manifestPath = path.join(root, '.next', 'prerender-manifest.json');
  if (!fs.existsSync(manifestPath)) fail('bounded reads', 'no .next/prerender-manifest.json — run this after `next build`');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const routes = Object.entries(manifest.routes ?? {});
  if (routes.length === 0) fail('bounded reads', 'the build prerendered no routes at all');
  for (const [route, info] of routes) {
    const r = info.initialRevalidateSeconds;
    if (r === false || r === undefined) continue;
    if (route in TIMED_ROUTES && typeof r === 'number' && r >= TIMED_ROUTES[route]) continue;
    problems.push(`${route}: built with a revalidate interval of ${r}`);
  }
  for (const [route, floor] of Object.entries(TIMED_ROUTES)) {
    const r = manifest.routes?.[route]?.initialRevalidateSeconds;
    if (!(typeof r === 'number' && r >= floor)) {
      problems.push(`${route}: built without its timer (${JSON.stringify(r)}) — it would never change between deploys`);
    }
  }
  for (const [route, info] of Object.entries(manifest.dynamicRoutes ?? {})) {
    if (route.startsWith('/api/')) continue;
    const r = info.fallbackRevalidate ?? info.initialRevalidateSeconds;
    if (!(r === false || r === undefined || r === null)) {
      problems.push(`${route}: pages rendered on request carry a revalidate interval of ${JSON.stringify(r)}`);
    }
  }
  if (!problems.length) pass('bounded reads (output)', `${routes.length} prerendered routes, none on a timer but the three named files`);
}

if (problems.length) {
  fail('bounded reads', [
    ...problems,
    '',
    'A page render may read one company\'s precomputed rows from schema `site` and nothing else, and a',
    'page changes only when the daily sweep names it. See lib/data/site-db.ts, supabase/migrations/0007',
    'and docs/investigation-2026-10.md.',
  ]);
}
pass('bounded reads (source)', `${routeFiles.length} routes, one database module, every relation in \`site\``);
