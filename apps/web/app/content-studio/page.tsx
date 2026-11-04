"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { getBrowserSupabase } from "../../lib/supabase";

type Media = { id: string; filename: string; media_type: string; size_bytes: number; status: string; preview_url?: string | null };
type Item = { id: string; body: string; content_type: string; visibility: string; status: string; moderation_status: string; version: number; created_at: string; updated_at: string; media?: Media[] };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function responseError(response: Response) {
  try { const body = await response.json(); return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function ContentStudioPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState("");
  const [editingId, setEditingId] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editVisibility, setEditVisibility] = useState("public");
  const [history, setHistory] = useState<Array<{ id: string; version: number; snapshot: Record<string, unknown>; created_at: string }>>([]);
  const [selected, setSelected] = useState("");
  const [preview, setPreview] = useState<{ item: Item; media: Media[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState<"create" | "edit" | "preview" | "history" | "archive" | "delete" | "appeal" | "schedule" | null>(null);
  const [pendingContentId, setPendingContentId] = useState("");
  const [appealReason, setAppealReason] = useState("");
  const [scheduleLocal, setScheduleLocal] = useState("");
  const [scheduleTimezone, setScheduleTimezone] = useState("Asia/Jakarta");
  const [showDeleted, setShowDeleted] = useState(false);

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Silakan masuk terlebih dahulu untuk membuat konten.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await responseError(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const refresh = useCallback(async (includeDeleted = showDeleted) => {
    const result = await request("/v1/content/mine" + (includeDeleted ? "?include_deleted=true" : ""));
    setItems(Array.isArray(result?.items) ? result.items : []);
  }, [request, showDeleted]);

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (!next) { setItems([]); setPreview(null); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session) return;
    let active = true;
    setLoading(true); setError("");
    void request("/v1/content/mine").then(result => {
      if (active) setItems(Array.isArray(result?.items) ? result.items : []);
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Konten tidak dapat dimuat."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session, request]);

  async function createDraft(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const created = await request("/v1/content", { method: "POST", body: JSON.stringify({
        body: body.trim(), visibility, content_type: file ? (file.type.startsWith("video/") ? "video" : file.type.startsWith("audio/") ? "audio" : "image") : "text"
      }) });
      const id = created.item.id as string;
      setSelected(id);
      await refresh();
      if (file) {
        const data = new FormData(); data.append("file", file);
        const key = uploadId || crypto.randomUUID();
        setUploadId(key);
        await request(`/v1/content/${id}/media`, { method: "POST", headers: { "Idempotency-Key": key }, body: data });
      }
      setBody(""); setFile(null); setUploadId(""); setModal(null);
      setNotice(file ? "Draft tersimpan dan media berhasil diunggah." : "Draft konten berhasil disimpan.");
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Draft gagal disimpan."); }
    finally { setBusy(false); }
  }

  async function uploadToSelectedDraft() {
    if (!selected || !file) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const data = new FormData(); data.append("file", file);
      const key = uploadId || crypto.randomUUID();
      setUploadId(key);
      await request(`/v1/content/${selected}/media`, { method: "POST", headers: { "Idempotency-Key": key }, body: data });
      setFile(null); setUploadId(""); setNotice("Media berhasil diunggah ke draft.");
      await refresh(); await showPreview(selected);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unggah gagal. Draft tetap tersimpan dan dapat dicoba lagi."); }
    finally { setBusy(false); }
  }

  async function showPreview(id: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${id}/preview`);
      setPreview({ item: result.item, media: result.media ?? [] }); setSelected(id); setModal("preview");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pratinjau gagal dimuat."); }
    finally { setBusy(false); }
  }

  async function loadHistory(id: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${id}/versions`);
      setHistory(Array.isArray(result?.items) ? result.items : []);
      setSelected(id); setModal("history");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Riwayat versi gagal dimuat."); }
    finally { setBusy(false); }
  }

  async function saveEdit(item: Item) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${item.id}`, { method: "PATCH", body: JSON.stringify({
        body: editBody, visibility: editVisibility, expected_version: item.version
      }) });
      setNotice("Perubahan draft tersimpan sebagai versi baru.");
      setEditingId(""); setPreview(null); setModal(null);
      await refresh();
      if (result?.item?.id) setSelected(result.item.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Perubahan draft gagal disimpan."); }
    finally { setBusy(false); }
  }

  async function saveSchedule(item: Item) {
    if (!scheduleLocal) { setError("Pilih waktu publikasi terlebih dahulu."); return; }
    const publishAt = new Date(scheduleLocal);
    if (Number.isNaN(publishAt.getTime()) || publishAt.getTime() <= Date.now()) { setError("Waktu publikasi harus berada di masa depan."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const body = { publish_at: publishAt.toISOString(), creator_timezone: scheduleTimezone, expected_version: item.version, rights_confirmed: true, disclosure_confirmed: true };
      const method = item.status === "scheduled" ? "PATCH" : "POST";
      await request(`/v1/content/${item.id}/schedule`, { method, headers: method === "POST" ? { "Idempotency-Key": crypto.randomUUID() } : undefined, body: JSON.stringify(body) });
      setNotice(item.status === "scheduled" ? "Jadwal publikasi diperbarui." : "Jadwal disimpan dan konten otomatis masuk antrean moderasi.");
      setModal(null); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Jadwal publikasi gagal disimpan."); }
    finally { setBusy(false); }
  }

  async function cancelSchedule(id: string) {
    setBusy(true); setError(""); setNotice("");
    try { await request(`/v1/content/${id}/schedule`, { method: "DELETE" }); setNotice("Jadwal publikasi dibatalkan."); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pembatalan jadwal gagal."); }
    finally { setBusy(false); }
  }

  async function restoreContent(id: string) {
    setBusy(true); setError(""); setNotice("");
    try { const result = await request(`/v1/content/${id}/restore`, { method: "POST" }); setNotice(result?.message || "Konten dipulihkan."); await refresh(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pemulihan konten gagal."); }
    finally { setBusy(false); }
  }

  async function publish(id: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${id}/publish`, { method: "POST" });
      setNotice(result.message ?? "Konten dikirim untuk ditinjau.");
      await refresh(); await showPreview(id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Konten gagal dikirim."); }
    finally { setBusy(false); }
  }

  async function retry(id: string) {
    setBusy(true); setError(""); setNotice("");
    try { const result = await request(`/v1/content/${id}/retry`, { method: "POST" }); setNotice(result.message ?? "Draft dipulihkan."); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pemulihan draft gagal."); }
    finally { setBusy(false); }
  }

  async function archive(id: string, confirmed = false) {
    if (!confirmed) { setPendingContentId(id); setModal("archive"); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${id}/archive`, { method: "POST" });
      setNotice(result.message ?? "Konten diarsipkan."); setModal(null); setPendingContentId("");
      if (selected === id) { setSelected(""); setPreview(null); }
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Arsip konten gagal."); }
    finally { setBusy(false); }
  }

  async function deleteContent(id: string, confirmed = false) {
    if (!confirmed) { setPendingContentId(id); setModal("delete"); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${id}`, { method: "DELETE" });
      setNotice(result.message ?? "Konten dihapus dari akun."); setModal(null); setPendingContentId("");
      if (selected === id) { setSelected(""); setPreview(null); }
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Penghapusan konten gagal."); }
    finally { setBusy(false); }
  }

  const selectedItem = items.find(item => item.id === selected);
  const closeModal = () => { if (busy) return; setModal(null); setPendingContentId(""); };
  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-4 py-6 text-slate-900 dark:text-slate-100 sm:px-6 sm:py-8">
      <nav className="mb-6 flex items-center justify-between gap-4"><Link className="text-sm text-blue-600 hover:underline" href="/">← Allpha</Link><span className="text-xs text-slate-500">ENG-P13 · Creator Studio</span></nav>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-600">Creator Studio</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Konten & Media</h1><p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300">Kelola draft, media, pratinjau, moderasi, dan riwayat konten melalui satu ruang kerja.</p></div>{session ? <button onClick={() => { setModal("create"); setError(""); setNotice(""); }} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white">＋ Buat konten</button> : null}</header>
      {!session && !loading ? <section className="rounded-2xl border border-slate-200 p-6 dark:border-slate-700"><h2 className="font-semibold">Masuk diperlukan</h2><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Silakan masuk melalui aplikasi Allpha untuk membuat dan mengelola konten.</p><Link href="/" className="mt-4 inline-block rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white">Kembali ke Allpha</Link></section> : null}
      {error ? <div role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</div> : null}
      {notice ? <div role="status" className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">{notice}</div> : null}
      {session ? <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:p-5">
        <div className="flex items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Konten saya</h2><p className="mt-1 text-xs text-slate-500">Draft, konten terkirim, terbit, dan arsip</p></div><div className="flex gap-3"><button onClick={() => { const next = !showDeleted; setShowDeleted(next); void refresh(next).catch(cause => setError(cause instanceof Error ? cause.message : "Refresh gagal.")); }} className="text-sm text-blue-600 hover:underline">{showDeleted ? "Sembunyikan dihapus" : "Tampilkan dihapus"}</button><button onClick={() => void refresh().catch(cause => setError(cause instanceof Error ? cause.message : "Refresh gagal."))} className="text-sm text-blue-600 hover:underline">Muat ulang</button></div></div>
        {loading ? <p className="py-10 text-center text-sm text-slate-500">Memuat konten…</p> : items.length === 0 ? <div className="py-12 text-center"><p className="text-sm text-slate-500">Belum ada konten.</p><button onClick={() => setModal("create")} className="mt-3 rounded-xl border border-slate-300 px-4 py-2 text-sm dark:border-slate-600">Buat draft pertama</button></div> : <ul className="mt-4 space-y-3">{items.map(item => <li key={item.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><p className="line-clamp-2 whitespace-pre-wrap text-sm font-medium">{item.body || (item.media?.length ? item.media.map(media => media.filename).join(", ") : "Konten tanpa teks")}</p><p className="mt-1 text-xs text-slate-500">{item.content_type} · v{item.version} · {item.status} · {item.moderation_status}</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{item.visibility}</span></div>
          <div className="mt-3 flex flex-wrap gap-2"><button onClick={() => void showPreview(item.id)} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Pratinjau</button><button onClick={() => void loadHistory(item.id)} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Riwayat versi</button>{["draft","failed"].includes(item.status) ? <button onClick={() => { setEditingId(item.id); setEditBody(item.body); setEditVisibility(item.visibility); setModal("edit"); }} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Edit</button> : null}{["draft","failed"].includes(item.status) ? <button onClick={() => void publish(item.id)} disabled={busy} className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">Kirim moderasi</button> : null}{item.status === "failed" ? <button onClick={() => void retry(item.id)} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Pulihkan</button> : null}{["draft","failed","review","scheduled"].includes(item.status) ? <button onClick={() => { setSelected(item.id); setScheduleLocal(""); setScheduleTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Jakarta"); setModal("schedule"); setError(""); }} disabled={busy} className="rounded-lg border border-indigo-300 px-3 py-1.5 text-xs text-indigo-700 dark:border-indigo-800 dark:text-indigo-300">{item.status === "scheduled" ? "Atur ulang jadwal" : "Jadwalkan"}</button> : null}{item.status === "scheduled" ? <button onClick={() => void cancelSchedule(item.id)} disabled={busy} className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs text-amber-800">Batalkan jadwal</button> : null}{item.status === "deleted" ? <button onClick={() => void restoreContent(item.id)} disabled={busy} className="rounded-lg border border-emerald-300 px-3 py-1.5 text-xs text-emerald-700">Pulihkan (30 hari)</button> : null}{item.moderation_status === "rejected" ? <button onClick={() => { setSelected(item.id); setAppealReason(""); setModal("appeal"); }} disabled={busy} className="rounded-lg border border-violet-300 px-3 py-1.5 text-xs text-violet-700 dark:border-violet-800 dark:text-violet-300">Ajukan banding</button> : null}{["draft","failed","published"].includes(item.status) ? <button onClick={() => void archive(item.id)} disabled={busy} className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs text-amber-800 dark:border-amber-800 dark:text-amber-300">Arsipkan</button> : null}{["draft","failed","archived"].includes(item.status) ? <button onClick={() => void deleteContent(item.id)} disabled={busy} className="rounded-lg border border-red-300 px-3 py-1.5 text-xs text-red-700 dark:border-red-800 dark:text-red-300">Hapus</button> : null}</div>
        </li>)}</ul>}
      </section> : null}
      {modal ? <div className="fixed inset-0 z-[100] flex items-end justify-center bg-slate-950/70 p-0 backdrop-blur-sm sm:items-center sm:p-4" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) closeModal(); }}>
        <section role="dialog" aria-modal="true" aria-labelledby="content-modal-title" className="flex max-h-[94dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900 sm:rounded-3xl">
          <header className="flex items-center justify-between border-b border-slate-200 px-4 py-4 dark:border-slate-700 sm:px-5"><div><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-600">Allpha · Content lifecycle</p><h2 id="content-modal-title" className="mt-1 text-lg font-semibold">{modal === "create" ? "Buat konten" : modal === "edit" ? "Edit draft" : modal === "preview" ? "Pratinjau konten" : modal === "history" ? "Riwayat versi" : modal === "schedule" ? "Jadwalkan publikasi" : modal === "archive" ? "Arsipkan konten?" : "Hapus konten?"}</h2></div><button type="button" onClick={closeModal} disabled={busy} aria-label="Tutup modal" className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-600">Tutup</button></header>
          <div className="overflow-y-auto p-4 sm:p-5">
            {modal === "create" ? <form className="space-y-4" onSubmit={createDraft}>
              <label className="block text-sm font-medium">Teks konten <span className="font-normal text-slate-500">(opsional jika ada media)</span><textarea value={body} onChange={event => setBody(event.target.value)} maxLength={10000} rows={5} placeholder="Apa yang ingin kamu bagikan?" className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm outline-none focus:border-blue-500 dark:border-slate-600" /></label>
              <label className="block text-sm font-medium">Visibilitas<select value={visibility} onChange={event => setVisibility(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600"><option value="public">Publik (setelah moderasi)</option><option value="followers">Pengikut</option><option value="private">Pribadi</option></select></label>
              <label className="block text-sm font-medium">Gambar, video, atau audio <span className="block text-xs font-normal text-slate-500">JPG/PNG/WebP hingga 10 MB; MP4/WebM dan audio hingga 50 MB</span><input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/wav,audio/webm" onChange={event => { const nextFile = event.target.files?.[0] ?? null; setFile(nextFile); setUploadId(nextFile ? crypto.randomUUID() : ""); }} className="mt-2 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 dark:file:bg-slate-800" /></label>
              {file ? <p className="text-xs text-slate-500">Dipilih: {file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB</p> : null}
              <button disabled={busy || !session || (!body.trim() && !file)} className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Memproses…" : "Simpan draft"}</button>
            </form> : null}
            {modal === "edit" ? <div className="space-y-4"><label className="block text-sm font-medium">Caption / teks<textarea value={editBody} onChange={event => setEditBody(event.target.value)} maxLength={10000} rows={5} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600" /></label><label className="block text-sm font-medium">Visibilitas<select value={editVisibility} onChange={event => setEditVisibility(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600"><option value="public">Publik</option><option value="followers">Pengikut</option><option value="private">Pribadi</option></select></label><label className="block text-sm font-medium">Tambah media ke draft<input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/wav,audio/webm" onChange={event => { const nextFile = event.target.files?.[0] ?? null; setFile(nextFile); setUploadId(nextFile ? crypto.randomUUID() : ""); }} className="mt-2 block w-full text-sm" /></label>{file ? <div className="flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500">{file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB</span><button type="button" onClick={() => void uploadToSelectedDraft()} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Unggah media</button></div> : null}<div className="flex gap-2"><button onClick={() => { const item = items.find(candidate => candidate.id === editingId); if (item) void saveEdit(item); }} disabled={busy} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Simpan versi baru</button><button onClick={closeModal} disabled={busy} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm dark:border-slate-600">Batal</button></div></div> : null}
            {modal === "preview" && preview ? <div><p className="whitespace-pre-wrap text-sm">{preview.item.body || "Tidak ada teks."}</p><div className="mt-4 grid gap-4 sm:grid-cols-2">{preview.media.map(media => <div key={media.id} className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">{media.media_type.startsWith("image/") ? <img src={media.preview_url || ""} alt={media.filename} className="max-h-72 w-full object-contain" /> : media.media_type.startsWith("audio/") ? <div className="p-4"><p className="text-sm font-medium">{media.filename}</p><audio controls preload="metadata" src={media.preview_url || undefined} className="mt-2 w-full" /><p className="text-xs text-slate-500">{media.status} · {media.media_type}</p></div> : <div className="p-4"><p className="text-sm font-medium">{media.filename}</p><p className="text-xs text-slate-500">{media.status} · {media.media_type}</p>{media.preview_url ? <a href={media.preview_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm text-blue-600 underline">Buka media privat sementara</a> : null}</div>}</div>)}</div><p className="mt-4 text-xs text-slate-500">Status: {preview.item.status} · Moderasi: {preview.item.moderation_status} · Versi {preview.item.version}</p></div> : null}
            {modal === "history" ? history.length ? <div className="space-y-3">{history.map(version => <article key={version.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"><div className="flex items-center justify-between gap-3"><strong className="text-sm">Versi {version.version}</strong><time className="text-xs text-slate-500">{new Date(version.created_at).toLocaleString("id-ID")}</time></div><p className="mt-2 whitespace-pre-wrap text-sm">{String(version.snapshot.body ?? "(Tanpa teks)")}</p><p className="mt-1 text-xs text-slate-500">{String(version.snapshot.status)} · {String(version.snapshot.moderation_status)} · {String(version.snapshot.visibility)}</p></article>)}</div> : <p className="py-8 text-center text-sm text-slate-500">Belum ada snapshot versi sebelumnya.</p> : null}
            {modal === "schedule" && selectedItem ? <div className="space-y-4"><p className="text-sm text-slate-600 dark:text-slate-300">Seluruh media harus berstatus siap. Menyimpan jadwal akan otomatis mengirim konten ke antrean moderasi; publikasi hanya terjadi setelah moderator menyetujui konten. Waktu disimpan sebagai UTC dengan zona waktu pembuat.</p><label className="block text-sm font-medium">Tanggal dan waktu publikasi<input type="datetime-local" value={scheduleLocal} onChange={event => setScheduleLocal(event.target.value)} min={new Date(Date.now()+60000).toISOString().slice(0,16)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600"/></label><label className="block text-sm font-medium">IANA timezone<input value={scheduleTimezone} onChange={event => setScheduleTimezone(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600" placeholder="Asia/Jakarta"/></label><p className="text-xs text-slate-500">Dengan melanjutkan, Anda menyatakan memiliki hak atas konten dan telah memberikan disclosure yang diwajibkan.</p><div className="flex gap-2"><button onClick={() => void saveSchedule(selectedItem)} disabled={busy || !scheduleLocal} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Menyimpan…" : "Simpan jadwal"}</button><button onClick={closeModal} disabled={busy} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm dark:border-slate-600">Batal</button></div></div> : null}
            {modal === "appeal" ? <div className="space-y-4"><p className="text-sm text-slate-600 dark:text-slate-300">Jelaskan alasan peninjauan ulang. Banding akan diperiksa operator manusia dan tidak otomatis mempublikasikan konten.</p><textarea value={appealReason} onChange={event => setAppealReason(event.target.value)} minLength={8} maxLength={2000} rows={5} placeholder="Tuliskan alasan banding (minimal 8 karakter)" className="w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600" /><button disabled={busy || appealReason.trim().length < 8 || !selectedItem} onClick={() => { if (!selectedItem) return; setBusy(true); setError(""); setNotice(""); void request(`/v1/content/${selectedItem.id}/appeals`, { method: "POST", body: JSON.stringify({ reason: appealReason.trim(), expected_version: selectedItem.version }) }).then(result => { setNotice(result.message || "Banding diajukan."); setModal(null); return refresh(); }).catch(cause => setError(cause instanceof Error ? cause.message : "Banding gagal diajukan.")).finally(() => setBusy(false)); }} className="rounded-xl bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Kirim banding</button></div> : null}\n            {modal === "archive" ? <div><p className="text-sm text-slate-600 dark:text-slate-300">Konten tidak lagi tampil di Feed publik. Media privat tetap tersimpan.</p><div className="mt-5 flex gap-2"><button onClick={() => void archive(pendingContentId, true)} disabled={busy} className="rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">Ya, arsipkan</button><button onClick={closeModal} disabled={busy} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm dark:border-slate-600">Batal</button></div></div> : null}
            {modal === "delete" ? <div><p className="text-sm text-slate-600 dark:text-slate-300">Konten dihapus secara soft-delete. Media tidak langsung dihapus; masa pemulihan mengikuti kebijakan retensi yang telah disetujui.</p><div className="mt-5 flex gap-2"><button onClick={() => void deleteContent(pendingContentId, true)} disabled={busy} className="rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white">Ya, hapus konten</button><button onClick={closeModal} disabled={busy} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm dark:border-slate-600">Batal</button></div></div> : null}
            {busy ? <p role="status" className="mt-4 text-xs text-slate-500">Memproses permintaan ke API…</p> : null}
          </div>
        </section>
      </div> : null}
    </main>
  );
}