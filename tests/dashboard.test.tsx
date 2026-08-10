import { describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { CompanyDashboard } from "@/components/company/company-dashboard";
import type { Mention } from "@/components/data/mention-card";
import type { SubredditStat } from "@/lib/data/types";

const mk = (over: Partial<Mention>): Mention => ({
  brandName: "HubSpot", brandSlug: "hubspot", subreddit: "sales", author: "a",
  createdUtc: "2026-01-01T00:00:00.000Z", sentiment: "neu", docType: "comment",
  matchedForm: "hubspot", body: "body about HubSpot",
  permalink: "https://www.reddit.com/r/sales/comments/abc/x/1/",
  ...over,
});

const mentions: Mention[] = [
  mk({ sentiment: "pos", subreddit: "sales", createdUtc: "2026-03-01T00:00:00.000Z",
       permalink: "https://www.reddit.com/r/sales/comments/a1/x/p1/" }),
  mk({ sentiment: "neg", subreddit: "crm", createdUtc: "2026-02-01T00:00:00.000Z",
       permalink: "https://www.reddit.com/r/crm/comments/a2/x/p2/" }),
  mk({ sentiment: "neu", subreddit: "sales", createdUtc: "2026-01-01T00:00:00.000Z",
       permalink: "https://www.reddit.com/r/sales/comments/a3/x/p3/" }),
];

const stats: SubredditStat[] = [
  { subreddit: "sales", total: 2, pos: 1, neg: 0, neu: 1, newest: "2026-03-01T00:00:00.000Z" },
  { subreddit: "crm", total: 1, pos: 0, neg: 1, neu: 0, newest: "2026-02-01T00:00:00.000Z" },
];

function mount() {
  return render(
    <CompanyDashboard
      mentions={mentions}
      subredditStats={stats}
      totals={{ pos: 1, neg: 1, neu: 1 }}
      totalMentions={3}
    />,
  );
}

describe("company dashboard island", () => {
  it("renders every card by default, newest first — no effect needed", () => {
    const { container } = mount();
    const cards = container.querySelectorAll(".mention-card");
    expect(cards).toHaveLength(3);
    const times = [...container.querySelectorAll(".mention-card time")]
      .map((t) => t.getAttribute("datetime"));
    expect(times[0]).toBe("2026-03-01T00:00:00.000Z");
  });

  it("filters by sentiment", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: /Negative/ }));
    const cards = container.querySelectorAll(".mention-card");
    expect(cards).toHaveLength(1);
    expect(cards[0]?.getAttribute("data-sentiment")).toBe("neg");
  });

  it("filters by subreddit via the ledger and clears", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: "r/crm" }));
    expect(container.querySelectorAll(".mention-card")).toHaveLength(1);
    // active row highlighted
    expect(container.querySelector(".sub-ledger tr[data-active]")).not.toBeNull();
    // clear chip
    fireEvent.click(getByRole("button", { name: /r\/crm ✕/ }));
    expect(container.querySelectorAll(".mention-card")).toHaveLength(3);
  });

  it("flips sort order", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: "Oldest" }));
    const times = [...container.querySelectorAll(".mention-card time")]
      .map((t) => t.getAttribute("datetime"));
    expect(times[0]).toBe("2026-01-01T00:00:00.000Z");
  });

  it("stacks filters (sentiment + subreddit)", () => {
    const { container, getByRole } = mount();
    fireEvent.click(getByRole("button", { name: "r/sales" }));
    fireEvent.click(getByRole("button", { name: /Positive/ }));
    const cards = container.querySelectorAll(".mention-card");
    expect(cards).toHaveLength(1);
    expect(cards[0]?.getAttribute("data-sentiment")).toBe("pos");
  });
});
