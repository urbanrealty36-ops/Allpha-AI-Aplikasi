"use client";

import Link from "next/link";
import { Film, Plus, Radio, Sparkles, TrendingUp, Users } from "lucide-react";

type FeedMode = "for_you" | "recent";

export default function ReferenceFeedChrome({
  mode,
  onModeChange,
}: {
  mode: FeedMode;
  onModeChange: (mode: FeedMode) => void;
}) {
  return (
    <div className="reference-feed-chrome" aria-label="Feed Allpha">
      <nav className="reference-feed-tabs" aria-label="Kategori feed">
        <button type="button" className={mode === "for_you" ? "is-active" : ""} aria-pressed={mode === "for_you"} onClick={() => onModeChange("for_you")}>Untuk Anda</button>
        <button type="button" className={mode === "recent" ? "is-active" : ""} aria-pressed={mode === "recent"} onClick={() => onModeChange("recent")}>Terbaru</button>
        <Link href="/search" className="reference-feed-explore">Jelajahi</Link>
        <Link href="/reels" className="reference-feed-reels"><Film size={19} aria-hidden="true" /><span>Reels / Video</span><b>HD</b></Link>
      </nav>

      <section className="reference-stories" aria-label="Stories">
        <Link href="/stories" className="reference-story-add">
          <span><Plus size={31} strokeWidth={3} aria-hidden="true" /></span>
          <strong>Tambah</strong>
        </Link>
        <div className="reference-stories-empty">
          <span className="reference-story-empty-icon"><Users size={22} aria-hidden="true" /></span>
          <span>Stories dari akun yang Anda ikuti akan tampil di sini</span>
        </div>
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
