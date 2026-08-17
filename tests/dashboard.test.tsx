import type React from "react";
import { describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { CompanyDashboard } from "@/components/company/company-dashboard";
import type { Mention } from "@/components/data/mention-card";
import type { SubredditStat } from "@/lib/data/types";

const mk = (i: number, over: Partial<Mention>): Mention => ({
  brandName: "HubSpot", brandSlug: "hubspot", subreddit: "sales", author: "a",
  createdUtc: `2026-01-${String((i % 27) + 1).padStart(2, "0")}T00:00:00.000Z`,
  sentiment: "neu", docType: "comment",
  matchedForm: "hubspot", threadTitle: "Which CRM do you actually like?",
  body: "body about HubSpot",
  permalink: `https://www.reddit.com/r/sales/comments/a${i}/x/p${i}/`,
  ...over,
});

// 25 mentions: 8 pos (r/sales), 5 neg (r/crm), 12 neu (r/sales).
// Four of the neutrals are POSTS — the type filter is only testable against a
// fixture that actually holds both kinds of document.
const mentions: Mention[] = [
  ...Array.from({ length: 8 }, (_, i) => mk(i, { sentiment: "pos" })),
  ...Array.from({ length: 5 }, (_, i) => mk(i + 8, { sentiment: "neg", subreddit: "crm",
      permalink: `https://www.reddit.com/r/crm/comments/b${i}/x/q${i}/` })),
  ...Array.from({ length: 8 }, (_, i) => mk(i + 13, { sentiment: "neu" })),
  ...Array.from({ length: 4 }, (_, i) => mk(i + 21, { sentiment: "neu",
      docType: "post_body" })),
];

const stats: SubredditStat[] = [
  { subreddit: "sales", total: 20, pos: 8, neg: 0, neu: 12, newest: "2026-01-27T00:00:00.000Z" },
  { subreddit: "crm", total: 5, pos: 0, neg: 5, neu: 0, newest: "2026-01-13T00:00:00.000Z" },
];

function mount(over: Partial<React.ComponentProps<typeof CompanyDashboard>> = {}) {
  return render(
    <CompanyDashboard
      mentions={mentions}
      subredditStats={stats}
      totals={{ pos: 8, neg: 5, neu: 12 }}
      totalMentions={25}
      docTypeTotals={{ posts: 5, comments: 20 }}
      unlabelled={0}
      oldestMention="2026-01-01T00:00:00.000Z"
      heroScore={54}
      heroLabel="Reddit ❤️ Score · CRM"
      rank={null}
      rankLabel={null}
      {...over}
    />,
  );
}

describe("company dashboard v2", () => {
  it("defaults to Mentions collected, selected, 10 cards on page 1", () => {
    const { container, getByRole } = mount();
    expect(getByRole("button", { name: /Mentions collected/ })
      .getAttribute("aria-pressed")).toBe("true");
    expect(container.querySelectorAll(".mention-card")).toHaveLength(10);
    expect(container.querySelector(".pager")).not.toBeNull();
  });

  it("sentiment tiles filter the cards", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: /Negative/ }));
    const cards = container.querySelectorAll(".mention-card");
    expect(cards).toHaveLength(5);
    expect([...cards].every((c) => c.getAttribute("data-sentiment") === "neg")).toBe(true);
    expect(getByRole("button", { name: /Negative/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("the Subreddits tile switches to the ledger view (no cards)", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: /Subreddits/ }));
    expect(container.querySelector(".sub-ledger")).not.toBeNull();
    expect(container.querySelectorAll(".mention-card")).toHaveLength(0);
  });

  it("clicking a subreddit drills back into filtered mentions", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: /Subreddits/ }));
    fireEvent.click(getByRole("button", { name: "r/crm" }));
    expect(container.querySelector(".sub-ledger")).toBeNull();
    expect(container.querySelectorAll(".mention-card")).toHaveLength(5);
    // clear returns to all
    fireEvent.click(getByRole("button", { name: /r\/crm ✕/ }));
    expect(container.querySelectorAll(".mention-card")).toHaveLength(10); // page 1 of 25
  });

  it("paginates 10 per page and Next advances", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: "Next" }));
    expect(container.querySelectorAll(".mention-card")).toHaveLength(10);
    fireEvent.click(getByRole("button", { name: "Next" }));
    expect(container.querySelectorAll(".mention-card")).toHaveLength(5); // 25 -> page 3
    expect(getByRole("button", { name: "Next" })).toHaveProperty("disabled", true);
  });

  it("filter changes reset to page 1", () => {
    const { getByRole } = mount();
    fireEvent.click(getByRole("button", { name: "Next" }));
    fireEvent.click(getByRole("button", { name: /Neutral/ })); // 12 -> 2 pages
    const current = getByRole("button", { name: "1" });
    expect(current.getAttribute("aria-current")).toBe("page");
  });

  it("the type filter shows posts only, comments only, or both", () => {
    const { container, getByRole } = mount();
    const kinds = () => [...container.querySelectorAll(".doc-type-tag")]
      .map((t) => t.getAttribute("data-doc"));

    fireEvent.click(getByRole("button", { name: /^Posts/ }));
    expect(kinds()).toHaveLength(4);
    expect(kinds().every((k) => k === "post_body")).toBe(true);

    fireEvent.click(getByRole("button", { name: /^Comments/ }));
    expect(kinds().every((k) => k === "comment")).toBe(true);

    fireEvent.click(getByRole("button", { name: /^All/ }));
    expect(container.querySelectorAll(".mention-card")).toHaveLength(10);
  });

  it("the type filter counts the whole corpus, not the visible window", () => {
    const { getByRole } = mount({ docTypeTotals: { posts: 5, comments: 20 } });
    // docTypeTotals says 5 posts / 20 comments while the rail holds 4 and 21.
    // The button must read the corpus: a filter that counts its own window
    // tells a reader the window is everything.
    expect(getByRole("button", { name: /^Posts/ }).textContent).toContain("5");
    expect(getByRole("button", { name: /^Comments/ }).textContent).toContain("20");
  });

  it("says the list is a window and how far collection reaches back", () => {
    // 25 cards standing for 34,000 mentions is the shape every real company
    // page has; the note exists so the page never implies otherwise.
    const { container } = mount({ totalMentions: 34287 });
    const note = container.querySelector(".rail-note")?.textContent ?? "";
    expect(note).toContain("25 most recent");
    expect(note).toContain("34,287 mentions");
    expect(note).toContain("2026-01-01");
  });

  it("says so when unclassified mentions are big enough to move the bar", () => {
    const { container } = mount({ unlabelled: 12 });     // 12 of 25 = 48%
    expect(container.textContent).toContain("still being classified");
    const quiet = mount({ unlabelled: 1 });              // 1 of 25 = 4%
    expect(quiet.container.textContent).not.toContain("still being classified");
  });

  it("sort order flips", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: /^Oldest/ }));
    const times = [...container.querySelectorAll(".mention-card time")]
      .map((t) => t.getAttribute("datetime"));
    expect(times[0]! <= times[1]!).toBe(true);
  });
});
