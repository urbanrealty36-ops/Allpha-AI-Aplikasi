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
  version: number;
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
type CreatorMedia = ReadyMedia & { status: string; scan_status: string; processed_at?: string | null; created_at: string };
type CinemaCollaborator = { id: string; collaborator_user_id?: string | null; collaborator_agent_id?: string | null; role: string; permissions: string[]; status: string };
type CinemaInvitation = { id: string; title?: { title: string; status: string } | null; role: string; permissions: string[]; status: string };
type CinemaCredit = { id: string; contributor_type: string; role: string; attribution_label: string };
type CinemaVersion = { id: string; version: number; created_at: string };

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
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
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
  const [creatorMedia, setCreatorMedia] = useState<CreatorMedia[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDraftId, setUploadDraftId] = useState("");
  const [uploadIdempotencyKey, setUploadIdempotencyKey] = useState("");
  const [selectedMediaId, setSelectedMediaId] = useState("");
  const [selectedTitleId, setSelectedTitleId] = useState("");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("c_drama");
  const [synopsis, setSynopsis] = useState("");
  const [episodeTitle, setEpisodeTitle] = useState("");
  const [episodeSynopsis, setEpisodeSynopsis] = useState("");
  const [episodeNumber, setEpisodeNumber] = useState("1");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [aiDisclosureConfirmed, setAiDisclosureConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [collaboratorUserId, setCollaboratorUserId] = useState("");
  const [collaboratorRole, setCollaboratorRole] = useState("Editor");
  const [collaboratorPermissions, setCollaboratorPermissions] = useState<string[]>(["edit_metadata","upload_episodes"]);
  const [collaborators, setCollaborators] = useState<CinemaCollaborator[]>([]);
  const [invitations, setInvitations] = useState<CinemaInvitation[]>([]);
  const [credits, setCredits] = useState<CinemaCredit[]>([]);
  const [creditType, setCreditType] = useState("human");
  const [creditAgentId, setCreditAgentId] = useState("");
  const [creditRole, setCreditRole] = useState("Creator");
  const [creditLabel, setCreditLabel] = useState("Kontribusi kreator");
  const [versions, setVersions] = useState<CinemaVersion[]>([]);

  const loadCapabilityStatus = useCallback(async () => {
    try {
      const result = await authorizedRequest<CreatorStatus>("/v1/cinema/creator/status");
      setCapabilityStatus(result);
    } catch {
      setCapabilityStatus(null);
    }
  }, []);

  const loadCreatorMedia = useCallback(async () => {
    try {
      const result = await authorizedRequest<{ items: CreatorMedia[] }>("/v1/cinema/creator/media");
      const rows = Array.isArray(result.items) ? result.items : [];
      setCreatorMedia(rows);
      setReadyMedia(rows.filter(item => item.status === "ready" && item.scan_status === "clean" && item.processed_at).map(({ id, filename, media_type, size_bytes }) => ({ id, filename, media_type, size_bytes })));
    } catch {
      setCreatorMedia([]); setReadyMedia([]);
    }
  }, []);

  const loadReadyMedia = useCallback(async () => { await loadCreatorMedia(); }, [loadCreatorMedia]);

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

  const loadCreatorGovernance = useCallback(async () => {
    try {
      const inbox = await authorizedRequest<{items:CinemaInvitation[]}>("/v1/cinema/creator/collaborations");
      setInvitations(Array.isArray(inbox.items)?inbox.items:[]);
      if (!selectedTitleId) { setCollaborators([]); setCredits([]); setVersions([]); return; }
      const base = "/v1/cinema/creator/titles/" + encodeURIComponent(selectedTitleId);
      const [collabData,creditData,versionData]=await Promise.all([
        authorizedRequest<{items:CinemaCollaborator[]}>(base+"/collaborators"),
        authorizedRequest<{items:CinemaCredit[]}>(base+"/credits"),
        authorizedRequest<{items:CinemaVersion[]}>(base+"/versions"),
      ]);
      setCollaborators(collabData.items||[]); setCredits(creditData.items||[]); setVersions(versionData.items||[]);
    } catch (cause) {
      setError(cause instanceof Error?cause.message:"Data kolaborasi Creator Studio belum dapat dimuat.");
    }
  },[selectedTitleId]);

  useEffect(()=>{ void loadCreatorGovernance(); },[loadCreatorGovernance]);

  async function inviteCollaborator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(!selectedTitleId||!collaboratorUserId.trim())return;
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/titles/"+encodeURIComponent(selectedTitleId)+"/collaborators",{
        method:"POST",body:JSON.stringify({collaborator_user_id:collaboratorUserId.trim(),role:collaboratorRole,permissions:collaboratorPermissions}),
      });
      setCollaboratorUserId("");setNotice("Undangan collaborator dikirim dan menunggu persetujuan penerima.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Undangan collaborator gagal dibuat.");}
    finally{setSaving(false);}
  }

  async function decideCollaboration(id:string,decision:"accept"|"revoke") {
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/collaborations/"+encodeURIComponent(id)+"/decision",{
        method:"POST",body:JSON.stringify({decision}),
      });
      setNotice(decision==="accept"?"Undangan kolaborasi diterima.":"Akses kolaborasi dicabut.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Perubahan kolaborasi gagal.");}
    finally{setSaving(false);}
  }

  async function addCreatorCredit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(!selectedTitleId)return;
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/titles/"+encodeURIComponent(selectedTitleId)+"/credits",{
        method:"POST",body:JSON.stringify({contributor_type:creditType,contributor_agent_id:creditType==="agent"?creditAgentId.trim():null,role:creditRole,attribution_label:creditLabel,disclosure:"Kontribusi AI/Human dicatat oleh Creator Studio"}),
      });
      setCreditAgentId("");setNotice("Kredit kontributor tersimpan.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Kredit kontributor gagal disimpan.");}
    finally{setSaving(false);}
  }

  async function snapshotVersion() {
    if(!selectedTitleId)return;
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/titles/"+encodeURIComponent(selectedTitleId)+"/versions",{method:"POST",body:"{}"});
      setNotice("Snapshot versi film tersimpan.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Snapshot versi gagal dibuat.");}
    finally{setSaving(false);}
  }



  async function uploadCinemaMedia() {
    if (!uploadFile || !uploadFile.type.startsWith("video/")) { setError("Pilih file video MP4 atau WebM terlebih dahulu."); return; }
    if (uploadFile.size <= 0 || uploadFile.size > 50 * 1024 * 1024) { setError("Ukuran video harus lebih dari 0 dan maksimal 50 MiB."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      let contentId = uploadDraftId;
      if (!contentId) {
        const draft = await authorizedRequest<{ item: { id: string } }>("/v1/content", { method: "POST", body: JSON.stringify({ body: "", visibility: "private", content_type: "video" }) });
        contentId = draft.item.id; setUploadDraftId(contentId);
      }
      const idempotencyKey = uploadIdempotencyKey || crypto.randomUUID();
      setUploadIdempotencyKey(idempotencyKey);
      const form = new FormData(); form.append("file", uploadFile);
      const uploaded = await authorizedRequest<{ item: CreatorMedia }>("/v1/content/" + encodeURIComponent(contentId) + "/media", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: form });
      setUploadFile(null); setUploadDraftId(""); setUploadIdempotencyKey("");
      setNotice("Video diterima pipeline media Allpha (" + (uploaded.item?.status || "uploaded") + "). Tunggu pemindaian dan transcode; video dapat dipilih setelah status ready dan scan clean.");
      await loadCreatorMedia();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload video AI Cinema gagal."); }
    finally { setSaving(false); }
  }

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

  async function submitForReview() {
    const selected = titles.find(item => item.id === selectedTitleId);
    if (!selected || !rightsConfirmed || !aiDisclosureConfirmed) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ item: DraftTitle }>(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/submit-review`, {
        method: "POST",
        body: JSON.stringify({ expected_version: selected.version, rights_confirmed: true, ai_disclosure_confirmed: true }),
      });
      setTitles(current => current.map(item => item.id === result.item.id ? result.item : item));
      setRightsConfirmed(false); setAiDisclosureConfirmed(false);
      setNotice("Film diajukan ke antrean rights review dan moderasi. Pengajuan bukan persetujuan atau publikasi.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Pengajuan review gagal.");
    } finally { setSaving(false); }
  }

  return (
    <section className="mx-auto my-8 w-full max-w-6xl rounded-3xl border-2 border-slate-900 bg-white p-5 text-slate-900 shadow-[3px_3px_0px_#0f172a] sm:p-7">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[.2em] text-sky-700">Creator Workspace</p><h2 className="mt-1 text-2xl font-black">Draft Film & Episode</h2><p className="mt-1 text-sm text-slate-700">Draft disimpan melalui FastAPI dan hanya dapat diakses pemiliknya.</p></div>
        <button type="button" onClick={() => { void loadTitles(); void loadCapabilityStatus(); void loadCreatorMedia(); }} disabled={loading} className="rounded-xl border-2 border-slate-900 bg-slate-100 px-4 py-2 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-200 disabled:opacity-50">{loading ? "Memuat…" : "Muat ulang"}</button>
      </div>
      {capabilityStatus && <div className="mb-4 rounded-xl border border-2 border-slate-900 bg-amber-50 p-3 text-xs text-amber-900">
        <p className="font-bold">Status layanan terhubung</p>
        <p className="mt-1">Generation: {capabilityStatus.generation} · Generation jobs: {capabilityStatus.generation_jobs} · Billing: {capabilityStatus.billing} · Playback entitlement: {capabilityStatus.playback_entitlement}</p>
        <p className="mt-1 text-amber-800">Generate, pembayaran, dan playback premium belum dapat digunakan sampai kontrak job, policy kredit, billing, dan entitlement tersedia.</p>
      </div>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-2 border-slate-900 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-xl border border-2 border-slate-900 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={createTitle} className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
          <h3 className="font-bold">Buat draft film</h3>
          <label className="block text-xs text-slate-700">Judul film<input required maxLength={160} value={title} onChange={event => setTitle(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
          <label className="block text-xs text-slate-700">Genre<select value={genre} onChange={event => setGenre(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"><option value="c_drama">C-Drama</option><option value="k_drama">K-Drama</option><option value="scifi">Sci-Fi</option><option value="romance">Romance</option><option value="thriller">Thriller</option><option value="animation_3d">Animasi 3D</option><option value="documentary">Dokumenter</option><option value="other">Lainnya</option></select></label>
          <label className="block text-xs text-slate-700">Sinopsis<textarea maxLength={5000} rows={4} value={synopsis} onChange={event => setSynopsis(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
          <button disabled={saving || !title.trim()} className="w-full rounded-xl bg-sky-300 px-4 py-3 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan draft film"}</button>
        </form>
        <div className="space-y-4">
          <div className="rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="mb-3 font-bold">Film milik saya</h3>
            {titles.length === 0 ? <p className="text-sm text-slate-600">{loading ? "Memuat draft…" : "Belum ada draft film pada akun ini."}</p> : <select aria-label="Pilih draft film" value={selectedTitleId} onChange={event => setSelectedTitleId(event.target.value)} className="w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900">{titles.map(item => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}</select>}
          </div>
          <div className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="font-bold">Ajukan ke review</h3>
            <label className="flex items-start gap-2 text-xs text-slate-700"><input type="checkbox" checked={rightsConfirmed} onChange={event => setRightsConfirmed(event.target.checked)} />Saya menyatakan memiliki hak/izin atas materi yang digunakan.</label>
            <label className="flex items-start gap-2 text-xs text-slate-700"><input type="checkbox" checked={aiDisclosureConfirmed} onChange={event => setAiDisclosureConfirmed(event.target.checked)} />Saya mengonfirmasi pengungkapan penggunaan AI pada metadata film.</label>
            <button type="button" onClick={() => void submitForReview()} disabled={saving || !selectedTitleId || !rightsConfirmed || !aiDisclosureConfirmed} className="w-full rounded-xl border-2 border-slate-900 bg-rose-100 px-4 py-3 text-sm font-black text-rose-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-40">{saving ? "Mengajukan…" : "Ajukan rights review & moderasi"}</button>
            <p className="text-xs text-slate-600">API akan menolak pengajuan jika episode belum memiliki media ready dan scan clean. Keputusan hak cipta dan moderasi tetap dilakukan operator.</p>
          </div>
          <section className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="font-bold">Upload video film · Media Pipeline</h3>
            <p className="text-xs text-slate-600">MP4/WebM maksimal 50 MiB. File disimpan melalui FastAPI ke Supabase Storage; worker dan pemeriksaan keamanan menentukan kapan media siap digunakan.</p>
            <input type="file" accept="video/mp4,video/webm" onChange={event => { const next = event.target.files?.[0] ?? null; const sameFile = Boolean(next && uploadFile && next.name === uploadFile.name && next.size === uploadFile.size && next.lastModified === uploadFile.lastModified); setUploadFile(next); if (!sameFile) setUploadIdempotencyKey(""); }} className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-sky-300 file:border-2 file:border-slate-900 file:px-3 file:py-2 file:text-xs file:font-black file:text-slate-950" />
            {uploadFile && <p className="text-xs text-slate-700">{uploadFile.name} · {(uploadFile.size / 1024 / 1024).toFixed(1)} MiB</p>}
            <button type="button" onClick={() => void uploadCinemaMedia()} disabled={saving || !uploadFile} className="w-full rounded-xl bg-sky-300 px-4 py-3 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{saving ? "Mengunggah…" : "Unggah video ke Media Pipeline"}</button>
            <div className="space-y-1 border-t border-slate-900 pt-3"><p className="text-xs font-bold text-slate-700">Status media saya</p>{creatorMedia.length ? creatorMedia.map(media => <p key={media.id} className="text-xs text-slate-600">{media.filename} · {media.status} · scan {media.scan_status}{media.processed_at ? " · diproses " + new Date(media.processed_at).toLocaleString("id-ID") : ""}</p>) : <p className="text-xs text-slate-600">Belum ada media milik akun ini.</p>}</div>
          </section>
          <form onSubmit={createEpisode} className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="font-bold">Tambah draft episode</h3>
            <label className="block text-xs text-slate-700">Nomor episode<input required type="number" min="1" max="10000" value={episodeNumber} onChange={event => setEpisodeNumber(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
            <label className="block text-xs text-slate-700">Judul episode<input required maxLength={160} value={episodeTitle} onChange={event => setEpisodeTitle(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
            <label className="block text-xs text-slate-700">Sinopsis<textarea maxLength={3000} rows={2} value={episodeSynopsis} onChange={event => setEpisodeSynopsis(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
            <label className="block text-xs text-slate-700">Media episode · hanya media siap dan scan clean<select value={selectedMediaId} onChange={event => setSelectedMediaId(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"><option value="">Simpan tanpa media (draft)</option>{readyMedia.map(media => <option key={media.id} value={media.id}>{media.filename} · {media.media_type} · {(media.size_bytes / 1024 / 1024).toFixed(1)} MiB</option>)}</select><span className="mt-1 block text-slate-600">Media dari Creator Studio hanya tersedia setelah processing selesai dan scan berstatus clean.</span></label>
            <button disabled={saving || !selectedTitleId || !episodeTitle.trim()} className="w-full rounded-xl bg-rose-300 px-4 py-3 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan draft episode"}</button>
          </form>
        </div>
      </div>
      <div className="mt-6 rounded-2xl border-2 border-slate-900 bg-slate-50 p-4">
        <h3 className="mb-3 font-bold">Daftar episode</h3>
        {episodes.length === 0 ? <p className="text-sm text-slate-600">Belum ada episode untuk film yang dipilih.</p> : <ol className="space-y-2">{episodes.map(item => <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3 text-sm"><span><strong>Episode {item.episode_number} — {item.title}</strong><span className="ml-2 text-xs text-slate-600">{item.status}</span></span><span className="text-xs text-slate-600">{item.duration_seconds ? `${item.duration_seconds} dtk` : "Durasi belum ditetapkan"}</span></li>)}</ol>}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border-2 border-slate-900 bg-white p-4">
          <h3 className="font-bold">Kolaborator & Human-Agent credits</h3>
          <p className="mt-1 text-xs text-slate-600">Akses diberikan per film dan per scope. Undangan Human aktif setelah penerima menyetujui.</p>
          <form onSubmit={inviteCollaborator} className="mt-3 space-y-2">
            <label className="block text-xs text-slate-700">ID akun Human yang diundang (UUID)<input value={collaboratorUserId} onChange={e=>setCollaboratorUserId(e.target.value)} placeholder="UUID akun collaborator" className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <label className="block text-xs text-slate-700">Peran<input value={collaboratorRole} onChange={e=>setCollaboratorRole(e.target.value)} maxLength={80} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <div className="flex flex-wrap gap-3 text-xs text-slate-700">
              {["edit_metadata","upload_episodes","manage_credits","submit_review"].map(scope=><label key={scope} className="flex items-center gap-1"><input type="checkbox" checked={collaboratorPermissions.includes(scope)} onChange={e=>setCollaboratorPermissions(v=>e.target.checked?[...v,scope]:v.filter(x=>x!==scope))}/>{scope}</label>)}
            </div>
            <button disabled={saving||!selectedTitleId||!collaboratorUserId.trim()} className="rounded-xl bg-sky-300 px-4 py-2 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">Undang collaborator</button>
          </form>
          <div className="mt-4 space-y-2">
            {collaborators.map(item=><div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3 text-xs"><span><strong>{item.role}</strong><span className="ml-2 text-slate-600">{item.collaborator_user_id||item.collaborator_agent_id} · {item.status}</span><span className="block text-slate-600">{item.permissions.join(", ")}</span></span>{item.status!=="revoked"&&<button onClick={()=>void decideCollaboration(item.id,"revoke")} className="rounded-lg border border-2 border-slate-900 px-3 py-1 text-rose-800">Cabut akses</button>}</div>)}
            {collaborators.length===0&&<p className="text-xs text-slate-600">Belum ada collaborator pada film ini.</p>}
          </div>
          <div className="mt-4 border-t border-slate-900 pt-3">
            <h4 className="text-sm font-bold">Undangan saya</h4>
            {invitations.map(item=><div key={item.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3 text-xs"><span>{item.title?.title||"Film"} · {item.role} · {item.status}</span>{item.status==="invited"&&<button onClick={()=>void decideCollaboration(item.id,"accept")} className="rounded-lg bg-violet-400 px-3 py-1 font-bold text-slate-950">Terima</button>}</div>)}
          </div>
        </section>
        <section className="rounded-2xl border-2 border-slate-900 bg-white p-4">
          <h3 className="font-bold">Creator Credits & Version History</h3>
          <form onSubmit={addCreatorCredit} className="mt-3 space-y-2">
            <label className="block text-xs text-slate-700">Jenis kontributor<select value={creditType} onChange={e=>setCreditType(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"><option value="human">Human (akun saya)</option><option value="agent">AI Agent</option></select></label>
            {creditType==="agent"&&<label className="block text-xs text-slate-700">ID AI Agent (UUID)<input value={creditAgentId} onChange={e=>setCreditAgentId(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" placeholder="UUID AI Agent milik pemilik film"/></label>}
            <label className="block text-xs text-slate-700">Peran kontribusi<input value={creditRole} onChange={e=>setCreditRole(e.target.value)} maxLength={80} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <label className="block text-xs text-slate-700">Label atribusi<input value={creditLabel} onChange={e=>setCreditLabel(e.target.value)} maxLength={160} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <button disabled={saving||!selectedTitleId||(creditType==="agent"&&!creditAgentId.trim())} className="rounded-xl bg-violet-400 px-4 py-2 text-sm font-black text-slate-950 disabled:opacity-50">Simpan creator credit</button>
          </form>
          <div className="mt-3 space-y-1">{credits.map(item=><p key={item.id} className="rounded-lg bg-slate-50 p-2 text-xs">{item.attribution_label} · {item.role} · {item.contributor_type}</p>)}{credits.length===0&&<p className="text-xs text-slate-600">Belum ada kredit kreator.</p>}</div>
          <div className="mt-4 border-t border-slate-900 pt-3">
            <button type="button" disabled={saving||!selectedTitleId} onClick={()=>void snapshotVersion()} className="rounded-xl border border-cyan-300/40 px-4 py-2 text-sm font-bold text-sky-800 disabled:opacity-50">Simpan snapshot versi film</button>
            <div className="mt-2 space-y-1">{versions.map(item=><p key={item.id} className="text-xs text-slate-600">Versi {item.version} · {new Date(item.created_at).toLocaleString("id-ID")}</p>)}{versions.length===0&&<p className="text-xs text-slate-600">Belum ada snapshot versi.</p>}</div>
          </div>
        </section>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-amber-800">Generate AI, tarif/kredit, publikasi, moderasi, dan entitlement belum diaktifkan di panel ini karena kontrak job, policy billing, dan bukti runtime terkait belum lengkap.</p>
    </section>
  );
}
