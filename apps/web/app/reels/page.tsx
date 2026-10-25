"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { getBrowserSupabase } from "../../lib/supabase";
import ReelsView from "../../components/reference-ui/ReelsView";

type ReelsMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type Reel = { id: string; owner_id: string; body: string; content_type: string; published_at?: string | null; created_at: string; media?: ReelsMedia[]; engagement?: { likes: number; comments: number; saves: number; shares?: number }; viewer_reaction?: string | null; saved?: boolean };
type ReferenceReel = { id: string; title: string; caption: string; bgImage: string; creatorName: string; creatorHandle: string; creatorAvatar: string; agentName: string; agentHandle: string; audioName: string; likes: number; commentsCount: number; sharesCount: number; badge: string; ownerId: string; mediaUrl: string | null; mediaType: string | null; createdAt: string; liked: boolean };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function messageFor(response: Response) {
  try { const body = await response.json(); return body?.detail?.message ?? body?.error?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function ReelsPage() {
  const router = useRouter();
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<Reel[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Masuk terlebih dahulu untuk membuka Reels.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) throw new Error(await messageFor(response));
    return response.json();
  }, [session]);

  const load = useCallback(async (reset = true, nextCursor?: string | null) => {
    if (!session) return;
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "20", mode: "recent" });
      if (!reset && nextCursor) params.set("cursor", nextCursor);
      const data = await request("/v1/reels?" + params.toString()) as { items?: Reel[]; next_cursor?: string | null };
      setItems(current => reset ? (data.items ?? []) : [...current, ...(data.items ?? [])]);
      setCursor(data.next_cursor ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reels gagal dimuat."); }
    finally { setLoading(false); }
  }, [request, session]);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (!data.session) setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (!next) { setItems([]); setCursor(null); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => { if (session) void load(true); }, [session, load]);

  async function toggleLike(reel: ReferenceReel) {
    setBusy(reel.id); setError(""); setNotice("");
    try {
      const item = items.find(row => row.id === reel.id);
      if (!item) return;
      await request("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", item.viewer_reaction
        ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ reaction: "like" }) });
      await load(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reaksi gagal disimpan."); }
    finally { setBusy(""); }
  }

  async function share(reel: ReferenceReel) {
    setBusy(reel.id); setError(""); setNotice("");
    try {
      const result = await request("/v1/feed/" + encodeURIComponent(reel.id) + "/share", {
        method: "POST", body: JSON.stringify({ share_target: "copy_link" }),
      }) as { share_url: string };
      try { await navigator.clipboard.writeText(result.share_url); setNotice("Tautan Reels disalin."); }
      catch { setNotice("Tautan Reels: " + result.share_url); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Tautan Reels gagal dibuat."); }
    finally { setBusy(""); }
  }

  const referenceReels: ReferenceReel[] = items.map(item => {
    const media = item.media?.find(entry => Boolean(entry.preview_url));
    const mediaUrl = media?.preview_url ?? null;
    const ownerLabel = "Kreator";
    return {
      id: item.id, title: item.body || "Konten Allpha", caption: item.body || "",
      bgImage: mediaUrl || "", creatorName: ownerLabel, creatorHandle: "",
      creatorAvatar: "", agentName: "", agentHandle: "", audioName: media?.filename || "Media Allpha",
      likes: item.engagement?.likes ?? 0, commentsCount: item.engagement?.comments ?? 0,
      sharesCount: item.engagement?.shares ?? 0, badge: item.content_type.toUpperCase(),
      ownerId: item.owner_id, mediaUrl, mediaType: media?.media_type ?? null,
      createdAt: item.published_at ?? item.created_at, liked: Boolean(item.viewer_reaction),
    };
  });

  return <>
    {error && <p role="alert" className="fixed left-3 right-3 top-3 z-50 mx-auto max-w-xl rounded-xl border border-red-300 bg-white p-3 text-sm text-red-700 shadow">{error}</p>}
    {notice && <p role="status" className="fixed left-3 right-3 top-3 z-50 mx-auto max-w-xl rounded-xl border border-emerald-300 bg-white p-3 text-sm text-emerald-800 shadow">{notice}</p>}
    {!session ? <main className="flex min-h-[70dvh] items-center justify-center bg-black px-6 text-center text-white"><div><h1 className="text-xl font-black">Allpha Reels</h1><p className="my-3 text-sm text-white/70">Masuk untuk melihat konten Reels yang dipublikasikan.</p><button className="rounded-xl border-2 border-white px-4 py-2 font-bold" onClick={() => router.push("/login")}>Masuk</button></div></main> : <>
      {loading && referenceReels.length === 0 ? <main className="flex min-h-[70dvh] items-center justify-center bg-black text-sm text-white/70">Memuat Reels…</main> : <ReelsView
        reels={referenceReels}
        onToggleLike={reel => void toggleLike(reel)}
        onShare={reel => void share(reel)}
        onOpenComments={reel => router.push("/feed?content=" + encodeURIComponent(reel.id) + "&comments=1")}
        onOpenBrandCustomizer={() => router.push("/create")}
        onOpenAskAi={(agentName) => router.push(agentName ? "/ask-ai?agent=" + encodeURIComponent(agentName) : "/ask-ai")}
        onBackToFeed={() => router.push("/feed")}
        onOpenLiveStage={() => router.push("/live")}
        onOpenFilmAi={() => router.push("/ai-cinema")}
      />}
      {cursor && <div className="fixed bottom-3 left-3 right-3 z-40 mx-auto max-w-sm"><button className="w-full rounded-xl border-2 border-slate-900 bg-white px-4 py-3 text-sm font-black text-slate-900 shadow-[3px_3px_0px_#0f172a]" disabled={loading} onClick={() => void load(false, cursor)}>Muat Reels berikutnya</button></div>}
    </>}
  </>;
}
