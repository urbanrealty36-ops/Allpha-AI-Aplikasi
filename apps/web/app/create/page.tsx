"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
type CreatedContent = { id: string; status: string; moderation_status: string };
type ContentResponse = { item: CreatedContent; message?: string };

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.detail?.message ?? body?.error?.message ?? body?.message ?? `Permintaan gagal (HTTP ${response.status}).`;
  } catch {
    return `Permintaan gagal (HTTP ${response.status}).`;
  }
}

export default function CreatePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"public" | "followers" | "private">("public");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data, error: sessionError }) => {
      if (!active) return;
      if (sessionError) setError(sessionError.message);
      setSession(data.session);
      setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (active) setSession(next);
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  async function request(path: string, init: RequestInit = {}) {
    if (!session) throw new Error("Sesi login diperlukan.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await responseMessage(response));
    return response.status === 204 ? null : response.json();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || saving) return;
    if (!body.trim() && !file) { setError("Tulis konten atau pilih file media terlebih dahulu."); return; }
    setSaving(true); setError(""); setNotice("");
    let created: CreatedContent | null = null;
    try {
      const allowedMedia: Record<string, { contentType: "image" | "video" | "audio"; maxBytes: number }> = {
        "image/jpeg": { contentType: "image", maxBytes: 10 * 1024 * 1024 },
        "image/png": { contentType: "image", maxBytes: 10 * 1024 * 1024 },
        "image/webp": { contentType: "image", maxBytes: 10 * 1024 * 1024 },
        "video/mp4": { contentType: "video", maxBytes: 50 * 1024 * 1024 },
        "video/webm": { contentType: "video", maxBytes: 50 * 1024 * 1024 },
        "audio/mpeg": { contentType: "audio", maxBytes: 50 * 1024 * 1024 },
        "audio/mp4": { contentType: "audio", maxBytes: 50 * 1024 * 1024 },
        "audio/aac": { contentType: "audio", maxBytes: 50 * 1024 * 1024 },
        "audio/ogg": { contentType: "audio", maxBytes: 50 * 1024 * 1024 },
        "audio/wav": { contentType: "audio", maxBytes: 50 * 1024 * 1024 },
        "audio/webm": { contentType: "audio", maxBytes: 50 * 1024 * 1024 },
      };
      const mediaPolicy = file ? allowedMedia[file.type] : undefined;
      if (file && !mediaPolicy) throw new Error("Format file tidak didukung. Gunakan JPEG, PNG, WebP, MP4, WebM, atau format audio yang didukung.");
      if (file && mediaPolicy && file.size > mediaPolicy.maxBytes) {
        const limit = mediaPolicy.maxBytes / (1024 * 1024);
        throw new Error(`Ukuran file melewati batas ${limit} MB untuk format ini.`);
      }
      const contentType = mediaPolicy?.contentType ?? "text";
      const result = await request("/v1/content", {
        method: "POST",
        body: JSON.stringify({ body: body.trim(), visibility, content_type: contentType }),
      }) as ContentResponse;
      created = result.item;
      if (!created?.id) throw new Error("Draft tersimpan tetapi ID konten tidak dikembalikan API. Buka konten Anda untuk memeriksa statusnya.");
      if (file) {
        const form = new FormData();
        form.append("file", file, file.name);
        await request("/v1/content/" + encodeURIComponent(created.id) + "/media", { method: "POST", body: form });
      }
      const published = await request("/v1/content/" + encodeURIComponent(created.id) + "/publish", { method: "POST" }) as ContentResponse;
      setBody(""); setFile(null);
      const status = published.item?.status ?? "review";
      setNotice(published.message ?? (status === "review" ? "Konten masuk antrean moderasi. Konten belum tampil untuk publik." : "Permintaan publikasi diterima; periksa status konten."));
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Konten belum berhasil dikirim.";
      setError(created ? `Draft ${created.id} sudah dibuat. ${message} Draft tidak dianggap terpublikasi; periksa statusnya sebelum mencoba ulang.` : message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="mx-auto max-w-2xl p-6 text-sm text-slate-500">Memeriksa sesi…</main>;

  return (
    <>
      <main className="allpha-page allpha-create-page mx-auto min-h-screen w-full max-w-2xl px-4 py-6 text-slate-900 dark:text-slate-100 sm:px-6">
      <nav aria-label="Navigasi utama" className="mb-8 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 dark:border-slate-800">
        <Link href="/feed" className="font-semibold tracking-tight">Allpha Universe</Link>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/feed" className="hover:underline">Feed</Link>
          <Link href="/stories" className="hover:underline">Stories</Link>
          <Link href="/reels" className="hover:underline">Reels</Link>
          <Link href="/agents" className="hover:underline">AI Agent</Link>
          <Link href="/" className="hover:underline">Profil & pengaturan</Link>
        </div>
      </nav>
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">Creator</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Buat konten</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Konten dikirim ke antrean moderasi. Konten tidak langsung dianggap publik.</p>
      </header>
      {!session ? (
        <section className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
          <p className="mb-3 text-sm">Masuk terlebih dahulu untuk membuat konten.</p>
          <Link href="/" className="font-semibold text-blue-600 hover:underline">Masuk melalui Allpha</Link>
        </section>
      ) : (
        <form onSubmit={submit} className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900 sm:p-6">
          <label className="block text-sm font-medium">Isi konten
            <textarea value={body} onChange={event => setBody(event.target.value)} maxLength={10000} rows={7} placeholder="Apa yang ingin Anda bagikan?" className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm leading-6 outline-none focus:border-blue-500 dark:border-slate-600" />
            <span className="mt-1 block text-right text-xs text-slate-500">{body.length}/10.000</span>
          </label>
          <label className="block text-sm font-medium">Visibilitas
            <select value={visibility} onChange={event => setVisibility(event.target.value as typeof visibility)} className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-3 text-sm dark:border-slate-600">
              <option value="public">Publik (tetap melalui moderasi)</option>
              <option value="followers">Pengikut</option>
              <option value="private">Pribadi</option>
            </select>
          </label>
          <label className="block text-sm font-medium">Lampirkan media (opsional)
            <input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/wav,audio/webm" onChange={event => setFile(event.target.files?.[0] ?? null)} className="mt-2 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:font-medium dark:file:bg-slate-800" />
            <span className="mt-1 block text-xs text-slate-500">Format dan ukuran akhir divalidasi oleh API. Media opsional; draft bisa tersimpan jika unggahan gagal.</span>
          </label>
          {file && <div className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800"><p className="font-medium">{file.name}</p><p className="text-xs text-slate-500">{file.type || "Tipe tidak diketahui"} · {(file.size / (1024 * 1024)).toFixed(2)} MB</p><button type="button" onClick={() => setFile(null)} className="mt-2 text-xs font-semibold text-red-600">Hapus lampiran</button></div>}
          {error && <p role="alert" className="rounded-xl border border-red-300 p-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
          {notice && <p role="status" className="rounded-xl border border-emerald-300 p-3 text-sm text-emerald-800 dark:text-emerald-200">{notice}</p>}
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={saving || (!body.trim() && !file)} className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900">{saving ? "Mengirim…" : "Kirim untuk moderasi"}</button>
            <Link href="/feed" className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-medium dark:border-slate-600">Kembali ke Feed</Link>
          </div>
        </form>
      )}
    </main>
    </>
  );
}
