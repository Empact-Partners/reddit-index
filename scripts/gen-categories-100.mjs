#!/usr/bin/env node
/**
 * Build the 100-row data/categories.csv from data/taxonomy-100.csv.
 *
 * - The 20 published rows keep their hex, icon, tier and measured columns
 *   BYTE-IDENTICAL (published identities never shift); they gain only the
 *   new `nouns` column.
 * - The 80 new rows get colours by farthest-point sampling inside the
 *   C1-C7-legal OKLCH region with the 20 existing points held fixed, icons
 *   from the hand map below (uniqueness asserted across all 100), and the
 *   provisional thin tier (200 / ±7pp) until discovery measures them.
 *
 * At 100 colours the min pairwise dE necessarily drops (~n^-1/3): the floor
 * asserted here is the achieved maximin (hard sanity floor 0.030). Colour is never the only identity carrier — the
 * icon and name always co-render — which is what makes that acceptable.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { hexToOklch, hexToOklab, deltaE, contrast, checkConstraints, minPairwise } from './color.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const FLOOR = 0.030;  // hard sanity floor; the ACHIEVED maximin is reported and published

// ── icons: 80 new, distinct from the 20 shipped and from each other ─────────
// added for the never-replied expansion (P4)
const ROSTER_ICONS = {
  'sales-intelligence': 'binoculars',
  'affiliate-referral-marketing': 'handshake',
  'ai-agent-platforms': 'bot-message-square',
  'sales-enablement': 'book-check',
  'music-production': 'music',
  'wealth-management': 'gem',
  'investment-research': 'line-chart',
  'influencer-marketing': 'badge-check',
  'cloud-cost-management': 'cloud-cog',
  'revenue-intelligence': 'area-chart',
  'reputation-management': 'star',
  'application-security-testing': 'bug-play',
  'headless-cms': 'file-code',
  'digital-adoption-platforms': 'compass',
  'software-test-automation': 'flask-conical',
  'fitness-business-management': 'dumbbell',
  'contract-lifecycle-management': 'file-signature',
  'carbon-accounting-esg-reporting': 'leaf',
  'aml-financial-crime': 'shield-alert',
  'advocacy-software': 'heart-handshake',
  'financial-planning-analysis': 'sigma',
  'customer-success': 'smile',
  'procurement-automation': 'package-search',
  'sales-engagement': 'send-horizontal',
  'crypto-trading': 'bitcoin',
  'digital-asset-management': 'images',
  'insurance-software': 'umbrella',
  'dental-practice-management': 'stethoscope',
  'privacy-management': 'lock-keyhole',
  'equity-management': 'pie-chart',
  'blockchain-infrastructure': 'boxes',
  'configure-price-quote': 'tag',
  'marketing-attribution': 'route',
  'security-operations-automation': 'radar',
  'customer-data-platforms': 'contact',
  'intelligent-document-processing': 'scan-text',
  'farm-management': 'sprout',
  'automotive-retail-repair': 'car',
  'sports-management': 'trophy',
  'proposal-rfp-software': 'file-check',
  'llm-operations': 'brain-circuit',
  'voice-ai': 'mic-vocal',
  'backend-as-a-service': 'hard-drive-download',
  'hotel-management': 'hotel',
  'cloud-security-posture-management': 'cloud-alert',
  'wedding-business-software': 'heart',
  'email-security': 'mail-warning',
  'electronic-health-records': 'clipboard-plus',
  'public-relations-software': 'quote',
  'loan-management': 'banknote-arrow-up',
  'healthcare-data-platforms': 'activity-square'
};

const NEW_ICONS = {
  ...ROSTER_ICONS,
  "vpn": "globe-lock", "antivirus": "shield-check", "web-hosting": "panel-top",
  "domain-registrars": "at-sign", "website-builders": "layout-template",
  "seo-tools": "trending-up", "social-media-management": "share-2",
  "live-chat": "message-circle", "voip": "phone-call", "video-conferencing": "video",
  "webinars": "presentation", "lms": "graduation-cap", "course-platforms": "book-open",
  "form-builders": "clipboard-list", "survey-tools": "list-checks",
  "scheduling": "calendar-clock", "time-tracking": "timer", "invoicing": "receipt",
  "expense-management": "wallet", "esignature": "signature",
  "document-management": "folder-open", "pdf-tools": "file-text",
  "cloud-storage": "cloud", "photo-editing": "image", "cad": "box",
  "game-engines": "gamepad-2", "ides": "code", "code-hosting": "git-branch",
  "ci-cd": "workflow", "containers": "container", "iac": "layers",
  "observability": "activity", "error-tracking": "bug", "feature-flags": "flag",
  "product-analytics": "chart-line", "web-analytics": "chart-area",
  "session-replay": "mouse-pointer-click", "data-warehouses": "database",
  "etl": "git-merge", "databases": "database-zap", "api-tools": "plug",
  "identity": "fingerprint", "mdm": "tablet-smartphone", "remote-desktop": "monitor-smartphone",
  "rmm": "server-cog", "network-security": "brick-wall", "email-providers": "inbox",
  "communication-apis": "send", "newsletters": "newspaper", "podcast-hosting": "mic",
  "video-hosting": "play", "screen-recording": "screen-share",
  "presentations": "gallery-vertical-end", "no-code": "blocks",
  "workflow-automation": "zap", "internal-tools": "wrench", "spreadsheets": "table",
  "diagramming": "spline", "wikis": "library", "localization": "languages",
  "writing-assistants": "spell-check", "ai-assistants": "bot",
  "ai-image": "image-plus", "ai-video": "film", "ai-coding": "braces",
  "transcription": "audio-lines", "field-service": "truck", "construction": "hammer",
  "property-management": "building-2", "restaurant-pos": "utensils",
  "pos": "scan-barcode", "inventory": "package", "shipping": "package-check",
  "print-on-demand": "shirt", "legal-practice": "scale", "nonprofit": "hand-heart",
  "event-management": "ticket", "community-platforms": "users",
  "budgeting": "piggy-bank", "tax-software": "landmark",
};

// ── load inputs ─────────────────────────────────────────────────────────────
function parseCsv(text) {
  const [head, ...lines] = text.trim().split('\n');
  const cols = head.split(',');
  return lines.map((l) => {
    // naive split is fine: none of our fields contain commas except quoted —
    // assert that so drift fails loudly
    if (l.includes('"')) throw new Error('quoted field in CSV — extend the parser: ' + l);
    const vals = l.split(',');
    return Object.fromEntries(cols.map((c, i) => [c, vals[i] ?? '']));
  });
}

const existing = parseCsv(fs.readFileSync(path.join(ROOT, 'data', 'categories.csv'), 'utf8'));
const tax = parseCsv(fs.readFileSync(path.join(ROOT, 'data', 'taxonomy-100.csv'), 'utf8'));
const existingBySlug = new Map(existing.map((r) => [r.slug, r]));
const newRows = tax.filter((r) => !existingBySlug.has(r.slug));
// Generalized 2026-08-20 (index expansion): "existing" is whatever categories.csv holds
// today, and every existing row keeps hex + icon byte-identical — published category
// identity is frozen the same way slugs are (decisions/0007/0008). Only slugs newly added
// to the taxonomy CSV get placed. The taxonomy may only GROW: a removed row would orphan a
// published category page, so removals fail loudly here.
if (existing.length < 20) throw new Error(`categories.csv looks truncated: ${existing.length} rows`);
const taxSlugs = new Set(tax.map((r) => r.slug));
const removed = existing.filter((r) => !taxSlugs.has(r.slug)).map((r) => r.slug);
if (removed.length) throw new Error(`taxonomy removed published categories: ${removed.join(', ')}`);

// icon uniqueness across all 100
const allIcons = [...existing.map((r) => r.icon), ...newRows.map((r) => {
  const ic = NEW_ICONS[r.slug];
  if (!ic) throw new Error(`no icon mapped for new slug ${r.slug}`);
  return ic;
})];
const dupIcons = allIcons.filter((ic, i) => allIcons.indexOf(ic) !== i);
if (dupIcons.length) throw new Error(`duplicate icons: ${dupIcons.join(', ')}`);

// ── farthest-point colour sampling ──────────────────────────────────────────
// Candidate grid over the legal region; score = min OKLab distance to every
// already-placed point; place the argmax; repeat. Deterministic (no RNG).
function oklchToHex(L, C, H) {
  // OKLab -> linear sRGB -> hex (inverse of color.mjs's forward path)
  const rad = (H * Math.PI) / 180;
  const a = C * Math.cos(rad), b = C * Math.sin(rad);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  let R = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  let G = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  let B = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
  const g = (x) => x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055;
  const to255 = (x) => Math.round(Math.min(1, Math.max(0, g(x))) * 255);
  const [r8, g8, b8] = [to255(R), to255(G), to255(B)];
  if ([R, G, B].some((x) => x < -0.004 || x > 1.004)) return null; // out of gamut
  return '#' + [r8, g8, b8].map((v) => v.toString(16).padStart(2, '0')).join('').toUpperCase();
}

const placedLab = existing.map((r) => hexToOklab(r.hex));
const candidates = [];
for (let L = 0.625; L <= 0.817; L += 0.008) {
  for (let C = 0.092; C <= 0.218; C += 0.007) {
    for (let H = 0; H < 360; H += 1.5) {
      const hex = oklchToHex(L, C, H);
      if (!hex) continue;
      if (checkConstraints(hex).length) continue; // C1-C7 on the QUANTISED hex
      candidates.push({ hex, lab: hexToOklab(hex) });
    }
  }
}
console.log(`${candidates.length} legal candidate colours`);

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const picked = [];
for (let k = 0; k < newRows.length; k++) {
  let best = null, bestScore = -1;
  for (const c of candidates) {
    if (picked.some((p) => p.hex === c.hex)) continue;
    let d = Infinity;
    for (const p of placedLab) d = Math.min(d, dist(c.lab, p));
    for (const p of picked) d = Math.min(d, dist(c.lab, p.lab));
    if (d > bestScore) { bestScore = d; best = c; }
  }
  if (!best || bestScore < FLOOR) {
    throw new Error(`could not place colour ${k + 1}: best separation ${bestScore.toFixed(4)} < ${FLOOR}`);
  }
  picked.push(best);
}

const allHexes = [...existing.map((r) => r.hex), ...picked.map((p) => p.hex)];
const { d: minD } = (() => {
  let best = Infinity;
  for (let i = 0; i < allHexes.length; i++)
    for (let j = i + 1; j < allHexes.length; j++)
      best = Math.min(best, deltaE(allHexes[i], allHexes[j]));
  return { d: best };
})();
console.log(`min pairwise dE across 100: ${minD.toFixed(4)} (floor ${FLOOR})`);
if (minD < FLOOR) throw new Error('separation floor violated');

// ── emit ────────────────────────────────────────────────────────────────────
const LUCKY = '#40C890', GRAPE = '#A155FF', RORANGE = '#FF4500';
const SPACE = '#171616', SNOW = '#EEF1ED';
const nounsBySlug = new Map(tax.map((r) => [r.slug, r.nouns]));

const cols = ['category', 'slug', 'icon', 'hex', 'oklch', 'contrast_space_black',
  'contrast_snowbelt', 'dE_loved', 'dE_hated', 'dE_nearest_category',
  'min_pairwise_dE', 'dE_orange', 'threshold_tier', 'precision_target_pp',
  'n_min', 'scorable_subreddits', 'meets_5_sub_floor', 'nouns'];

function nearest(hex) {
  let best = Infinity;
  for (const h of allHexes) if (h !== hex) best = Math.min(best, deltaE(hex, h));
  return best;
}

const out = [cols.join(',')];
// existing rows: verbatim + recomputed shared columns + nouns
for (const r of existing) {
  out.push([r.category, r.slug, r.icon, r.hex, r.oklch, r.contrast_space_black,
    r.contrast_snowbelt, r.dE_loved, r.dE_hated, nearest(r.hex).toFixed(4),
    minD.toFixed(4), r.dE_orange, r.threshold_tier, r.precision_target_pp,
    r.n_min, r.scorable_subreddits, r.meets_5_sub_floor,
    nounsBySlug.get(r.slug) ?? ''].join(','));
}
for (let i = 0; i < newRows.length; i++) {
  const r = newRows[i], hex = picked[i].hex;
  const [L, C, H] = hexToOklch(hex);
  out.push([r.category, r.slug, NEW_ICONS[r.slug], hex,
    `oklch(${L.toFixed(3)} ${C.toFixed(3)} ${H.toFixed(1)})`,
    contrast(hex, SPACE).toFixed(2), contrast(hex, SNOW).toFixed(2),
    deltaE(hex, LUCKY).toFixed(4), deltaE(hex, GRAPE).toFixed(4),
    nearest(hex).toFixed(4), minD.toFixed(4), deltaE(hex, RORANGE).toFixed(4),
    'thin', '7', '200', '0', 'False', r.nouns].join(','));
}

// identity gate: every pre-existing slug must re-emit its exact hex + icon
const emitted = new Map(out.slice(1).map((l) => {
  const c = l.split(',');
  return [c[1], { icon: c[2], hex: c[3] }];
}));
for (const r of existing) {
  const e = emitted.get(r.slug);
  if (!e || e.hex !== r.hex || e.icon !== r.icon) {
    throw new Error(`identity drift on published category ${r.slug}: ` +
      `${r.icon}/${r.hex} -> ${e ? e.icon + '/' + e.hex : 'MISSING'}`);
  }
}

const outFp = path.join(ROOT, 'data', 'categories.csv');
fs.writeFileSync(outFp + '.tmp', out.join('\n') + '\n');
fs.renameSync(outFp + '.tmp', outFp);
console.log(`wrote data/categories.csv — ${out.length - 1} rows (${existing.length} kept, ${newRows.length} new)`);
