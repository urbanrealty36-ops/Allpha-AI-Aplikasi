import { redirect } from "next/navigation";

type ExplorePageProps = {
  searchParams: Promise<{ q?: string | string[] }>;
};

/**
 * Canonical Explore entry point.
 *
 * Search, trends and recommendations already use the authenticated FastAPI
 * contracts in /search. Keep /explore as a stable reference-navigation route
 * without duplicating the search implementation or importing sample data.
 */
export default async function ExplorePage({ searchParams }: ExplorePageProps) {
  const params = await searchParams;
  const rawQuery = Array.isArray(params.q) ? params.q[0] : params.q;
  const query = rawQuery?.trim();
  redirect(query ? `/search?q=${encodeURIComponent(query)}` : "/search");
}
