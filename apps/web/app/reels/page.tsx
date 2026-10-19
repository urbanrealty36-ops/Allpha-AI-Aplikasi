"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type ReelsMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type Reel = { id: string; owner_id: string; body: string; content_type: string; published_at?: string | null; created_at: string; media?: ReelsMedia[]; engagement?: { likes: number; comments: number; saves: number; shares?: number }; viewer_reaction?: string | null; saved?: boolean };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function messageFor(response: Response) {
  try { const body = await response.json(); return body?.detail?.message ?? body?.error?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function ReelsPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<Reel[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Masuk terlebih dahulu untuk membuka Reels.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await messageFor(response));
    return response.json();
  }, [session]);

  const load = useCallback(async (reset = true, nextCursor?: string | null) => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "20", mode: "recent" });
      if (!reset && nextCursor) params.set("cursor", nextCursor);
      const data = await request("/v1/reels?" + params.toString()) as { items?: Reel[]; next_cursor?: string | null };
      setItems(current => reset ? (data.items ?? []) : [...current, ...(data.items ?? [])]);
      setCursor(data.next_cursor ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reels gagal dimuat."); }
    finally { setLoading(false); }
  }, [request]);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (!data.session) setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (!next) { setItems([]); setCursor(null); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => { if (session) void load(true); }, [session, load]);

  async function toggleLike(item: Reel) {
    setBusy(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", item.viewer_reaction
        ? { method: "DELETE" }
        : { method: "PUT", body: JSON.stringify({ reaction: "like" }) });
      await load(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reaksi gagal disimpan."); }
    finally { setBusy(""); }
  }

  async function share(item: Reel) {
    setBusy(item.id); setError(""); setNotice("");
    try {
      const result = await request("/v1/feed/" + encodeURIComponent(item.id) + "/share", {
        method: "POST", body: JSON.stringify({ share_target: "copy_link" }),
      }) as { share_url: string };
      try { await navigator.clipboard.writeText(result.share_url); setNotice("Tautan Reels disalin."); }
      catch { setNotice("Tautan Reels: " + result.share_url); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Tautan Reels gagal dibuat."); }
    finally { setBusy(""); }
  }

  return <main className="min-h-screen bg-slate-950 text-white">
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-slate-950/95 px-4 py-3 backdrop-blur">
      <Link href="/feed" className="text-sm text-cyan-300 hover:underline">← Feed</Link>
      <div className="text-center"><p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300">ALLPHA UNIVERSE</p><h1 className="text-lg font-semibold">Reels</h1></div>
      <button className="text-sm text-slate-300" onClick={() => void load(true)} disabled={loading}>Muat ulang</button>
    </header>
    {!session ? <section className="mx-auto max-w-md p-8 text-center"><p className="mb-4">Masuk untuk menonton video pendek dan audio.</p><Link href="/" className="text-cyan-300 underline">Masuk melalui Allpha</Link></section> : <>
      {error && <p role="alert" className="mx-auto max-w-xl p-3 text-sm text-red-300">{error}</p>}
      {notice && <p role="status" className="mx-auto max-w-xl p-3 text-sm text-emerald-300">{notice}</p>}
      {loading && items.length === 0 && <p className="p-10 text-center text-slate-400">Memuat Reels…</p>}
      {!loading && items.length === 0 && <section className="mx-auto max-w-md p-10 text-center"><h2 className="font-semibold">Belum ada Reels</h2><p className="mt-2 text-sm text-slate-400">Video/audio akan tampil setelah konten disetujui dan dipublikasikan.</p></section>}
      <div className="mx-auto flex max-w-xl snap-y snap-mandatory flex-col items-center gap-4 px-3 py-4">
        {items.map(item => <article key={item.id} className="flex min-h-[72vh] w-full snap-start flex-col justify-center overflow-hidden rounded-3xl border border-white/10 bg-slate-900">
          <div className="flex items-center justify-between px-4 py-3 text-xs text-slate-400"><span>Creator · {item.owner_id.slice(0, 8)}</span><time>{new Date(item.published_at ?? item.created_at).toLocaleDateString()}</time></div>
          {item.body && <p className="whitespace-pre-wrap px-4 pb-3 text-sm leading-6">{item.body}</p>}
          <div className="flex flex-1 flex-col justify-center gap-3 bg-black px-3 py-4">
            {item.media?.map(media => media.preview_url && (media.media_type.startsWith("video/")
              ? <video key={media.id} src={media.preview_url} controls playsInline preload="metadata" className="max-h-[60vh] w-full rounded-2xl bg-black" aria-label={media.filename} />
              : media.media_type.startsWith("audio/")
                ? <div key={media.id} className="rounded-2xl bg-slate-800 p-4"><p className="mb-3 text-sm font-medium">{media.filename}</p><audio controls preload="metadata" src={media.preview_url} className="w-full" aria-label={media.filename} /></div>
                : null))}
          </div>
          <div className="flex items-center justify-between gap-3 px-4 py-3"><button className="rounded-full border border-white/20 px-4 py-2 text-sm" disabled={busy === item.id} onClick={() => void toggleLike(item)}>{item.viewer_reaction ? "♥ Disukai" : "♡ Suka"} · {item.engagement?.likes ?? 0}</button><span className="text-xs text-slate-400">{item.engagement?.comments ?? 0} komentar</span><button className="rounded-full border border-white/20 px-4 py-2 text-sm" disabled={busy === item.id} onClick={() => void share(item)}>Bagikan</button></div>
        </article>)}
      </div>
      {cursor && <div className="mx-auto max-w-xl px-3 pb-8"><button className="w-full rounded-xl border border-white/20 p-3 text-sm font-semibold disabled:opacity-50" disabled={loading} onClick={() => void load(false, cursor)}>Muat Reels berikutnya</button></div>}
    </>}
  </main>;
}
