import { getSnapshot } from "@/lib/data/snapshot";
import { buildBoards } from "@/lib/data/boards";
import { buildSearchIndex } from "@/lib/data/search-index";
import { IndexPage } from "@/components/pages/index-page";

export const dynamic = "force-static";
export const revalidate = 86400;

export default async function Home() {
  const snap = await getSnapshot();
  return <IndexPage data={buildBoards(snap)} scope="all" search={buildSearchIndex(snap)} />;
}
