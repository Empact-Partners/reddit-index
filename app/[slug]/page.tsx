import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { SITE_URL } from "@/lib/env";
import { getCompany, getIndex, getIndexRows } from "@/lib/data/site-db";
import { getRegistry } from "@/lib/routing";
import { buildBoards } from "@/lib/data/boards";
import { buildSearchIndex } from "@/lib/data/search-index";
import { IndexPage } from "@/components/pages/index-page";
import { CompanyPage } from "@/components/pages/company-page";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";

/**
 * ONE dynamic segment serves both categories and companies.
 *
 * decisions/0007: "/category/{slug}" and "/brand/{slug}" are not routes and must never be generated.
 * `typedRoutes` in next.config.ts makes a stray <Link href="/category/crm"> a compile error, and
 * scripts/gates/slugs.mjs re-checks the actual prerender manifest afterwards.
 */

export const dynamic = "force-static";
// Categories are prerendered at build. A COMPANY page is rendered the first time it is asked for and cached
// from then on: a build no longer reads 6,000 companies' cards to deploy a code change, and a brand that
// gets its first mention has a page without waiting for a build. An unknown slug costs one primary-key
// lookup that returns nothing.
export const dynamicParams = true;
// NEVER a number. See app/page.tsx: a timed revalidate is what cost 3.80 billion rows. A page is expired
// only when the daily sweep names its path at /api/revalidate.
export const revalidate = false;

/** Lowercase kebab, the shape the registry enforces on every slug it mints. Anything else never reaches
 *  the database. */
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export async function generateStaticParams() {
  // Building the registry here is the collision gate (decisions/0007): two slugs for one path fail the build.
  const reg = await getRegistry();
  return reg.categories.map((slug) => ({ slug }));
}

function isCategory(slug: string): slug is CategorySlug {
  return Object.prototype.hasOwnProperty.call(CATEGORY_BY_SLUG, slug);
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
  const { slug } = await params;
  if (!SLUG.test(slug) || slug.length > 120) {
    return { title: "Not found" };
  }

  if (isCategory(slug)) {
    const c = CATEGORY_BY_SLUG[slug];
    const { rows, hash } = await getIndex();
    // Count what the page actually SHOWS: the board's own rows.
    const boardRows = buildBoards(rows)[slug]?.rows ?? [];
    const n = boardRows.length;
    const mentions = boardRows.reduce((a, r) => a + r.mentions, 0);
    const top = boardRows[0]?.brandName;
    const bottom = boardRows[boardRows.length - 1]?.brandName;
    // ABSOLUTE title: the layout template appends " · Reddit Brand Index", which pushed every page past
    // 80 characters — Google truncates around 60, so the differentiating words were the ones being cut.
    const longTitle = `Most Loved & Hated ${c.name} On Reddit`;
    const title = longTitle.length <= 60
      ? longTitle
      : `${c.name} On Reddit: Loved & Hated`;
    const description = n > 0
      ? `${n} ${c.name.toLowerCase()} ranked by what Reddit actually says, from `
        + `${mentions.toLocaleString("en-US")} real mentions`
        + (top && bottom && top !== bottom
          ? `. ${top} is the most loved, ${bottom} the most hated.`
          : ".")
      : `The most loved and most hated ${c.name} on Reddit, ranked from real mentions.`;
    return {
      title: { absolute: title },
      description,
      alternates: { canonical: `/${slug}/` },
      openGraph: { title, description, url: `${SITE_URL}/${slug}/`, type: "website" },
      twitter: { title, description },
      other: { "ri-hash": hash },
    };
  }

  const data = await getCompany(slug);
  if (!data) {
    return { title: "Not found", alternates: { canonical: `/${slug}/` } };
  }
  const co = data.company;
  const t = co.sentimentTotals;
  const primary = co.primaryCategorySlug ? CATEGORY_BY_SLUG[co.primaryCategorySlug] : null;
  // ONE number (decisions/0011): the description quotes the score the page shows. Until October 2026 it
  // quoted a different one, the 365-day score from brand_category_scores, so Notion's page said 48 and its
  // description said "scored 40/100".
  const score = co.pageScore;
  // Long brand names ("Alibaba Cloud Container Service for Kubernetes") blow past the ~60 characters
  // Google shows, and the words that get cut are the descriptive ones. Drop the suffix progressively
  // rather than truncating the name — the company's own name is the part that must survive.
  const fullTitle = `${co.name} On Reddit: Reviews & Reddit ❤️ Score`;
  const title = fullTitle.length <= 60
    ? fullTitle
    : `${co.name} On Reddit: Reddit ❤️ Score`.length <= 60
      ? `${co.name} On Reddit: Reddit ❤️ Score`
      : `${co.name} On Reddit`;
  const description =
    `What Reddit really thinks of ${co.name}: `
    + `${co.totalMentions.toLocaleString("en-US")} mentions across `
    + `${co.subredditStats.length} subreddits, `
    + `${t.pos.toLocaleString("en-US")} positive and ${t.neg.toLocaleString("en-US")} negative`
    + (score !== null ? `, scored ${score}/100` : "")
    + (primary ? ` in ${primary.name}.` : ".");
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: `/${slug}/` },
    openGraph: { title, description, url: `${SITE_URL}/${slug}/`, type: "website" },
    twitter: { title, description },
    other: { "ri-hash": data.pageHash },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!SLUG.test(slug) || slug.length > 120) notFound();

  if (isCategory(slug)) {
    // The same board as the homepage, preselected — ONE experience, not a second page design. The dropdown
    // swaps scope in place from here too. A category always wins the path (decisions/0007).
    const rows = await getIndexRows();
    return <IndexPage data={buildBoards(rows)} scope={slug} search={buildSearchIndex(rows)} />;
  }

  const data = await getCompany(slug);
  if (!data) notFound();
  // The rank is the one worker/site_score.py stored, computed with the same ordering the board uses
  // (lib/data/board-shapes.ts byBoardOrder), so it is the position a reader finds on the category page.
  return (
    <CompanyPage
      company={data.company}
      boardRank={data.boardRank}
      boardSize={data.boardSize}
    />
  );
}
