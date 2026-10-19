"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type SearchItem = { id: string; body: string; content_type: string; owner_id: string; published_at?: string | null; created_at: string };
type Trend = { topic: string; content_count: number; example_content_id: string };
type Payload<T> = { items: T[]; query?: string; count?: number; has_more?: boolean; error?: { message?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

export default function SearchPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchItem[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    if (!session) { setTrends([]); return; }
    let cancelled = false;
    void fetch(apiBase + "/v1/trends?limit=10", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Tren belum dapat dimuat.");
        return response.json() as Promise<Payload<Trend>>;
      }).then(payload => { if (!cancelled) setTrends(payload.items || []); })
      .catch(() => { if (!cancelled) setTrends([]); });
    return () => { cancelled = true; };
  }, [session]);

  async function runSearch(event?: FormEvent, value = query) {
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
  }

  return <main style={{ maxWidth: 820, margin: "0 auto", padding: "32px 20px", color: "var(--foreground, #172033)" }}>
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
      <p style={{ opacity: .7, lineHeight: 1.5 }}>Topik dihitung dari konten nyata yang dapat Anda lihat, bukan data tren buatan.</p>
      {trends.length ? <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{trends.map(item =>
        <button key={item.topic} type="button" onClick={() => { setQuery(item.topic); void runSearch(undefined, item.topic); }} style={{ border: "1px solid #c8cfda", background: "transparent", color: "inherit", borderRadius: 999, padding: "9px 13px", cursor: "pointer" }}>
          #{item.topic} <small>({item.content_count})</small>
        </button>)}</div> : <p style={{ opacity: .7 }}>Tren akan muncul saat tersedia konten publik yang sesuai dan dapat diakses.</p>}
    </section>
  </main>;
}
