"use client";

import { useEffect, useState } from "react";

/**
 * "Data refreshed 3 October 2026": the date of the last successful daily sweep.
 *
 * Read from /freshness.json in the browser rather than rendered into each page, because every page shows
 * it and it changes daily: baked into the HTML it would force all 6,000 pages to regenerate every night,
 * each with a database read, to change one line. The file is one static response the sweep refreshes.
 * Until it loads, and with scripts off, the line is simply absent.
 */
export function Freshness() {
  const [iso, setIso] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    fetch("/freshness.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { refreshedAt?: string | null } | null) => {
        if (live && j?.refreshedAt) setIso(j.refreshedAt);
      })
      .catch(() => {});
    return () => { live = false; };
  }, []);
  if (!iso) return null;
  const day = new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
  return (
    <p className="venture-fresh">
      Data refreshed <time dateTime={iso}>{day}</time>
    </p>
  );
}
