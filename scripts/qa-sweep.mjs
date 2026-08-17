#!/usr/bin/env node
/**
 * Read every built page and check the things no gate covers.
 *
 * The design gates police CSS and slugs; the Python audit polices the corpus.
 * Nothing looked at the RENDERED HTML as a whole — which is where a number
 * that disagrees with itself between two surfaces, a broken internal link, or
 * a stray "undefined" actually reaches a reader.
 *
 *   node scripts/qa-sweep.mjs            # all pages
 *   node scripts/qa-sweep.mjs --sample 200
 */
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, basename } from "node:path";

const ROOT = process.cwd();
const APP = join(ROOT, ".next/server/app");
const args = process.argv.slice(2);
const SAMPLE = args.includes("--sample")
  ? Number(args[args.indexOf("--sample") + 1]) : 0;

if (!existsSync(APP)) {
  console.error("no build found — run `pnpm build` first");
  process.exit(1);
}

const failures = [];
const fail = (page, check, detail) => failures.push({ page, check, detail });

function htmlFiles(dir) {
  const out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    const st = statSync(p);
    if (st.isDirectory()) out.push(...htmlFiles(p));
    else if (e.endsWith(".html")) out.push(p);
  }
  return out;
}

let pages = htmlFiles(APP);
if (SAMPLE && pages.length > SAMPLE) {
  const step = Math.floor(pages.length / SAMPLE);
  pages = pages.filter((_, i) => i % step === 0).slice(0, SAMPLE);
}

// the set of slugs that legitimately exist, from the prerender manifest
const manifest = JSON.parse(
  readFileSync(join(ROOT, ".next/prerender-manifest.json"), "utf8"));
const routes = new Set(Object.keys(manifest.routes ?? {}));
const KNOWN = new Set(["/", "/methodology/", "/robots.txt", "/sitemap.xml", "/llms.txt"]);

const text = (h) => h.replace(/<script[\s\S]*?<\/script>/g, "")
                     .replace(/<style[\s\S]*?<\/style>/g, "")
                     .replace(/<[^>]+>/g, " ");

/**
 * The same, MINUS quoted Reddit comment bodies. Those are other people's
 * words: r/losslesscut quotes "23.976 (24000/1001) FPS", an Attio thread says
 * "an undefined sales process", a Kubernetes thread discusses "quiet/signaling
 * NaNs". Scanning them for NaN/undefined/out-of-range numbers reports the
 * corpus as a bug. Only OUR chrome is checked for stray values.
 */
const chrome = (h) => text(h.replace(/<blockquote[\s\S]*?<\/blockquote>/g, " "));

for (const fp of pages) {
  const page = "/" + basename(fp, ".html");
  const h = readFileSync(fp, "utf8");
  const visible = text(h);
  const ours = chrome(h);

  // 1. stray values that mean a formatting or data bug reached the reader
  for (const bad of ["NaN", "undefined", "[object Object]", "No verdict",
                     "Invalid Date", "&amp;amp;"]) {
    if (ours.includes(bad)) fail(page, "stray-string", bad);
  }

  // 2. meta: a page with no title or an empty description is not shippable
  const title = /<title>([^<]*)<\/title>/.exec(h)?.[1] ?? "";
  const desc = /<meta name="description" content="([^"]*)"/.exec(h)?.[1] ?? "";
  if (page.startsWith("/_")) continue;   // framework boundary, not a page
  if (!title.trim()) fail(page, "meta", "empty <title>");
  if (!desc.trim()) fail(page, "meta", "empty description");
  if (title.length > 70) fail(page, "meta", `title ${title.length} chars`);
  if (desc && desc.length > 200) fail(page, "meta", `description ${desc.length} chars`);

  // 3. internal links must resolve to a real prerendered route
  for (const m of h.matchAll(/href="(\/[^"#?]*)"/g)) {
    const href = m[1];
    if (KNOWN.has(href) || href.startsWith("/_next")) continue;
    const norm = href.endsWith("/") ? href : href + "/";
    const bare = norm.slice(0, -1);
    if (!routes.has(norm) && !routes.has(bare) && !routes.has(href)) {
      fail(page, "dead-link", href);
    }
  }

  // 4. external links leak PageRank unless marked; reddit + calendly only
  for (const m of h.matchAll(/<a[^>]*href="(https?:\/\/[^"]+)"[^>]*>/g)) {
    const tag = m[0], url = m[1];
    const host = new URL(url).hostname.replace(/^www\./, "");
    // reddit.com is the evidence; empact.partners and calendly are ours.
    if (!/reddit\.com$|calendly\.com$|empact\.partners$/.test(host)) {
      fail(page, "external-host", host);
    } else if (/reddit\.com$/.test(host) && !/rel="[^"]*nofollow/.test(tag)) {
      // UGC we link to must be nofollow; our own properties need not be.
      fail(page, "external-rel", url.slice(0, 60));
    }
  }

  // 5. the sentiment bar must describe a whole: its three shares sum to 100
  const bar = /(\d+)% positive, (\d+)% negative, (\d+)% neutral/.exec(visible);
  if (bar) {
    const sum = Number(bar[1]) + Number(bar[2]) + Number(bar[3]);
    if (Math.abs(sum - 100) > 2) fail(page, "sentiment-sum", `${sum}%`);
  }

  // 6. a score tile claiming a number out of range is a computation bug
  for (const m of ours.matchAll(/(\d+)\s*\/\s*100/g)) {
    const v = Number(m[1]);
    if (v < 0 || v > 100) fail(page, "score-range", m[0]);
  }

  // 7. noindex must be present on every page while provisional
  // _global-error is a framework boundary, not a routable page
  if (!page.startsWith("/_") && !/name="robots"[^>]*noindex/.test(h)) {
    fail(page, "noindex", "missing");
  }
}

// 8. cross-surface: a company's rank tile must match its board position.
// Resolve the category by NAME, not by row count: matching on size alone
// picked whichever board happened to have the same number of rows, which
// reported SharePoint ("of 12 in Document Management") against
// /community-platforms and called a correct rank a mismatch.
const catSlugByName = new Map(
  readFileSync(join(ROOT, "data/categories.csv"), "utf8")
    .split("\n").slice(1).filter(Boolean)
    .map((line) => {
      const cells = line.match(/("[^"]*"|[^,]+)/g) ?? [];
      const clean = (x) => (x ?? "").replace(/^"|"$/g, "").trim();
      return [clean(cells[0]), clean(cells[1])];   // categories.csv is `category,slug`
    }),
);
const boardRows = new Map();          // category slug -> [brandSlug...]
for (const fp of htmlFiles(APP)) {
  const slug = basename(fp, ".html");
  const h = readFileSync(fp, "utf8");
  const rows = [...h.matchAll(/col-brand[^>]*>\s*<a[^>]*href="\/([^"\/]+)\//g)]
    .map((m) => m[1]);
  if (rows.length) boardRows.set(slug, rows);
}
let crossChecked = 0;
for (const fp of pages) {
  const slug = basename(fp, ".html");
  const h = readFileSync(fp, "utf8");
  const rank = /stat-hash[^>]*>#<\/span>(\d+)</.exec(h);
  if (!rank) continue;
  const claimed = Number(rank[1]);
  // read the label from the RAW html: after tag-stripping, "of 24 in CRM" is
  // followed by whitespace, not by "<"
  const label = /of (\d+) in ([^<]+)<\/span>/.exec(h);
  if (!label) continue;
  const size = Number(label[1]);

  const catName = label[2].trim();
  const cat = catSlugByName.get(catName);
  const rows = cat ? boardRows.get(cat) : undefined;
  if (!rows) { fail("/" + slug, "rank-category", `no board for "${catName}"`); continue; }
  const i = rows.indexOf(slug);
  if (i < 0) { fail("/" + slug, "rank-absent", `not on /${cat}`); continue; }
  if (rows.length !== size) {
    fail("/" + slug, "rank-size", `page says of ${size}, /${cat} renders ${rows.length}`);
    continue;
  }
  // The two-card view renders LOVED (the top ceil(N/2)) and then HATED —
  // the BOTTOM of the ordering, reversed. DOM order is not board order, and
  // a check that assumes it is calls every hated-side brand a mismatch.
  const lovedN = Math.ceil(rows.length / 2);
  const expected = i < lovedN ? i + 1 : rows.length - (i - lovedN);
  crossChecked++;
  if (expected !== claimed) {
    fail("/" + slug, "rank-mismatch",
         `page says #${claimed}, /${cat} implies ${expected}`);
  }
}

// ── report ──────────────────────────────────────────────────────────────────
const byCheck = new Map();
for (const f of failures) {
  if (!byCheck.has(f.check)) byCheck.set(f.check, []);
  byCheck.get(f.check).push(f);
}
console.log(`qa-sweep: ${pages.length} pages, ${crossChecked} rank cross-checks\n`);
if (!failures.length) {
  console.log("  ALL CHECKS PASS");
  process.exit(0);
}
for (const [check, list] of [...byCheck].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${check}: ${list.length}`);
  const seen = new Set();
  for (const f of list) {
    const k = `${f.detail}`;
    if (seen.has(k)) continue;
    seen.add(k);
    if (seen.size > 5) { console.log(`    …and more`); break; }
    console.log(`    ${f.page}  ${f.detail}`);
  }
}
console.log(`\n  ${failures.length} finding(s)`);
process.exit(1);
