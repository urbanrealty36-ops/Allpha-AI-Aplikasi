"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import StoriesViewerModal from "../../components/reference-ui/StoriesViewerModal";
import type { StoryItem } from "../../components/reference-ui/StoriesViewerModal";
type StoryMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type Story = {
  id: string; owner_id: string; body: string; content_type: string; visibility: string;
  status: string; moderation_status: string; version: number; created_at: string;
  published_at?: string | null; expires_at?: string | null; media?: StoryMedia[];
  creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null };
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function messageFor(response: Response) {
  try { const data = await response.json(); return data?.error?.message ?? data?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function StoriesPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [mine, setMine] = useState<Story[]>([]);
  const [active, setActive] = useState<Story[]>([]);
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"public" | "followers" | "private">("public");
  const [ttl, setTtl] = useState(24);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const method = (init.method || "GET").toUpperCase();
    if (!session && method !== "GET") throw new Error("Masuk terlebih dahulu untuk mengubah Stories.");
    const headers = new Headers(init.headers);
    if (session) headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await messageFor(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const reload = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const activeResult = await request("/v1/stories?limit=100") as { items?: Story[] };
      setActive(activeResult.items ?? []);
      if (session) {
        const mineResult = await request("/v1/stories/mine?limit=50") as { items?: Story[] };
        setMine(mineResult.items ?? []);
      } else {
        setMine([]);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Stories belum dapat dimuat."); }
    finally { setLoading(false); }
  }, [request, session]);

  useEffect(() => {
    if (!supabase) { setSession(null); setLoading(false); return; }
    let alive = true;
    void supabase.auth.getSession().then(({ data }) => { if (alive) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => { if (alive) setSession(next); });
    return () => { alive = false; data.subscription.unsubscribe(); };
  }, [supabase]);
  useEffect(() => { void reload(); }, [session, reload]);
  useEffect(() => {
    const storyId = new URLSearchParams(window.location.search).get("story");
    if (storyId) setSelectedStoryId(storyId);
  }, []);

  async function createStory(event: FormEvent) {
    event.preventDefault();
    if (!body.trim() && !file) { setError("Isi teks atau pilih gambar/video terlebih dahulu."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await request("/v1/stories", {
        method: "POST",
        body: JSON.stringify({ body: body.trim(), visibility, expires_after_hours: ttl }),
      }) as { item: Story };
      if (file) {
        const form = new FormData(); form.append("file", file);
        await request("/v1/content/" + encodeURIComponent(created.item.id) + "/media", { method: "POST", body: form });
      }
      const submitted = await request("/v1/content/" + encodeURIComponent(created.item.id) + "/publish", { method: "POST" }) as { item?: Story; message?: string };
      setBody(""); setFile(null);
      const picker = document.getElementById("story-media") as HTMLInputElement | null;
      if (picker) picker.value = "";
      const status = submitted.item?.status ?? created.item.status;
      const moderation = submitted.item?.moderation_status ?? created.item.moderation_status;
      setNotice(submitted.message
        ? `${submitted.message} Status: ${status}; moderasi: ${moderation}.`
        : `Story diterima API. Status: ${status}; moderasi: ${moderation}.`);
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Story tidak dapat disimpan."); }
    finally { setBusy(false); }
  }

  async function archive(story: Story) {
    setBusy(true); setError(""); setNotice("");
    try {
      await request("/v1/stories/" + encodeURIComponent(story.id), { method: "DELETE" });
      setNotice("Story diarsipkan.");
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Story tidak dapat diarsipkan."); }
    finally { setBusy(false); }
  }

  const selectedStory = active.find(story => story.id === selectedStoryId) ?? null;
  const closeStory = useCallback(() => {
    setSelectedStoryId(null);
    window.history.replaceState(null, "", "/stories");
  }, []);

  return (
    <>
      <main className="allpha-page allpha-stories-page mx-auto min-h-screen w-full max-w-4xl px-4 py-6 text-slate-900 dark:text-slate-100 sm:px-6">
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">Allpha Universe</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Stories & Moments</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Momen sementara dengan audience scope dan waktu kedaluwarsa yang ditegakkan server. Story baru masuk moderasi sebelum ditampilkan.</p>
      </header>
      {selectedStoryId && selectedStory && <StoriesViewerModal
        isOpen
        productionMode
        initialIndex={Math.max(0, active.findIndex(story => story.id === selectedStoryId))}
        onClose={closeStory}
        storiesData={active.map(story => {
          const media = story.media?.find(item => item.preview_url && (item.media_type.startsWith("image/") || item.media_type.startsWith("video/")));
          return {
            id: story.id,
            creatorName: story.creator?.display_name || story.creator?.username || "Kreator",
            creatorHandle: story.creator?.username || "",
            creatorAvatar: story.creator?.avatar_url || "",
            isAiAgent: false,
            mediaUrl: media?.preview_url || "",
            mediaType: media?.media_type,
            ownerId: story.owner_id,
            caption: story.body || "",
            timestamp: new Date(story.created_at).toLocaleString("id-ID"),
            expiresAt: story.expires_at || undefined,
          } satisfies StoryItem;
        })}
        enabledReactions={session && selectedStory.owner_id !== session.user.id ? ["❤️"] : []}
        onSendReaction={session && selectedStory.owner_id !== session.user.id ? async (storyId, emoji) => {
          if (emoji !== "❤️") throw new Error("Reaksi ini belum didukung kontrak API.");
          await request("/v1/feed/" + encodeURIComponent(storyId) + "/reaction", {
            method: "PUT",
            body: JSON.stringify({ reaction: "like" }),
          });
          setNotice("Reaksi Story tersimpan melalui API.");
        } : undefined}
        onSendReply={session ? async (storyId, body) => {
          await request("/v1/feed/" + encodeURIComponent(storyId) + "/comments", {
            method: "POST",
            body: JSON.stringify({ body }),
          });
          setNotice("Balasan Story tersimpan melalui API.");
        } : undefined}
      />}
      {selectedStoryId && !selectedStory && !loading && <section className="mb-6 rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a] dark:bg-slate-900" aria-label="Story unavailable">
        <div className="mb-3 flex items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-cyan-700">Story publik</p><h2 className="text-lg font-semibold">Story tidak tersedia</h2></div><button type="button" onClick={closeStory} className="rounded-xl border-2 border-slate-900 px-3 py-2 text-sm font-semibold">Tutup</button></div>
        <p className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">Story tidak tersedia untuk akun ini, sudah kedaluwarsa, atau tidak ditemukan.</p>
      </section>}
      {!session ? <>
        <section className="mb-6 rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a] dark:bg-slate-900"><h2 className="text-sm font-black">Temukan Stories publik</h2><p className="my-2 text-xs leading-5 text-slate-600 dark:text-slate-300">Lihat momen publik dari kreator yang belum Anda ikuti. Masuk atau daftar untuk membuat Story dan menggunakan fitur akun.</p><div className="flex gap-2"><Link className="rounded-xl border-2 border-slate-900 bg-sky-300 px-3 py-2 text-xs font-black text-slate-950" href={"/login?next=" + encodeURIComponent("/stories")}>Masuk</Link><Link className="rounded-xl border-2 border-slate-900 px-3 py-2 text-xs font-black" href={"/login?next=" + encodeURIComponent("/stories")}>Daftar</Link></div></section>
        {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
        <section className="mb-8"><div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">Stories publik</h2><button onClick={() => void reload()} disabled={loading} className="text-sm text-cyan-600 hover:underline">Muat ulang</button></div>
          {loading ? <p role="status" className="text-sm text-slate-500">Memuat Stories publik…</p> : active.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">Belum ada Story publik yang tersedia.</p> : <div className="grid gap-3 sm:grid-cols-2">{active.map(story => <button type="button" key={story.id} onClick={() => { setSelectedStoryId(story.id); window.history.replaceState(null, "", "/stories?story=" + encodeURIComponent(story.id)); }} className="rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:border-cyan-500 dark:bg-slate-900 dark:border-slate-700"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-xs font-semibold uppercase text-cyan-600">{story.creator?.display_name || story.creator?.username || "Kreator publik"}</span><span className="text-xs text-slate-500">Publik</span></div>{story.media?.find(media => media.preview_url && media.media_type.startsWith("image/"))?.preview_url && <img src={story.media.find(media => media.preview_url && media.media_type.startsWith("image/"))?.preview_url || ""} alt="" className="mb-3 max-h-56 w-full rounded-xl object-cover" />}{story.body && <p className="line-clamp-3 whitespace-pre-wrap text-sm">{story.body}</p>}<span className="mt-3 inline-block text-xs font-semibold text-cyan-700">Buka Story →</span></button>)}</div>}
        </section>
      </> : <>
        <form onSubmit={createStory} className="mb-6 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold">Bagikan momen</h2>
          <textarea aria-label="Isi Story" value={body} onChange={e => setBody(e.target.value)} maxLength={2000} rows={4} className="w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600" placeholder="Apa yang sedang terjadi? (opsional jika ada media)" />
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">Audience
              <select value={visibility} onChange={e => setVisibility(e.target.value as typeof visibility)} className="mt-1 block w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-600">
                <option value="public">Publik</option><option value="followers">Pengikut</option><option value="private">Pribadi (draft pemilik)</option>
              </select>
            </label>
            <label className="text-sm">Kedaluwarsa
              <select value={ttl} onChange={e => setTtl(Number(e.target.value))} className="mt-1 block w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-600">
                <option value={6}>6 jam</option><option value={12}>12 jam</option><option value={24}>24 jam</option><option value={48}>48 jam</option><option value={72}>72 jam</option><option value={168}>7 hari</option>
              </select>
            </label>
            <label className="text-sm">Gambar / video
              <input id="story-media" type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" onChange={e => setFile(e.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm" />
            </label>
          </div>
          {file && <p className="text-xs text-slate-500">{file.name} · {(file.size / 1048576).toFixed(2)} MB</p>}
          <button disabled={busy} className="rounded-xl bg-indigo-300 px-5 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50">{busy ? "Mengirim…" : "Kirim ke moderasi"}</button>
        </form>
        {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}
        {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-300 p-3 text-sm">{notice}</p>}
        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">Momen aktif</h2><button onClick={() => void reload()} disabled={loading || busy} className="text-sm text-cyan-600 hover:underline">Muat ulang</button></div>
          {loading ? <p className="text-sm text-slate-500">Memuat Stories…</p> : active.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">Belum ada Story aktif yang dapat Anda lihat.</p> : <div className="grid gap-3 sm:grid-cols-2">{active.map(story => <article key={story.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-xs font-semibold uppercase text-cyan-600">{story.visibility}</span><span className="text-xs text-slate-500">{story.expires_at ? "Berakhir " + new Date(story.expires_at).toLocaleString("id-ID") : "Expiry belum tersedia"}</span></div><p className="whitespace-pre-wrap text-sm">{story.body || "Momen media"}</p>{story.media?.map(media => media.preview_url ? <a key={media.id} href={media.preview_url} target="_blank" rel="noreferrer" className="mt-3 block break-all text-xs text-blue-600 underline">{media.filename} · buka media</a> : null)}<button type="button" onClick={() => { setSelectedStoryId(story.id); window.history.replaceState(null, "", "/stories?story=" + encodeURIComponent(story.id)); }} className="mt-3 rounded-xl border-2 border-slate-900 bg-sky-300 px-3 py-2 text-xs font-black text-slate-950 shadow-[2px_2px_0px_#0f172a]">Buka Story</button></article>)}</div>}
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold">Stories saya</h2>
          {mine.length === 0 ? <p className="text-sm text-slate-500">Belum ada Story pada akun ini.</p> : <div className="space-y-3">{mine.map(story => <article key={story.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm">{story.status} · {story.moderation_status}</strong><span className="text-xs text-slate-500">{story.expires_at ? "Expiry: " + new Date(story.expires_at).toLocaleString("id-ID") : "Expiry dimulai setelah publikasi disetujui"}</span></div><p className="mt-2 whitespace-pre-wrap text-sm">{story.body || "Momen media"}</p>{story.status !== "archived" && story.status !== "deleted" && <button disabled={busy} onClick={() => void archive(story)} className="mt-3 text-sm text-red-600 hover:underline">Arsipkan Story</button>}</article>)}</div>}
        </section>
      </>}
    </main>
    </>
  );
}
