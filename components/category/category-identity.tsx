import Link from "next/link";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";
import { CATEGORY_ICONS } from "@/lib/generated/category-icons";

/**
 * The icon tile. 40px desktop / 32px mobile, 6px radius, category-colour fill,
 * Space Black lucide glyph at strokeWidth 2.
 *
 * NEVER circular, never a pill — decisions/0008: that shape is precisely what
 * stops the tile reading as a sentiment chip. Sentiment chips are pills;
 * category tiles are 6px squares; the two colour systems never share a surface.
 *
 * Hue is assigned in wheel order, not by meaning. No category gets a colour
 * that implies a judgment about it — a "money-green" Payroll or a "warning-red"
 * Payment Processing would leak sentiment into what is meant to be navigation.
 *
 * The tile is aria-hidden when the category name sits beside it, because a
 * duplicate announcement is worse than none.
 */
export function CategoryTile({ slug, labelled = true }: { slug: CategorySlug; labelled?: boolean }) {
  const Icon = CATEGORY_ICONS[slug];
  const cat = CATEGORY_BY_SLUG[slug];
  return (
    <span className="cat-tile" data-category={slug} aria-hidden={labelled ? true : undefined}>
      <Icon
        width={20}
        height={20}
        strokeWidth={2}
        color="#171616"
        aria-hidden="true"
        focusable="false"
      />
      {!labelled && <span className="sr-only">{cat.name}</span>}
    </span>
  );
}

/**
 * The category chip — third column on a pooled board, and the category label
 * anywhere else. Colour is never the only carrier: the category name is present
 * as text wherever its colour is, which is what makes a minimum pairwise
 * separation of ΔE 0.0927 acceptable in the first place.
 */
export function CategoryChip({ slug, link = true }: { slug: CategorySlug; link?: boolean }) {
  const cat = CATEGORY_BY_SLUG[slug];
  const body = (
    <span className="cat-chip" data-category={slug}>
      {cat.name}
    </span>
  );
  return link ? <Link href={`/${slug}/`}>{body}</Link> : body;
}
