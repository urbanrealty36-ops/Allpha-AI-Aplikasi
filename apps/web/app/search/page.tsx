"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import ReferenceNavigation from "../../components/reference-ui/ReferenceNavigation";

type SearchItem = { id: string; body: string; content_type: string; owner_id: string; published_at?: string | null; created_at: string };
type Trend = { topic: string; content_count: number; example_content_id: string };
type Recommendation = SearchItem;
type Payload<T> = { items: T[]; query?: string; count?: number; has_more?: boolean; error?: { message?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

export default function SearchPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
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
  const initialQueryHandled = useRef(false);

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

  useEffect(() => {
    if (!session || initialQueryHandled.current) return;
    const initialQuery = new URLSearchParams(window.location.search).get("q")?.trim().slice(0, 100);
    initialQueryHandled.current = true;
    if (!initialQuery || initialQuery.length < 2) return;
    setQuery(initialQuery);
    void runSearch(undefined, initialQuery);
  }, [session, runSearch]);

  return <>
    <ReferenceNavigation />
    <main className="allpha-page allpha-search-page" style={{ maxWidth: 820, margin: "0 auto", padding: "32px 20px", color: "var(--foreground, #172033)" }}>
    <a href="/" style={{ color: "inherit", textDecoration: "none" }}>← Allpha</a>
    <h1 style={{ fontSize: 32, marginBottom: 8 }}>Search & Discovery</h1>
    <p style={{ lineHeight: 1.6, opacity: .75 }}>Temukan konten yang sudah dipublikasikan dan disetujui. Hasil mengikuti aturan visibilitas, follow, block, dan mute akun Anda.</p>
    {!session && <p role="status">Masuk ke Allpha untuk menggunakan pencarian dan tren personal.</p>}
    <form onSubmit={event => void runSearch(event)} style={{ display: "flex", gap: 8, margin: "22px 0" }}>
      <input aria-label="Cari konten" value={query} onChange={event => setQuery(event.target.value)} minLength={2} maxLength={100} placeholder="Cari topik atau kata kunci…" style={{ flex: 1, minWidth: 0, padding: 14, borderRadius: 12, border: "1px solid #c8cfda", background: "transparent", color: "inherit" }}/>
      <button disabled={busy || !session} type="submit" style={{ padding: "0 18px", borderRadius: 12, border: 0, fontWeight: 700 }}>{busy ? "Mencari…" : "Cari"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {searched && !busy && !error && items.length === 0 && <p>Belum ada konten yang cocok dengan kata kunci tersebut.</p>}
    <section aria-label="Hasil pencarian">
      {items.map(item => <article key={item.id} style={{ padding: "16px 0", borderBottom: "1px solid #d8dce5" }}>
        <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.65, margin: "0 0 8px" }}>{item.body}</p>
        <small style={{ opacity: .65 }}>{item.content_type} · {item.published_at ? new Date(item.published_at).toLocaleString() : new Date(item.created_at).toLocaleString()}</small>
      </article>)}
    </section>
    <section style={{ marginTop: 36 }}>
      <h2 style={{ fontSize: 22 }}>Tren dari konten terbaru</h2>
      <p style={{ opacity: .7, lineHeight: 1.5 }}>Topik dihitung dari konten nyata yang dapat Anda lihat, bukan data tren buatan. Cakupan saat ini adalah konten, belum profil atau Agent.</p>
      {trendsBusy ? <p role="status">Memuat tren…</p> : trendsError ? <p role="alert">{trendsError} <button type="button" onClick={() => void loadTrends()}>Coba lagi</button></p> : trends.length ? <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{trends.map(item =>
        <button key={item.topic} type="button" onClick={() => { setQuery(item.topic); void runSearch(undefined, item.topic); }} style={{ border: "1px solid #c8cfda", background: "transparent", color: "inherit", borderRadius: 999, padding: "9px 13px", cursor: "pointer" }}>
          #{item.topic} <small>({item.content_count})</small>
        </button>)}</div> : <p style={{ opacity: .7 }}>Tren akan muncul saat tersedia konten publik yang sesuai dan dapat diakses.</p>}
    </section>
    <section style={{ marginTop: 36 }} aria-label="Rekomendasi konten">
      <h2 style={{ fontSize: 22 }}>Rekomendasi untuk Anda</h2>
      <p style={{ opacity: .7, lineHeight: 1.5 }}>Mengikuti ranking feed kanonis dan pengaturan personalisasi akun Anda.</p>
      {recommendationsBusy ? <p role="status">Memuat rekomendasi…</p> : recommendationsError ? <p role="alert">{recommendationsError} <button type="button" onClick={() => void loadRecommendations()}>Coba lagi</button></p> : recommendations.length ? recommendations.map(item => <article key={item.id} style={{ padding: "16px 0", borderBottom: "1px solid #d8dce5" }}><p style={{ whiteSpace: "pre-wrap", lineHeight: 1.65, margin: "0 0 8px" }}>{item.body}</p><small style={{ opacity: .65 }}>{item.content_type} · {item.published_at ? new Date(item.published_at).toLocaleString() : new Date(item.created_at).toLocaleString()}</small></article>) : <p style={{ opacity: .7 }}>Belum ada rekomendasi yang dapat ditampilkan.</p>}
    </section>
  </main>
  </>;
}
