#!/usr/bin/env node
/**
 * Every icon named in categories.csv resolves in the PINNED lucide version.
 *
 * The generated static imports already make a bad name a TypeScript error. This
 * gate catches the one case they do not: a version bump that renames an icon,
 * which would otherwise ship a blank tile nobody notices.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { ROOT, fail, pass } from './_util.mjs';

const require = createRequire(import.meta.url);
const root = process.env.GATE_ROOT || ROOT;
const PINNED = '1.28.0';

const version = JSON.parse(fs.readFileSync(
  path.join(ROOT, 'node_modules', 'lucide-react', 'package.json'), 'utf8')).version;
if (version !== PINNED) {
  fail('icon names', [
    `lucide-react is ${version}; 16-design-system.md §1 pins ${PINNED}.`,
    'The icon set is pinned because a minor bump can rename an icon and silently break a tile.',
  ]);
}

const lucide = require('lucide-react');
const csv = fs.readFileSync(path.join(root, 'data', 'categories.csv'), 'utf8').trim().split('\n');
const header = csv[0].split(',');
const iconIdx = header.indexOf('icon');
const slugIdx = header.indexOf('slug');
const pascal = (k) => k.split('-').map((p) => p[0].toUpperCase() + p.slice(1)).join('');

const missing = [];
for (const line of csv.slice(1)) {
  const cells = line.split(',');
  const name = pascal(cells[iconIdx]);
  if (!(name in lucide)) missing.push(`${cells[slugIdx]} -> ${cells[iconIdx]} (${name})`);
}
if (missing.length) fail('icon names', [`unresolved in lucide-react@${version}:`, ...missing]);

pass('icon names', `${csv.length - 1} icons resolve in lucide-react@${version}`);
