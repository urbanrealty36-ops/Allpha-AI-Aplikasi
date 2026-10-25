"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Film, Plus, Radio, Sparkles, TrendingUp, Users } from "lucide-react";
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
      setStories((data.items ?? []).filter(story => story.status === "published" && story.moderation_status === "approved"));
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
    <div className="reference-feed-chrome" aria-label="Feed Allpha">
      <nav className="reference-feed-tabs" aria-label="Kategori feed">
        <button type="button" className={mode === "for_you" ? "is-active" : ""} aria-pressed={mode === "for_you"} onClick={() => onModeChange("for_you")}>Untuk Anda</button>
        <button type="button" className={mode === "recent" ? "is-active" : ""} aria-pressed={mode === "recent"} onClick={() => onModeChange("recent")}>Mengikuti / Terbaru</button>
        <Link href="/search" className="reference-feed-explore">Trending</Link>
        <Link href="/reels" className="reference-feed-reels"><Film size={19} aria-hidden="true" /><span>Reels / Video</span><b>HD</b></Link>
      </nav>

      <section className="reference-stories" aria-label="Stories">
        <Link href="/stories" className="reference-story-add">
          <span><Plus size={31} strokeWidth={3} aria-hidden="true" /></span>
          <strong>Tambah</strong>
        </Link>
        {storiesLoading ? (
          <div className="reference-stories-empty" role="status">Memuat Stories…</div>
        ) : storiesError ? (
          <div className="reference-stories-empty" role="alert">{storiesError}</div>
        ) : stories.length ? (
          <div className="reference-stories-list">
            {stories.map(story => {
              const media = story.media?.find(item => item.preview_url && item.media_type.startsWith("image/"));
              return (
                <Link href={"/stories?story=" + encodeURIComponent(story.id)} className="reference-story-item" key={story.id}>
                  <span className="reference-story-avatar">
                    {media?.preview_url ? <img src={media.preview_url} alt="" loading="lazy" /> : <span>{story.owner_id.slice(0, 1).toUpperCase()}</span>}
                  </span>
                  <strong>{story.owner_id.slice(0, 8)}</strong>
                  {story.body && <small>{story.body}</small>}
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="reference-stories-empty">
            <span className="reference-story-empty-icon"><Users size={22} aria-hidden="true" /></span>
            <span>Stories yang telah dipublikasikan akan tampil di sini</span>
          </div>
        )}
      </section>

      <Link href="/spatial/navigation" className="reference-live-stage">
        <div className="reference-live-stage-top"><span><Radio size={15} aria-hidden="true" /> LIVE STAGE</span><small><Sparkles size={14} aria-hidden="true" /> Pengalaman 3D</small></div>
        <h2>Live Stage &amp; Universe Events</h2>
        <p>Jelajahi pengalaman live dan panggung 3D Allpha Universe.</p>
        <span className="reference-live-stage-cta">Jelajahi Live Stage <TrendingUp size={17} aria-hidden="true" /></span>
      </Link>
    </div>
  );
}
