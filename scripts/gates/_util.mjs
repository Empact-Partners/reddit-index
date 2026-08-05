import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

export function fail(gate, lines) {
  console.error(`\n\x1b[31mGATE FAILED — ${gate}\x1b[0m`);
  for (const l of [].concat(lines)) console.error(`  ${l}`);
  console.error('');
  process.exit(1);
}

export function pass(gate, note) {
  console.log(`  ok  ${gate}${note ? ` — ${note}` : ''}`);
}

/** Every file under `dir` whose basename matches `re`. */
export function walk(dir, re, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, re, acc);
    else if (re.test(e.name)) acc.push(p);
  }
  return acc;
}

export const builtCss = (root = ROOT) => walk(path.join(root, '.next', 'static'), /\.css$/);
export const builtHtml = (root = ROOT) => walk(path.join(root, '.next', 'server', 'app'), /\.html$/);
export const allSvg = (root = ROOT) => [
  ...walk(path.join(root, 'app'), /\.svg$/),
  ...walk(path.join(root, 'public'), /\.svg$/),
  ...walk(path.join(root, 'components'), /\.svg$/),
];

export function requireBuild(root = ROOT) {
  if (!fs.existsSync(path.join(root, '.next'))) {
    fail('build output', 'No .next directory. The post-build gates run after `next build`.');
  }
}
