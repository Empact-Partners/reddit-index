/**
 * THE ONLY PLACE THE SITE'S PUBLICATION STAGE IS DECIDED.
 *
 * `redditindex.com` is verified, attached, and public. Flipping this to
 * "public" is a reviewable commit, never an invisible dashboard toggle —
 * decisions/0007 prefers a build failure to a runtime resolution for exactly
 * this reason: a build failure is visible once, to the person who caused it.
 *
 * While "provisional", three independent layers keep the site out of search
 * indexes (robots.txt, a meta tag, and an X-Robots-Tag header), and a banner
 * says so on every page. Flipping the constant removes all four.
 *
 * Before this may become "public":
 *   · /methodology/ is live, versioned, and its freeze commit is recorded
 *   · every category carries measured data, not a placeholder
 *   · decisions/0005's six conditions are all met on every ranked surface
 *   · redditbrandindex.com is registered (decisions/0001 — a defensive name
 *     bought after a complaint lands reads as bad faith, not protection)
 *   · a free, unconditional correction route resolves
 */
export const SITE_STAGE: "provisional" | "public" = "provisional";

export const IS_PROVISIONAL = SITE_STAGE === "provisional";

/**
 * The measured corpus is a sample, not a census. Until it is one, nothing here
 * is a published ranking, and every surface says so in the same words.
 */
export const PROVISIONAL_NOTICE =
  "Provisional build. Partial data, methodology not yet frozen against a full collection window. Nothing on this site is a published ranking.";
