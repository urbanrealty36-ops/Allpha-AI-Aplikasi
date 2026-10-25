"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bot, Film, Plus, Radio, Sparkles, Users } from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type FeedMode = "for_you" | "recent";
type StoryMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type Story = {
  id: string;
  owner_id: string;
  body: string;
  content_type: string;
  status: string;
  moderation_status: string;
  created_at: string;
  published_at?: string | null;
  expires_at?: string | null;
  media?: StoryMedia[];
};

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const storyRings = [
  "from-rose-500 via-purple-600 to-amber-500",
  "from-blue-500 to-sky-400",
  "from-cyan-400 to-teal-500",
  "from-rose-500 via-pink-500 to-purple-600",
  "from-purple-500 to-indigo-600",
  "from-blue-600 to-cyan-400",
];

export default function ReferenceFeedChrome({
  mode,
  onModeChange,
}: {
  mode: FeedMode;
  onModeChange: (mode: FeedMode) => void;
}) {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [stories, setStories] = useState<Story[]>([]);
  const [storiesLoading, setStoriesLoading] = useState(true);
  const [storiesError, setStoriesError] = useState("");

  const loadStories = useCallback(async (activeSession: Session) => {
    setStoriesLoading(true);
    setStoriesError("");
    try {
      const response = await fetch(apiBase + "/v1/stories?limit=30", {
        headers: { Authorization: "Bearer " + activeSession.access_token, Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        let message = `Stories tidak dapat dimuat (HTTP ${response.status}).`;
        try {
          const body = await response.json();
          message = body?.error?.message ?? body?.detail?.message ?? message;
        } catch {}
        throw new Error(message);
      }
      const data = await response.json() as { items?: Story[] };
      setStories(data.items ?? []);
    } catch (cause) {
      setStoriesError(cause instanceof Error ? cause.message : "Stories tidak dapat dimuat.");
      setStories([]);
    } finally {
      setStoriesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!supabase) {
      setStoriesLoading(false);
      setStoriesError("Konfigurasi autentikasi belum tersedia.");
      return;
    }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (!data.session) {
        setStories([]);
        setStoriesLoading(false);
      } else {
        void loadStories(data.session);
      }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (next) void loadStories(next);
      else {
        setStories([]);
        setStoriesLoading(false);
      }
    });
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [supabase, loadStories]);

  return (
    <div className="w-full max-w-xl mx-auto px-3.5 sm:px-4 pt-3.5 pb-4 space-y-4 font-sans" aria-label="Feed Allpha">
      <nav className="flex items-center gap-2 overflow-x-auto py-1" aria-label="Kategori feed">
        <button
          type="button"
          aria-pressed={mode === "for_you"}
          onClick={() => onModeChange("for_you")}
          className={`px-4 py-2 rounded-full text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer border-2 border-slate-900 ${mode === "for_you" ? "bg-slate-900 text-white shadow-[2px_2px_0px_#0f172a]" : "bg-white text-slate-800 hover:bg-slate-50"}`}
        >
          <Sparkles className={`w-3.5 h-3.5 ${mode === "for_you" ? "text-white" : "text-slate-700"}`} />
          <span>Untuk Anda</span>
        </button>
        <button
          type="button"
          aria-pressed={mode === "recent"}
          onClick={() => onModeChange("recent")}
          className={`px-4 py-2 rounded-full text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer border-2 border-slate-900 ${mode === "recent" ? "bg-slate-900 text-white shadow-[2px_2px_0px_#0f172a]" : "bg-white text-slate-800 hover:bg-slate-50"}`}
        >
          <Users className="w-3.5 h-3.5 text-slate-700" />
          <span>Mengikuti</span>
        </button>
        <Link
          href="/agents"
          className="px-4 py-2 rounded-full text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap border-2 border-slate-900 bg-white text-slate-800 hover:bg-slate-50"
        >
          <Bot className="w-3.5 h-3.5 text-slate-700" />
          <span>AI Agents</span>
        </Link>
        <Link
          href="/reels"
          title="Buka Video & 3D Spatial Reels"
          className="px-4 py-2 rounded-full text-xs font-bold bg-rose-50 text-rose-600 border-2 border-rose-300 hover:bg-rose-100 transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer shadow-2xs"
        >
          <Film className="w-3.5 h-3.5 text-rose-500 fill-rose-500" />
          <span>Reels / Video</span>
        </Link>
      </nav>

      <section className="flex items-center gap-3.5 overflow-x-auto py-2 px-1" aria-label="Stories">
        <Link href="/stories" className="flex flex-col items-center gap-1 shrink-0 cursor-pointer group">
          <span className="w-15 h-15 rounded-full border-2 border-dashed border-blue-400 bg-blue-50/70 flex items-center justify-center text-blue-600 shadow-2xs group-hover:bg-blue-100 transition">
            <Plus className="w-7 h-7" strokeWidth={2.5} aria-hidden="true" />
          </span>
          <strong className="text-[11px] font-semibold text-slate-800 truncate max-w-[68px] mt-0.5">Tambah</strong>
        </Link>
        {storiesLoading ? (
          <div className="text-xs text-slate-500 shrink-0" role="status">Memuat Stories…</div>
        ) : storiesError ? (
          <div className="text-xs text-rose-700 shrink-0" role="alert">{storiesError}</div>
        ) : stories.length ? (
          stories.map((story, index) => {
            const media = story.media?.find(item => item.preview_url && item.media_type.startsWith("image/"));
            return (
              <Link href="/stories" className="flex flex-col items-center gap-1 shrink-0 cursor-pointer group active:scale-95 transition" key={story.id}>
                <span className={`relative w-15 h-15 rounded-full p-0.5 bg-gradient-to-tr ${storyRings[index % storyRings.length]} shadow-2xs`}>
                  {media?.preview_url ? (
                    <img src={media.preview_url} alt="" loading="lazy" className="w-full h-full rounded-full object-cover border-2 border-white" />
                  ) : (
                    <span className="w-full h-full rounded-full border-2 border-white bg-white flex items-center justify-center text-sm font-bold text-slate-700">
                      {story.owner_id.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                </span>
                <strong className="text-[11px] font-semibold text-slate-800 truncate max-w-[68px] mt-0.5">{story.owner_id.slice(0, 8)}</strong>
              </Link>
            );
          })
        ) : (
          <div className="text-xs text-slate-500 shrink-0 max-w-[220px]" role="status">
            Stories yang telah dipublikasikan akan tampil di sini.
          </div>
        )}
      </section>

      <section className="relative rounded-3xl overflow-hidden border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] bg-gradient-to-r from-purple-950 via-indigo-950 to-slate-950 text-white p-4.5 sm:p-5">
        <div className="flex items-center justify-between mb-2.5">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-950/80 border border-indigo-500/50 text-indigo-200 text-[10px] font-black uppercase tracking-wider">
            <Radio className="w-3 h-3" aria-hidden="true" />
            <span>LIVE STAGE</span>
          </div>
          <span className="text-xs font-semibold text-slate-300">3D Spatial</span>
        </div>
        <div className="relative z-10 space-y-1 max-w-sm">
          <h2 className="text-base sm:text-lg font-black text-white leading-tight">Live Stage &amp; 3D Spatial Universe</h2>
          <p className="text-xs text-slate-300 leading-snug">Jelajahi panggung pengalaman, acara, dan dunia 3D Allpha Universe.</p>
        </div>
        <div className="flex items-center justify-between mt-3.5 pt-1 relative z-10">
          <Link
            href="/live"
            className="px-4 py-2 rounded-full bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-400 hover:to-rose-400 text-white font-extrabold text-xs shadow-md border border-pink-400/40 flex items-center gap-1.5 active:scale-95 transition"
          >
            <span>Jelajahi Live Stage</span>
            <span className="text-sm">↗</span>
          </Link>
        </div>
        <div className="absolute right-0 top-0 bottom-0 w-44 bg-gradient-to-l from-cyan-500/20 via-purple-500/10 to-transparent pointer-events-none" />
      </section>
    </div>
  );
}
