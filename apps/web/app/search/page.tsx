"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import ExploreView, { type SocialAccountItem } from "../../components/reference-ui/ExploreView";
import type { PostItem } from "../../lib/reference-store";
type SearchItem = { id: string; body: string; content_type: string; owner_id: string; published_at?: string | null; created_at: string; creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null }; engagement?: { likes: number; comments: number; saves: number; shares: number }; viewer_reaction?: string | null; saved?: boolean };
type Trend = { topic: string; content_count: number; example_content_id: string };
type Recommendation = SearchItem;
type Creator = { id: string; username?: string | null; display_name: string; avatar_url?: string | null; bio?: string; public_post_count: number; is_ai: boolean };
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
  const [creators, setCreators] = useState<Creator[]>([]);
  const [creatorsBusy, setCreatorsBusy] = useState(false);
  const [creatorsError, setCreatorsError] = useState("");
  const [followedAccountIds, setFollowedAccountIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [authPrompt, setAuthPrompt] = useState("");
  const lastUrlQuery = useRef<string | null>(null);\n  const searchRequestSequence = useRef(0);

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) setSession(data.session); });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; searchRequestSequence.current += 1; data.subscription.unsubscribe(); };
  }, [supabase]);

  async function loadTrends() {
    setTrendsBusy(true); setTrendsError("");
    try {
      const response = await fetch(apiBase + "/v1/trends?limit=10", { headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store" });
      const payload = await response.json() as Payload<Trend>;
      if (!response.ok) throw new Error(payload.error?.message || "Tren belum dapat dimuat.");
      setTrends(payload.items || []);
    } catch (cause) { setTrendsError(cause instanceof Error ? cause.message : "Tren belum dapat dimuat."); }
    finally { setTrendsBusy(false); }
  }

  async function loadRecommendations() {
    setRecommendationsBusy(true); setRecommendationsError("");
    try {
      const response = await fetch(apiBase + "/v1/recommendations?limit=10", { headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store" });
      const payload = await response.json() as Payload<Recommendation>;
      if (!response.ok) throw new Error(payload.error?.message || "Rekomendasi belum dapat dimuat.");
      setRecommendations(payload.items || []);
    } catch (cause) { setRecommendationsError(cause instanceof Error ? cause.message : "Rekomendasi belum dapat dimuat."); }
    finally { setRecommendationsBusy(false); }
  }

  async function loadCreators() {
    setCreatorsBusy(true); setCreatorsError("");
    try {
      const response = await fetch(apiBase + "/v1/recommendations/creators?limit=20", {
        headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store",
      });
      const payload = await response.json() as Payload<Creator>;
      if (!response.ok) throw new Error(payload.error?.message || "Rekomendasi akun belum dapat dimuat.");
      setCreators(payload.items || []);
    } catch (cause) {
      setCreatorsError(cause instanceof Error ? cause.message : "Rekomendasi akun belum dapat dimuat.");
      setCreators([]);
    } finally { setCreatorsBusy(false); }
  }

  useEffect(() => {
    void loadTrends();
    void loadRecommendations();
    void loadCreators();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.access_token]);

  const runSearch = useCallback(async (event?: FormEvent, value = query) => {
    event?.preventDefault();
    if (value.trim().length < 2) { setError("Masukkan minimal 2 karakter."); return; }
    const sequence = ++searchRequestSequence.current;
    setBusy(true); setError(""); setSearched(true);
    try {
      const response = await fetch(apiBase + "/v1/search?q=" + encodeURIComponent(value.trim()) + "&limit=30", {
        headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store",
      });
      const payload = await response.json() as Payload<SearchItem>;
      if (!response.ok) throw new Error(payload.error?.message || "Pencarian gagal.");
      if (sequence !== searchRequestSequence.current) return;
      setItems(payload.items || []);
    } catch (cause) {
      if (sequence !== searchRequestSequence.current) return;
      setError(cause instanceof Error ? cause.message : "Pencarian gagal.");
      setItems([]);
    } finally { if (sequence === searchRequestSequence.current) setBusy(false); }
  }, [query, session]);

  const urlQuery = searchParams.get("q")?.trim().slice(0, 100) ?? "";

  useEffect(() => {
    if (!urlQuery || urlQuery.length < 2) {
      lastUrlQuery.current = null;
      return;
    }
    if (lastUrlQuery.current === urlQuery) return;
    lastUrlQuery.current = urlQuery;
    setQuery(urlQuery);
    void runSearch(undefined, urlQuery);
  }, [session, urlQuery, runSearch]);

  const accountsForReference: SocialAccountItem[] = creators.map(item => ({
    id: item.id,
    name: item.display_name || item.username || "Kreator",
    handle: item.username || "",
    avatar: item.avatar_url || "/icon.svg",
    isAi: item.is_ai,
    specialty: "Kreator publik",
    bio: item.bio || "",
    publicPostCount: item.public_post_count,
    tags: [],
  }));

  const postsForReference: PostItem[] = items.map(item => ({
    id: item.id,
    humanOwner: { name: item.creator?.display_name || item.creator?.username || "Kreator", handle: item.creator?.username || "", avatar: item.creator?.avatar_url || "", verified: false },
    aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
    takeoverMode: false,
    timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
    content: item.body,
    tags: [],
    likes: item.engagement?.likes ?? 0,
    commentsCount: item.engagement?.comments ?? 0,
    reposts: item.engagement?.shares ?? 0,
    isLiked: Boolean(item.viewer_reaction),
    isBookmarked: Boolean(item.saved),
    comments: [],
  }));

  const recommendationsForReference: PostItem[] = recommendations.map(item => ({
    id: item.id,
    humanOwner: { name: "Kreator", handle: "", avatar: "", verified: false },
    aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
    takeoverMode: false,
    timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
    content: item.body,
    tags: [],
    likes: item.engagement?.likes ?? 0,
    commentsCount: item.engagement?.comments ?? 0,
    reposts: item.engagement?.shares ?? 0,
    isLiked: Boolean(item.viewer_reaction),
    isBookmarked: Boolean(item.saved),
    comments: [],
  }));

  return <>
    {!session && <section className="mx-auto mt-3 max-w-xl rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]"><p className="text-xs font-black text-slate-950">{authPrompt || "Jelajahi konten publik. Masuk untuk personalisasi dan interaksi."}</p><div className="mt-2 flex gap-2"><a href={"/login?next=" + encodeURIComponent("/search")} className="rounded-xl border-2 border-slate-900 bg-sky-300 px-3 py-2 text-xs font-black text-slate-950">Masuk</a><a href={"/login?next=" + encodeURIComponent("/search")} className="rounded-xl border-2 border-slate-900 px-3 py-2 text-xs font-black text-slate-950">Daftar</a></div></section>}
      <ExploreView
        posts={postsForReference}
        trendsData={trends}
        accountsData={accountsForReference}
        accountsLoading={creatorsBusy}
        accountsError={creatorsError}
        onRetryAccounts={() => { void loadCreators(); }}
        followedAccountIds={followedAccountIds}
        onFollowAccount={async (accountId, currentlyFollowed) => {
          if (!session) { setAuthPrompt("Masuk untuk mengikuti kreator ini."); return; }
          try {
            const response = await fetch(apiBase + "/v1/social/follow/" + encodeURIComponent(accountId), {
              method: currentlyFollowed ? "DELETE" : "PUT",
              headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" },
              cache: "no-store",
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload?.detail?.message || "Status mengikuti akun tidak dapat diubah.");
            setFollowedAccountIds(previous => currentlyFollowed ? previous.filter(id => id !== accountId) : [...new Set([...previous, accountId])]);
            setAuthPrompt("");
          } catch (cause) { setAuthPrompt(cause instanceof Error ? cause.message : "Status mengikuti akun tidak dapat diubah."); }
        }}
        trendsLoading={trendsBusy}
        trendsError={trendsError}
        recommendationsData={recommendationsForReference}
        recommendationsLoading={recommendationsBusy}
        recommendationsError={recommendationsError}
        productionMode
        onOpenMarketplace={() => { window.location.assign("/marketplace"); }}
        onOpenStoreAndBoothModal={() => { window.location.assign("/profile?open=store"); }}
        initialSearchQuery={query}
        searchLoading={busy}
        searchError={error}
        searchEmpty={searched && !busy && !error && items.length === 0}
        searchPrompt={!searched && !busy && !error}
        onRetrySearch={() => { void runSearch(undefined, query); }}
        onRetryTrends={() => { void loadTrends(); }}
        onRetryRecommendations={() => { void loadRecommendations(); }}
        onSearch={value => { setQuery(value); void runSearch(undefined, value); }}
        onOpenAskAi={(agentName) => { if (!session) { setAuthPrompt("Masuk untuk menggunakan Tanya AI Agent."); return; } window.location.assign("/ask-ai?agent=" + encodeURIComponent(agentName)); }}
        onOpenWorld3D={() => { if (!session) { setAuthPrompt("Masuk untuk memasuki Universe 3D."); return; } window.location.assign("/spatial/navigation"); }}
        onOpenLiveStage={() => { if (!session) { setAuthPrompt("Masuk untuk bergabung dengan Live Stage."); return; } window.location.assign("/live"); }}
        onOpenFilmAi={() => { window.location.assign("/ai-cinema"); }}
      />
  </>;
}

export default function SearchPage() {
  return (
    <Suspense fallback={<main className="min-h-[70dvh] bg-sky-50 px-4 py-8 text-center text-sm font-semibold text-slate-600" role="status">Menyiapkan pencarian…</main>}>
      <SearchPageContent />
    </Suspense>
  );
}
