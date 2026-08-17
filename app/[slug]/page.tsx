import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getRegistry } from "@/lib/routing";
import { SITE_URL } from "@/lib/env";
import { getSnapshot } from "@/lib/data/snapshot";
import { buildBoards } from "@/lib/data/boards";
import { buildSearchIndex } from "@/lib/data/search-index";
import { IndexPage } from "@/components/pages/index-page";
import { CompanyPage } from "@/components/pages/company-page";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";

/**
 * ONE dynamic segment serves both categories and companies.
 *
 * decisions/0007: "/category/{slug}" and "/brand/{slug}" are not routes and must
 * never be generated. `typedRoutes` in next.config.ts makes a stray
 * <Link href="/category/crm"> a compile error, and scripts/gates/slugs.mjs
 * re-checks the actual prerender manifest afterwards.
 */

export const dynamic = "force-static";
export const dynamicParams = false;
export const revalidate = 86400; // the daily-publish floor, 08-architecture.md §4

export async function generateStaticParams() {
  const reg = await getRegistry();
  return [...reg.categories, ...reg.companies].map((slug) => ({ slug }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
  const { slug } = await params;
  const [reg, snap] = await Promise.all([getRegistry(), getSnapshot()]);
  const hit = reg.bySlug.get(slug);

  if (hit?.tier === "category") {
    const c = CATEGORY_BY_SLUG[slug as CategorySlug];
    const cat = snap.categories.find((x) => x.slug === slug);
    // Count what the page actually SHOWS. cat.scores holds every scored row
    // including those below the category's threshold, so describing the page
    // from it overstated /web-hosting as 67 brands against the 32 on its
    // board — a meta description that contradicts the page it describes.
    const boardRows = buildBoards(snap)[slug]?.rows ?? [];
    const n = boardRows.length;
    const mentions = cat?.scores.reduce((a, s) => a + s.n, 0) ?? 0;
    const top = boardRows[0]?.brandName;
    const bottom = boardRows[boardRows.length - 1]?.brandName;
    // ABSOLUTE title: the layout template appends " · Reddit Brand Index",
    // which pushed every page past 80 characters — Google truncates around
    // 60, so the differentiating words were the ones being cut.
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
    };
  }

  const co = snap.companies.get(slug);
  if (!co) {
    return { title: "Not found", alternates: { canonical: `/${slug}/` } };
  }
  const t = co.sentimentTotals;
  const primary = co.primaryCategorySlug ? CATEGORY_BY_SLUG[co.primaryCategorySlug] : null;
  const score = primary
    ? co.scores.find((s) => s.categorySlug === primary.slug)?.redditLoveScore ?? null
    : null;
  // Long brand names ("Alibaba Cloud Container Service for Kubernetes") blow
  // past the ~60 characters Google shows, and the words that get cut are the
  // descriptive ones. Drop the suffix progressively rather than truncating
  // the name — the company's own name is the part that must survive.
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
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [reg, snap] = await Promise.all([getRegistry(), getSnapshot()]);
  const hit = reg.bySlug.get(slug);

  if (hit?.tier === "category") {
    // The same board as the homepage, preselected — ONE experience, not a
    // second page design. The dropdown swaps scope in place from here too.
    return <IndexPage data={buildBoards(snap)} scope={slug as CategorySlug} search={buildSearchIndex(snap)} />;
  }

  if (hit?.tier === "company") {
    const company = snap.companies.get(slug);
    if (!company) notFound();
    // The rank shown on a company page must be the position on the board a
    // reader can go and look at, so it is read from buildBoards rather than
    // from brand_category_scores.rank_desc. Those disagree: rank_desc comes
    // from an eligibility-gated ordering, so HubSpot — first on the CRM board
    // with 1,353 opinionated mentions — carries a NULL rank_desc there.
    const boards = buildBoards(snap);
    const cat = company.primaryCategorySlug;
    const rows = cat ? boards[cat]?.rows ?? [] : [];
    const idx = rows.findIndex((r) => r.brandSlug === slug);
    return (
      <CompanyPage
        company={company}
        boardRank={idx >= 0 ? idx + 1 : null}
        boardSize={rows.length}
      />
    );
  }

  notFound();
}
