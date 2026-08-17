/**
 * Regression tests for the two defects that stopped the index from collecting
 * and from ever reading a post title.
 *
 *  1. `ingest_state.watermark` is a TEXT column. daily.py read it back with
 *     `float(...)`, which raised ValueError on EVERY subreddit — a cron that
 *     ran, exited 0, and collected nothing for two days. The first run reads
 *     None and works, so only a SECOND run reproduces it: pinned here.
 *  2. The post document was built from selftext alone, so a brand named in the
 *     title resolved to nothing and a link post produced no document at all.
 *
 * Run: node --test tests/collect.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WORKER = path.join(ROOT, 'worker');

/** Run a python snippet inside worker/ and parse its single JSON line. */
function py(code) {
  const out = execFileSync('python3', ['-c', code], {
    cwd: WORKER,
    encoding: 'utf8',
    env: { ...process.env, PYTHONPATH: WORKER },
  });
  return JSON.parse(out.trim().split('\n').pop());
}

test('as_epoch parses the TEXT watermark Postgres actually returns', () => {
  const r = py(`
import json, datetime, importlib
daily = importlib.import_module("daily")
pg = "2026-08-15 10:02:29+00"          # exactly what psycopg reads back
iso = "2026-08-15T10:02:29+00:00"
dt = datetime.datetime(2026, 8, 15, 10, 2, 29, tzinfo=datetime.timezone.utc)
print(json.dumps({
  "pg": daily.as_epoch(pg),
  "iso": daily.as_epoch(iso),
  "dt": daily.as_epoch(dt),
  "epoch": daily.as_epoch("1786788149.0"),
  "none": daily.as_epoch(None),
  "empty": daily.as_epoch(""),
  "junk": daily.as_epoch("not a time"),
}))`);
  assert.equal(r.pg, 1786788149);
  assert.equal(r.iso, r.pg, 'ISO and Postgres renderings must agree');
  assert.equal(r.dt, r.pg, 'a datetime must agree with its text form');
  assert.equal(r.epoch, 1786788149, 'a legacy bare epoch still parses');
  assert.equal(r.none, null);
  assert.equal(r.empty, null);
  assert.equal(r.junk, null, 'unparseable is absent, never an exception');
});

test('the post document carries the TITLE, and a link post is still a document', () => {
  const r = py(`
import json
from harvest import post_doc
link = post_doc({"id": "abc123", "author": "someone", "title": "Anyone moved off HubSpot?",
                 "selftext": "", "created_utc": 1786788149, "permalink": "/r/sales/comments/abc123/x/"})
self_ = post_doc({"id": "t3_def456", "author": "someone", "title": "HubSpot vs Salesforce",
                  "selftext": "We run 40 seats.", "created_utc": 1, "permalink": "/r/crm/comments/def456/y/"})
print(json.dumps({
  "link_body": link and link["body"],
  "link_id": link and link["id"],
  "link_type": link and link["doc_type"],
  "link_permalink": link and link["permalink"],
  "self_body": self_ and self_["body"],
  "self_id": self_ and self_["id"],
  "deleted": post_doc({"id": "x", "author": "[deleted]", "title": "t", "selftext": "s"}),
  "removed_self": post_doc({"id": "y", "author": "u", "title": "Zoom is down",
                            "selftext": "[removed]"})["body"],
  "empty": post_doc({"id": "z", "author": "u", "title": "", "selftext": ""}),
  "bot": post_doc({"id": "w", "author": "AutoModerator", "title": "Weekly thread",
                   "selftext": "I am a bot"}),
}))`);
  assert.equal(r.link_body, 'Anyone moved off HubSpot?',
    'a link post with no selftext is its title');
  assert.equal(r.link_id, 't3_abc123', 'doc_id is the t3_ fullname');
  assert.equal(r.link_type, 2);
  assert.match(r.link_permalink, /^https:\/\/www\.reddit\.com\/r\//);
  assert.equal(r.self_body, 'HubSpot vs Salesforce\n\nWe run 40 seats.',
    'title first, then selftext');
  assert.equal(r.self_id, 't3_def456', 'an already-prefixed id is not doubled');
  assert.equal(r.deleted, null, 'an unattributable post is not a document');
  assert.equal(r.removed_self, 'Zoom is down', 'a removed body leaves the title');
  assert.equal(r.empty, null);
  assert.equal(r.bot, null);
});

test('tree_docs returns the post body with its title, alongside the comments', () => {
  const r = py(`
import json
from harvest import tree_docs
tree = [
  {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": {
     "id": "abc123", "author": "op", "title": "Best CRM for a 10-person team?",
     "selftext": "We are on spreadsheets.", "created_utc": 10,
     "permalink": "/r/crm/comments/abc123/best/"}}]}},
  {"kind": "Listing", "data": {"children": [{"kind": "t1", "data": {
     "id": "t1_c1", "author": "someone", "body": "HubSpot free tier.",
     "created_utc": 11, "permalink": "/r/crm/comments/abc123/best/c1/"}}]}},
]
docs, title = tree_docs(tree)
print(json.dumps({"title": title, "types": sorted(d["doc_type"] for d in docs),
                  "post": [d["body"] for d in docs if d["doc_type"] == 2]}))`);
  assert.equal(r.title, 'Best CRM for a 10-person team?');
  assert.deepEqual(r.types, [1, 2], 'both a comment and a post body come back');
  assert.equal(r.post[0], 'Best CRM for a 10-person team?\n\nWe are on spreadsheets.');
});
