#!/usr/bin/env node
/**
 * Prove the bounded-reads gate can fail: copy the source, break one rule at a time, expect a non-zero exit.
 * A gate that has never been seen failing has been written, not tested.
 *
 * Run: node scripts/gates/bounded-reads.selftest.mjs     (no build needed)
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { ROOT } from './_util.mjs';

const GATE = path.join(ROOT, 'scripts', 'gates', 'bounded-reads.mjs');
const run = (dir) => spawnSync(process.execPath, [GATE], { env: { ...process.env, GATE_ROOT: dir }, encoding: 'utf8' });
const fresh = () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ri-bounded-'));
  for (const c of ['app', 'lib', 'components']) fs.cpSync(path.join(ROOT, c), path.join(tmp, c), { recursive: true });
  return tmp;
};
const edit = (dir, file, fn) => {
  const p = path.join(dir, file);
  fs.writeFileSync(p, fn(fs.readFileSync(p, 'utf8')));
};

const CASES = [
  ['a timed revalidate on a page', (d) => edit(d, 'app/page.tsx', (s) => s.replace('export const revalidate = false;', 'export const revalidate = 86400;'))],
  ['a page that is not force-static', (d) => edit(d, 'app/page.tsx', (s) => s.replace('export const dynamic = "force-static";', ''))],
  ['a second file opening a database connection', (d) => fs.writeFileSync(path.join(d, 'lib', 'data', 'sneaky.ts'), 'import postgres from "postgres";\nexport const q = postgres(process.env.DATABASE_URL_SITE!);\n')],
  ['a query against the corpus', (d) => edit(d, 'lib/data/site-db.ts', (s) => s.replace('from site.meta`', 'from published.mentions`'))],
  ['an unqualified relation', (d) => edit(d, 'lib/data/site-db.ts', (s) => s.replace('from site.meta`', 'from mentions`'))],
  ['the old corpus-reading connection string', (d) => edit(d, 'lib/data/site-db.ts', (s) => s.replaceAll('DATABASE_URL_SITE', 'DATABASE_URL_READONLY'))],
  ['a second cache', (d) => edit(d, 'app/page.tsx', (s) => s + '\nimport { unstable_cache } from "next/cache";\nexport const x = unstable_cache;\n')],
  ['a timer on a generated file that is not one of the three', (d) => fs.writeFileSync(path.join(d, 'app', 'robots.ts'), 'export const dynamic = "force-static";\nexport const revalidate = 3600;\nexport default function robots() { return { rules: [] }; }\n')],
  ['a named file refreshing faster than its floor', (d) => edit(d, 'app/llms.txt/route.ts', (s) => s.replace('export const revalidate = 3600;', 'export const revalidate = 60;'))],
  ['a named file with its timer removed', (d) => edit(d, 'app/freshness.json/route.ts', (s) => s.replace('export const revalidate = 300;', ''))],
  ['the publish endpoint reading data', (d) => edit(d, 'app/api/revalidate/route.ts', (s) => 'import { getMeta } from "@/lib/data/site-db";\n' + s)],
];

let bad = 0;
const clean = fresh();
const base = run(clean);
if (base.status !== 0) { console.error('the gate fails on the untouched tree:\n' + base.stderr); process.exit(1); }
fs.rmSync(clean, { recursive: true, force: true });

for (const [what, breakIt] of CASES) {
  const dir = fresh();
  breakIt(dir);
  const r = run(dir);
  const ok = r.status !== 0;
  console.log(`  ${ok ? 'ok  ' : 'MISS'} fails on ${what}`);
  if (!ok) bad++;
  fs.rmSync(dir, { recursive: true, force: true });
}
if (bad) { console.error(`\n${bad} violation(s) passed the gate`); process.exit(1); }
console.log(`  ok  bounded-reads gate: passes clean, fails on all ${CASES.length} violations`);
