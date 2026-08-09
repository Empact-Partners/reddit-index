#!/usr/bin/env node
/**
 * Put Syne Medium and Public Sans Regular/SemiBold into `app/_fonts/`.
 *
 * 09-design.md bans Reddit Sans "with any lookalike… no substitution, no
 * fallback stack that can land near it", and 16-design-system.md requires the
 * faces self-hosted via next/font/local — "never a CDN or a system fallback".
 * So the files are committed, and this script is how they got there: copied out
 * of the Fontsource packages (both fonts are OFL) and hashed, so a silent
 * substitution is detectable.
 *
 *   node scripts/fetch-fonts.mjs            copy + write the manifest
 *   node scripts/fetch-fonts.mjs --check    recompute hashes, fail on drift
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
// GATE_ROOT lets scripts/gates/__selftest__.mjs point the check at a sandboxed
// copy. Without it the gate would silently verify the real files while the
// self-test broke a copy — which is how a gate passes a test it is not running.
const ROOT = process.env.GATE_ROOT
  || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEST = path.join(ROOT, 'app', '_fonts');
const MANIFEST = path.join(DEST, 'MANIFEST.json');
const CHECK = process.argv.includes('--check');

// Syne ships 400-800; Medium is weight 500. `latin` subset only — next/font/local
// carries no unicodeRange, so it is one file per weight and non-latin glyphs in
// Reddit mention text fall through to the fallback stack, which is correct.
const WANT = [
  { pkg: '@fontsource/syne', file: 'syne-latin-500-normal.woff2', out: 'Syne-Medium.woff2', family: 'Syne' },
  { pkg: '@fontsource/syne', file: 'syne-latin-700-normal.woff2', out: 'Syne-Bold.woff2', family: 'Syne' },
  { pkg: '@fontsource/public-sans', file: 'public-sans-latin-400-normal.woff2', out: 'PublicSans-Regular.woff2', family: 'PublicSans' },
  { pkg: '@fontsource/public-sans', file: 'public-sans-latin-600-normal.woff2', out: 'PublicSans-SemiBold.woff2', family: 'PublicSans' },
];

const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');

function pkgDir(pkg) {
  return path.dirname(require.resolve(`${pkg}/package.json`));
}

if (CHECK) {
  if (!fs.existsSync(MANIFEST)) {
    console.error('FAIL: app/_fonts/MANIFEST.json is missing. Run `node scripts/fetch-fonts.mjs`.');
    process.exit(1);
  }
  const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
  let bad = 0;
  for (const entry of manifest.files) {
    const p = path.join(DEST, entry.file);
    if (!fs.existsSync(p)) {
      console.error(`FAIL: ${entry.file} is missing`);
      bad++;
      continue;
    }
    const got = sha256(fs.readFileSync(p));
    if (got !== entry.sha256) {
      console.error(`FAIL: ${entry.file} hash drift\n  manifest ${entry.sha256}\n  on disk  ${got}`);
      bad++;
    }
  }
  if (bad) {
    console.error(`\n${bad} font file(s) do not match the manifest. A substituted face is a trade-dress risk (09-design.md), not a cosmetic one.`);
    process.exit(1);
  }
  console.log(`fonts OK — ${manifest.files.length} files match MANIFEST.json`);
  process.exit(0);
}

fs.mkdirSync(DEST, { recursive: true });
const files = [];
for (const w of WANT) {
  const dir = pkgDir(w.pkg);
  const version = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8')).version;
  const src = path.join(dir, 'files', w.file);
  if (!fs.existsSync(src)) {
    // Fontsource has renamed files between majors. A missing file is a hard
    // failure, never a silent "pick something close".
    const avail = fs.readdirSync(path.join(dir, 'files')).filter((f) => f.endsWith('.woff2')).slice(0, 12);
    throw new Error(`${w.pkg} has no ${w.file}. Available (first 12): ${avail.join(', ')}`);
  }
  const buf = fs.readFileSync(src);
  fs.writeFileSync(path.join(DEST, w.out), buf);
  files.push({ file: w.out, sha256: sha256(buf), sourcePkg: w.pkg, sourceVersion: version, sourceFile: w.file, subset: 'latin' });
  console.log(`  ${w.out.padEnd(28)} ${(buf.length / 1024).toFixed(1)} KB  from ${w.pkg}@${version}`);

  const lic = ['LICENSE', 'LICENSE.md', 'LICENSE.txt'].map((f) => path.join(dir, f)).find(fs.existsSync);
  if (lic) fs.copyFileSync(lic, path.join(DEST, `${w.family}-OFL.txt`));
}

fs.writeFileSync(MANIFEST, JSON.stringify({ generatedBy: 'scripts/fetch-fonts.mjs', files }, null, 2) + '\n');
console.log(`wrote ${path.relative(ROOT, MANIFEST)}`);
