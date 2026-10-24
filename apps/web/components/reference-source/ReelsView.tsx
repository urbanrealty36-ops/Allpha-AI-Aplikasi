'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  Heart, 
  MessageCircle, 
  Share2, 
  Bookmark, 
  Music, 
  Bot, 
  Sparkles, 
  Volume2, 
  VolumeX, 
  Box, 
  ChevronUp, 
  ChevronDown, 
  Radio, 
  ArrowUpRight, 
  Film, 
  Crown,
  ArrowLeft
} from 'lucide-react';

interface ReelItem {
  id: string;
  title: string;
  caption: string;
  bgImage: string;
  creatorName: string;
  creatorHandle: string;
  creatorAvatar: string;
  agentName: string;
  agentHandle: string;
  audioName: string;
  likes: number;
  commentsCount: number;
  sharesCount: number;
  badge: string;
  isLive?: boolean;
  liveViewers?: string;
  isFilmTrailer?: boolean;
  filmId?: string;
}

interface ReelsViewProps {
  onOpenBrandCustomizer: () => void;
  onOpenAskAi: (agentName: string, ownerName: string, specialty: string) => void;
  onBackToFeed?: () => void;
  onOpenLiveStage?: () => void;
  onOpenFilmAi?: (filmId?: string) => void;
}

export default function ReelsView({
  onOpenBrandCustomizer,
  onOpenAskAi,
  onBackToFeed,
  onOpenLiveStage,
  onOpenFilmAi,
}: ReelsViewProps) {
  const [currentReelIndex, setCurrentReelIndex] = useState(0);
  const [isMuted, setIsMuted] = useState(true);
  const [reelsFilter, setReelsFilter] = useState<'FOR_YOU' | 'FOLLOWING' | 'FILM_AI'>('FOR_YOU');
  const [touchStartY, setTouchStartY] = useState<number | null>(null);

  // Reels items dataset (including active Live Stage streaming and Film AI trailers!)
  const reelsList: ReelItem[] = [
    {
      id: 'r-film-1',
      title: '🎬 TRAILER RESMI: The Reborn Cyber Empress (Drama Pendek AI)',
      caption: 'Lin Yue terlahir kembali dengan AI Agent pelindung di Shanghai 2099! Tonton 15 episode lengkap di Allpha AI Cinema dengan royalti 70% untuk kreator.',
      bgImage: '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg',
      creatorName: 'Chen Wei',
      creatorHandle: '@chenwei_films',
      creatorAvatar: 'https://picsum.photos/seed/chen-producer/100/100',
      agentName: 'CineGenius AI',
      agentHandle: '@cinegenius.ai',
      audioName: 'CineGenius AI · Cyber Empress Theme OST 4K',
      likes: 48200,
      commentsCount: 1420,
      sharesCount: 3800,
      badge: '🎬 FILM AI TRAILER • C-DRAMA',
      isLive: false,
      isFilmTrailer: true,
      filmId: 'film-1',
    },
    {
      id: 'r-1',
      title: 'Eksplorasi Crystal City Central Avenue di Malam Hari 🌌',
      caption: 'AI dan manusia bisa membangun dunia spatial yang lebih baik bersama di Allpha Universe.',
      bgImage: '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
      creatorName: 'Alex Tamara',
      creatorHandle: '@alextamara',
      creatorAvatar: 'https://picsum.photos/seed/alex-tamara/100/100',
      agentName: 'Luna AI',
      agentHandle: '@luna.ai',
      audioName: 'Luna AI & Alex Tamara · Original Audio',
      likes: 24500,
      commentsCount: 320,
      sharesCount: 1200,
      badge: '3D SPATIAL REEL • 60 FPS',
      isLive: false,
    },
    {
      id: 'r-2',
      title: '🔴 SEDANG LIVE: AI Innovation & Spatial Stage Summit',
      caption: 'Siaran langsung dari Live Stage Arena 3D. Diskusi panggung virtual bersama AI Agent!',
      bgImage: '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
      creatorName: 'Alex Tamara',
      creatorHandle: '@alextamara',
      creatorAvatar: 'https://picsum.photos/seed/alex-tamara/100/100',
      agentName: 'Luna AI',
      agentHandle: '@luna.ai',
      audioName: 'Live Stage Audio Broadcast • Spatial Mic',
      likes: 31200,
      commentsCount: 890,
      sharesCount: 2400,
      badge: '🔴 LIVE STAGE ARENA',
      isLive: true,
      liveViewers: '2.4K Menonton',
    },
    {
      id: 'r-film-2',
      title: '🎬 TRAILER K-DRAMA AI: Neo-Seoul Destined Neural Hearts',
      caption: 'Desainer spatial muda bertemu CEO android misterius di Neo-Seoul. Serial 12 episode penuh tayang eksklusif di Allpha Cinema!',
      bgImage: '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
      creatorName: 'Park Ji-hoon',
      creatorHandle: '@jihoon_media',
      creatorAvatar: 'https://picsum.photos/seed/jihoon/100/100',
      agentName: 'Luna AI',
      agentHandle: '@luna.ai',
      audioName: 'Neo-Seoul Lo-Fi Beats · Neural OST',
      likes: 39500,
      commentsCount: 940,
      sharesCount: 2100,
      badge: '🎬 FILM AI TRAILER • K-DRAMA',
      isLive: false,
      isFilmTrailer: true,
      filmId: 'film-2',
    },
    {
      id: 'r-3',
      title: 'Neo-Kyoto Digital Atrium & Cyberwear Fashion 🥽',
      caption: 'Showcase kostum avatar cybernetic dengan dynamic bloom emissive dan haptic feedback.',
      bgImage: '/assets/aistudio/file_00000000d5a08211bff1d1706016eb9d_2018bbd5.png',
      creatorName: 'Mika Tanaka',
      creatorHandle: '@mikatanaka',
      creatorAvatar: 'https://picsum.photos/seed/mika-tanaka/100/100',
      agentName: 'TechNova',
      agentHandle: '@technova',
      audioName: 'Synthwave Night Ride (Spatial Audio)',
      likes: 18900,
      commentsCount: 215,
      sharesCount: 850,
      badge: 'DIGITAL FASHION 3D',
      isLive: false,
    },
  ];

  const currentReel = reelsList[currentReelIndex] || reelsList[0];

  // Like state map
  const [likesState, setLikesState] = useState<Record<string, { liked: boolean; count: number }>>({
    'r-film-1': { liked: true, count: 48200 },
    'r-1': { liked: false, count: 24500 },
    'r-2': { liked: true, count: 31200 },
    'r-film-2': { liked: true, count: 39500 },
    'r-3': { liked: false, count: 18900 },
  });

  const toggleLike = () => {
    setLikesState((prev) => {
      const current = prev[currentReel.id] || { liked: false, count: currentReel.likes };
      const newLiked = !current.liked;
      return {
        ...prev,
        [currentReel.id]: {
          liked: newLiked,
          count: newLiked ? current.count + 1 : current.count - 1,
        },
      };
    });
  };

  const currentLikeInfo = likesState[currentReel.id] || { liked: false, count: currentReel.likes };

  const handleNextReel = () => {
    setCurrentReelIndex((prev) => (prev < reelsList.length - 1 ? prev + 1 : 0));
  };

  const handlePrevReel = () => {
    setCurrentReelIndex((prev) => (prev > 0 ? prev - 1 : reelsList.length - 1));
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        handleNextReel();
      } else if (e.key === 'ArrowUp') {
        handlePrevReel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentReelIndex]);

  // Touch Swipe Handlers for mobile gestures (Instagram / TikTok style)
  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStartY(e.touches[0].clientY);
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartY === null) return;
    const touchEndY = e.changedTouches[0].clientY;
    const diffY = touchStartY - touchEndY;

    // Minimum swipe threshold (40px)
    if (diffY > 40) {
      handleNextReel(); // Swipe up -> next reel
    } else if (diffY < -40) {
      handlePrevReel(); // Swipe down -> prev reel
    }
    setTouchStartY(null);
  };

  return (
    <div 
      className="relative w-full h-[100dvh] bg-black text-white overflow-hidden flex flex-col justify-between select-none"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Fullscreen Video / Visual Canvas Background */}
      <div
        key={currentReel.id}
        className="absolute inset-0 bg-cover bg-center transition-all duration-700 ease-out"
        style={{ backgroundImage: `url('${currentReel.bgImage}')` }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/90" />
      </div>

      {/* ======================================================== */}
      {/* MINIMAL FLOATING TOP HEADER (Instagram / TikTok Style)   */}
      {/* ======================================================== */}
      <div className="relative z-30 pt-3 px-3 sm:px-4 space-y-2 pointer-events-auto">
        {/* Story Progress Indicators */}
        <div className="flex gap-1.5 w-full max-w-lg mx-auto">
          {reelsList.map((r, i) => (
            <div
              key={r.id}
              onClick={() => setCurrentReelIndex(i)}
              className="flex-1 h-0.5 sm:h-1 rounded-full cursor-pointer overflow-hidden bg-white/30 backdrop-blur-sm"
            >
              <div
                className={`h-full transition-all duration-300 ${
                  i === currentReelIndex
                    ? 'bg-white'
                    : i < currentReelIndex
                    ? 'bg-white/70'
                    : 'bg-transparent'
                }`}
              />
            </div>
          ))}
        </div>

        {/* Minimal Floating Bar: Back Button, Filter Tabs, Audio Toggle */}
        <div className="flex items-center justify-between text-xs max-w-lg mx-auto">
          {onBackToFeed && (
            <button
              onClick={onBackToFeed}
              className="px-2.5 py-1.5 rounded-full bg-black/40 hover:bg-black/60 backdrop-blur-md text-white/90 hover:text-white transition flex items-center gap-1 font-bold text-[11px] border border-white/10"
              title="Kembali ke Beranda"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Beranda</span>
            </button>
          )}

          {/* Clean Segmented Filter (No heavy bars) */}
          <div className="flex items-center gap-3 text-xs font-bold drop-shadow">
            <button 
              onClick={() => setReelsFilter('FOR_YOU')}
              className={`transition pb-0.5 ${reelsFilter === 'FOR_YOU' ? 'text-white border-b-2 border-white' : 'text-white/60 hover:text-white'}`}
            >
              Untuk Anda
            </button>
            <button 
              onClick={() => setReelsFilter('FOLLOWING')}
              className={`transition pb-0.5 ${reelsFilter === 'FOLLOWING' ? 'text-white border-b-2 border-white' : 'text-white/60 hover:text-white'}`}
            >
              Mengikuti
            </button>
            {onOpenFilmAi && (
              <button 
                onClick={() => onOpenFilmAi()}
                className="text-rose-400 hover:text-rose-300 transition flex items-center gap-1 font-extrabold"
              >
                <Film className="w-3.5 h-3.5" />
                <span>Film AI</span>
              </button>
            )}
          </div>

          {/* Sound Toggle Button */}
          <button
            onClick={() => setIsMuted(!isMuted)}
            className="p-2 rounded-full bg-black/40 hover:bg-black/60 backdrop-blur-md text-white transition border border-white/10"
            title={isMuted ? 'Aktifkan Suara' : 'Bisukan Suara'}
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5 text-white/80" /> : <Volume2 className="w-3.5 h-3.5 text-cyan-400" />}
          </button>
        </div>
      </div>

      {/* Floating Center Indicator if Live */}
      {currentReel.isLive && (
        <div className="relative z-20 self-center px-3 py-1 rounded-full bg-rose-600/95 text-white text-[11px] font-bold flex items-center gap-1.5 shadow-xl animate-pulse">
          <Radio className="w-3.5 h-3.5 text-white" />
          <span>SEDANG SIARAN LANGSUNG • {currentReel.liveViewers}</span>
        </div>
      )}

      {/* ======================================================== */}
      {/* RIGHT ACTION ICONS SIDEBAR (TikTok / Instagram Style)    */}
      {/* ======================================================== */}
      <div className="absolute right-2.5 sm:right-4 bottom-24 sm:bottom-28 z-30 flex flex-col items-center gap-3.5">
        {/* Like Button */}
        <button
          onClick={toggleLike}
          className="flex flex-col items-center gap-1 group"
        >
          <div className={`w-11 h-11 rounded-full flex items-center justify-center transition shadow-2xl backdrop-blur-sm ${
            currentLikeInfo.liked
              ? 'bg-rose-600 text-white scale-110'
              : 'bg-black/50 text-white hover:bg-black/70 border border-white/10'
          }`}>
            <Heart className={`w-5 h-5 ${currentLikeInfo.liked ? 'fill-white' : ''}`} />
          </div>
          <span className="text-white text-[10px] font-bold drop-shadow">
            {(currentLikeInfo.count / 1000).toFixed(1)}k
          </span>
        </button>

        {/* Comment Button */}
        <button
          onClick={() => alert(`Membuka 320 komentar untuk: "${currentReel.title}"`)}
          className="flex flex-col items-center gap-1 group"
        >
          <div className="w-11 h-11 rounded-full bg-black/50 hover:bg-black/70 border border-white/10 text-white flex items-center justify-center transition shadow-2xl backdrop-blur-sm">
            <MessageCircle className="w-5 h-5" />
          </div>
          <span className="text-white text-[10px] font-bold drop-shadow">
            {currentReel.commentsCount}
          </span>
        </button>

        {/* Share Button */}
        <button
          onClick={() => {
            if (navigator.clipboard) {
              navigator.clipboard.writeText(window.location.href);
              alert('Tautan Reels disalin ke papan klip!');
            }
          }}
          className="flex flex-col items-center gap-1 group"
          title="Salin Tautan"
        >
          <div className="w-11 h-11 rounded-full bg-black/50 hover:bg-black/70 border border-white/10 text-white flex items-center justify-center transition shadow-2xl backdrop-blur-sm">
            <Share2 className="w-5 h-5" />
          </div>
          <span className="text-white text-[10px] font-bold drop-shadow">
            {currentReel.sharesCount}
          </span>
        </button>

        {/* AI Agent Ask Button */}
        <button
          onClick={() => onOpenAskAi(currentReel.agentName, currentReel.creatorName, 'Kreativitas & Desain 3D')}
          className="flex flex-col items-center gap-1 group"
          title={`Tanya ${currentReel.agentName}`}
        >
          <div className="w-11 h-11 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center transition shadow-2xl">
            <Bot className="w-5 h-5" />
          </div>
          <span className="text-white text-[10px] font-bold drop-shadow">
            Tanya
          </span>
        </button>

        {/* If Reel is an AI Film trailer: Dedicated Watch in AI Cinema button */}
        {currentReel.isFilmTrailer && onOpenFilmAi && (
          <button
            onClick={() => onOpenFilmAi(currentReel.filmId)}
            className="flex flex-col items-center gap-1 group animate-bounce"
            title="Tonton Film Penuh di AI Cinema"
          >
            <div className="w-11 h-11 rounded-full bg-gradient-to-tr from-rose-600 to-amber-500 text-white flex items-center justify-center transition shadow-2xl ring-2 ring-amber-400">
              <Film className="w-5 h-5" />
            </div>
            <span className="text-amber-300 text-[10px] font-black drop-shadow uppercase">
              Cinema
            </span>
          </button>
        )}
      </div>

      {/* Floating Vertical Next / Prev Stepper Controls (Left side) */}
      <div className="absolute left-2.5 sm:left-4 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-2">
        <button
          onClick={handlePrevReel}
          className="p-2 rounded-full bg-black/40 hover:bg-black/70 text-white backdrop-blur-md transition shadow-md border border-white/10"
          title="Video Sebelumnya (Swipe Up)"
        >
          <ChevronUp className="w-4 h-4" />
        </button>
        <span className="text-[9px] font-mono font-bold text-center text-white/90 bg-black/60 px-1.5 py-0.5 rounded-full border border-white/10">
          {currentReelIndex + 1}/{reelsList.length}
        </span>
        <button
          onClick={handleNextReel}
          className="p-2 rounded-full bg-black/40 hover:bg-black/70 text-white backdrop-blur-md transition shadow-md border border-white/10"
          title="Video Selanjutnya (Swipe Down)"
        >
          <ChevronDown className="w-4 h-4" />
        </button>
      </div>

      {/* ======================================================== */}
      {/* BOTTOM CONTENT OVERLAY & CREATOR ATTRIBUTION            */}
      {/* (Padded from bottom so never covered by bottom nav)     */}
      {/* ======================================================== */}
      <div className="relative z-20 px-4 pt-4 pb-20 sm:pb-20 space-y-2.5 max-w-xl bg-gradient-to-t from-black/95 via-black/70 to-transparent">
        {/* Creator Info Lockup */}
        <div className="flex items-center gap-2.5">
          <img
            src={currentReel.creatorAvatar}
            alt={currentReel.creatorName}
            className="w-10 h-10 rounded-full object-cover ring-2 ring-white/80 shrink-0"
          />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-bold text-white text-xs">{currentReel.creatorName}</span>
              <span className="text-[10px] text-white/70">{currentReel.creatorHandle}</span>
              <span className="text-[9px] px-2 py-0.2 rounded-full bg-white/20 text-white font-bold">
                {currentReel.badge}
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-cyan-300 font-medium">
              <Bot className="w-3 h-3 text-cyan-400" />
              <span>{currentReel.agentName} · AI Co-Director</span>
            </div>
          </div>
        </div>

        {/* Title & Caption (Constrained width so never overlaps right sidebar) */}
        <div className="max-w-[78%] sm:max-w-md">
          <p className="text-white font-extrabold text-xs sm:text-sm leading-snug drop-shadow">
            {currentReel.title}
          </p>
          <p className="text-slate-200 text-[11px] mt-1 leading-relaxed line-clamp-2 drop-shadow-sm">
            {currentReel.caption}
          </p>
        </div>

        {/* Audio attribution */}
        <div className="flex items-center gap-2 text-white/80 text-[10px]">
          <Music className="w-3 h-3 text-cyan-400 animate-spin" />
          <span className="truncate max-w-[220px]">{currentReel.audioName}</span>
        </div>

        {/* Context CTA Buttons */}
        <div className="pt-1 flex items-center gap-2 max-w-[80%] sm:max-w-md">
          {currentReel.isFilmTrailer && onOpenFilmAi ? (
            <button
              onClick={() => onOpenFilmAi(currentReel.filmId)}
              className="flex-1 py-2.5 px-3 rounded-2xl bg-gradient-to-r from-rose-600 via-purple-600 to-amber-500 hover:from-rose-500 hover:to-amber-400 text-white font-black text-xs shadow-xl transition flex items-center justify-center gap-1.5"
            >
              <Film className="w-3.5 h-3.5 text-white" />
              <span>🎬 Tonton Seri Penuh di Film AI</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          ) : currentReel.isLive && onOpenLiveStage ? (
            <button
              onClick={onOpenLiveStage}
              className="flex-1 py-2.5 px-3 rounded-2xl bg-gradient-to-r from-rose-600 to-purple-600 hover:from-rose-500 hover:to-purple-500 text-white font-black text-xs shadow-xl transition flex items-center justify-center gap-1.5"
            >
              <Radio className="w-3.5 h-3.5 text-white animate-pulse" />
              <span>🎙️ Gabung Live Stage Arena</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={onOpenBrandCustomizer}
              className="flex-1 py-2.5 px-3 rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-extrabold text-xs shadow-xl transition flex items-center justify-center gap-1.5 group"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-200 group-hover:rotate-12 transition" />
              <span>Buat Video dengan Brand Saya</span>
            </button>
          )}

          <button
            onClick={handleNextReel}
            className="px-3 py-2.5 rounded-2xl bg-white/20 hover:bg-white/30 text-white text-xs font-bold transition flex items-center gap-1 shrink-0"
            title="Lanjut ke Video Berikutnya"
          >
            <span>Lanjut</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
