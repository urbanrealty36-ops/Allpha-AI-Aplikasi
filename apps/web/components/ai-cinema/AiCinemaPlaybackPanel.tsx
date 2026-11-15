"use client";

import { useRef, useState } from "react";
import { getBrowserSupabase } from "../../lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
type Title = { id: string; title: string };
type Episode = { id: string; episode_number: number; title: string; synopsis?: string | null; duration_seconds?: number | null; is_free_preview: boolean; locked: boolean; playback_url?: string | null };
type Playback = { title: { id: string; title: string; maturity_rating: string }; episodes: Episode[]; premium_entitled: boolean };
type ActivePlayback = { session_id: string; session_token: string; episode_id: string; playback_url: string; last_heartbeat_at: number };

export default function AiCinemaPlaybackPanel({ titles }: { titles: Title[] }) {
  const [selected, setSelected] = useState<Playback | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [activePlayback, setActivePlayback] = useState<ActivePlayback | null>(null);
  const [lastPositionSeconds, setLastPositionSeconds] = useState(0);
  const [playbackFinishPending, setPlaybackFinishPending] = useState(false);
  const heartbeatLock = useRef(false);

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

  async function startEpisode(episode: Episode) {
    setError(""); setBusy(episode.id);
    try {
      const auth = getBrowserSupabase();
      const session = auth ? (await auth.auth.getSession()).data.session : null;
      if (!session?.access_token) throw new Error("Masuk untuk memulai sesi pemutaran. Preview publik dapat diaktifkan setelah kebijakan akses disetujui.");
      const idempotencyKey = crypto.randomUUID();
      const response = await fetch(apiBase + "/v1/cinema/titles/" + encodeURIComponent(selected!.title.id) + "/episodes/" + encodeURIComponent(episode.id) + "/playback-session", {
        method: "POST", cache: "no-store",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ idempotency_key: idempotencyKey }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail?.message || "Sesi pemutaran belum dapat dimulai.");
      setLastPositionSeconds(0); setPlaybackFinishPending(false);
      setActivePlayback({ session_id: data.session.id, session_token: data.session_token, episode_id: episode.id, playback_url: data.playback_url, last_heartbeat_at: Date.now() });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sesi pemutaran gagal."); }
    finally { setBusy(null); }
  }

  async function sendHeartbeat(position: number, finish = false): Promise<boolean> {
    if (!activePlayback || heartbeatLock.current) return false;
    heartbeatLock.current = true;
    try {
      const auth = getBrowserSupabase();
      const session = auth ? (await auth.auth.getSession()).data.session : null;
      if (!session?.access_token) throw new Error("Sesi login berakhir; masuk kembali untuk menyimpan progres pemutaran.");
      const response = await fetch(apiBase + "/v1/cinema/playback-sessions/" + activePlayback.session_id + (finish ? "/finish" : "/heartbeat"), {
        method: "POST", cache: "no-store",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", "X-Cinema-Session-Token": activePlayback.session_token },
        body: JSON.stringify({ event_id: crypto.randomUUID(), position_seconds: Math.max(0, Math.floor(position)) }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.detail?.message || "Progres pemutaran belum dikonfirmasi oleh server.");
      setError("");
      setActivePlayback(current => current ? { ...current, last_heartbeat_at: Date.now() } : current);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Progres pemutaran belum dapat disimpan.");
      return false;
    } finally { heartbeatLock.current = false; }
  }

  function onPlaybackTime(position: number) {
    setLastPositionSeconds(position);
    if (!activePlayback || Date.now() - activePlayback.last_heartbeat_at < 15000) return;
    void sendHeartbeat(position);
  }

  if (!titles.length) return null;
  return <section id="ai-cinema-playback" className="mx-auto my-8 w-full max-w-6xl scroll-mt-24 px-4 sm:px-6">
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
          {activePlayback?.episode_id === episode.id ? <video className="mt-3 aspect-video w-full rounded-lg bg-black" controls autoPlay preload="none" src={activePlayback.playback_url} onTimeUpdate={event => onPlaybackTime(event.currentTarget.currentTime)} onEnded={async event => { const finished = await sendHeartbeat(event.currentTarget.currentTime, true); if (finished) { setActivePlayback(null); setPlaybackFinishPending(false); } else { setPlaybackFinishPending(true); } }}>Browser tidak mendukung video.</video> : <div className="mt-3 rounded-lg border border-slate-200 p-4 text-sm text-slate-600 dark:border-slate-700"><p>URL playback hanya diterbitkan setelah pemeriksaan sesi, media dan entitlement.</p><button disabled={busy !== null} onClick={() => void startEpisode(episode)} className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">{busy === episode.id ? "Menyiapkan sesi…" : episode.is_free_preview ? "Mulai Preview" : "Periksa Premium & Putar"}</button></div>}
          {playbackFinishPending && activePlayback?.episode_id === episode.id && <button type="button" onClick={async () => { const finished = await sendHeartbeat(lastPositionSeconds, true); if (finished) { setActivePlayback(null); setPlaybackFinishPending(false); } }} disabled={heartbeatLock.current} className="mt-3 rounded-lg border border-amber-500 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-950 disabled:opacity-50">Coba konfirmasi akhir sesi</button>}
          {episode.synopsis && <p className="mt-2 text-xs text-slate-500">{episode.synopsis}</p>}
        </article>)}
      </div>
      <p className="mt-4 text-[11px] text-slate-500">Tautan media bersifat sementara. Hak akses diperiksa kembali di server; kebijakan wilayah, maturity, dan batas stream bersamaan masih menunggu persetujuan produk/legal.</p>
    </div>}
  </section>;
}
