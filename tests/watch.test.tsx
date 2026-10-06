import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";

vi.mock("next/navigation", () => ({ usePathname: () => "/", useRouter: () => ({ push: () => {} }), useSearchParams: () => new URLSearchParams() }));

import { CompanyPage } from "@/components/pages/company-page";
import type { CompanyView } from "@/lib/data/types";
import type { Mention } from "@/components/data/mention-card";

// decisions/0020: the closer watch's mentions are shown in their own section, counted in nothing.
const watch: Mention[] = [1, 2, 3].map((i) => ({
  brandName: "DevRev", brandSlug: "devrev", subreddit: "salesengineers", author: `someone${i}`,
  createdUtc: `2026-10-0${i}T00:00:00.000Z`, sentiment: "neu", docType: "comment", matchedForm: "DevRev",
  threadTitle: "SE job opportunity", body: `I came across DevRev ${i}`,
  permalink: `https://www.reddit.com/r/salesengineers/comments/abc/x/c${i}/`,
}));

const zero: CompanyView = {
  slug: "devrev", name: "DevRev", primaryCategorySlug: null, pageScore: null, pageNOp: 0, mentions: [],
  totalMentions: 0, sentimentTotals: { pos: 0, neg: 0, neu: 0 }, docTypeTotals: { posts: 0, comments: 0 },
  unlabelled: 0, oldestMention: null, railSize: 0, subredditStats: [], watchMentions: watch,
};

describe("the closer watch section", () => {
  it("renders on a page with nothing counted yet, marked as counted in nothing, with attribution", () => {
    const { container, getByText } = render(<CompanyPage company={zero} boardRank={null} boardSize={0} />);
    const sec = container.querySelector("#closer-watch");
    expect(sec).not.toBeNull();
    expect(getByText("More mentions, from a closer watch")).toBeTruthy();
    expect(sec!.textContent).toMatch(/not counted in the score, the totals, the subreddit table or the\s+rank/);
    expect(sec!.querySelectorAll("article.mention-card").length).toBe(3);
    expect(sec!.textContent).toContain("from Reddit");
    expect(sec!.querySelector('a[href="https://www.reddit.com/r/salesengineers/comments/abc/x/c1/"]')).not.toBeNull();
  });

  it("is absent for a company that is not watched", () => {
    const { container } = render(<CompanyPage company={{ ...zero, watchMentions: [] }} boardRank={null} boardSize={0} />);
    expect(container.querySelector("#closer-watch")).toBeNull();
  });
});
