"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { getBrowserSupabase } from "@/lib/supabase";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type LiveParticipant = {
  id: string;
  user_id: string;
  participant_role: "host" | "cohost" | "speaker" | "viewer";
  status: "invited" | "joined" | "left" | "removed";
  recording_consent?: boolean;
};
type LiveSession = {
  id: string;
  host_user_id: string;
  conversation_id: string;
  title: string;
  description: string;
  visibility: "public" | "followers" | "private";
  status: string;
  version: number;
  scheduled_at?: string | null;
  media_plane?: { status: string; provider_approved: boolean; publish_subscribe_tokens_available: boolean; reason?: string };
  recording_provider_enabled?: boolean;
  participants?: LiveParticipant[];
};

async function liveRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = getBrowserSupabase();
  if (!supabase) throw new Error("Autentikasi Live belum dikonfigurasi.");
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Silakan masuk kembali untuk mengelola Live Session.");
  const response = await fetch(API_BASE + path, {
    ...init, cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${data.session.access_token}`,
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Operasi Live belum dapat dikonfirmasi.");
  return body as T;
}

export default function LiveControlPanel() {
  const [items, setItems] = useState<LiveSession[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"public" | "followers" | "private">("public");
  const [inviteUserId, setInviteUserId] = useState("");
  const [inviteRole, setInviteRole] = useState<"cohost" | "speaker" | "viewer">("speaker");
  const [details, setDetails] = useState<LiveSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const result = await liveRequest<{ items: LiveSession[] }>("/v1/live/sessions");
      const rows = Array.isArray(result.items) ? result.items : [];
      setItems(rows);
      setSelectedId(current => rows.some(row => row.id === current) ? current : rows[0]?.id ?? "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Daftar sesi Live tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, []);

  const loadDetails = useCallback(async (sessionId: string) => {
    if (!sessionId) { setDetails(null); return; }
    try {
      const result = await liveRequest<{ session: LiveSession; participants: LiveParticipant[]; media_plane: LiveSession["media_plane"] }>(`/v1/live/sessions/${encodeURIComponent(sessionId)}`);
      setDetails({ ...result.session, participants: result.participants, media_plane: result.media_plane });
    } catch (cause) {
      setDetails(null);
      setError(cause instanceof Error ? cause.message : "Detail sesi Live tidak dapat dimuat.");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void loadDetails(selectedId); }, [loadDetails, selectedId]);

  async function createSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await liveRequest<{ session: LiveSession }>("/v1/live/sessions", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), description, visibility, idempotency_key: crypto.randomUUID() }),
      });
      setTitle(""); setDescription("");
      setNotice("Sesi Live dibuat pada control plane. Status tetap planned sampai host menyiapkan sesi dan provider media mendapat persetujuan.");
      await load();
      if (result.session?.id) setSelectedId(result.session.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sesi Live gagal dibuat."); }
    finally { setBusy(false); }
  }

  async function prepareSession() {
    if (!details) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await liveRequest(`/v1/live/sessions/${encodeURIComponent(details.id)}/transition`, {
        method: "POST",
        body: JSON.stringify({ expected_version: details.version, next_status: "preparing", reason: "host_prepared_stage" }),
      });
      setNotice("Sesi masuk status preparing. Media streaming belum aktif.");
      await load(); await loadDetails(details.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Persiapan sesi gagal."); }
    finally { setBusy(false); }
  }

  async function inviteParticipant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!details || !inviteUserId.trim()) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await liveRequest(`/v1/live/sessions/${encodeURIComponent(details.id)}/participants`, {
        method: "POST",
        body: JSON.stringify({ user_id: inviteUserId.trim(), role: inviteRole, idempotency_key: crypto.randomUUID() }),
      });
      setInviteUserId(""); setNotice("Undangan peserta tersimpan pada control plane.");
      await loadDetails(details.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Undangan peserta gagal."); }
    finally { setBusy(false); }
  }

  async function removeParticipant(userId: string) {
    if (!details) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await liveRequest(`/v1/live/sessions/${encodeURIComponent(details.id)}/participants/${encodeURIComponent(userId)}/remove`, {
        method: "POST",
        body: JSON.stringify({ reason: "host_removed_participant", idempotency_key: crypto.randomUUID() }),
      });
      setNotice("Akses peserta dicabut dari sesi dan percakapan Live.");
      await loadDetails(details.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pencabutan peserta gagal."); }
    finally { setBusy(false); }
  }

  return (
    <section className="mx-auto my-6 w-full max-w-5xl space-y-4 px-4 text-slate-900">
      <div className="rounded-3xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a] sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-xs font-black uppercase tracking-[.18em] text-sky-800">Live Control Plane · ENG-P25</p><h2 className="mt-1 text-xl font-black">Sesi & Stage Collaboration</h2><p className="mt-1 text-xs text-slate-600">Kelola host, co-host, speaker, viewer, undangan, dan lifecycle sesi melalui FastAPI.</p></div>
          <button type="button" onClick={() => void load()} disabled={loading} className="rounded-xl border-2 border-slate-900 bg-slate-100 px-3 py-2 text-xs font-bold disabled:opacity-40">{loading ? "Memuat…" : "Muat ulang"}</button>
        </div>
        <div className="mt-4 rounded-xl border-2 border-amber-700 bg-amber-50 p-3 text-xs text-amber-950">
          <strong>Media plane belum diaktifkan.</strong> Provider WebRTC/SFU/TURN, publish/subscribe token, audio/video streaming, dan recording tetap terkunci sampai ADR-WP10-001 serta persetujuan terkait selesai. Control plane tidak menampilkan penonton atau status LIVE palsu.
        </div>
        {error && <p role="alert" className="mt-3 rounded-xl border border-rose-700 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
        {notice && <p role="status" className="mt-3 rounded-xl border border-emerald-700 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
        <form onSubmit={createSession} className="mt-4 grid gap-3 rounded-2xl border border-slate-300 bg-slate-50 p-3 md:grid-cols-2">
          <label className="text-xs font-bold text-slate-700">Judul sesi<input value={title} onChange={event => setTitle(event.target.value)} required maxLength={160} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2 text-sm" placeholder="Judul Live Session" /></label>
          <label className="text-xs font-bold text-slate-700">Visibilitas<select value={visibility} onChange={event => setVisibility(event.target.value as typeof visibility)} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2 text-sm"><option value="public">Public</option><option value="followers">Followers</option><option value="private">Private / invitation</option></select></label>
          <label className="text-xs font-bold text-slate-700 md:col-span-2">Deskripsi<textarea value={description} onChange={event => setDescription(event.target.value)} maxLength={4000} rows={2} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2 text-sm" /></label>
          <button disabled={busy || !title.trim()} className="rounded-xl border-2 border-slate-900 bg-sky-200 px-4 py-2 text-sm font-black disabled:opacity-40 md:col-span-2">{busy ? "Menyimpan…" : "Buat sesi Live"}</button>
        </form>
        <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <div className="space-y-2">
            <h3 className="text-sm font-black">Sesi Anda</h3>
            {items.map(item => <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} className={`w-full rounded-xl border-2 p-3 text-left ${selectedId === item.id ? "border-slate-900 bg-sky-50" : "border-slate-300 bg-white"}`}>
              <span className="block text-sm font-bold">{item.title}</span><span className="mt-1 block text-xs text-slate-600">{item.status} · {item.visibility}</span>
            </button>)}
            {!items.length && <p className="rounded-xl border border-dashed border-slate-400 p-3 text-xs text-slate-500">Belum ada sesi Live pada akun ini.</p>}
          </div>
          <div className="rounded-2xl border-2 border-slate-900 bg-slate-50 p-3">
            {details ? <>
              <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="text-base font-black">{details.title}</h3><p className="text-xs text-slate-600">Status: {details.status} · v{details.version}</p></div><span className="rounded-lg border border-slate-900 bg-amber-100 px-2 py-1 text-[10px] font-black uppercase">{details.media_plane?.status || "not_configured"}</span></div>
              {details.status === "planned" && <button type="button" onClick={() => void prepareSession()} disabled={busy} className="mt-3 rounded-lg border-2 border-slate-900 bg-emerald-100 px-3 py-2 text-xs font-black disabled:opacity-40">Siapkan Stage</button>}
              <form onSubmit={inviteParticipant} className="mt-4 space-y-2 border-t border-slate-300 pt-3">
                <h4 className="text-xs font-black">Undang peserta</h4>
                <input value={inviteUserId} onChange={event => setInviteUserId(event.target.value)} placeholder="UUID akun Allpha" className="w-full rounded-lg border border-slate-400 bg-white p-2 text-xs" />
                <div className="flex gap-2"><select value={inviteRole} onChange={event => setInviteRole(event.target.value as typeof inviteRole)} className="flex-1 rounded-lg border border-slate-400 bg-white p-2 text-xs"><option value="cohost">Co-host</option><option value="speaker">Speaker</option><option value="viewer">Viewer</option></select><button disabled={busy || !inviteUserId.trim()} className="rounded-lg border-2 border-slate-900 bg-violet-100 px-3 py-2 text-xs font-black disabled:opacity-40">Undang</button></div>
              </form>
              <div className="mt-4 space-y-2 border-t border-slate-300 pt-3"><h4 className="text-xs font-black">Peserta</h4>
                {(details.participants || []).map(participant => <div key={participant.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white p-2 text-xs"><span className="min-w-0"><strong>{participant.participant_role}</strong> · {participant.status}<span className="block truncate text-slate-500">{participant.user_id}</span></span>{details.host_user_id && participant.participant_role !== "host" && <button type="button" onClick={() => void removeParticipant(participant.user_id)} disabled={busy || participant.status === "removed"} className="rounded-md border border-slate-900 px-2 py-1 font-bold text-rose-800 disabled:opacity-40">Cabut</button>}</div>)}
              </div>
              <p className="mt-3 text-[11px] text-slate-600">Chat memakai conversation dan Messaging API kanonis: {details.conversation_id}</p>
            </> : <p className="text-xs text-slate-500">Pilih sesi untuk melihat lifecycle dan peserta.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
