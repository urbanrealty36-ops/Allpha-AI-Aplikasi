"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type FeedMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type FeedItem = {
  id: string; owner_id: string; body: string; content_type: string; visibility: string;
  published_at?: string | null; created_at: string; media?: FeedMedia[];
  engagement?: { likes: number; comments: number; saves: number; shares?: number };
  viewer_reaction?: string | null; saved?: boolean; ranking_signals?: string[];
};
type FeedComment = { id: string; actor_user_id: string; body: string; created_at: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function errorMessage(response: Response) {
  try { const body = await response.json(); return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function FeedPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [mode, setMode] = useState<"for_you" | "recent">("for_you");
  const [personalizationEnabled, setPersonalizationEnabled] = useState(true);
  const [comments, setComments] = useState<Record<string, FeedComment[]>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const [commentsOpen, setCommentsOpen] = useState<Record<string, boolean>>({});
  const [reportReasons, setReportReasons] = useState<Record<string, "spam" | "harassment" | "privacy" | "misinformation" | "other">>({});
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Masuk terlebih dahulu untuk membuka feed personal.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const loadFeed = useCallback(async (reset = true, nextCursor?: string | null) => {
    if (!session) return;
    setLoading(true); setError("");
    try {
      const sharedContentId = reset && typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("content") : null;
      if (sharedContentId) {
        const direct = await request("/v1/feed/item/" + encodeURIComponent(sharedContentId)) as { item: FeedItem };
        setItems([direct.item]); setCursor(null); return;
      }
      const params = new URLSearchParams({ mode, limit: "20" });
      if (!reset && nextCursor) params.set("cursor", nextCursor);
      const data = await request("/v1/feed?" + params.toString()) as { items?: FeedItem[]; next_cursor?: string | null; mode?: string; personalization_enabled?: boolean };
      setItems(current => reset ? (data.items ?? []) : [...current, ...(data.items ?? [])]);
      setCursor(data.next_cursor ?? null);
      if (typeof data.personalization_enabled === "boolean") setPersonalizationEnabled(data.personalization_enabled);
      if (data.mode === "for_you" || data.mode === "recent") setMode(data.mode);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Feed tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [mode, request, session]);

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session) return;
    void (async () => {
      try {
        const prefs = await request("/v1/feed/preferences") as { preferences?: { personalization_enabled?: boolean; ranking_mode?: "for_you" | "recent" } };
        if (typeof prefs.preferences?.personalization_enabled === "boolean") setPersonalizationEnabled(prefs.preferences.personalization_enabled);
        if (prefs.preferences?.ranking_mode) setMode(prefs.preferences.ranking_mode);
      } catch (cause) { setError(cause instanceof Error ? cause.message : "Preferensi feed tidak dapat dimuat."); }
    })();
  }, [request, session]);

  useEffect(() => { if (session) void loadFeed(true); }, [session, mode, loadFeed]);

  async function savePreferences(enabled: boolean, rankingMode = mode) {
    setBusyKey("preferences"); setError(""); setNotice("");
    try {
      await request("/v1/feed/preferences", { method: "PUT", body: JSON.stringify({ personalization_enabled: enabled, ranking_mode: rankingMode }) });
      setPersonalizationEnabled(enabled); setMode(rankingMode); setNotice("Preferensi feed disimpan."); await loadFeed(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Preferensi feed gagal disimpan."); }
    finally { setBusyKey(""); }
  }

  async function toggleReaction(item: FeedItem) {
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", item.viewer_reaction
        ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ reaction: "like" }) });
      await loadFeed(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reaksi gagal disimpan."); }
    finally { setBusyKey(""); }
  }

  async function toggleSave(item: FeedItem) {
    setBusyKey(item.id); setError(""); setNotice("");
    try { await request("/v1/feed/" + encodeURIComponent(item.id) + "/save", { method: item.saved ? "DELETE" : "PUT" }); await loadFeed(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Simpan konten gagal."); }
    finally { setBusyKey(""); }
  }

  async function openComments(item: FeedItem) {
    const opening = !commentsOpen[item.id];
    setCommentsOpen(current => ({ ...current, [item.id]: opening }));
    if (!opening || comments[item.id]) return;
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/comments") as { items?: FeedComment[] };
      setComments(current => ({ ...current, [item.id]: data.items ?? [] }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar tidak dapat dimuat."); }
  }

  async function submitComment(item: FeedItem) {
    const body = (commentDrafts[item.id] ?? "").trim();
    if (!body) return;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/comments", { method: "POST", body: JSON.stringify({ body }) }) as { comment: FeedComment };
      setComments(current => ({ ...current, [item.id]: [...(current[item.id] ?? []), data.comment] }));
      setCommentDrafts(current => ({ ...current, [item.id]: "" }));
      setItems(current => current.map(row => row.id === item.id ? { ...row, engagement: { likes: row.engagement?.likes ?? 0, saves: row.engagement?.saves ?? 0, comments: (row.engagement?.comments ?? 0) + 1 } } : row));
      setNotice("Komentar ditambahkan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar gagal dikirim."); }
    finally { setBusyKey(""); }
  }

  async function report(item: FeedItem) {
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/report", { method: "POST", body: JSON.stringify({ reason: reportReasons[item.id] ?? "other" }) });
      setNotice("Laporan diterima untuk ditinjau.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Laporan gagal dikirim."); }
    finally { setBusyKey(""); }
  }

  async function share(item: FeedItem) {
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/share", {
        method: "POST", body: JSON.stringify({ share_target: "copy_link" }),
      }) as { share_url: string };
      try {
        await navigator.clipboard.writeText(data.share_url);
        setNotice("Tautan konten disalin.");
      } catch {
        setNotice("Tautan untuk dibagikan: " + data.share_url);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Tautan berbagi gagal dibuat."); }
    finally { setBusyKey(""); }
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-4 py-6 text-slate-900 dark:text-slate-100 sm:px-6">
      <nav className="mb-6 flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-4"><Link href="/" className="text-sm text-blue-600 hover:underline">← Allpha</Link><Link href="/create" className="text-sm font-semibold text-cyan-600 hover:underline">＋ Buat konten</Link><Link href="/stories" className="text-sm font-semibold text-cyan-600 hover:underline">Stories & Moments</Link><Link href="/reels" className="text-sm font-semibold text-cyan-600 hover:underline">Reels video/audio →</Link></div>
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ENG-P14 · Social Feed</span>
      </nav>
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">Allpha Universe</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Feed sosial</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Konten publik yang telah disetujui, dengan ranking yang dapat Anda kendalikan.</p>
      </header>
      {!session ? <section className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><p className="mb-3 text-sm">Masuk untuk melihat feed personal, memberi reaksi, menyimpan, dan berkomentar.</p><Link className="font-semibold text-blue-600 hover:underline" href="/">Masuk melalui Allpha</Link></section> : <>
        <section className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold">Kontrol feed</h2><p className="mt-1 text-xs text-slate-500">Matikan personalisasi kapan saja.</p></div>
            <select aria-label="Mode ranking feed" className="rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-600" value={mode} onChange={e => void savePreferences(personalizationEnabled, e.target.value as "for_you" | "recent")} disabled={busyKey === "preferences"}>
              <option value="for_you">Untuk Anda</option><option value="recent">Terbaru</option>
            </select>
          </div>
          <label className="mt-4 flex items-center gap-3 text-sm"><input type="checkbox" checked={personalizationEnabled} onChange={e => void savePreferences(e.target.checked, mode)} disabled={busyKey === "preferences"} /> Personalisasi feed aktif</label>
        </section>
        {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 p-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
        {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-300 p-3 text-sm text-emerald-800 dark:text-emerald-200">{notice}</p>}
        {loading && <p className="py-8 text-center text-sm text-slate-500">Memuat feed…</p>}
        {!loading && items.length === 0 && <section className="rounded-2xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><h2 className="font-semibold">Belum ada konten publik</h2><p className="mt-2 text-sm text-slate-500">Konten akan muncul setelah disetujui melalui moderasi.</p></section>}
        <div className="space-y-4">
          {items.map(item => <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-3 flex items-start justify-between gap-3"><div><p className="text-xs text-slate-500">Creator · {item.owner_id.slice(0, 8)}</p><time className="mt-1 block text-xs text-slate-500">{new Date(item.published_at ?? item.created_at).toLocaleString()}</time></div><div className="flex items-center gap-2"><select aria-label="Alasan laporan konten" className="max-w-40 rounded-lg border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-600" value={reportReasons[item.id] ?? "other"} onChange={e => setReportReasons(current => ({ ...current, [item.id]: e.target.value as "spam" | "harassment" | "privacy" | "misinformation" | "other" }))}><option value="spam">Spam</option><option value="harassment">Pelecehan</option><option value="privacy">Privasi</option><option value="misinformation">Misinformasi</option><option value="other">Lainnya</option></select><button className="text-xs text-slate-500 hover:text-red-600" onClick={() => void report(item)} disabled={busyKey === item.id}>Laporkan</button></div></div>
            {item.body && <p className="whitespace-pre-wrap break-words text-sm leading-6">{item.body}</p>}
            {item.media?.map(media => media.preview_url && (media.media_type.startsWith("video/") ? <video key={media.id} src={media.preview_url} controls playsInline preload="metadata" className="mt-3 max-h-[480px] w-full rounded-xl bg-black" /> : media.media_type.startsWith("audio/") ? <audio key={media.id} src={media.preview_url} controls preload="metadata" className="mt-3 w-full" aria-label={media.filename} /> : <img key={media.id} src={media.preview_url} alt={media.filename} className="mt-3 max-h-[480px] w-full rounded-xl object-contain" />))}
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
              <button className={"rounded-full border px-3 py-2 text-sm " + (item.viewer_reaction ? "border-blue-500 text-blue-600" : "border-slate-300 dark:border-slate-600")} onClick={() => void toggleReaction(item)} disabled={busyKey === item.id}>♥ {item.engagement?.likes ?? 0}</button>
              <button className={"rounded-full border px-3 py-2 text-sm " + (item.saved ? "border-blue-500 text-blue-600" : "border-slate-300 dark:border-slate-600")} onClick={() => void toggleSave(item)} disabled={busyKey === item.id}>{item.saved ? "Tersimpan" : "Simpan"} · {item.engagement?.saves ?? 0}</button>
              <button className="rounded-full border border-slate-300 px-3 py-2 text-sm dark:border-slate-600" onClick={() => void openComments(item)}>{commentsOpen[item.id] ? "Tutup komentar" : "Komentar"} · {item.engagement?.comments ?? 0}</button>
              <button className="rounded-full border border-slate-300 px-3 py-2 text-sm dark:border-slate-600" onClick={() => void share(item)} disabled={busyKey === item.id}>Bagikan · {item.engagement?.shares ?? 0}</button>
            </div>
            {commentsOpen[item.id] && <div className="mt-3 space-y-3">
              {(comments[item.id] ?? []).map(comment => <div key={comment.id} className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800"><p className="mb-1 text-xs text-slate-500">{comment.actor_user_id.slice(0, 8)} · {new Date(comment.created_at).toLocaleString()}</p><p className="whitespace-pre-wrap">{comment.body}</p></div>)}
              <form className="flex gap-2" onSubmit={e => { e.preventDefault(); void submitComment(item); }}>
                <input aria-label="Tulis komentar" className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-600" value={commentDrafts[item.id] ?? ""} onChange={e => setCommentDrafts(current => ({ ...current, [item.id]: e.target.value }))} maxLength={2000} placeholder="Tulis komentar…" />
                <button className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900" disabled={busyKey === item.id || !(commentDrafts[item.id] ?? "").trim()}>Kirim</button>
              </form>
            </div>}
          </article>)}
        </div>
        {cursor && <button className="mt-6 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold disabled:opacity-50 dark:border-slate-600" onClick={() => void loadFeed(false, cursor)} disabled={loading}>Muat konten berikutnya</button>}
      </>}
    </main>
  );
}
