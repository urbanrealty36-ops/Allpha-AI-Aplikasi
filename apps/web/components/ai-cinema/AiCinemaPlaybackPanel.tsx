"use client";

import Link from "next/link";
import { useState } from "react";
import { getBrowserSupabase } from "../../lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
type Title = { id: string; title: string };
type Episode = { id: string; episode_number: number; title: string; synopsis?: string | null; duration_seconds?: number | null; is_free_preview: boolean; locked: boolean; playback_url?: string | null };
type Playback = { title: { id: string; title: string; maturity_rating: string }; episodes: Episode[]; premium_entitled: boolean };

export default function AiCinemaPlaybackPanel({ titles }: { titles: Title[] }) {
  const [selected, setSelected] = useState<Playback | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function openTitle(title: Title) {
    setBusy(title.id); setError(""); setSelected(null);
    try {
      const auth = getBrowserSupabase();
      const session = auth ? (await auth.auth.getSession()).data.session : null;
      const response = await fetch(apiBase + "/v1/cinema/titles/" + encodeURIComponent(title.id) + "/playback", {
        cache: "no-store",
        headers: session?.access_token ? { Authorization: "Bearer " + session.access_token } : {},
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail?.message || "Informasi playback tidak dapat dimuat.");
      setSelected(data as Playback);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Playback tidak tersedia.");
    } finally { setBusy(null); }
  }

  if (!titles.length) return null;
  return <section className="mx-auto my-8 w-full max-w-6xl px-4 sm:px-6">
    <div className="mb-4"><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-700">Watch · Entitlement</p><h2 className="mt-2 text-2xl font-semibold">Tonton AI Cinema</h2><p className="mt-1 text-sm text-slate-500">Preview gratis tersedia sesuai penandaan episode. Episode premium memerlukan entitlement server yang aktif.</p></div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {titles.map(title => <article key={title.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700"><div className="min-w-0"><h3 className="truncate font-semibold">{title.title}</h3><p className="text-xs text-slate-500">Judul terbit · katalog terverifikasi</p></div><button onClick={() => void openTitle(title)} disabled={busy !== null} className="shrink-0 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{busy === title.id ? "Memuat…" : "Lihat episode"}</button></article>)}
    </div>
    {error && <p role="alert" className="mt-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {selected && <div className="mt-5 rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-xl font-semibold">{selected.title.title}</h3><p className="text-xs text-slate-500">Maturity: {selected.title.maturity_rating} · {selected.premium_entitled ? "Premium entitlement aktif" : "Preview saja"}</p></div><button onClick={() => setSelected(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs">Tutup</button></div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {selected.episodes.map(episode => <article key={episode.id} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-2"><h4 className="font-medium">Episode {episode.episode_number}: {episode.title}</h4><span className="text-[10px] uppercase text-slate-500">{episode.is_free_preview ? "Free preview" : "Premium"}</span></div>
          {episode.locked ? <div className="mt-3 rounded-lg border border-slate-200 p-4 text-sm text-slate-500 dark:border-slate-700">Episode terkunci. <Link href="/billing" className="font-semibold text-cyan-700 underline">Lihat paket Premium</Link></div> : episode.playback_url ? <video className="mt-3 aspect-video w-full rounded-lg bg-black" controls preload="none" src={episode.playback_url}>Browser tidak mendukung video.</video> : <p className="mt-3 text-xs text-amber-700">Media belum siap untuk diputar.</p>}
          {episode.synopsis && <p className="mt-2 text-xs text-slate-500">{episode.synopsis}</p>}
        </article>)}
      </div>
      <p className="mt-4 text-[11px] text-slate-500">Tautan media bersifat sementara. Hak akses diperiksa kembali di server; kebijakan wilayah, maturity, dan batas stream bersamaan masih menunggu persetujuan produk/legal.</p>
    </div>}
  </section>;
}
