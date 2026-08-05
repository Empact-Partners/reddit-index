import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SiteFooter, NON_AFFILIATION } from "@/components/site/site-footer";
import GlobalError from "@/app/global-error";
import ErrorBoundary from "@/app/error";

/**
 * scripts/gates/footer-slot4.mjs walks PRERENDERED HTML, and no error boundary
 * ever prerenders. These cases are the only mechanism that covers them, and
 * global-error.tsx is the dangerous one: it supplies its own <html> and <body>
 * and therefore inherits nothing from the root layout — including the footer,
 * and with it slot 4.
 */
describe("footer slot 4", () => {
  it("ships the non-affiliation notice verbatim", () => {
    render(<SiteFooter />);
    expect(screen.getByText(NON_AFFILIATION)).toBeTruthy();
    expect(NON_AFFILIATION).toBe(
      "Not affiliated with, endorsed by, or sponsored by Reddit, Inc. 'Reddit' is a trademark of Reddit, Inc., used here descriptively.",
    );
  });

  it("renders it at Small size and full opacity, never Micro or dimmed", () => {
    const { container } = render(<SiteFooter />);
    const el = [...container.querySelectorAll("p")].find(
      (p) => p.textContent === NON_AFFILIATION,
    );
    expect(el).toBeTruthy();
    expect(el!.getAttribute("style")).toContain("--fs-small");
    expect(el!.getAttribute("style")).not.toContain("--fs-micro");
    expect(el!.closest("details")).toBeNull();
    expect(el!.closest("[aria-hidden='true']")).toBeNull();
  });

  it("survives global-error.tsx, which replaces the root layout entirely", () => {
    const { container } = render(
      <GlobalError error={new Error("boom")} reset={() => {}} />,
    );
    expect(container.textContent).toContain(NON_AFFILIATION);
  });

  it("is reachable from the route-level error boundary too", () => {
    // error.tsx renders INSIDE the root layout, so its footer comes from there.
    // This asserts the boundary itself renders rather than throwing.
    const { container } = render(
      <ErrorBoundary error={new Error("boom")} reset={() => {}} />,
    );
    expect(container.textContent).toContain("Something broke");
  });
});
