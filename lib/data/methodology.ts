import "server-only";
import { METHODOLOGY_VERSION } from "@/lib/format";
import { getMethodologyParamRows } from "./site-db";

export type MethodologyParam = {
  version: string;
  scope: string;
  key: string;
  value: unknown;
  rationale: string;
  gitCommit: string;
};

/**
 * Read the frozen constants straight from the append-only table, so /methodology cannot drift from the
 * code that actually ran. 07 §9's audit trail is only an audit trail if a reader can see it.
 *
 * The table is append-only across versions; the page renders exactly the set the running code uses.
 */
export async function getMethodologyParams(): Promise<MethodologyParam[]> {
  const rows = await getMethodologyParamRows(METHODOLOGY_VERSION);
  return rows.map((r) => ({
    version: String(r.version),
    scope: String(r.scope),
    key: String(r.key),
    value: r.value,
    rationale: String(r.rationale),
    gitCommit: String(r.git_commit),
  }));
}
