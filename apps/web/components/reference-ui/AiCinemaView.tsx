'use client';

import React, { useState } from 'react';
import { 
  Film, 
  Play, 
  Pause, 
  Sparkles, 
  Crown, 
  Check, 
  CheckCircle2, 
  Star, 
  Eye, 
  Clock, 
  Share2, 
  Lock, 
  Unlock, 
  Bot, 
  User, 
  Coins, 
  Tv, 
  Volume2, 
  VolumeX, 
  Maximize2, 
  ArrowLeft, 
  X, 
  PlusCircle, 
  TrendingUp, 
  Layers, 
  Radio,
  ChevronRight,
  Flame,
  MessageCircle,
  Upload,
  Video,
  FileText,
  ShieldCheck,
  AlertCircle,
  Trash2,
  Plus,
  ListChecks
} from 'lucide-react';

export type FilmGenre = 
  | 'ALL' 
  | 'C_DRAMA' 
  | 'K_DRAMA' 
  | 'SCIFI' 
  | 'ROMANCE' 
  | 'THRILLER' 
  | 'ANIMATION_3D';

export interface MovieEpisodePart {
  id: string;
  partNumber: number;
  title: string;
  duration: string;
  fileName?: string;
  fileSize?: string;
  isFreePreview: boolean;
  videoUrl?: string;
}

export interface AiMovieItem {
  id: string;
  title: string;
  originalTitle?: string;
  genre: FilmGenre;
  genreLabel: string;
  coverImage: string;
  bannerImage: string;
  episodesCount: number;
  totalViews: string;
  rating: number;
  durationPerEp: string;
  releaseYear: string;
  producerHuman: {
    name: string;
    handle: string;
    avatar: string;
  };
  aiCoDirector: {
    name: string;
    handle: string;
    avatar: string;
    specialty: string;
  };
  synopsis: string;
  aiTechStack: string;
  creatorMonthlyEarningsCredits: number;
  isTrending?: boolean;
  isFeatured?: boolean;
  trailerTitle?: string;
  trailerDuration?: string;
  trailerVideoUrl?: string;
  verificationStatus?: 'VERIFIED' | 'PENDING_VERIFICATION' | 'REJECTED';
  isUserUploaded?: boolean;
  parts?: MovieEpisodePart[];
}

interface AiCinemaViewProps {
  onBackToFeed?: () => void;
  onOpenAskAi?: (agentName: string, ownerName: string, specialty: string) => void;
  userCredits: number | null;
  onPostTrailerToFeed?: (movie: AiMovieItem) => void;
  initialSelectedMovieId?: string;
  catalogItems?: AiMovieItem[];
  catalogState?: 'ready' | 'unavailable';
}

export default function AiCinemaView({
  onBackToFeed,
  onOpenAskAi,
  userCredits,
  onPostTrailerToFeed,
  initialSelectedMovieId,
  catalogItems = [],
  catalogState = 'unavailable',
}: AiCinemaViewProps) {
  // Movie catalog state (supports dynamic user submissions)
  const [moviesList, setMoviesList] = useState<AiMovieItem[]>(catalogItems);

  // VIP Monthly Subscription State
  const [isVipSubscribed, setIsVipSubscribed] = useState<boolean>(false);
  const [isSubscriptionModalOpen, setIsSubscriptionModalOpen] = useState<boolean>(false);

  // View Mode: 'CATALOG' | 'MY_STUDIO'
  const [cinemaViewMode, setCinemaViewMode] = useState<'CATALOG' | 'MY_STUDIO'>('CATALOG');

  // Genre filter
  const [activeGenre, setActiveGenre] = useState<FilmGenre>('ALL');

  // "Create Film AI" Dedicated Studio Modal / Screen
  const [isCreateStudioOpen, setIsCreateStudioOpen] = useState<boolean>(false);

  // Create Film AI Form Fields
  const [newTitle, setNewTitle] = useState('');
  const [newOriginalTitle, setNewOriginalTitle] = useState('');
  const [newGenre, setNewGenre] = useState<FilmGenre>('C_DRAMA');
  const [newDurationPerPart, setNewDurationPerPart] = useState('');
  const [newTechStack, setNewTechStack] = useState('');
  const [newSynopsis, setNewSynopsis] = useState('');
  const [newProducerName, setNewProducerName] = useState('');
  const [newAiCoDirector, setNewAiCoDirector] = useState('');

  // Trailer Upload State
  const [trailerFileName, setTrailerFileName] = useState('');
  const [trailerDuration, setTrailerDuration] = useState('');
  const [isTrailerUploaded, setIsTrailerUploaded] = useState(false);
  const [isPreviewingTrailer, setIsPreviewingTrailer] = useState(false);
  const [selectedPosterPreset, setSelectedPosterPreset] = useState<string>('');

  // Video Parts State (Multi-Part Upload)
  const [videoParts, setVideoParts] = useState<MovieEpisodePart[]>([]);

  // Verification review modal after publishing
  const [reviewModalData, setReviewModalData] = useState<{
    isOpen: boolean;
    movie: AiMovieItem | null;
  }>({
    isOpen: false,
    movie: null,
  });

  // Active playing movie in theater modal
  const [activeTheaterMovie, setActiveTheaterMovie] = useState<AiMovieItem | null>(() => {
    if (initialSelectedMovieId) {
      return catalogItems.find((m) => m.id === initialSelectedMovieId) || null;
    }
    return null;
  });

  // Selected episode / part inside theater modal
  const [activeEpisodeNumber, setActiveEpisodeNumber] = useState<number>(1);
  const [isViewingTrailerInTheater, setIsViewingTrailerInTheater] = useState<boolean>(false);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [isAudioMuted, setIsAudioMuted] = useState<boolean>(false);

  // Toast notification
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const genreLabels: Record<FilmGenre, string> = {
    ALL: 'Semua Kategori',
    C_DRAMA: 'Drama China AI (C-Drama)',
    K_DRAMA: 'Drama Korea AI (K-Drama)',
    SCIFI: 'Sci-Fi Spatial 3D',
    THRILLER: 'Thriller & Misteri',
    ROMANCE: 'Romance & Time Travel',
    ANIMATION_3D: 'Animasi 3D & Wuxia',
  };

  const filteredMovies = activeGenre === 'ALL'
    ? moviesList
    : moviesList.filter((m) => m.genre === activeGenre);

  const myUploadedFilms = moviesList.filter((m) => m.isUserUploaded || m.producerHuman.name === 'Alex Tamara');
  const featuredMovie = moviesList[0];

  // Add Part Handler
  const handleAddVideoPart = () => {
    const nextNum = videoParts.length + 1;
    const newPart: MovieEpisodePart = {
      id: `p-${Date.now()}`,
      partNumber: nextNum,
      title: `Part ${nextNum}: Episode Lanjutan ${nextNum}`,
      duration: '02:40',
      fileName: `part${nextNum}_video_render.mp4`,
      fileSize: '52 MB',
      isFreePreview: false,
    };
    setVideoParts([...videoParts, newPart]);
    showToast(`Part ${nextNum} berhasil ditambahkan ke draf film!`);
  };

  // Remove Part Handler
  const handleRemoveVideoPart = (partId: string) => {
    if (videoParts.length <= 1) {
      showToast('Minimal harus ada 1 part video film.');
      return;
    }
    const filtered = videoParts.filter((p) => p.id !== partId);
    // Renumber parts
    const renumbered = filtered.map((p, idx) => ({
      ...p,
      partNumber: idx + 1,
    }));
    setVideoParts(renumbered);
  };

  // Update Part title or duration
  const handleUpdatePart = (id: string, updates: Partial<MovieEpisodePart>) => {
    setVideoParts(videoParts.map((p) => (p.id === id ? { ...p, ...updates } : p)));
  };

  // Submit and Publish Film for Verification by Team Allpha
  const handlePublishForVerification = () => {
    showToast('Studio Film AI belum terhubung ke API kanonis. Tidak ada film yang disimpan atau dipublikasikan.');
  };

  const handleApproveByTeamAllpha = (_movieId: string) => {
    showToast('Verifikasi hanya dapat dilakukan melalui layanan Allpha yang berwenang. Tidak ada status yang diubah di browser.');
  };

  const handleConfirmVipSubscription = () => {
    showToast('Langganan VIP belum tersedia sampai kontrak billing, payment dan entitlement kanonis terhubung. Tidak ada langganan yang diaktifkan.');
  };

  // Handler for opening a movie in theater modal
  const handleOpenTheater = (movie: AiMovieItem, episodeNum = 1, showTrailer = false) => {
    setActiveTheaterMovie(movie);
    setActiveEpisodeNumber(episodeNum);
    setIsViewingTrailerInTheater(showTrailer);
    setIsPlaying(true);
  };

  // Handler for subscribing VIP
  const handleConfirmVipSubscription = () => {
    if (catalogState !== 'ready') {
      showToast('Langganan VIP belum tersedia karena kontrak billing kanonis belum terhubung.');
      return;
    }
    setIsVipSubscribed(true);
    setIsSubscriptionModalOpen(false);
    showToast('Selamat! Langganan VIP Allpha Cinema Aktif. Semua episode terbuka tanpa batas!');
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-4 space-y-6 pb-28 text-slate-900 font-sans">
      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed top-16 right-4 z-50 px-4 py-3 rounded-2xl bg-slate-950 text-white border border-rose-500/60 shadow-2xl text-xs font-semibold flex items-center gap-2.5 animate-in fade-in slide-in-from-top-3 max-w-sm">
          <CheckCircle2 className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Top Header & VIP Subscription Bar */}
      <div className="rounded-3xl bg-gradient-to-r from-slate-950 via-rose-950 to-slate-900 text-white p-5 sm:p-6 border border-rose-500/30 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-rose-600 via-purple-600 to-amber-500 flex items-center justify-center shadow-lg shadow-rose-500/30 shrink-0">
              <Film className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-lg sm:text-xl font-black tracking-tight text-white">
                  ALLPHA AI CINEMA
                </h1>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 uppercase tracking-wider">
                  Platform Film & Mini-Drama AI
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Wadah bagi produser dan kreator Film AI. Katalog, akses tontonan, dan skema bagi hasil mengikuti kebijakan kanonis yang telah diaktifkan.
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 self-start sm:self-auto flex-wrap">
            {isVipSubscribed ? (
              <span className="px-3.5 py-1.5 rounded-2xl bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 font-black text-xs shadow-md flex items-center gap-1.5">
                <Crown className="w-3.5 h-3.5 fill-slate-950" />
                <span>VIP PASS AKTIF ✓</span>
              </span>
            ) : (
              <button
                onClick={() => setIsSubscriptionModalOpen(true)}
                className="px-3.5 py-2 rounded-2xl bg-gradient-to-r from-rose-600 via-purple-600 to-amber-500 hover:from-rose-500 hover:to-amber-400 text-white font-black text-xs shadow-lg shadow-rose-500/25 transition flex items-center gap-1.5"
              >
                <Crown className="w-3.5 h-3.5" />
                <span>Paket VIP (detail harga menyusul)</span>
              </button>
            )}

            <button
              onClick={() => setIsCreateStudioOpen(true)}
              className="px-4 py-2 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-black shadow-md shadow-rose-600/30 transition flex items-center gap-1.5"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Create Film AI</span>
            </button>
          </div>
        </div>

        {/* Creator Profit Sharing Guarantee Strip */}
        <div className="p-3 rounded-2xl bg-black/40 border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping shrink-0" />
            <span>
              <strong>Model Monetisasi Kreator:</strong> pembagian hasil dan distribusi royalti mengikuti kebijakan billing serta ledger kanonis yang berlaku.
            </span>
          </div>
          <span className="text-[11px] font-mono text-amber-300 font-bold shrink-0">
            Royalti akan tersedia setelah ledger dan settlement kanonis aktif
          </span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. CREATOR / PRODUCER CALLOUT BANNER (Sesuai Permintaan User)             */}
      {/* ========================================================================= */}
      <div className="relative rounded-3xl overflow-hidden p-5 sm:p-6 bg-gradient-to-br from-slate-950 via-purple-950/80 to-rose-950/90 border-2 border-rose-500/50 shadow-2xl text-white space-y-4">
        {/* Glow elements */}
        <div className="absolute top-0 right-0 w-80 h-80 rounded-full bg-rose-600/20 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-60 h-60 rounded-full bg-purple-600/20 blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-500/20 border border-rose-400/40 text-rose-300 text-[11px] font-bold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-rose-400" />
              <span>Program Resmi Kreator & Produser Allpha</span>
            </div>

            <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight leading-snug">
              Ingin menjadi Creator/Produser Film AI di Allpha?
            </h2>

            <p className="text-xs sm:text-sm text-slate-200 leading-relaxed">
              Agar Karyamu ditonton orang banyak serta mendapatkan keuntungan dan pendapatan dari Film AI kamu, yuk registrasi dan upload film kamu! Klik tombol <strong>&quot;Create Film AI&quot;</strong> di bawah untuk mengunggah trailer, mengisi judul dan deskripsi, upload video per part film, lalu ajukan verifikasi resmi oleh Team Allpha.
            </p>

            {/* Benefit Highlights */}
            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
              <span className="px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-semibold flex items-center gap-1.5">
                <Coins className="w-3.5 h-3.5 text-emerald-400" />
                Skema bagi hasil sesuai kebijakan aktif
              </span>
              <span className="px-3 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 font-semibold flex items-center gap-1.5">
                <Tv className="w-3.5 h-3.5 text-cyan-400" />
                Distribusi sesuai kanal yang diaktifkan
              </span>
              <span className="px-3 py-1 rounded-full bg-purple-950/80 border border-purple-500/40 text-purple-300 font-semibold flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                Verifikasi Resmi Team Allpha
              </span>
            </div>
          </div>

          {/* Action CTA Buttons */}
          <div className="relative z-10 flex flex-col sm:flex-row md:flex-col gap-2.5 shrink-0">
            <button
              onClick={() => setIsCreateStudioOpen(true)}
              className="px-6 py-3.5 rounded-2xl bg-gradient-to-r from-rose-500 via-pink-600 to-purple-600 hover:from-rose-400 hover:to-purple-500 text-white font-black text-sm shadow-[0_0_30px_rgba(244,63,94,0.45)] hover:shadow-[0_0_35px_rgba(244,63,94,0.65)] transition transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer"
            >
              <PlusCircle className="w-4 h-4 fill-white text-rose-600" />
              <span>Create Film AI</span>
              <ChevronRight className="w-4 h-4" />
            </button>

            <button
              onClick={() => setCinemaViewMode(cinemaViewMode === 'MY_STUDIO' ? 'CATALOG' : 'MY_STUDIO')}
              className="px-4 py-2.5 rounded-2xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-bold transition flex items-center justify-center gap-1.5"
            >
              <Film className="w-3.5 h-3.5 text-rose-400" />
              <span>{cinemaViewMode === 'MY_STUDIO' ? 'Lihat Semua Katalog Film' : `Status Film Saya (${myUploadedFilms.length})`}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Featured Blockbuster Banner */}
      {featuredMovie && cinemaViewMode === 'CATALOG' && (
        <div className="relative rounded-3xl overflow-hidden bg-slate-950 text-white border border-slate-800 shadow-xl group">
          <div className="relative h-64 sm:h-80 w-full overflow-hidden">
            <img
              src={featuredMovie.bannerImage}
              alt={featuredMovie.title}
              className="w-full h-full object-cover group-hover:scale-105 transition duration-700"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/50 to-transparent" />

            {/* Badges on top */}
            <div className="absolute top-4 left-4 right-4 flex items-center justify-between">
              <span className="px-3 py-1 rounded-full bg-rose-600 text-white font-extrabold text-xs uppercase shadow-md flex items-center gap-1.5">
                <Flame className="w-3.5 h-3.5" />
                <span>Trending #1 Drama Pendek AI</span>
              </span>

              <span className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-sm text-amber-400 text-xs font-mono font-bold flex items-center gap-1">
                <Star className="w-3.5 h-3.5 fill-amber-400" />
                <span>{featuredMovie.rating}</span>
                <span className="text-white/60">({featuredMovie.totalViews} Penonton)</span>
              </span>
            </div>

            {/* Content overlay at bottom */}
            <div className="absolute bottom-4 left-4 right-4 space-y-2.5 max-w-2xl">
              <div>
                <span className="text-[11px] font-mono text-cyan-300 font-bold uppercase tracking-wider block">
                  {featuredMovie.genreLabel} • {featuredMovie.episodesCount} Episode
                </span>
                <h2 className="text-xl sm:text-2xl font-black text-white leading-tight">
                  {featuredMovie.title}
                </h2>
                <p className="text-xs text-slate-300 line-clamp-2 mt-1 leading-relaxed">
                  {featuredMovie.synopsis}
                </p>
              </div>

              {/* Creator lockup & Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <button
                  onClick={() => handleOpenTheater(featuredMovie, 1)}
                  className="px-5 py-2.5 rounded-2xl bg-gradient-to-r from-rose-600 to-purple-600 hover:from-rose-500 hover:to-purple-500 text-white font-extrabold text-xs shadow-lg shadow-rose-500/25 transition flex items-center gap-2"
                >
                  <Play className="w-4 h-4 fill-white" />
                  <span>Tonton Trailer & Part 1 (Gratis)</span>
                </button>

                <button
                  onClick={() => {
                    if (onPostTrailerToFeed) {
                      onPostTrailerToFeed(featuredMovie);
                      showToast(`Trailer "${featuredMovie.title}" berhasil diposting ke Feed & Reels Anda!`);
                    } else {
                      showToast('Tautan trailer disalin!');
                    }
                  }}
                  className="px-3.5 py-2.5 rounded-2xl bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white font-bold text-xs transition flex items-center gap-1.5"
                  title="Posting Trailer ke Feed & Reels"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Bagikan Trailer</span>
                </button>

                <div className="text-[11px] text-slate-300 flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Disutradarai oleh {featuredMovie.producerHuman.name} × {featuredMovie.aiCoDirector.name}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mode View: My Studio vs All Catalog */}
      {cinemaViewMode === 'MY_STUDIO' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
            <div>
              <h3 className="font-black text-base text-slate-900 flex items-center gap-2">
                <span>Studio Produser: Film AI Saya</span>
                <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-xs font-bold font-mono">
                  {myUploadedFilms.length} Film
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                Kelola status verifikasi, statistik tontonan, dan royalti berdasarkan data layanan kanonis.
              </p>
            </div>

            <button
              onClick={() => setIsCreateStudioOpen(true)}
              className="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Upload Film Baru</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {myUploadedFilms.map((film) => (
              <div
                key={film.id}
                className="p-4 rounded-3xl bg-white border border-slate-200 shadow-sm hover:shadow-md transition space-y-3"
              >
                <div className="flex gap-3">
                  <img
                    src={film.coverImage}
                    alt={film.title}
                    className="w-20 h-28 rounded-2xl object-cover shrink-0 shadow-sm"
                  />
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-1.5">
                      {film.verificationStatus === 'VERIFIED' ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          Terverifikasi Team Allpha
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold flex items-center gap-1">
                          <AlertCircle className="w-3 h-3 text-amber-600" />
                          Dalam Verifikasi Team Allpha
                        </span>
                      )}
                    </div>

                    <h4 className="font-extrabold text-sm text-slate-900 line-clamp-1">{film.title}</h4>
                    <p className="text-[11px] text-slate-500 line-clamp-2">{film.synopsis}</p>
                    <p className="text-[10px] text-rose-600 font-bold">{film.genreLabel} • {film.episodesCount} Part</p>
                  </div>
                </div>

                {/* Earnings & Actions */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                  <div className="space-y-0.5">
                    <span className="text-[10px] text-slate-400">Royalti (data kanonis):</span>
                    <p className="font-mono font-bold text-amber-700">+{film.creatorMonthlyEarningsCredits} Cr</p>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {film.verificationStatus === 'PENDING_VERIFICATION' && (
                      <button
                        onClick={() => handleApproveByTeamAllpha(film.id)}
                        className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold"
                        title="Simulasi Verifikasi Cepat"
                      >
                        ⚡ Setujui Sekarang
                      </button>
                    )}
                    <button
                      onClick={() => handleOpenTheater(film, 1)}
                      className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold flex items-center gap-1"
                    >
                      <Play className="w-3 h-3 fill-white" />
                      <span>Nonton</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* Genre Filter Tabs */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-extrabold text-sm text-slate-900">
                Katalog Film Pendek & Serial Drama AI
              </h3>
              <span className="text-xs text-slate-500 font-mono">
                {filteredMovies.length} Judul Tersedia
              </span>
            </div>

            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
              {[
                { id: 'ALL' as FilmGenre, label: 'Semua Kategori' },
                { id: 'C_DRAMA' as FilmGenre, label: 'Drama China AI (C-Drama)' },
                { id: 'K_DRAMA' as FilmGenre, label: 'Drama Korea AI (K-Drama)' },
                { id: 'SCIFI' as FilmGenre, label: 'Sci-Fi Spatial 3D' },
                { id: 'THRILLER' as FilmGenre, label: 'Thriller & Misteri' },
              ].map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveGenre(cat.id)}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition whitespace-nowrap shrink-0 ${
                    activeGenre === cat.id
                      ? 'bg-rose-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* Film Catalog Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {filteredMovies.map((movie) => (
              <div
                key={movie.id}
                className="rounded-3xl bg-white border border-slate-200/80 hover:border-slate-300 shadow-sm hover:shadow-md transition overflow-hidden flex flex-col justify-between group"
              >
                <div>
                  {/* Poster / Cover Image */}
                  <div className="relative aspect-[16/10] w-full overflow-hidden bg-slate-950">
                    <img
                      src={movie.coverImage}
                      alt={movie.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent" />

                    {/* Category pill on top */}
                    <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-full bg-slate-950/80 text-white text-[10px] font-bold backdrop-blur-xs">
                        {movie.genreLabel}
                      </span>
                    </div>

                    {/* Verification Badge */}
                    <div className="absolute top-2.5 right-2.5">
                      {movie.verificationStatus === 'VERIFIED' ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-950/90 border border-emerald-500/50 text-emerald-300 text-[10px] font-bold flex items-center gap-1 backdrop-blur-xs">
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          <span>Terverifikasi</span>
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-amber-950/90 border border-amber-500/50 text-amber-300 text-[10px] font-bold flex items-center gap-1 backdrop-blur-xs">
                          <Clock className="w-3 h-3 text-amber-400" />
                          <span>Ditinjau Team</span>
                        </span>
                      )}
                    </div>

                    {/* Rating and episodes count on bottom */}
                    <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-center justify-between text-xs text-white">
                      <span className="font-mono text-[11px] font-bold text-amber-300 flex items-center gap-1">
                        <Star className="w-3 h-3 fill-amber-300" />
                        {movie.rating}
                      </span>
                      <span className="text-[10px] text-slate-300 font-mono">
                        {movie.episodesCount} Episode ({movie.totalViews} Views)
                      </span>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="p-3.5 space-y-2">
                    <div>
                      <h4 className="font-extrabold text-sm text-slate-900 group-hover:text-rose-600 transition line-clamp-1">
                        {movie.title}
                      </h4>
                      {movie.originalTitle && (
                        <p className="text-[10px] text-slate-400 line-clamp-1">
                          {movie.originalTitle}
                        </p>
                      )}
                    </div>

                    <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                      {movie.synopsis}
                    </p>

                    {/* Producer & AI Director */}
                    <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-100">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <img
                          src={movie.producerHuman.avatar}
                          alt={movie.producerHuman.name}
                          className="w-4 h-4 rounded-full object-cover"
                        />
                        <span className="text-[11px] font-semibold text-slate-700 truncate">
                          {movie.producerHuman.name}
                        </span>
                      </div>
                      <span className="text-[10px] text-cyan-700 font-medium shrink-0">
                        & {movie.aiCoDirector.name}
                      </span>
                    </div>

                    {/* Profit Royalty Badge */}
                    <div className="p-2 rounded-xl bg-amber-50/80 border border-amber-200/60 flex items-center justify-between text-[10px] text-amber-900">
                      <span>Royalti Kreator:</span>
                      <span className="font-mono font-bold">
                        +{movie.creatorMonthlyEarningsCredits.toLocaleString('id-ID')} Cr/bln
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="p-3.5 pt-0 flex gap-2">
                  <button
                    onClick={() => handleOpenTheater(movie, 1)}
                    className="flex-1 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs transition flex items-center justify-center gap-1 shadow-xs"
                  >
                    <Play className="w-3.5 h-3.5 fill-white" />
                    <span>Nonton</span>
                  </button>
                  <button
                    onClick={() => {
                      if (onPostTrailerToFeed) {
                        onPostTrailerToFeed(movie);
                        showToast(`Trailer "${movie.title}" siap dibagikan ke Feed & Reels!`);
                      }
                    }}
                    className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition"
                    title="Bagikan ke Feed & Reels"
                  >
                    <Share2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ========================================================================= */}
      {/* 2. DEDICATED STUDIO MODAL: "CREATE FILM AI" (Lengkap Form, Trailer, Parts) */}
      {/* ========================================================================= */}
      {isCreateStudioOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="w-full max-w-2xl rounded-3xl bg-slate-950 text-white border border-slate-800 shadow-2xl p-5 sm:p-6 space-y-5 my-auto animate-in fade-in zoom-in-95 duration-200 text-xs">
            {/* Header */}
            <div className="flex items-start justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-2xl bg-gradient-to-tr from-rose-600 to-purple-600 text-white shadow-md">
                  <Film className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">
                    Studio Registrasi & Produksi Film AI Allpha
                  </span>
                  <h3 className="text-base sm:text-lg font-black text-white mt-0.5">
                    Create Film AI & Daftarkan Karyamu
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Upload trailer, kelola part video, dan kirim untuk verifikasi resmi Team Allpha.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsCreateStudioOpen(false)}
                className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Stepper overview */}
            <div className="grid grid-cols-4 gap-1 p-2 rounded-2xl bg-slate-900 border border-slate-800 text-[10px] text-center font-bold text-slate-300">
              <span className="text-rose-400">1. Info Judul</span>
              <span className="text-rose-400">2. Upload Trailer</span>
              <span className="text-rose-400">3. Video per Part</span>
              <span className="text-emerald-400">4. Verifikasi Team</span>
            </div>

            {/* Section 1: Form Judul & Kategori */}
            <div className="space-y-3 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
              <h4 className="font-extrabold text-xs text-rose-300 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" />
                <span>1. Form Judul & Informasi Film AI</span>
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-300">Judul Utama Film AI:</label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="Contoh: The Secret Cyborg Prince (K-Drama AI)..."
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white outline-none focus:border-rose-400"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-300">Judul Asli / Hanzi / Tagline:</label>
                  <input
                    type="text"
                    value={newOriginalTitle}
                    onChange={(e) => setNewOriginalTitle(e.target.value)}
                    placeholder="Contoh: 总裁的秘密仿生新娘 / Neo Shanghai 2099..."
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white outline-none focus:border-rose-400"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-300">Kategori / Genre Film:</label>
                  <select
                    value={newGenre}
                    onChange={(e) => setNewGenre(e.target.value as FilmGenre)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white outline-none"
                  >
                    <option value="C_DRAMA">Drama China AI (C-Drama)</option>
                    <option value="K_DRAMA">Drama Korea AI (K-Drama)</option>
                    <option value="SCIFI">Sci-Fi Spatial 3D</option>
                    <option value="THRILLER">Thriller & Misteri</option>
                    <option value="ROMANCE">Romance & Time Travel</option>
                    <option value="ANIMATION_3D">Animasi 3D & Wuxia</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-300">Durasi Rata-rata per Part:</label>
                  <input
                    type="text"
                    value={newDurationPerPart}
                    onChange={(e) => setNewDurationPerPart(e.target.value)}
                    placeholder="Contoh: 2–3 Menit / Part..."
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white outline-none"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-slate-300">Deskripsi Lengkap & Sinopsis Alur Cerita:</label>
                <textarea
                  rows={3}
                  value={newSynopsis}
                  onChange={(e) => setNewSynopsis(e.target.value)}
                  placeholder="Tuliskan hook cerita, karakter utama, alur konflik, dan pesan moral film AI..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white outline-none focus:border-rose-400"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
                <div className="space-y-1">
                  <label className="text-slate-400">Produser (Human):</label>
                  <input
                    type="text"
                    value={newProducerName}
                    onChange={(e) => setNewProducerName(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-slate-400">Co-Director (AI Agent):</label>
                  <input
                    type="text"
                    value={newAiCoDirector}
                    onChange={(e) => setNewAiCoDirector(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-slate-400">AI Tech Stack Digunakan:</label>
                  <input
                    type="text"
                    value={newTechStack}
                    onChange={(e) => setNewTechStack(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200"
                  />
                </div>
              </div>
            </div>

            {/* Section 2: Upload Trailer & Cover Poster */}
            <div className="space-y-3 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
              <h4 className="font-extrabold text-xs text-rose-300 flex items-center gap-1.5">
                <Video className="w-3.5 h-3.5" />
                <span>2. Upload Trailer Film AI & Poster</span>
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Trailer Upload Box */}
                <div className="p-3.5 rounded-xl bg-slate-950 border border-dashed border-rose-500/50 flex flex-col justify-between space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white flex items-center gap-1.5">
                      <Upload className="w-3.5 h-3.5 text-rose-400" />
                      File Trailer Video (MP4 / 4K)
                    </span>
                    <span className="text-[10px] text-emerald-400 font-mono font-bold">Terunggah ✓</span>
                  </div>
                  <p className="text-[11px] text-slate-300 font-mono truncate">{trailerFileName}</p>
                  
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <div className="flex items-center gap-1 text-[10px] text-slate-400">
                      <Clock className="w-3 h-3" />
                      <span>Durasi: {trailerDuration}</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => setIsPreviewingTrailer(!isPreviewingTrailer)}
                      className="px-2.5 py-1 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white text-[10px] font-bold flex items-center gap-1"
                    >
                      <Play className="w-2.5 h-2.5 fill-white" />
                      <span>{isPreviewingTrailer ? 'Stop Preview' : 'Preview Trailer'}</span>
                    </button>
                  </div>

                  {isPreviewingTrailer && (
                    <div className="p-2 rounded-lg bg-black text-center space-y-1 animate-in fade-in">
                      <div className="w-full h-20 rounded bg-slate-800 flex items-center justify-center relative overflow-hidden">
                        <img
                          src={selectedPosterPreset}
                          alt="Trailer Preview"
                          className="w-full h-full object-cover opacity-80"
                        />
                        <span className="absolute inset-0 flex items-center justify-center font-bold text-rose-300 text-[10px]">
                          ▶ Memutar Trailer Sinematik 4K...
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Poster Artwork Selector */}
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                  <span className="font-bold text-white block">Pilih Poster Cover Film:</span>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg',
                      '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
                      '/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png',
                    ].map((img, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setSelectedPosterPreset(img)}
                        className={`relative rounded-xl overflow-hidden aspect-[3/4] border-2 transition ${
                          selectedPosterPreset === img
                            ? 'border-rose-500 scale-105 shadow-md shadow-rose-500/30'
                            : 'border-slate-800 opacity-60 hover:opacity-100'
                        }`}
                      >
                        <img src={img} alt="Poster" className="w-full h-full object-cover" />
                        {selectedPosterPreset === img && (
                          <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-rose-600 text-white flex items-center justify-center text-[9px] font-bold">
                            ✓
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Section 3: Upload Video per Part Film (Multi-Part) */}
            <div className="space-y-3 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-extrabold text-xs text-rose-300 flex items-center gap-1.5">
                    <ListChecks className="w-3.5 h-3.5" />
                    <span>3. Upload Video per Part Film ({videoParts.length} Part Terdaftar)</span>
                  </h4>
                  <p className="text-[10px] text-slate-400">
                    Serial drama pendek di Allpha diunggah per part/episode (Part 1, Part 2, dst).
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleAddVideoPart}
                  className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-[11px] flex items-center gap-1 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Tambah Part</span>
                </button>
              </div>

              {/* Dynamic Parts List */}
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {videoParts.map((part) => (
                  <div
                    key={part.id}
                    className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <span className="w-6 h-6 rounded-lg bg-rose-600/30 border border-rose-500/40 text-rose-300 font-mono font-bold flex items-center justify-center shrink-0">
                        {part.partNumber}
                      </span>
                      <div className="flex-1 min-w-0">
                        <input
                          type="text"
                          value={part.title}
                          onChange={(e) => handleUpdatePart(part.id, { title: e.target.value })}
                          className="w-full bg-transparent font-bold text-slate-200 outline-none text-xs border-b border-transparent focus:border-rose-400"
                        />
                        <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5">
                          <span>{part.fileName}</span>
                          <span>•</span>
                          <span>{part.fileSize || '50 MB'}</span>
                          <span>•</span>
                          <span className="text-emerald-400 font-mono">Durasi: {part.duration}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                      <button
                        type="button"
                        onClick={() => handleUpdatePart(part.id, { isFreePreview: !part.isFreePreview })}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition ${
                          part.isFreePreview
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                            : 'bg-amber-950 text-amber-300 border border-amber-500/40'
                        }`}
                      >
                        {part.isFreePreview ? 'Gratis (Preview)' : 'Khusus VIP'}
                      </button>

                      {videoParts.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveVideoPart(part.id)}
                          className="p-1 rounded-lg text-slate-500 hover:text-rose-400 transition"
                          title="Hapus Part"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 4: Revenue & Verification Notice */}
            <div className="p-3.5 rounded-2xl bg-gradient-to-r from-purple-950/60 to-rose-950/60 border border-rose-500/40 text-[11px] text-slate-300 space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Publish & Verifikasi oleh Team Allpha</span>
              </div>
              <p>
                Setelah menekan tombol di bawah, film AI Anda akan masuk ke antrean verifikasi Team Allpha. Setelah terverifikasi, film akan otomatis tampil di katalog dan dapat ditonton oleh seluruh pengguna Allpha, serta mendatangkan <strong>sesuai kebijakan aktif royalti AI Credits</strong> langsung ke dompet kreator Anda.
              </p>
            </div>

            {/* Bottom Actions */}
            <div className="flex items-center gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setIsCreateStudioOpen(false)}
                className="flex-1 py-3 rounded-2xl bg-slate-900 hover:bg-slate-800 text-slate-300 font-bold transition"
              >
                Simpan Sebagai Draf
              </button>

              <button
                type="button"
                onClick={handlePublishForVerification}
                className="flex-1 py-3 rounded-2xl bg-gradient-to-r from-rose-600 via-pink-600 to-purple-600 hover:from-rose-500 hover:to-purple-500 text-white font-black shadow-lg shadow-rose-600/30 flex items-center justify-center gap-2 transition transform active:scale-95"
              >
                <span>Publish & Kirim Verifikasi ke Team Allpha</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. REVIEW / VERIFICATION STATUS MODAL (Simulasi Verifikasi Team Allpha)   */}
      {/* ========================================================================= */}
      {reviewModalData.isOpen && reviewModalData.movie && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-slate-950 text-white border border-slate-800 shadow-2xl p-5 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs">
            <div className="text-center space-y-2 pt-2">
              <div className="w-14 h-14 mx-auto rounded-full bg-gradient-to-tr from-rose-500 to-purple-600 flex items-center justify-center shadow-lg shadow-rose-500/30 animate-pulse">
                {reviewModalData.movie.verificationStatus === 'VERIFIED' ? (
                  <Check className="w-8 h-8 text-white" />
                ) : (
                  <Clock className="w-7 h-7 text-white" />
                )}
              </div>

              <div>
                <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">
                  Status Pengajuan Film AI
                </span>
                <h3 className="text-base font-black text-white mt-0.5">
                  &quot;{reviewModalData.movie.title}&quot;
                </h3>
              </div>
            </div>

            {/* Status Card */}
            <div className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Status Kurasi:</span>
                {reviewModalData.movie.verificationStatus === 'VERIFIED' ? (
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    Terverifikasi Team Allpha
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40 flex items-center gap-1 animate-pulse">
                    <Clock className="w-3 h-3 text-amber-400" />
                    Sedang Diverifikasi Team Allpha
                  </span>
                )}
              </div>

              <div className="space-y-1.5 pt-2 border-t border-slate-800 text-[11px] text-slate-300">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Trailer Video 4K Terunggah & Valid</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{reviewModalData.movie.episodesCount} Video Part Siap Diputar</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Sistem Royalti sesuai kebijakan aktif Terhubung ke Dompet Anda</span>
                </div>
              </div>
            </div>

            {/* Explanation text */}
            <p className="text-[11px] text-slate-300 text-center leading-relaxed">
              {reviewModalData.movie.verificationStatus === 'VERIFIED'
                ? 'Film AI Anda telah resmi terverifikasi dan kini tampil di halaman utama Film AI Allpha untuk ditonton seluruh pengguna!'
                : 'Team Kurasi Allpha sedang meninjau kualitas visual dan audio spatial film Anda. Anda juga dapat memilih simulasi persetujuan instan di bawah ini.'}
            </p>

            {/* Actions */}
            <div className="space-y-2 pt-1">
              {reviewModalData.movie.verificationStatus !== 'VERIFIED' ? (
                <button
                  type="button"
                  onClick={() => handleApproveByTeamAllpha(reviewModalData.movie!.id)}
                  className="w-full py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-extrabold shadow-md flex items-center justify-center gap-2 transition cursor-pointer"
                >
                  <ShieldCheck className="w-4 h-4" />
                  <span>Verifikasi Sekarang oleh Team Allpha (Instant)</span>
                </button>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setReviewModalData({ isOpen: false, movie: null });
                      handleOpenTheater(reviewModalData.movie!, 1);
                    }}
                    className="py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold flex items-center justify-center gap-1.5"
                  >
                    <Play className="w-3.5 h-3.5 fill-white" />
                    <span>Tonton Film</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      if (onPostTrailerToFeed && reviewModalData.movie) {
                        onPostTrailerToFeed(reviewModalData.movie);
                        showToast('Trailer berhasil dibagikan ke Feed Threads!');
                      }
                      setReviewModalData({ isOpen: false, movie: null });
                    }}
                    className="py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold flex items-center justify-center gap-1.5"
                  >
                    <Share2 className="w-3.5 h-3.5" />
                    <span>Share Trailer</span>
                  </button>
                </div>
              )}

              <button
                type="button"
                onClick={() => setReviewModalData({ isOpen: false, movie: null })}
                className="w-full py-2.5 rounded-2xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white font-bold transition"
              >
                Tutup & Kembali ke Katalog
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. THEATER / VIDEO PLAYER MODAL (Play Trailer & Video Parts)              */}
      {/* ========================================================================= */}
      {activeTheaterMovie && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-2 sm:p-4 overflow-y-auto">
          <div className="w-full max-w-3xl rounded-3xl bg-slate-950 text-white border border-slate-800 shadow-2xl overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-200">
            {/* Top Bar of Theater */}
            <div className="px-4 py-3 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse shrink-0" />
                <h3 className="font-extrabold text-sm text-white truncate">
                  {activeTheaterMovie.title} — {isViewingTrailerInTheater ? 'Trailer Resmi' : `Part / Episode ${activeEpisodeNumber}`}
                </h3>
              </div>
              <button
                onClick={() => setActiveTheaterMovie(null)}
                className="p-1 rounded-full text-slate-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Video Player Canvas Viewport */}
            <div className="relative aspect-video w-full bg-black overflow-hidden flex items-center justify-center group">
              <img
                src={activeTheaterMovie.bannerImage}
                alt={activeTheaterMovie.title}
                className={`w-full h-full object-cover transition duration-700 ${isPlaying ? 'scale-105 filter brightness-105' : 'filter brightness-75'}`}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-black/40" />

              {/* Watermark Logo Allpha Cinema */}
              <div className="absolute top-3 left-4 flex items-center gap-1.5 pointer-events-none">
                <div className="w-6 h-6 rounded-lg bg-rose-600 flex items-center justify-center font-black text-white text-xs">
                  A
                </div>
                <span className="font-extrabold text-xs tracking-wider text-white drop-shadow">
                  ALLPHA CINEMA
                </span>
                {activeTheaterMovie.verificationStatus === 'VERIFIED' && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/30 text-emerald-300 font-bold ml-2">
                    ✓ Verified
                  </span>
                )}
              </div>

              {/* Center Play/Pause Indicator if Clicked */}
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="absolute w-14 h-14 rounded-full bg-rose-600/90 hover:bg-rose-600 text-white flex items-center justify-center shadow-2xl transition transform active:scale-95 z-20 cursor-pointer"
              >
                {isPlaying ? <Pause className="w-6 h-6 fill-white" /> : <Play className="w-6 h-6 fill-white ml-1" />}
              </button>

              {/* Bottom Video Controls Overlay */}
              <div className="absolute bottom-0 left-0 right-0 p-4 space-y-2 z-20 bg-gradient-to-t from-black via-black/80 to-transparent">
                {/* Seek Bar */}
                <div className="w-full h-1.5 rounded-full bg-white/20 cursor-pointer overflow-hidden">
                  <div className="h-full bg-rose-500 rounded-full transition-all duration-300" style={{ width: '42%' }} />
                </div>

                <div className="flex items-center justify-between text-xs text-white">
                  <div className="flex items-center gap-3">
                    <button onClick={() => setIsPlaying(!isPlaying)} className="hover:text-rose-400 transition">
                      {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white" />}
                    </button>
                    <button onClick={() => setIsAudioMuted(!isAudioMuted)} className="hover:text-rose-400 transition">
                      {isAudioMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>
                    <span className="font-mono text-[11px] text-slate-300">
                      01:14 / {isViewingTrailerInTheater ? (activeTheaterMovie.trailerDuration || '00:45') : activeTheaterMovie.durationPerEp}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 font-mono">
                      4K Ultra HD
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Video Details & Parts Selector */}
            <div className="p-4 sm:p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                <div>
                  <h3 className="text-base sm:text-lg font-black text-white">
                    {activeTheaterMovie.title}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {activeTheaterMovie.genreLabel} • Disutradarai oleh {activeTheaterMovie.producerHuman.name} × {activeTheaterMovie.aiCoDirector.name}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (onPostTrailerToFeed) {
                        onPostTrailerToFeed(activeTheaterMovie);
                        showToast(`Trailer "${activeTheaterMovie.title}" berhasil di-share ke Feed Allpha!`);
                      }
                    }}
                    className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition flex items-center gap-1.5"
                  >
                    <Share2 className="w-3.5 h-3.5" />
                    <span>Share ke Feed</span>
                  </button>

                  {onOpenAskAi && (
                    <button
                      onClick={() => onOpenAskAi(
                        activeTheaterMovie.aiCoDirector.name,
                        activeTheaterMovie.producerHuman.name,
                        activeTheaterMovie.aiCoDirector.specialty
                      )}
                      className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition flex items-center gap-1.5"
                    >
                      <Bot className="w-3.5 h-3.5" />
                      <span>Tanya Sutradara AI</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Part & Trailer Switcher */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-300">Pilih Trailer & Video Part:</span>
                  {!isVipSubscribed && (
                    <span className="text-[11px] text-amber-400">
                      Trailer & Part 1 Gratis • Part Lainnya Khusus VIP
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
                  {/* Trailer Button */}
                  <button
                    onClick={() => {
                      setIsViewingTrailerInTheater(true);
                      setIsPlaying(true);
                      showToast(`Memutar Trailer: "${activeTheaterMovie.title}"`);
                    }}
                    className={`px-3 py-2 rounded-xl text-xs font-bold transition shrink-0 flex items-center gap-1.5 ${
                      isViewingTrailerInTheater
                        ? 'bg-rose-600 text-white shadow-md shadow-rose-500/25 ring-2 ring-white'
                        : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                    }`}
                  >
                    <Video className="w-3 h-3" />
                    <span>Trailer Resmi ({activeTheaterMovie.trailerDuration || '00:45'})</span>
                  </button>

                  {/* Episodes / Parts */}
                  {Array.from({ length: activeTheaterMovie.episodesCount }, (_, i) => i + 1).map((ep) => {
                    const isFree = ep <= 2;
                    const isUnlocked = isFree || isVipSubscribed;
                    const isActive = !isViewingTrailerInTheater && activeEpisodeNumber === ep;

                    return (
                      <button
                        key={ep}
                        onClick={() => {
                          if (ep > 2 && !isVipSubscribed) {
                            setIsSubscriptionModalOpen(true);
                            return;
                          }
                          setIsViewingTrailerInTheater(false);
                          setActiveEpisodeNumber(ep);
                          setIsPlaying(true);
                          showToast(`Memutar Part ${ep}: "${activeTheaterMovie.title}"`);
                        }}
                        className={`px-3 py-2 rounded-xl text-xs font-bold transition shrink-0 flex items-center gap-1.5 ${
                          isActive
                            ? 'bg-rose-600 text-white shadow-md shadow-rose-500/25 ring-2 ring-white'
                            : isUnlocked
                            ? 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                            : 'bg-slate-900/80 text-slate-500 border border-slate-800'
                        }`}
                      >
                        {!isUnlocked ? (
                          <Lock className="w-3 h-3 text-amber-500" />
                        ) : (
                          <Play className="w-2.5 h-2.5 fill-current" />
                        )}
                        <span>Part {ep}</span>
                        {isFree && !isVipSubscribed && (
                          <span className="text-[9px] px-1 rounded bg-emerald-500/20 text-emerald-300">
                            Free
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Synopsis and AI Stack */}
              <div className="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs">
                <p className="text-slate-300 leading-relaxed">
                  {activeTheaterMovie.synopsis}
                </p>
                <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                  <span>AI Tech Stack: {activeTheaterMovie.aiTechStack}</span>
                  <span className="text-amber-300 font-mono">
                    Royalti Kreator: +{activeTheaterMovie.creatorMonthlyEarningsCredits} Cr/bln
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 5. VIP SUBSCRIPTION MODAL                                                 */}
      {/* ========================================================================= */}
      {isSubscriptionModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-slate-950 text-white border border-rose-500/40 shadow-2xl p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center">
                  <Crown className="w-4 h-4" />
                </div>
                <h3 className="font-extrabold text-sm text-white">Langganan VIP Allpha Cinema</h3>
              </div>
              <button
                onClick={() => setIsSubscriptionModalOpen(false)}
                className="p-1 rounded-full text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Price Tag */}
            <div className="p-4 rounded-2xl bg-gradient-to-r from-rose-950/80 to-purple-950/80 border border-rose-500/30 text-center space-y-1">
              <span className="text-[10px] uppercase font-bold text-rose-300 tracking-wider">
                Paket Berlangganan Bulanan
              </span>
              <p className="text-2xl font-mono font-black text-white">
                Harga dan kuota paket ditampilkan setelah kontrak billing aktif.
              </p>
              <p className="text-[11px] text-slate-300">
                Saldo Anda saat ini: <strong className="font-mono text-amber-300">{userCredits === null ? '—' : userCredits} Credits</strong>
              </p>
            </div>

            {/* Benefit Checkpoints */}
            <div className="space-y-2 text-slate-300 text-xs">
              {[
                'Buka ribuan episode Drama Pendek AI (C-Drama & K-Drama) tanpa iklan',
                'Resolusi 4K Ultra HD 60 FPS dengan audio spatial 3D',
                'Akses premiere episode baru 24 jam lebih awal',
                'Skema royalti mengikuti kebijakan yang disahkan dan settlement kanonis',
                'Bisa diakses dari Feed, Reels, dan 3D Universe Cinema District',
              ].map((benefit, i) => (
                <div key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span className="leading-snug">{benefit}</span>
                </div>
              ))}
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsSubscriptionModalOpen(false)}
                className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold"
              >
                Nanti Saja
              </button>
              <button
                type="button"
                onClick={handleConfirmVipSubscription}
                className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 via-purple-600 to-amber-500 hover:from-rose-500 hover:to-amber-400 text-white font-extrabold shadow-lg shadow-rose-500/25"
              >
                Aktifkan VIP Sekarang
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
