"use client";

import Link from "next/link";
import { Film, MessageCircle, Plus, Radio, Sparkles, TrendingUp, Users, Video } from "lucide-react";

const feedTabs = [
  { label: "Untuk Anda", href: "/feed", active: true },
  { label: "Mengikuti", href: "/feed?mode=following" },
  { label: "Trending", href: "/search?sort=trending" },
];

export default function ReferenceFeedChrome() {
  return (
    <div className="reference-feed-chrome" aria-label="Feed Allpha">
      <nav className="reference-feed-tabs" aria-label="Kategori feed">
        {feedTabs.map((tab) => (
          <Link key={tab.label} href={tab.href} className={tab.active ? "is-active" : ""} aria-current={tab.active ? "page" : undefined}>
            {tab.label}
          </Link>
        ))}
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
