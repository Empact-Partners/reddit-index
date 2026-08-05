#!/usr/bin/env node
/**
 * SLUG UNIQUENESS, checked against the ACTUAL prerender manifest.
 *
 * The registry already throws during the build if two slugs collide, which
 * fails `next build`. This gate is the second, independent check, and it looks
 * at output rather than intent: what did the build actually emit?
 *
 * decisions/0007 also bans two URL shapes outright — `/category/{slug}` and
 * `/brand/{slug}`. `typedRoutes` makes writing one a compile error; this proves
 * none was emitted anyway.
 */
import fs from 'node:fs';
import path from 'node:path';
import { BANNED_PATH_PREFIXES } from '../../lib/routing/registry.mjs';
import { ROOT, fail, pass, requireBuild } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
requireBuild(root);

const manifestPath = path.join(root, '.next', 'prerender-manifest.json');
if (!fs.existsSync(manifestPath)) fail('slug uniqueness', 'no .next/prerender-manifest.json');

const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const routes = Object.keys(manifest.routes ?? {});
if (routes.length === 0) fail('slug uniqueness', 'the build prerendered no routes at all');

const problems = [];

// 1. Nothing under a banned prefix.
for (const r of routes) {
  for (const p of BANNED_PATH_PREFIXES) {
    if (r.startsWith(p)) problems.push(`${r} uses the banned ${p} shape (decisions/0007)`);
  }
}

// 2. Every content route is exactly one segment deep.
const KNOWN_FILE_ROUTES = new Set(['/', '/robots.txt', '/sitemap.xml', '/favicon.ico']);
for (const r of routes) {
  if (KNOWN_FILE_ROUTES.has(r)) continue;
  const segments = r.split('/').filter(Boolean);
  if (segments.length !== 1) {
    problems.push(`${r} is ${segments.length} segments deep; the flat namespace is one`);
  }
}

// 3. No two routes fold onto the same path under case, NFC or trailing-slash
//    normalisation. A published slug is frozen, so a near-collision is permanent.
const folded = new Map();
for (const r of routes) {
  const key = r.replace(/\/$/, '').toLowerCase().normalize('NFC') || '/';
  const prev = folded.get(key);
  if (prev && prev !== r) problems.push(`${prev} and ${r} normalise to the same path`);
  folded.set(key, r);
}

if (problems.length) fail('slug uniqueness', [`${problems.length} problem(s):`, ...problems]);
pass('slug uniqueness', `${routes.length} prerendered routes, all one segment, no banned shapes`);
