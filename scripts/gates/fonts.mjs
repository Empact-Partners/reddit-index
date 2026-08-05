#!/usr/bin/env node
/** Thin wrapper: the font manifest check, as a named gate in the ladder. */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { ROOT, fail, pass } from './_util.mjs';

const root = process.env.GATE_ROOT || ROOT;
const r = spawnSync(process.execPath,
  [path.join(ROOT, 'scripts', 'fetch-fonts.mjs'), '--check'],
  { encoding: 'utf8', env: { ...process.env, GATE_ROOT: root } });
if (r.status !== 0) fail('fonts', (r.stdout + r.stderr).trim().split('\n'));
pass('fonts', (r.stdout || '').trim());
