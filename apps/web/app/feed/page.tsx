"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import FeedView from "../../components/reference-ui/FeedView";
import CreatePostModal from "../../components/reference-ui/CreatePostModal";
import type { AIAgentProfile, HumanProfile, PostItem } from "../../lib/reference-store";

type FeedMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type FeedItem = {
  id: string; owner_id: string; body: string; content_type: string; visibility: string;
  published_at?: string | null; created_at: string; media?: FeedMedia[];
  creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null };
  engagement?: { likes: number; comments: number; saves: number; shares?: number };
  viewer_reaction?: string | null; saved?: boolean; ranking_signals?: string[];
};
type FeedComment = { id: string; actor_user_id: string; body: string; created_at: string };
type FeedStory = { id: string; owner_id: string; created_at: string; discovery_group?: "following" | "suggested_public"; creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null }; media?: FeedMedia[] };
type MeResponse = { user?: { id: string; email?: string }; profile?: { username?: string | null; display_name?: string | null; avatar_url?: string | null; bio?: string | null } | null };
type ApiAgent = { id: string; display_name: string; handle: string; avatar_url?: string | null; description?: string | null; persona?: Record<string, unknown> | null; status: string; ownership?: { owner_user_id?: string; status?: string } | null };
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
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [composerHuman, setComposerHuman] = useState<HumanProfile | null>(null);
  const [composerAgent, setComposerAgent] = useState<AIAgentProfile | null>(null);
  const sessionEpoch = useRef(0);
  const sessionUserId = useRef<string | null>(null);
  const feedRequestSequence = useRef(0);
  const preferencesRequestSequence = useRef(0);
  const commentRequestSequence = useRef(0);

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
    const epoch = sessionEpoch.current;
    const sequence = ++feedRequestSequence.current;
    setLoading(true); setError("");
    try {
      const sharedContentId = reset && typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("content") : null;
      if (sharedContentId) {
        const direct = await request("/v1/feed/item/" + encodeURIComponent(sharedContentId)) as { item: FeedItem };
        if (epoch !== sessionEpoch.current || sequence !== feedRequestSequence.current) return;
        setItems([direct.item]); setCursor(null); return;
      }
      const params = new URLSearchParams({ mode, limit: "20" });
      if (!reset && nextCursor) params.set("cursor", nextCursor);
      const data = await request("/v1/feed?" + params.toString()) as { items?: FeedItem[]; next_cursor?: string | null; mode?: string; personalization_enabled?: boolean };
      if (epoch !== sessionEpoch.current || sequence !== feedRequestSequence.current) return;
      setItems(current => reset ? (data.items ?? []) : [...current, ...(data.items ?? [])]);
      setCursor(data.next_cursor ?? null);
      if (typeof data.personalization_enabled === "boolean") setPersonalizationEnabled(data.personalization_enabled);
      if (data.mode === "for_you" || data.mode === "recent") setMode(data.mode);
    } catch (cause) {
      if (epoch === sessionEpoch.current && sequence === feedRequestSequence.current) setError(cause instanceof Error ? cause.message : "Feed tidak dapat dimuat.");
    } finally { if (epoch === sessionEpoch.current && sequence === feedRequestSequence.current) setLoading(false); }
  }, [mode, request, session]);

  useEffect(() => {
    // Authentication is optional for public Feed browsing. If the browser auth
    // client is not configured, keep the visitor anonymous instead of blocking
    // the public API read; protected actions still fail closed in the API.
    if (!supabase) { setSession(null); setLoading(false); return; }
    let active = true;
    let authEventSeen = false;
    const applySession = (next: Session | null) => {
      const nextUserId = next?.user.id || null;
      if (sessionUserId.current !== nextUserId) {
        sessionUserId.current = nextUserId;
        sessionEpoch.current += 1;
        feedRequestSequence.current += 1;
        preferencesRequestSequence.current += 1;
        setItems([]);
        setStories([]);
        setCursor(null);
        setComments({});
        setCommentDrafts({});
        setCommentsOpen({});
        setComposerHuman(null);
        setComposerAgent(null);
        setBusyKey("");
        setError("");
        setNotice("");
        setAuthPrompt("");
        setLoading(Boolean(next));
      }
      setSession(next);
    };
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      authEventSeen = true;
      if (active) applySession(next);
    });
    void supabase.auth.getSession().then(({ data }) => {
      if (active && !authEventSeen) applySession(data.session);
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session) return;
    const epoch = sessionEpoch.current;
    const sequence = ++preferencesRequestSequence.current;
    void (async () => {
      try {
        const prefs = await request("/v1/feed/preferences") as { preferences?: { personalization_enabled?: boolean; ranking_mode?: "for_you" | "recent" } };
        if (epoch !== sessionEpoch.current || sequence !== preferencesRequestSequence.current) return;
        if (typeof prefs.preferences?.personalization_enabled === "boolean") setPersonalizationEnabled(prefs.preferences.personalization_enabled);
        if (prefs.preferences?.ranking_mode) setMode(prefs.preferences.ranking_mode);
      } catch (cause) {
        if (epoch === sessionEpoch.current && sequence === preferencesRequestSequence.current) setError(cause instanceof Error ? cause.message : "Preferensi feed tidak dapat dimuat.");
      }
    })();
  }, [request, session]);

  useEffect(() => { void loadFeed(true); }, [session, mode, loadFeed]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const composeRequested = new URLSearchParams(window.location.search).get("compose") === "1";
    if (!composeRequested) return;
    if (!session) {
      setAuthPrompt("Masuk untuk membuat postingan.");
      return;
    }
    if (composerHuman) setCreateModalOpen(true);
  }, [session, composerHuman]);

  // Load the actual signed-in Human and owned Agent before opening the copied source composer.
  useEffect(() => {
    if (!session) {
      setComposerHuman(null);
      setComposerAgent(null);
      return;
    }
    let active = true;
    const loadComposerIdentity = async () => {
      try {
        const me = await request("/v1/me") as MeResponse;
        if (!me.user) throw new Error("Identitas Human kanonis belum tersedia.");
        let agentPayload: { items?: ApiAgent[] } = { items: [] };
        try {
          agentPayload = await request("/v1/agents") as { items?: ApiAgent[] };
        } catch {
          // A Human can still create a Human-authored post when the optional Agent catalog is unavailable.
          agentPayload = { items: [] };
        }
        const name = me.profile?.display_name?.trim() || me.user.email || "Pengguna";
        const human: HumanProfile = {
          id: me.user.id,
          name,
          username: me.profile?.username || "",
          avatar: me.profile?.avatar_url || "/icon.svg",
          bio: me.profile?.bio || "",
          followers: 0,
          following: 0,
          postsCount: 0,
          badge: "Human",
        };
        const owned = (agentPayload.items || []).filter(item =>
          item.ownership?.owner_user_id === me.user!.id && item.ownership.status === "active"
        );
        const activeAgent = owned.find(item => item.status === "active") || null;
        if (!active) return;
        setComposerHuman(human);
        setComposerAgent(activeAgent ? {
          id: activeAgent.id,
          name: activeAgent.display_name,
          handle: activeAgent.handle,
          avatar: activeAgent.avatar_url || "/icon.svg",
          ownerId: me.user.id,
          ownerName: name,
          ownerHandle: me.profile?.username || "",
          specialty: activeAgent.description || "Belum ditentukan",
          category: typeof activeAgent.persona?.category === "string" ? activeAgent.persona.category : "Belum ditentukan",
          bio: activeAgent.description || "",
          skills: [],
          creditsEarned: 0,
          autoReply: false,
          model: "Allpha AI Runtime",
          goals: [],
          tasks: [],
        } : null);
      } catch (cause) {
        if (active) {
          setComposerHuman(null);
          setComposerAgent(null);
          setError(cause instanceof Error ? cause.message : "Identitas untuk membuat konten belum tersedia.");
        }
      }
    };
    void loadComposerIdentity();
    return () => { active = false; };
  }, [request, session]);

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
    const epoch = sessionEpoch.current;
    setBusyKey("preferences"); setError(""); setNotice("");
    try {
      await request("/v1/feed/preferences", { method: "PUT", body: JSON.stringify({ personalization_enabled: enabled, ranking_mode: rankingMode }) });
      if (epoch !== sessionEpoch.current) return;
      setPersonalizationEnabled(enabled); setMode(rankingMode); setNotice("Preferensi feed disimpan."); await loadFeed(true);
    } catch (cause) { if (epoch === sessionEpoch.current) setError(cause instanceof Error ? cause.message : "Preferensi feed gagal disimpan."); }
    finally { if (epoch === sessionEpoch.current) setBusyKey(""); }
  }

  async function toggleReaction(item: FeedItem) {
    if (requireLogin("Masuk untuk menyukai postingan.")) return;
    const epoch = sessionEpoch.current;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", item.viewer_reaction
        ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ reaction: "like" }) });
      if (epoch !== sessionEpoch.current) return;
      await loadFeed(true);
    } catch (cause) { if (epoch === sessionEpoch.current) setError(cause instanceof Error ? cause.message : "Reaksi gagal disimpan."); }
    finally { if (epoch === sessionEpoch.current) setBusyKey(""); }
  }

  async function toggleSave(item: FeedItem) {
    if (requireLogin("Masuk untuk menyimpan postingan.")) return;
    const epoch = sessionEpoch.current;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/save", { method: item.saved ? "DELETE" : "PUT" });
      if (epoch !== sessionEpoch.current) return;
      await loadFeed(true);
    } catch (cause) { if (epoch === sessionEpoch.current) setError(cause instanceof Error ? cause.message : "Simpan konten gagal."); }
    finally { if (epoch === sessionEpoch.current) setBusyKey(""); }
  }

  async function openComments(item: FeedItem) {
    // Public comments can be read without an account; submitting a comment
    // remains an authenticated mutation in submitComment and the API.
    const opening = !commentsOpen[item.id];
    setCommentsOpen(current => ({ ...current, [item.id]: opening }));
    if (!opening || comments[item.id]) return;
    const epoch = sessionEpoch.current;
    const sequence = ++commentRequestSequence.current;
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/comments") as { items?: FeedComment[] };
      if (epoch !== sessionEpoch.current || sequence !== commentRequestSequence.current) return;
      setComments(current => ({ ...current, [item.id]: data.items ?? [] }));
    } catch (cause) {
      if (epoch === sessionEpoch.current && sequence === commentRequestSequence.current) setError(cause instanceof Error ? cause.message : "Komentar tidak dapat dimuat.");
    }
  }

  async function submitComment(item: FeedItem) {
    if (requireLogin("Masuk untuk mengirim komentar.")) return;
    const body = (commentDrafts[item.id] ?? "").trim();
    if (!body) return;
    const epoch = sessionEpoch.current;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/comments", { method: "POST", body: JSON.stringify({ body }) }) as { comment: FeedComment };
      if (epoch !== sessionEpoch.current) return;
      setComments(current => ({ ...current, [item.id]: [...(current[item.id] ?? []), data.comment] }));
      setCommentDrafts(current => ({ ...current, [item.id]: "" }));
      setItems(current => current.map(row => row.id === item.id ? { ...row, engagement: { likes: row.engagement?.likes ?? 0, saves: row.engagement?.saves ?? 0, comments: (row.engagement?.comments ?? 0) + 1 } } : row));
      setNotice("Komentar ditambahkan.");
    } catch (cause) { if (epoch === sessionEpoch.current) setError(cause instanceof Error ? cause.message : "Komentar gagal dikirim."); }
    finally { if (epoch === sessionEpoch.current) setBusyKey(""); }
  }

  async function report(item: FeedItem, reason: "spam" | "harassment" | "privacy" | "misinformation" | "other" = "other") {
    if (requireLogin("Masuk untuk melaporkan konten.")) return;
    const epoch = sessionEpoch.current;
    setBusyKey(item.id); setError(""); setNotice("");
    try {
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/report", { method: "POST", body: JSON.stringify({ reason }) });
      if (epoch !== sessionEpoch.current) return;
      setNotice("Laporan diterima untuk ditinjau.");
    } catch (cause) { if (epoch === sessionEpoch.current) setError(cause instanceof Error ? cause.message : "Laporan gagal dikirim."); }
    finally { if (epoch === sessionEpoch.current) setBusyKey(""); }
  }

  async function share(item: FeedItem) {
    setError(""); setNotice("");
    if (!session) {
      const url = window.location.origin + "/feed?content=" + encodeURIComponent(item.id);
      try { await navigator.clipboard.writeText(url); setNotice("Tautan publik disalin."); }
      catch { setNotice("Tautan publik: " + url); }
      return;
    }
    const epoch = sessionEpoch.current;
    setBusyKey(item.id);
    try {
      const data = await request("/v1/feed/" + encodeURIComponent(item.id) + "/share", {
        method: "POST", body: JSON.stringify({ share_target: "copy_link" }),
      }) as { share_url: string };
      if (epoch !== sessionEpoch.current) return;
      try {
        await navigator.clipboard.writeText(data.share_url);
        setNotice("Tautan konten disalin.");
      } catch {
        setNotice("Tautan untuk dibagikan: " + data.share_url);
      }
    } catch (cause) { if (epoch === sessionEpoch.current) setError(cause instanceof Error ? cause.message : "Tautan berbagi gagal dibuat."); }
    finally { if (epoch === sessionEpoch.current) setBusyKey(""); }
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

  async function createPostFromReference(post: PostItem, visibility: "PUBLIC" | "FOLLOWERS" | "PRIVATE", mediaFile: File | null): Promise<{ accepted: boolean; message?: string }> {
    if (!session) {
      setAuthPrompt("Masuk untuk membuat postingan.");
      return { accepted: false, message: "Sesi login diperlukan untuk membuat konten." };
    }
    setError("");
    setNotice("");
    let createdId: string | null = null;
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
      const mediaPolicy = mediaFile ? allowedMedia[mediaFile.type] : undefined;
      if (mediaFile && !mediaPolicy) throw new Error("Format media tidak didukung.");
      if (mediaFile && mediaPolicy && mediaFile.size > mediaPolicy.maxBytes) {
        throw new Error(`Ukuran media melewati batas ${mediaPolicy.maxBytes / (1024 * 1024)} MB.`);
      }
      const created = await request("/v1/content", {
        method: "POST",
        body: JSON.stringify({ body: post.content.trim(), visibility: visibility.toLowerCase(), content_type: mediaPolicy?.contentType ?? "text" }),
      }) as { item?: { id?: string; status?: string; moderation_status?: string }; message?: string };
      const contentId = created.item?.id;
      createdId = contentId ?? null;
      if (!contentId) throw new Error("API tidak mengembalikan ID konten kanonis.");
      if (mediaFile) {
        const form = new FormData();
        form.append("file", mediaFile, mediaFile.name);
        await request("/v1/content/" + encodeURIComponent(contentId) + "/media", { method: "POST", body: form });
      }
      const published = await request("/v1/content/" + encodeURIComponent(contentId) + "/publish", { method: "POST" }) as {
        item?: { status?: string; moderation_status?: string };
        message?: string;
      };
      const status = published.item?.status ?? created.item?.status ?? "unknown";
      const moderation = published.item?.moderation_status ?? created.item?.moderation_status ?? "unknown";
      const confirmation = published.message
        ? `${published.message} Status: ${status}; moderasi: ${moderation}.`
        : status === "published" && moderation === "approved"
          ? "Konten disetujui dan dipublikasikan oleh API."
          : `Konten diterima API. Status: ${status}; moderasi: ${moderation}. Konten belum dianggap publik sampai API menyatakan published dan approved.`;
      await loadFeed(true);
      setNotice(confirmation);
      return { accepted: true, message: confirmation };
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Konten belum tersimpan melalui API.";
      const truthfulMessage = createdId
        ? `Draft ${createdId} sudah dibuat. ${message} Draft tidak dianggap terpublikasi; periksa statusnya sebelum mencoba ulang.`
        : message;
      setError(truthfulMessage);
      return { accepted: false, message: truthfulMessage };
    }
  }

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
          onOpenCreateModal={() => { if (requireLogin("Masuk untuk membuat postingan.")) return; if (!composerHuman) { setError("Identitas Human kanonis belum siap. Coba muat ulang sebelum membuat konten."); return; } setCreateModalOpen(true); }}
          onOpenFilmAi={() => { window.location.assign("/ai-cinema"); }}
          onOpenMessages={() => { window.location.assign("/messages"); }}
        />
        {createModalOpen && composerHuman && (
          <CreatePostModal
            isOpen={createModalOpen}
            onClose={() => setCreateModalOpen(false)}
            humanUser={composerHuman}
            agentProfile={composerAgent}
            onCreatePost={createPostFromReference}
          />
        )}
        {cursor && <div className="mx-auto max-w-xl px-4 pb-6"><button className="w-full rounded-2xl border-2 border-slate-900 bg-white px-4 py-3 text-sm font-black shadow-[3px_3px_0px_#0f172a]" onClick={() => void loadFeed(false, cursor)} disabled={loading}>Muat konten berikutnya</button></div>}
    </main>
  );
}
