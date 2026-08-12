import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getRegistry } from "@/lib/routing";
import { getSnapshot } from "@/lib/data/snapshot";
import { buildBoards } from "@/lib/data/boards";
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
    const n = cat?.scores.length ?? 0;
    const mentions = cat?.scores.reduce((a, s) => a + s.n, 0) ?? 0;
    return {
      title: `Most Loved & Hated ${c.name} On Reddit`,
      description:
        n > 0
          ? `The most loved and most hated ${c.name} on Reddit: ` +
            `${n} brands ranked from ${mentions.toLocaleString("en-US")} real mentions.`
          : `The most loved and most hated ${c.name} on Reddit, ranked from real mentions.`,
      alternates: { canonical: `/${slug}/` },
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
  return {
    title: `${co.name} On Reddit: Reviews, Sentiment & Reddit ❤️ Score`,
    description:
      `${co.name} on Reddit: ${co.totalMentions.toLocaleString("en-US")} mentions ` +
      `across ${co.subredditStats.length} subreddits, ` +
      `${t.pos.toLocaleString("en-US")} positive and ${t.neg.toLocaleString("en-US")} negative` +
      (score !== null ? `, scored ${score}/100` : "") +
      `.`,
    alternates: { canonical: `/${slug}/` },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [reg, snap] = await Promise.all([getRegistry(), getSnapshot()]);
  const hit = reg.bySlug.get(slug);

  if (hit?.tier === "category") {
    // The same board as the homepage, preselected — ONE experience, not a
    // second page design. The dropdown swaps scope in place from here too.
    return <IndexPage data={buildBoards(snap)} scope={slug as CategorySlug} />;
  }

  if (hit?.tier === "company") {
    const company = snap.companies.get(slug);
    if (!company) notFound();
    return <CompanyPage company={company} />;
  }

  notFound();
}
