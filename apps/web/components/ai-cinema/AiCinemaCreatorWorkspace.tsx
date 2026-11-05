"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { getBrowserSupabase } from "@/lib/supabase";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type DraftTitle = {
  id: string;
  title: string;
  genre: string;
  synopsis: string;
  status: string;
  updated_at?: string;
};
type DraftEpisode = {
  id: string;
  episode_number: number;
  title: string;
  synopsis: string;
  status: string;
  duration_seconds?: number | null;
};
type CreatorStatus = { generation: string; generation_jobs: string; billing: string; playback_entitlement: string; generation_reason?: string | null; billing_reason?: string | null; entitlement_reason?: string | null };
type ReadyMedia = { id: string; filename: string; media_type: string; size_bytes: number };

async function authorizedRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = getBrowserSupabase();
  if (!supabase) throw new Error("Autentikasi belum dikonfigurasi pada aplikasi.");
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Silakan masuk kembali untuk mengelola draft Creator Studio.");
  const response = await fetch(API_BASE + path, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${data.session.access_token}`,
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.detail?.message || body?.message || "Permintaan Creator Studio gagal.";
    throw new Error(message);
  }
  return body as T;
}

export default function AiCinemaCreatorWorkspace() {
  const [titles, setTitles] = useState<DraftTitle[]>([]);
  const [capabilityStatus, setCapabilityStatus] = useState<CreatorStatus | null>(null);
  const [episodes, setEpisodes] = useState<DraftEpisode[]>([]);
  const [readyMedia, setReadyMedia] = useState<ReadyMedia[]>([]);
  const [selectedMediaId, setSelectedMediaId] = useState("");
  const [selectedTitleId, setSelectedTitleId] = useState("");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("c_drama");
  const [synopsis, setSynopsis] = useState("");
  const [episodeTitle, setEpisodeTitle] = useState("");
  const [episodeSynopsis, setEpisodeSynopsis] = useState("");
  const [episodeNumber, setEpisodeNumber] = useState("1");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadCapabilityStatus = useCallback(async () => {
    try {
      const result = await authorizedRequest<CreatorStatus>("/v1/cinema/creator/status");
      setCapabilityStatus(result);
    } catch {
      setCapabilityStatus(null);
    }
  }, []);

  const loadReadyMedia = useCallback(async () => {
    try {
      const result = await authorizedRequest<{ items: ReadyMedia[] }>("/v1/cinema/creator/media-ready");
      setReadyMedia(Array.isArray(result.items) ? result.items : []);
    } catch {
      setReadyMedia([]);
    }
  }, []);

  const loadTitles = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await authorizedRequest<{ items: DraftTitle[] }>("/v1/cinema/creator/titles");
      const rows = Array.isArray(result.items) ? result.items : [];
      setTitles(rows);
      setSelectedTitleId(current => rows.some(row => row.id === current) ? current : rows[0]?.id ?? "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft film tidak dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadEpisodes = useCallback(async (titleId: string) => {
    if (!titleId) { setEpisodes([]); return; }
    try {
      const result = await authorizedRequest<{ items: DraftEpisode[] }>(`/v1/cinema/creator/titles/${encodeURIComponent(titleId)}/episodes`);
      setEpisodes(Array.isArray(result.items) ? result.items : []);
    } catch (cause) {
      setEpisodes([]);
      setError(cause instanceof Error ? cause.message : "Episode tidak dapat dimuat.");
    }
  }, []);

  useEffect(() => { void loadTitles(); }, [loadTitles]);
  useEffect(() => { void loadReadyMedia(); }, [loadReadyMedia]);
  useEffect(() => { void loadCapabilityStatus(); }, [loadCapabilityStatus]);
  useEffect(() => { void loadEpisodes(selectedTitleId); }, [loadEpisodes, selectedTitleId]);

  async function createTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ item: DraftTitle }>("/v1/cinema/creator/titles", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), genre, synopsis: synopsis.trim(), language_code: "id" }),
      });
      setTitle(""); setSynopsis("");
      setTitles(current => [result.item, ...current.filter(item => item.id !== result.item.id)]);
      setSelectedTitleId(result.item.id);
      setNotice("Draft film tersimpan di akun Anda.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft film gagal disimpan.");
    } finally { setSaving(false); }
  }

  async function createEpisode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTitleId) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ item: DraftEpisode }>(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/episodes`, {
        method: "POST",
        body: JSON.stringify({ episode_number: Number(episodeNumber), title: episodeTitle.trim(), synopsis: episodeSynopsis.trim(), media_id: selectedMediaId || null }),
      });
      setEpisodes(current => [...current.filter(item => item.id !== result.item.id), result.item].sort((a,b) => a.episode_number-b.episode_number));
      setEpisodeNumber(String(Number(episodeNumber) + 1));
      setEpisodeTitle(""); setEpisodeSynopsis("");
      setNotice("Draft episode tersimpan.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft episode gagal disimpan.");
    } finally { setSaving(false); }
  }

  return (
    <section className="mx-auto my-8 w-full max-w-6xl rounded-3xl border border-white/15 bg-slate-950/90 p-5 text-white shadow-2xl sm:p-7">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[.2em] text-cyan-300">Creator Workspace</p><h2 className="mt-1 text-2xl font-black">Draft Film & Episode</h2><p className="mt-1 text-sm text-slate-300">Draft disimpan melalui FastAPI dan hanya dapat diakses pemiliknya.</p></div>
        <button type="button" onClick={() => void loadTitles()} disabled={loading} className="rounded-xl border border-white/20 px-4 py-2 text-sm font-bold hover:bg-white/10 disabled:opacity-50">{loading ? "Memuat…" : "Muat ulang"}</button>
      </div>
      {capabilityStatus && <div className="mb-4 rounded-xl border border-amber-300/30 bg-amber-950/20 p-3 text-xs text-amber-100">
        <p className="font-bold">Status layanan terhubung</p>
        <p className="mt-1">Generation: {capabilityStatus.generation} · Generation jobs: {capabilityStatus.generation_jobs} · Billing: {capabilityStatus.billing} · Playback entitlement: {capabilityStatus.playback_entitlement}</p>
        <p className="mt-1 text-amber-200/80">Generate, pembayaran, dan playback premium belum dapat digunakan sampai kontrak job, policy kredit, billing, dan entitlement tersedia.</p>
      </div>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-rose-400/40 bg-rose-950/50 p-3 text-sm text-rose-200">{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-400/40 bg-emerald-950/40 p-3 text-sm text-emerald-200">{notice}</p>}
      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={createTitle} className="space-y-3 rounded-2xl border border-white/10 bg-white/[.04] p-4">
          <h3 className="font-bold">Buat draft film</h3>
          <label className="block text-xs text-slate-300">Judul film<input required maxLength={160} value={title} onChange={event => setTitle(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white" /></label>
          <label className="block text-xs text-slate-300">Genre<select value={genre} onChange={event => setGenre(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white"><option value="c_drama">C-Drama</option><option value="k_drama">K-Drama</option><option value="scifi">Sci-Fi</option><option value="romance">Romance</option><option value="thriller">Thriller</option><option value="animation_3d">Animasi 3D</option><option value="documentary">Dokumenter</option><option value="other">Lainnya</option></select></label>
          <label className="block text-xs text-slate-300">Sinopsis<textarea maxLength={5000} rows={4} value={synopsis} onChange={event => setSynopsis(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white" /></label>
          <button disabled={saving || !title.trim()} className="w-full rounded-xl bg-cyan-500 px-4 py-3 text-sm font-black text-slate-950 disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan draft film"}</button>
        </form>
        <div className="space-y-4">
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-4">
            <h3 className="mb-3 font-bold">Film milik saya</h3>
            {titles.length === 0 ? <p className="text-sm text-slate-400">{loading ? "Memuat draft…" : "Belum ada draft film pada akun ini."}</p> : <select aria-label="Pilih draft film" value={selectedTitleId} onChange={event => setSelectedTitleId(event.target.value)} className="w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white">{titles.map(item => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}</select>}
          </div>
          <form onSubmit={createEpisode} className="space-y-3 rounded-2xl border border-white/10 bg-white/[.04] p-4">
            <h3 className="font-bold">Tambah draft episode</h3>
            <label className="block text-xs text-slate-300">Nomor episode<input required type="number" min="1" max="10000" value={episodeNumber} onChange={event => setEpisodeNumber(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white" /></label>
            <label className="block text-xs text-slate-300">Judul episode<input required maxLength={160} value={episodeTitle} onChange={event => setEpisodeTitle(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white" /></label>
            <label className="block text-xs text-slate-300">Sinopsis<textarea maxLength={3000} rows={2} value={episodeSynopsis} onChange={event => setEpisodeSynopsis(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white" /></label>
            <label className="block text-xs text-slate-300">Media episode · hanya media siap dan scan clean<select value={selectedMediaId} onChange={event => setSelectedMediaId(event.target.value)} className="mt-1 w-full rounded-xl border border-white/15 bg-slate-900 p-3 text-sm text-white"><option value="">Simpan tanpa media (draft)</option>{readyMedia.map(media => <option key={media.id} value={media.id}>{media.filename} · {media.media_type} · {(media.size_bytes / 1024 / 1024).toFixed(1)} MiB</option>)}</select><span className="mt-1 block text-slate-400">Media dari Creator Studio hanya tersedia setelah processing selesai dan scan berstatus clean.</span></label>
            <button disabled={saving || !selectedTitleId || !episodeTitle.trim()} className="w-full rounded-xl bg-violet-400 px-4 py-3 text-sm font-black text-slate-950 disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan draft episode"}</button>
          </form>
        </div>
      </div>
      <div className="mt-6 rounded-2xl border border-white/10 bg-white/[.03] p-4">
        <h3 className="mb-3 font-bold">Daftar episode</h3>
        {episodes.length === 0 ? <p className="text-sm text-slate-400">Belum ada episode untuk film yang dipilih.</p> : <ol className="space-y-2">{episodes.map(item => <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-900/80 p-3 text-sm"><span><strong>Episode {item.episode_number} — {item.title}</strong><span className="ml-2 text-xs text-slate-400">{item.status}</span></span><span className="text-xs text-slate-400">{item.duration_seconds ? `${item.duration_seconds} dtk` : "Durasi belum ditetapkan"}</span></li>)}</ol>}
      </div>
      <p className="mt-4 text-xs leading-relaxed text-amber-200/80">Generate AI, tarif/kredit, publikasi, moderasi, dan entitlement belum diaktifkan di panel ini karena kontrak job, policy billing, dan bukti runtime terkait belum lengkap.</p>
    </section>
  );
}
