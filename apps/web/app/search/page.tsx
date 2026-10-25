"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import ExploreView from "../../components/reference-ui/ExploreView";
import type { PostItem } from "../../lib/reference-store";
type SearchItem = { id: string; body: string; content_type: string; owner_id: string; published_at?: string | null; created_at: string };
type Trend = { topic: string; content_count: number; example_content_id: string };
type Recommendation = SearchItem;
type Payload<T> = { items: T[]; query?: string; count?: number; has_more?: boolean; error?: { message?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

function SearchPageContent() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const searchParams = useSearchParams();
  const [session, setSession] = useState<Session | null>(null);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchItem[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [trendsBusy, setTrendsBusy] = useState(false);
  const [trendsError, setTrendsError] = useState("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recommendationsBusy, setRecommendationsBusy] = useState(false);
  const [recommendationsError, setRecommendationsError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const lastUrlQuery = useRef<string | null>(null);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  async function loadTrends() {
    if (!session) { setTrends([]); setTrendsError(""); return; }
    setTrendsBusy(true); setTrendsError("");
    try {
      const response = await fetch(apiBase + "/v1/trends?limit=10", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const payload = await response.json() as Payload<Trend>;
      if (!response.ok) throw new Error(payload.error?.message || "Tren belum dapat dimuat.");
      setTrends(payload.items || []);
    } catch (cause) { setTrendsError(cause instanceof Error ? cause.message : "Tren belum dapat dimuat."); }
    finally { setTrendsBusy(false); }
  }

  async function loadRecommendations() {
    if (!session) { setRecommendations([]); setRecommendationsError(""); return; }
    setRecommendationsBusy(true); setRecommendationsError("");
    try {
      const response = await fetch(apiBase + "/v1/recommendations?limit=10", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const payload = await response.json() as Payload<Recommendation>;
      if (!response.ok) throw new Error(payload.error?.message || "Rekomendasi belum dapat dimuat.");
      setRecommendations(payload.items || []);
    } catch (cause) { setRecommendationsError(cause instanceof Error ? cause.message : "Rekomendasi belum dapat dimuat."); }
    finally { setRecommendationsBusy(false); }
  }

  useEffect(() => {
    if (!session) {
      setTrends([]); setTrendsError(""); setRecommendations([]); setRecommendationsError("");
      return;
    }
    void loadTrends();
    void loadRecommendations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.access_token]);

  const runSearch = useCallback(async (event?: FormEvent, value = query) => {
    event?.preventDefault();
    if (!session) { setError("Silakan masuk untuk mencari konten."); return; }
    if (value.trim().length < 2) { setError("Masukkan minimal 2 karakter."); return; }
    setBusy(true); setError(""); setSearched(true);
    try {
      const response = await fetch(apiBase + "/v1/search?q=" + encodeURIComponent(value.trim()) + "&limit=30", {
        headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store",
      });
      const payload = await response.json() as Payload<SearchItem>;
      if (!response.ok) throw new Error(payload.error?.message || "Pencarian gagal.");
      setItems(payload.items || []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Pencarian gagal.");
      setItems([]);
    } finally { setBusy(false); }
  }, [query, session]);

  const urlQuery = searchParams.get("q")?.trim().slice(0, 100) ?? "";

  useEffect(() => {
    if (!session) return;
    if (!urlQuery || urlQuery.length < 2) {
      lastUrlQuery.current = null;
      return;
    }
    if (lastUrlQuery.current === urlQuery) return;
    lastUrlQuery.current = urlQuery;
    setQuery(urlQuery);
    void runSearch(undefined, urlQuery);
  }, [session, urlQuery, runSearch]);

  const postsForReference: PostItem[] = items.map(item => ({
    id: item.id,
    humanOwner: { name: "Kreator", handle: "", avatar: "", verified: false },
    aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
    takeoverMode: false,
    timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
    content: item.body,
    tags: [],
    likes: 0,
    commentsCount: 0,
    reposts: 0,
    comments: [],
  }));

  const recommendationsForReference: PostItem[] = recommendations.map(item => ({
    id: item.id,
    humanOwner: { name: "Pengguna " + item.owner_id.slice(0, 8), handle: "@" + item.owner_id.slice(0, 8), avatar: "", verified: false },
    aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
    takeoverMode: false,
    timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
    content: item.body,
    tags: [],
    likes: 0,
    commentsCount: 0,
    reposts: 0,
    comments: [],
  }));

  return <>
    {!session ? <main className="min-h-[70dvh] bg-sky-50 px-4 py-8"><div className="mx-auto max-w-xl rounded-3xl border-2 border-slate-900 bg-white p-6 text-center shadow-[3px_3px_0px_#0f172a]"><h1 className="text-base font-black text-slate-950">Jelajahi & Cari</h1><p className="my-3 text-sm text-slate-600">Masuk untuk mencari konten, melihat tren, dan rekomendasi personal.</p><a href="/login" className="inline-flex rounded-2xl border-2 border-slate-900 bg-sky-300 px-4 py-2 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a]">Masuk</a></div></main> : <>
      <ExploreView
        posts={postsForReference}
        trendsData={trends}
        trendsLoading={trendsBusy}
        trendsError={trendsError}
        recommendationsData={recommendationsForReference}
        recommendationsLoading={recommendationsBusy}
        recommendationsError={recommendationsError}
        productionMode
        initialSearchQuery={query}
        searchLoading={busy}
        searchError={error}
        searchEmpty={searched && !busy && !error && items.length === 0}
        searchPrompt={!searched && !busy && !error}
        onSearch={value => { setQuery(value); void runSearch(undefined, value); }}
        onOpenAskAi={(agentName) => { window.location.assign("/ask-ai?agent=" + encodeURIComponent(agentName)); }}
        onOpenWorld3D={() => { window.location.assign("/spatial/navigation"); }}
        onOpenLiveStage={() => { window.location.assign("/live"); }}
        onOpenFilmAi={() => { window.location.assign("/ai-cinema"); }}
      />
    </>}
  </>;
}

export default function SearchPage() {
  return (
    <Suspense fallback={<main className="min-h-[70dvh] bg-sky-50 px-4 py-8 text-center text-sm font-semibold text-slate-600" role="status">Menyiapkan pencarian…</main>}>
      <SearchPageContent />
    </Suspense>
  );
}
