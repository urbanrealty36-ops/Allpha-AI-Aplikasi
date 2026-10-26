"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import FeedView from "../../components/reference-ui/FeedView";
import type { PostItem } from "../../lib/reference-store";

type FeedMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type FeedItem = {
  id: string; owner_id: string; body: string; content_type: string; visibility: string;
  published_at?: string | null; created_at: string; media?: FeedMedia[];
  engagement?: { likes: number; comments: number; saves: number; shares?: number };
  viewer_reaction?: string | null; saved?: boolean; ranking_signals?: string[];
};
type FeedComment = { id: string; actor_user_id: string; body: string; created_at: string };
type FeedStory = { id: string; owner_id: string; created_at: string; discovery_group?: "following" | "suggested_public"; creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null }; media?: FeedMedia[] };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function errorMessage(response: Response) {
  try { const body = await response.json(); return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function FeedPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [stories, setStories] = useState<FeedStory[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [mode, setMode] = useState<"for_you" | "recent">("for_you");
  const [personalizationEnabled, setPersonalizationEnabled] = useState(true);
  const [comments, setComments] = useState<Record<string, FeedComment[]>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const [commentsOpen, setCommentsOpen] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [authPrompt, setAuthPrompt] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    if (session) headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const loadFeed = useCallback(async (reset = true, nextCursor?: string | null) => {
    setLoading(true); setError("");
    try {
      const sharedContentId = reset && typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("content") : null;
      if (sharedContentId) {
        const direct = await request("/v1/feed/item/" + encodeURIComponent(sharedContentId)) as { item: FeedItem };
        setItems([direct.item]); setCursor(null); return;
      }
      const params = new URLSearchParams({ mode, limit: "20" });
      if (!reset && nextCursor) params.set("cursor", nextCursor);
      const data = await request("/v1/feed?" + params.toString()) as { items?: FeedItem[]; next_cursor?: string | null; mode?: string; personalization_enabled?: boolean };
      setItems(current => reset ? (data.items ?? []) : [...current, ...(data.items ?? [])]);
      setCursor(data.next_cursor ?? null);
      if (typeof data.personalization_enabled === "boolean") setPersonalizationEnabled(data.personalization_enabled);
      if (data.mode === "for_you" || data.mode === "recent") setMode(data.mode);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Feed tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [mode, request, session]);

  useEffect(() => {
    // Authentication is optional for public Feed browsing. If the browser auth
    // client is not configured, keep the visitor anonymous instead of blocking
    // the public API read; protected actions still fail closed in the API.
    if (!supabase) { setSession(null); setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session) return;
    void (async () => {
      try {
        const prefs = await request("/v1/feed/preferences") as { preferences?: { personalization_enabled?: boolean; ranking_mode?: "for_you" | "recent" } };
        if (typeof prefs.preferences?.personalization_enabled === "boolean") setPersonalizationEnabled(prefs.preferences.personalization_enabled);
        if (prefs.preferences?.ranking_mode) setMode(prefs.preferences.ranking_mode);
      } catch (cause) { setError(cause instanceof Error ? cause.message : "Preferensi feed tidak dapat dimuat."); }
    })();
  }, [request, session]);

  useEffect(() => { void loadFeed(true); }, [session, mode, loadFeed]);

  useEffect(() => {
    let active = true;
    void request("/v1/stories?limit=30").then((data: { items?: FeedStory[] }) => {
      if (active) setStories(data.items ?? []);
    }).catch(() => { if (active) setStories([]); });
    return () => { active = false; };
  }, [request, session]);

  function requireLogin(action: string) {
    if (session) { setAuthPrompt(""); return false; }
    setAuthPrompt(action);
    return true;
  }

  async function savePreferences(enabled: boolean, rankingMode = mode) {
    if (requireLogin("Masuk untuk mengubah preferensi Feed.")) return;
    setBusyKey("preferences"); setError(""); setNotice("");
    try {
      await request("/v1/feed/preferences", { method: "PUT", body: JSON.stringify({ personalization_enabled: enabled, ranking_mode: rankingMode }) });
      setPersonalizationEnabled(enabled); setMode(rankingMode); setNotice("Preferensi feed disimpan."); await loadFeed(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Preferensi feed gagal disimpan."); }
    finally { setBusyKey(""); }
  }

  async function toggleReaction(item: FeedItem) {
    if (requireLogin("Masuk untuk menyukai postingan.")) return;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", item.viewer_reaction
        ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ reaction: "like" }) });
      await loadFeed(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reaksi gagal disimpan."); }
    finally { setBusyKey(""); }
  }

  async function toggleSave(item: FeedItem) {
    if (requireLogin("Masuk untuk menyimpan postingan.")) return;
    setBusyKey(item.id); setError(""); setNotice("");
    try { await request("/v1/feed/" + encodeURIComponent(item.id) + "/save", { method: item.saved ? "DELETE" : "PUT" }); await loadFeed(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Simpan konten gagal."); }
    finally { setBusyKey(""); }
  }

  async function openComments(item: FeedItem) {
    // Public comments can be read without an account; submitting a comment
    // remains an authenticated mutation in submitComment and the API.
    const opening = !commentsOpen[item.id];
    setCommentsOpen(current => ({ ...current, [item.id]: opening }));
    if (!opening || comments[item.id]) return;
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/comments") as { items?: FeedComment[] };
      setComments(current => ({ ...current, [item.id]: data.items ?? [] }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar tidak dapat dimuat."); }
  }

  async function submitComment(item: FeedItem) {
    if (requireLogin("Masuk untuk mengirim komentar.")) return;
    const body = (commentDrafts[item.id] ?? "").trim();
    if (!body) return;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/comments", { method: "POST", body: JSON.stringify({ body }) }) as { comment: FeedComment };
      setComments(current => ({ ...current, [item.id]: [...(current[item.id] ?? []), data.comment] }));
      setCommentDrafts(current => ({ ...current, [item.id]: "" }));
      setItems(current => current.map(row => row.id === item.id ? { ...row, engagement: { likes: row.engagement?.likes ?? 0, saves: row.engagement?.saves ?? 0, comments: (row.engagement?.comments ?? 0) + 1 } } : row));
      setNotice("Komentar ditambahkan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar gagal dikirim."); }
    finally { setBusyKey(""); }
  }

  async function report(item: FeedItem, reason: "spam" | "harassment" | "privacy" | "misinformation" | "other" = "other") {
    if (requireLogin("Masuk untuk melaporkan konten.")) return;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/report", { method: "POST", body: JSON.stringify({ reason }) });
      setNotice("Laporan diterima untuk ditinjau.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Laporan gagal dikirim."); }
    finally { setBusyKey(""); }
  }

  async function share(item: FeedItem) {
    setError(""); setNotice("");
    if (!session) {
      const url = window.location.origin + "/feed?content=" + encodeURIComponent(item.id);
      try { await navigator.clipboard.writeText(url); setNotice("Tautan publik disalin."); }
      catch { setNotice("Tautan publik: " + url); }
      return;
    }
    setBusyKey(item.id);
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/share", {
        method: "POST", body: JSON.stringify({ share_target: "copy_link" }),
      }) as { share_url: string };
      try {
        await navigator.clipboard.writeText(data.share_url);
        setNotice("Tautan konten disalin.");
      } catch {
        setNotice("Tautan untuk dibagikan: " + data.share_url);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Tautan berbagi gagal dibuat."); }
    finally { setBusyKey(""); }
  }

  const initialCommentsPostId = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("comments") === "1"
    ? new URLSearchParams(window.location.search).get("content")
    : null;

  const postsForReference: PostItem[] = items.map(item => {
    const image = item.media?.find(media => media.media_type.startsWith("image/") && media.preview_url)?.preview_url;
    return {
      id: item.id,
      humanOwner: { name: item.creator?.display_name || item.creator?.username || "Kreator", handle: item.creator?.username || "", avatar: item.creator?.avatar_url || "", verified: false },
      aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
      takeoverMode: false,
      timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
      content: item.body,
      tags: [],
      ...(image ? { image } : {}),
      has3DModel: false,
      likes: item.engagement?.likes ?? 0,
      commentsCount: item.engagement?.comments ?? 0,
      reposts: item.engagement?.shares ?? 0,
      isLiked: Boolean(item.viewer_reaction),
      isBookmarked: Boolean(item.saved),
      comments: (comments[item.id] ?? []).map(comment => ({
        id: comment.id, authorName: "Pengguna",
        authorHandle: "", authorAvatar: "", isAi: false,
        content: comment.body, timestamp: new Date(comment.created_at).toLocaleString("id-ID"), likes: 0,
      })),
    };
  });

  async function addCommentFromReference(postId: string, body: string) {
    if (requireLogin("Masuk untuk mengirim komentar.")) return;
    const item = items.find(row => row.id === postId);
    if (!item || !body.trim()) return;
    setBusyKey(postId); setError(""); setNotice("");
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(postId) + "/comments", { method: "POST", body: JSON.stringify({ body: body.trim() }) }) as { comment: FeedComment };
      setComments(current => ({ ...current, [postId]: [...(current[postId] ?? []), data.comment] }));
      setItems(current => current.map(row => row.id === postId ? { ...row, engagement: { likes: row.engagement?.likes ?? 0, saves: row.engagement?.saves ?? 0, comments: (row.engagement?.comments ?? 0) + 1 } } : row));
      setNotice("Komentar ditambahkan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar gagal dikirim."); }
    finally { setBusyKey(""); }
  }

  return (
    <main className="min-h-screen w-full bg-sky-50 px-0 pb-24 pt-2 text-slate-900">
      {!session && <section className="mx-auto mt-3 max-w-xl rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]"><h1 className="text-sm font-black">Jelajahi Allpha</h1><p className="my-2 text-xs leading-5">{authPrompt || "Lihat postingan publik. Masuk atau daftar untuk menyukai, mengikuti kreator, dan berkomentar."}</p><div className="flex gap-2"><Link className="inline-flex rounded-xl border-2 border-slate-900 bg-sky-300 px-3 py-2 text-xs font-black text-slate-950 shadow-[2px_2px_0px_#0f172a]" href={"/login?next=" + encodeURIComponent(typeof window === "undefined" ? "/feed" : window.location.pathname + window.location.search)}>Masuk</Link><Link className="inline-flex rounded-xl border-2 border-slate-900 bg-white px-3 py-2 text-xs font-black text-slate-950" href={"/login?next=" + encodeURIComponent(typeof window === "undefined" ? "/feed" : window.location.pathname + window.location.search)}>Daftar</Link></div></section>}
        <FeedView
          productionMode
          loading={loading}
          errorMessage={error}
          onRetry={() => { void loadFeed(true); }}
          noticeMessage={notice}
          emptyState={!loading && !error && items.length === 0}
          posts={postsForReference}
          initialCommentsPostId={initialCommentsPostId}
          onLoadComments={postId => { const item = items.find(row => row.id === postId); if (item) void openComments(item); }}
          onSharePost={postId => { const item = items.find(row => row.id === postId); if (item) void share(item); }}
          onReportPost={(postId, reason) => { const item = items.find(row => row.id === postId); if (item) void report(item, reason); }}
          storiesData={[{ id: "create-story", name: "Tambah", isAdd: true }, ...stories.map((story, index) => ({ id: story.id, name: story.creator?.display_name || story.creator?.username || (story.discovery_group === "suggested_public" ? "Disarankan" : "Momen"), img: story.media?.find(media => media.media_type.startsWith("image/") && media.preview_url)?.preview_url ?? undefined, isLive: false, ringColor: ["from-rose-500 via-purple-600 to-amber-500", "from-blue-500 to-sky-400", "from-cyan-400 to-teal-500", "from-purple-500 to-indigo-600"][index % 4] }))]}
          onLikePost={postId => { const item = items.find(row => row.id === postId); if (item) void toggleReaction(item); }}
          onOpenAskAi={(agentName) => { if (requireLogin("Masuk untuk menggunakan Tanya AI Agent.")) return; window.location.assign(agentName && agentName !== "—" ? "/ask-ai?agent=" + encodeURIComponent(agentName) : "/ask-ai"); }}
          onOpenGenerate={() => { if (requireLogin("Masuk untuk menggunakan Generate AI.")) return; window.location.assign("/create"); }}
          onOpenWorld3D={() => { if (requireLogin("Masuk untuk memasuki Universe 3D.")) return; window.location.assign("/spatial/navigation"); }}
          onAddComment={(postId, body) => { void addCommentFromReference(postId, body); }}
          onSelectPost={post => { window.location.assign("/feed?content=" + encodeURIComponent(post.id)); }}
          onOpenReels={() => { window.location.assign("/reels"); }}
          onOpenStory={storyId => { window.location.assign("/stories?story=" + encodeURIComponent(storyId)); }}
          onOpenLiveStage={() => { window.location.assign("/live"); }}
          onOpenCreateModal={() => { if (requireLogin("Masuk untuk membuat postingan.")) return; window.location.assign("/create"); }}
          onOpenFilmAi={() => { window.location.assign("/ai-cinema"); }}
          onOpenMessages={() => { window.location.assign("/messages"); }}
        />
        {cursor && <div className="mx-auto max-w-xl px-4 pb-6"><button className="w-full rounded-2xl border-2 border-slate-900 bg-white px-4 py-3 text-sm font-black shadow-[3px_3px_0px_#0f172a]" onClick={() => void loadFeed(false, cursor)} disabled={loading}>Muat konten berikutnya</button></div>}
    </main>
  );
}
