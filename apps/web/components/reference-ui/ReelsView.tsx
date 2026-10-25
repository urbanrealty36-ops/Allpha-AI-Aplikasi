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
  ownerId?: string;
  mediaUrl?: string | null;
  mediaType?: string | null;
  createdAt?: string;
  liked?: boolean;
}

interface ReelsViewProps {
  onOpenBrandCustomizer: () => void;
  onOpenAskAi: (agentName: string, ownerName: string, specialty: string) => void;
  onBackToFeed?: () => void;
  onOpenLiveStage?: () => void;
  onOpenFilmAi?: (filmId?: string) => void;
  reels?: ReelItem[];
  loading?: boolean;
  onToggleLike?: (reel: ReelItem) => void;
  onShare?: (reel: ReelItem) => void;
  onOpenComments?: (reel: ReelItem) => void;
  mediaUnavailableMessage?: string;
}

export default function ReelsView({
  onOpenBrandCustomizer,
  onOpenAskAi,
  onBackToFeed,
  onOpenLiveStage,
  onOpenFilmAi,
  reels,
  loading = false,
  onToggleLike,
  onShare,
  onOpenComments,
  mediaUnavailableMessage = "Media belum tersedia",
}: ReelsViewProps) {
  const [currentReelIndex, setCurrentReelIndex] = useState(0);
  const [isMuted, setIsMuted] = useState(true);
  const [reelsFilter, setReelsFilter] = useState<'FOR_YOU' | 'FOLLOWING' | 'FILM_AI'>('FOR_YOU');
  const [touchStartY, setTouchStartY] = useState<number | null>(null);
  const [mediaErrors, setMediaErrors] = useState<Record<string, boolean>>({});
  const [mediaRetryKey, setMediaRetryKey] = useState(0);

  // Production route supplies API-backed reels. No demo fallback is used.
  const reelsList: ReelItem[] = reels ?? [];

  const currentReel = reelsList[currentReelIndex];
  useEffect(() => { setCurrentReelIndex(index => Math.min(index, Math.max(0, reelsList.length - 1))); }, [reelsList.length]);

  // Initial likes are taken from the authenticated API response, never seeded with demo values.
  const [likesState, setLikesState] = useState<Record<string, { liked: boolean; count: number }>>({});

  const toggleLike = () => {
    if (!currentReel) return;
    if (onToggleLike) { onToggleLike(currentReel); return; }
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

  const currentLikeInfo = currentReel ? (likesState[currentReel.id] || { liked: Boolean(currentReel.liked), count: currentReel.likes }) : { liked: false, count: 0 };

  const handleNextReel = () => {
    if (!reelsList.length) return;
    setCurrentReelIndex((prev) => (prev < reelsList.length - 1 ? prev + 1 : 0));
  };

  const handlePrevReel = () => {
    if (!reelsList.length) return;
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

  if (!currentReel) return <div className="relative flex min-h-[70dvh] w-full items-center justify-center bg-black px-6 text-center text-white"><div>{loading ? <p role="status" className="text-sm text-white/70">Memuat Reels…</p> : <><p className="text-lg font-black">Belum ada Reels</p><p className="mt-2 text-sm text-white/70">Konten video/audio akan tampil setelah tersedia dari layanan Allpha.</p></>}</div></div>;

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
        style={currentReel.mediaType?.startsWith('video/') ? undefined : { backgroundImage: currentReel.bgImage ? `url('${currentReel.bgImage}')` : undefined }}
      >
        {currentReel.mediaType?.startsWith('video/') && currentReel.mediaUrl && !mediaErrors[currentReel.id] ? <video key={`${currentReel.id}-${mediaRetryKey}`} src={currentReel.mediaUrl} autoPlay muted={isMuted} loop playsInline controls onError={() => setMediaErrors(prev => ({ ...prev, [currentReel.id]: true }))} className="h-full w-full object-cover" /> : currentReel.mediaType?.startsWith('audio/') && currentReel.mediaUrl && !mediaErrors[currentReel.id] ? <audio key={`${currentReel.id}-${mediaRetryKey}`} src={currentReel.mediaUrl} autoPlay muted={isMuted} loop controls onError={() => setMediaErrors(prev => ({ ...prev, [currentReel.id]: true }))} /> : null}
         {!mediaErrors[currentReel.id] && (!currentReel.mediaUrl || (!currentReel.mediaType?.startsWith("video/") && !currentReel.mediaType?.startsWith("audio/"))) && <div role="status" className="absolute inset-x-5 top-1/2 z-20 -translate-y-1/2 rounded-2xl border-2 border-white/70 bg-slate-950/90 p-5 text-center shadow-xl"><p className="text-sm font-black">{mediaUnavailableMessage}</p><p className="mt-2 text-xs text-white/80">Konten ini belum menyediakan media video atau audio yang dapat diputar.</p></div>}
        {mediaErrors[currentReel.id] && <div role="alert" className="absolute inset-x-5 top-1/2 z-20 -translate-y-1/2 rounded-2xl border-2 border-white/70 bg-slate-950/90 p-5 text-center shadow-xl"><p className="text-sm font-black">Media tidak dapat diputar</p><p className="mt-2 text-xs text-white/80">Perbarui tautan media dan coba lagi.</p><button type="button" className="mt-3 rounded-xl border-2 border-white px-4 py-2 text-xs font-black" onClick={() => { setMediaErrors(prev => ({ ...prev, [currentReel.id]: false })); setMediaRetryKey(key => key + 1); }}>Coba lagi</button></div>}
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

      {/* RIGHT ACTION ICONS SIDEBAR (Neo-Brutalist Soft Pastel Style) */}
      <div className="absolute right-2.5 sm:right-4 bottom-24 sm:bottom-28 z-30 flex flex-col items-center gap-3.5">
        {/* Like Button */}
        <button
          onClick={toggleLike}
          className="flex flex-col items-center gap-1 group active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
        >
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] ${
            currentLikeInfo.liked
              ? 'bg-rose-400 text-slate-950 scale-105'
              : 'bg-white text-slate-900 hover:bg-slate-100'
          }`}>
            <Heart className={`w-5 h-5 stroke-[2.5px] ${currentLikeInfo.liked ? 'fill-slate-950 text-slate-950' : 'text-slate-900'}`} />
          </div>
          <span className="text-white text-[10px] font-black drop-shadow-[1px_1px_0px_#000]">
            {currentLikeInfo.count >= 1000 ? (currentLikeInfo.count / 1000).toFixed(1) + 'k' : currentLikeInfo.count}
          </span>
        </button>

        {/* Comment Button */}
        <button
          onClick={() => onOpenComments?.(currentReel)}
          className="flex flex-col items-center gap-1 group active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
        >
          <div className="w-12 h-12 rounded-2xl bg-white hover:bg-slate-100 border-2 border-slate-900 text-slate-900 flex items-center justify-center transition shadow-[2px_2px_0px_#0f172a]">
            <MessageCircle className="w-5 h-5 stroke-[2.5px]" />
          </div>
          <span className="text-white text-[10px] font-black drop-shadow-[1px_1px_0px_#000]">
            {currentReel.commentsCount}
          </span>
        </button>

        {/* Share Button */}
        <button
          onClick={() => { if (onShare) onShare(currentReel); }}
          disabled={!onShare}
          className="flex flex-col items-center gap-1 group active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          title="Salin Tautan"
        >
          <div className="w-12 h-12 rounded-2xl bg-white hover:bg-slate-100 border-2 border-slate-900 text-slate-900 flex items-center justify-center transition shadow-[2px_2px_0px_#0f172a]">
            <Share2 className="w-5 h-5 stroke-[2.5px]" />
          </div>
          <span className="text-white text-[10px] font-black drop-shadow-[1px_1px_0px_#000]">
            {currentReel.sharesCount}
          </span>
        </button>

        {/* AI Agent Ask Button */}
        <button
          onClick={() => onOpenAskAi(currentReel.agentName, currentReel.creatorName, 'Kreativitas & Desain 3D')}
          className="flex flex-col items-center gap-1 group active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          title={`Tanya ${currentReel.agentName}`}
        >
          <div className="w-12 h-12 rounded-2xl bg-sky-300 hover:bg-sky-400 text-slate-950 flex items-center justify-center transition border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
            <Bot className="w-5 h-5 stroke-[2.5px]" />
          </div>
          <span className="text-white text-[10px] font-black drop-shadow-[1px_1px_0px_#000]">
            Tanya AI
          </span>
        </button>

        {/* If Reel is an AI Film trailer: Dedicated Watch in AI Cinema button */}
        {currentReel.isFilmTrailer && onOpenFilmAi && (
          <button
            onClick={() => onOpenFilmAi(currentReel.filmId)}
            className="flex flex-col items-center gap-1 group animate-bounce active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Tonton Film Penuh di AI Cinema"
          >
            <div className="w-12 h-12 rounded-2xl bg-amber-300 hover:bg-amber-400 text-slate-950 flex items-center justify-center transition border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <Film className="w-5 h-5 stroke-[2.5px]" />
            </div>
            <span className="text-amber-300 text-[10px] font-black drop-shadow-[1px_1px_0px_#000] uppercase">
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
          {currentReel.creatorAvatar ? <img src={currentReel.creatorAvatar} alt={currentReel.creatorName} className="w-10 h-10 rounded-full object-cover ring-2 ring-white/80 shrink-0" /> : <div aria-label={currentReel.creatorName} className="w-10 h-10 rounded-full bg-sky-100 text-sky-800 flex items-center justify-center ring-2 ring-white/80 shrink-0"><Sparkles className="w-5 h-5" /></div>}
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
              {currentReel.agentName && <span>{currentReel.agentName} · AI Co-Director</span>}
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
