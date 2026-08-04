# 0002 — Brand pages display full Reddit comment text

**Status:** Accepted, with known non-compliance · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets

⚠️ This decision is not compliant with Reddit's terms. It was taken with the exposure understood and priced. This record exists so nobody later claims it was an oversight.

## Bottom line

- Brand pages show **full comment text**, each permalinked and attributed. The owner saw the clause-level analysis in [../01-legal.md](../01-legal.md) and reaffirmed the design.
- It breaches [Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms) outright, stretches the [Data API Terms §2.4](https://www.redditinc.com/policies/data-api-terms) display licence past breaking, and adds per-commenter copyright exposure that no mitigation removes.
- The asset genuinely at risk is not the site. It is Empact's existing Reddit operation, which the [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) lets Reddit suspend by domain and by associated account.
- The five mitigations below are conditions of the decision, not options.

## Context

The product concept requires brand pages that show the actual Reddit mentions behind a score, each linked to its source thread. Without them a brand page is a number with nothing under it, and the cold-outreach hook ("here is what people say about you") has nothing to show.

Three lower-exposure architectures were put forward and rejected:

| Option | What it gives up |
|---|---|
| Link-only + aggregate scores | No comment text on the page. The evidence is one click away, so the page carries no persuasive weight. |
| [Reddit Embeds](https://www.redditinc.com/policies/embeds-terms) for each mention | Content stays served by Reddit and deletions propagate automatically, but pages get slow and the layout is dictated by Reddit's widget. |
| Aggregate scores only | Removes the entire reason a brand page exists. |

Note that the third option is no safer on contract. Developer Terms §4.1 and Data API Terms §6 both reach *derived* data, and contract is the theory Reddit litigates on. Dropping the text buys down copyright exposure, not commercial-use exposure.

## Decision

Brand pages display **full comment text** for qualifying mentions, each with a permalink to the source thread and the author's username.

## What this breaches

| Clause | Requirement | Our position |
|---|---|---|
| [Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms) | No use "by or on behalf of a business", extending to "any data derived from the foregoing" | Breached. Empact Partners is a business and the site is a lead-generation asset. |
| [Data API Terms §3.1](https://www.redditinc.com/policies/data-api-terms) | Commercial use "will need to enter into a separate agreement with Reddit" | No agreement in place. |
| [Data API Terms §2.4](https://www.redditinc.com/policies/data-api-terms) | Display licence covers copying and displaying User Content "using the Data API solely as necessary to… run your App" | Stretched past breaking. Historical backfill comes from the Arctic Shift / Academic Torrents monthly dumps, not the API ([../02-data-acquisition.md](../02-data-acquisition.md)), so most of what a page displays never passed through the licensed channel at all. |
| [Data API Terms §6](https://www.redditinc.com/policies/data-api-terms) | On termination, delete User Content **and** derived data and models | Accepted as an obligation we would have to honour. |
| [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) | "User Content is owned by Users and not by Reddit" | Unresolved. Ownership sits with each commenter, so no Reddit licence, granted or negotiated, reaches the text. No mitigation exists short of not displaying it. |

Reddit's [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) names this exact use case — "companies that help brands monitor trends associated with their brands" — as a paid data-licensee category.

## The real exposure

The [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) permits Reddit to suspend "associated accounts, bots, **domains**, or subreddits."

Empact Partners runs a live Reddit revenue line: managed personas, aged accounts, a production Reddit agent, and Reddit marketing across roughly 28 partner projects. That count is an internal Empact figure, not a published or externally sourced one.

**That operation, not the site, is the asset genuinely at risk.** A side project putting a multi-partner service line inside the blast radius is the single largest cost of this decision.

## Mitigations that are mandatory, not optional

These are conditions of the decision, and each has an owner in [../01-legal.md](../01-legal.md):

1. **Attribution on every mention** — permalink back to the thread, the author's username, and a clear statement that the content is from Reddit. That is the display requirement [Developer Terms §5.2](https://www.redditinc.com/policies/developer-terms) sets out verbatim, and it costs nothing.
2. **Nightly delete-sync.** [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) requires that content deleted, protected, suspended, withheld, modified or removed on Reddit be deleted or modified by us "as soon as possible." The contract names no interval. We implement a nightly job and treat that as our own target, not as the contractual one.
3. **No advertising anywhere on the property**, ever. Reddit's [developer documentation](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) answers "Can I display Reddit content and run ads?" with a flat no, and the [Embeds Terms](https://www.redditinc.com/policies/embeds-terms) forbid it independently.
4. **Free, fast, unconditional removal** on request from either a commenter or a brand, with no commercial offer attached to the process.
5. **A separate legal review before launch.** This repo is not legal advice.

## Revisit when

- Reddit sends any notice, or any Empact-operated Reddit account is actioned. Revisit immediately.
- Reddit publishes a commercial tier a consultancy can actually buy.
- Traffic or outreach volume grows enough to make the property visible to Reddit's enforcement team.

---

[← Back to README](../README.md) · [Legal position](../01-legal.md) · [Data acquisition](../02-data-acquisition.md) · [Concept](../00-concept.md)
