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
  const [selected, setSelected] = useState("");
  const [preview, setPreview] = useState<{ item: Item; media: Media[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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

  const refresh = useCallback(async () => {
    const result = await request("/v1/content/mine");
    setItems(Array.isArray(result?.items) ? result.items : []);
  }, [request]);

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
        body: body.trim(), visibility, content_type: file ? (file.type.startsWith("video/") ? "video" : "image") : "text"
      }) });
      const id = created.item.id as string;
      setSelected(id);
      await refresh();
      if (file) {
        const data = new FormData(); data.append("file", file);
        await request(`/v1/content/${id}/media`, { method: "POST", body: data });
      }
      setBody(""); setFile(null);
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
      await request(`/v1/content/${selected}/media`, { method: "POST", body: data });
      setFile(null); setNotice("Media berhasil diunggah ke draft.");
      await refresh(); await showPreview(selected);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unggah gagal. Draft tetap tersimpan dan dapat dicoba lagi."); }
    finally { setBusy(false); }
  }

  async function showPreview(id: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/content/${id}/preview`);
      setPreview({ item: result.item, media: result.media ?? [] }); setSelected(id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pratinjau gagal dimuat."); }
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

  const selectedItem = items.find(item => item.id === selected);
  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-5 py-8 text-slate-900 dark:text-slate-100">
      <nav className="mb-8 flex items-center justify-between gap-4"><Link className="text-sm text-blue-600 hover:underline" href="/">← Allpha</Link><span className="text-xs text-slate-500">ENG-P13 · Creator Studio</span></nav>
      <header className="mb-8"><p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-600">Creator Studio</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Buat konten</h1><p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300">Simpan draft, unggah gambar/video ke penyimpanan privat, periksa pratinjau, lalu kirim untuk moderasi sebelum tampil ke publik.</p></header>
      {!session && !loading ? <section className="rounded-2xl border border-slate-200 p-6 dark:border-slate-700"><h2 className="font-semibold">Masuk diperlukan</h2><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Silakan masuk melalui aplikasi Allpha untuk membuat dan mengelola konten.</p><Link href="/" className="mt-4 inline-block rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white">Kembali ke Allpha</Link></section> : null}
      {error ? <div role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</div> : null}
      {notice ? <div role="status" className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">{notice}</div> : null}
      {session ? <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
        <section className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
          <h2 className="text-lg font-semibold">Draft baru</h2>
          <form className="mt-4 space-y-4" onSubmit={createDraft}>
            <label className="block text-sm font-medium">Teks konten <span className="font-normal text-slate-500">(opsional jika ada media)</span><textarea value={body} onChange={event => setBody(event.target.value)} maxLength={10000} rows={5} placeholder="Apa yang ingin kamu bagikan?" className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm outline-none focus:border-blue-500 dark:border-slate-600" /></label>
            <label className="block text-sm font-medium">Visibilitas<select value={visibility} onChange={event => setVisibility(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600"><option value="public">Publik (setelah moderasi)</option><option value="followers">Pengikut</option><option value="private">Pribadi</option></select></label>
            <label className="block text-sm font-medium">Gambar atau video <span className="font-normal text-slate-500">JPG, PNG, WebP hingga 10 MB; MP4/WebM hingga 50 MB</span><input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" onChange={event => setFile(event.target.files?.[0] ?? null)} className="mt-2 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 dark:file:bg-slate-800" /></label>
            {file ? <p className="text-xs text-slate-500">Dipilih: {file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB</p> : null}
            {selected && file ? <button type="button" onClick={() => void uploadToSelectedDraft()} disabled={busy} className="mr-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold dark:border-slate-600">Unggah ke draft terpilih</button> : null}
            <button disabled={busy || !session || (!body.trim() && !file)} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Memproses…" : "Simpan draft baru"}</button>
          </form>
        </section>
        <section className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
          <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Konten saya</h2><button onClick={() => void refresh().catch(cause => setError(cause instanceof Error ? cause.message : "Refresh gagal."))} className="text-sm text-blue-600 hover:underline">Muat ulang</button></div>
          {loading ? <p className="py-8 text-sm text-slate-500">Memuat konten…</p> : items.length === 0 ? <p className="py-8 text-sm text-slate-500">Belum ada draft. Konten baru akan muncul di sini.</p> : <ul className="mt-4 space-y-3">{items.map(item => <li key={item.id} className={`rounded-xl border p-3 dark:border-slate-700 ${selected === item.id ? "border-blue-500 bg-blue-50/60 dark:bg-blue-950/30" : "border-slate-200"}`}>
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="line-clamp-2 whitespace-pre-wrap text-sm font-medium">{item.body || (item.media?.length ? item.media.map(media => media.filename).join(", ") : "Konten tanpa teks")}</p><p className="mt-1 text-xs text-slate-500">{item.content_type} · v{item.version} · {item.status} · {item.moderation_status}</p></div><button onClick={() => void showPreview(item.id)} disabled={busy} className="shrink-0 rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Pratinjau</button></div>
            <div className="mt-3 flex flex-wrap gap-2">{["draft","failed"].includes(item.status) ? <button onClick={() => void publish(item.id)} disabled={busy} className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">Kirim untuk moderasi</button> : null}{item.status === "failed" ? <button onClick={() => void retry(item.id)} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600">Pulihkan draft</button> : null}</div>
          </li>)}</ul>}
        </section>
        {preview ? <section className="rounded-2xl border border-slate-200 p-5 lg:col-span-2 dark:border-slate-700"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Pratinjau · {preview.item.status}</h2><button onClick={() => setPreview(null)} className="text-sm text-slate-500 hover:underline">Tutup</button></div><p className="mt-3 whitespace-pre-wrap text-sm">{preview.item.body || "Tidak ada teks."}</p><div className="mt-4 grid gap-4 sm:grid-cols-2">{preview.media.map(media => <div key={media.id} className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">{media.preview_url ? media.media_type.startsWith("video/") ? <video controls preload="metadata" src={media.preview_url} className="max-h-96 w-full bg-black" /> : <img alt={media.filename} src={media.preview_url} className="max-h-96 w-full object-contain" /> : <p className="p-4 text-sm text-slate-500">URL pratinjau tidak tersedia.</p>}<p className="p-3 text-xs text-slate-500">{media.filename} · {media.status}</p></div>)}</div><p className="mt-4 text-xs text-slate-500">URL pratinjau berlaku 5 menit. Konten berstatus review tidak tersedia untuk feed publik sampai moderasi menyetujuinya.</p></section> : selectedItem ? <section className="rounded-2xl border border-dashed border-slate-300 p-5 lg:col-span-2 dark:border-slate-700"><h2 className="font-semibold">Pratinjau konten</h2><p className="mt-2 text-sm text-slate-500">Pilih tombol pratinjau untuk menghasilkan URL media privat sementara.</p></section> : null}
      </div> : null}
    </main>
  );
}
