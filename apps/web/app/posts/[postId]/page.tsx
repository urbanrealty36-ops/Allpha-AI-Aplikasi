"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { ArrowLeft, Bookmark, Heart, LoaderCircle, RefreshCw, Share2 } from "lucide-react";
import { getBrowserSupabase } from "../../../lib/supabase";

type FeedMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type FeedItem = {
  id: string; owner_id: string; body: string; content_type: string; visibility: string;
  published_at?: string | null; created_at: string; media?: FeedMedia[];
  engagement?: { likes: number; comments: number; saves: number; shares?: number };
  viewer_reaction?: string | null; saved?: boolean;
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function responseError(response: Response) {
  try { const payload = await response.json(); return payload?.error?.message ?? payload?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function PostDetailPage() {
  const params = useParams<{ postId: string }>();
  const postId = params.postId;
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [item, setItem] = useState<FeedItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Masuk terlebih dahulu untuk membuka konten ini.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await responseError(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const loadPost = useCallback(async () => {
    if (!session || !postId) return;
    setLoading(true); setError(""); setNotice("");
    try {
      const payload = await request("/v1/feed/item/" + encodeURIComponent(postId)) as { item?: FeedItem };
      if (!payload?.item) throw new Error("Konten tidak ditemukan atau tidak dapat diakses.");
      setItem(payload.item);
    } catch (cause) {
      setItem(null);
      setError(cause instanceof Error ? cause.message : "Konten tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, [postId, request, session]);

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => { if (session) void loadPost(); else if (session === null) setLoading(false); }, [session, loadPost]);

  async function mutate(kind: "reaction" | "save" | "share") {
    if (!item) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (kind === "reaction") {
        await request("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", item.viewer_reaction
          ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ reaction: "like" }) });
      } else if (kind === "save") {
        await request("/v1/feed/" + encodeURIComponent(item.id) + "/save", { method: item.saved ? "DELETE" : "PUT" });
      } else {
        await request("/v1/feed/" + encodeURIComponent(item.id) + "/share", { method: "POST", body: JSON.stringify({ channel: "link" }) });
      }
      await loadPost();
      if (kind === "share" && typeof window !== "undefined") {
        await navigator.clipboard?.writeText(window.location.href);
        setNotice("Tautan konten disalin jika izin clipboard tersedia.");
      } else setNotice(kind === "reaction" ? "Reaksi diperbarui." : "Status simpan diperbarui.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Aksi tidak dapat diselesaikan."); }
    finally { setBusy(false); }
  }

  if (!session && !loading) return <main className="mx-auto w-full max-w-2xl px-4 py-10"><section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h1 className="text-xl font-semibold text-slate-950">Masuk untuk melihat konten</h1><p className="mt-2 text-sm text-slate-600">Detail konten mengikuti sesi Allpha dan izin akses yang berlaku.</p><Link className="mt-4 inline-flex rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white" href="/">Masuk ke Allpha</Link></section></main>;

  return <main className="mx-auto w-full max-w-2xl px-4 py-5 sm:py-8">
    <Link href="/feed" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950"><ArrowLeft size={16} /> Kembali ke Feed</Link>
    <header className="mt-5 border-b border-slate-200 pb-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">Allpha · Detail Konten</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Post Detail</h1>
      <p className="mt-1 text-sm text-slate-500">Konten dan status interaksi dimuat dari API Allpha.</p>
    </header>
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><p>{error}</p><button type="button" onClick={() => void loadPost()} className="mt-3 inline-flex items-center gap-2 font-semibold underline"><RefreshCw size={14} /> Coba lagi</button></div>}
    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
    {loading && <div className="mt-6 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600"><LoaderCircle className="animate-spin" size={18} /> Memuat detail konten…</div>}
    {!loading && item && <article className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-4 sm:p-5">
        <div className="flex min-w-0 items-center gap-3"><span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-full bg-blue-50 font-bold text-blue-700">A</span><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-950">Creator · {item.owner_id.slice(0, 8)}</p><p className="text-xs text-slate-500">{new Date(item.published_at ?? item.created_at).toLocaleString("id-ID")}</p></div></div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{item.content_type}</span>
      </div>
      {item.body && <p className="whitespace-pre-wrap px-4 py-5 text-[15px] leading-7 text-slate-800 sm:px-5">{item.body}</p>}
      {item.media?.map(media => media.preview_url && <div key={media.id} className="border-t border-slate-100 bg-slate-50">
        {media.media_type.startsWith("video/") ? <video className="max-h-[70vh] w-full bg-black" src={media.preview_url} controls playsInline preload="metadata" aria-label={media.filename} /> : media.media_type.startsWith("audio/") ? <div className="p-4"><audio className="w-full" src={media.preview_url} controls preload="metadata" aria-label={media.filename} /></div> : media.media_type.startsWith("image/") ? <img className="max-h-[70vh] w-full object-contain" src={media.preview_url} alt={media.filename} /> : <p className="p-4 text-sm text-slate-600">{media.filename}</p>}
      </div>)}
      <footer className="flex flex-wrap items-center gap-2 border-t border-slate-100 p-4 sm:px-5">
        <button disabled={busy} onClick={() => void mutate("reaction")} className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium disabled:opacity-50 ${item.viewer_reaction ? "border-rose-200 bg-rose-50 text-rose-700" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`}><Heart size={16} /> {item.engagement?.likes ?? 0}</button>
        <button disabled={busy} onClick={() => void mutate("save")} className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium disabled:opacity-50 ${item.saved ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`}><Bookmark size={16} /> {item.saved ? "Tersimpan" : "Simpan"}</button>
        <button disabled={busy} onClick={() => void mutate("share")} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"><Share2 size={16} /> Bagikan</button>
        <span className="ml-auto text-xs text-slate-500">{item.engagement?.comments ?? 0} komentar · {item.visibility}</span>
      </footer>
    </article>}
    {!loading && !item && !error && <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Konten tidak tersedia.</div>}
  </main>;
}
