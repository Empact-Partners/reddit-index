/**
 * Regression tests for the documented false matches.
 *
 * 05-entity-resolution.md §3 records what a naive substring pass produced:
 * "Monday" the weekday in r/nfl and r/rugbyunion, "SAP" the fluid in
 * r/worldbuilding, "Rippling" the water, "Sage" the herb. Those are the exact
 * cases that must never come back, so they are pinned here rather than
 * described in a comment.
 *
 * Run: node --test tests/resolve.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WORKER = path.join(ROOT, 'worker');

// One Python process per run, not per case: the automaton build reads 359
// surface forms and rebuilding it eight times is the slow part.
function resolveMany(cases) {
  const out = execFileSync('python3', ['-c', `
import json, sys
sys.path.insert(0, ${JSON.stringify(WORKER)})
from resolve import Resolver
r = Resolver()
cases = json.loads(sys.stdin.read())
print("@@" + json.dumps([
    sorted(h["brand_slug"] for h in r.resolve(c["text"], c.get("sub"), c.get("title")))
    for c in cases]))
`], { input: JSON.stringify(cases), encoding: 'utf8' });
  return JSON.parse(out.split('@@').pop().trim());
}

const CASES = [
  { text: 'We play the Giants on Monday night', sub: 'nfl', title: 'Game thread' },
  { text: 'Standup is every Monday morning', sub: 'sales', title: 'Process' },
  { text: 'The trees bleed a thick sap in this region', sub: 'worldbuilding', title: 'Flora' },
  { text: 'a navy pinstripe suit', sub: 'malefashionadvice', title: 'Suits' },
  { text: 'we take payments through stripe.com', sub: 'smallbusiness', title: 'Payment processor?' },
  { text: 'we close deals faster now', sub: 'sales', title: 'Pipeline' },
  { text: 'we moved our pipeline to Close CRM last quarter', sub: 'sales', title: 'CRM' },
  { text: 'Pipedrive has been solid for us', sub: 'sales', title: 'CRM' },
  { text: 'HubSpot is atrocious at scale', sub: 'sales', title: 'CRM' },
  { text: '> Pipedrive has been solid\n\nDisagree.', sub: 'sales', title: 'CRM' },
  { text: '```\nPIPEDRIVE_API_KEY=abc\n```', sub: 'sales', title: 'CRM' },
  { text: 'I switched from HubSpot to Pipedrive last month', sub: 'sales', title: 'CRM' },
];
const R = resolveMany(CASES);

test('the weekday is not a CRM', () => {
  assert.deepEqual(R[0], [], 'r/nfl Monday');
  assert.deepEqual(R[1], [], 'Monday morning standup');
});

test('the fluid is not the ERP', () => {
  assert.deepEqual(R[2], []);
});

test('a word boundary is not a substring', () => {
  // `stripe` inside `pinstripe` — the canonical example.
  assert.deepEqual(R[3], []);
  assert.ok(R[4].includes('stripe'), 'stripe.com should resolve');
});

test('a bare token no stop-context list can rescue never matches', () => {
  assert.deepEqual(R[5], [], '"close deals" is a verb phrase');
  assert.ok(R[6].includes('close'), 'Close CRM is qualified and unambiguous');
});

test('an unambiguous brand matches on a word boundary alone', () => {
  assert.ok(R[7].includes('pipedrive'));
  assert.ok(R[8].includes('hubspot'));
});

test('quoted text belongs to the person quoted, not the commenter', () => {
  assert.deepEqual(R[9], []);
});

test('a code fence is configuration, not an opinion', () => {
  assert.deepEqual(R[10], []);
});

test('one surface form resolves to one brand, never two', () => {
  // "HubSpot" is the canonical name of one brand and an alias of another.
  // Accepting both would count the company twice in every figure downstream.
  assert.deepEqual(R[11], ['hubspot', 'pipedrive']);
});
