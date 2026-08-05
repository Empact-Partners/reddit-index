import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getRegistry } from "@/lib/routing";
import { getSnapshot } from "@/lib/data/snapshot";
import { CategoryPage } from "@/components/pages/category-page";
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
  const reg = await getRegistry();
  const hit = reg.bySlug.get(slug);
  if (hit?.tier === "category") {
    const c = CATEGORY_BY_SLUG[slug as CategorySlug];
    return {
      title: c.name,
      description: `What Reddit says about ${c.name} software, measured over a stated window and published with its method.`,
      alternates: { canonical: `/${slug}/` },
    };
  }
  const snap = await getSnapshot();
  const co = snap.companies.get(slug);
  return {
    title: co?.name ?? "Not found",
    description: co
      ? `Every Reddit mention of ${co.name} we have collected, with its sentiment, its source and a link to the original.`
      : undefined,
    alternates: { canonical: `/${slug}/` },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [reg, snap] = await Promise.all([getRegistry(), getSnapshot()]);
  const hit = reg.bySlug.get(slug);

  if (hit?.tier === "category") {
    const category = snap.categories.find((c: (typeof snap.categories)[number]) => c.slug === slug);
    if (!category) notFound();
    return <CategoryPage category={category} snapshot={snap} />;
  }

  if (hit?.tier === "company") {
    const company = snap.companies.get(slug);
    if (!company) notFound();
    return <CompanyPage company={company} snapshot={snap} />;
  }

  notFound();
}
