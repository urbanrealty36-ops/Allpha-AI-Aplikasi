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
}

const INITIAL_MOVIES_LIST: AiMovieItem[] = [
  {
    id: 'film-1',
    title: 'The Reborn Cyber Empress',
    originalTitle: '重生之赛博女帝 (Drama Pendek AI C-Drama)',
    genre: 'C_DRAMA',
    genreLabel: 'Drama China AI (C-Drama)',
    coverImage: '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg',
    bannerImage: '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
    episodesCount: 15,
    totalViews: '1.4M',
    rating: 4.9,
    durationPerEp: '2–3 menit / ep',
    releaseYear: '2026',
    producerHuman: {
      name: 'Chen Wei',
      handle: '@chenwei_films',
      avatar: 'https://picsum.photos/seed/chen-producer/150/150',
    },
    aiCoDirector: {
      name: 'CineGenius AI',
      handle: '@cinegenius.ai',
      avatar: 'https://picsum.photos/seed/cinegenius/150/150',
      specialty: 'C-Drama Fast-Paced Directing & Neural Voice',
    },
    synopsis: 'Dikhianati oleh keluarga konglomerat di Shanghai 2099, Lin Yue terlahir kembali dengan memori masa depan dan AI Agent taktis untuk membalas dendam dan merebut kembali tahta bisnis teknologi terkuat.',
    aiTechStack: 'Kling 1.5 + Midjourney v6 + ElevenLabs Neural Voice + Wan2.1 Video',
    creatorMonthlyEarningsCredits: 14850,
    isTrending: true,
    isFeatured: true,
    verificationStatus: 'VERIFIED',
    trailerTitle: 'Official Premiere Trailer 4K',
    trailerDuration: '00:45',
    parts: [
      { id: 'p1', partNumber: 1, title: 'Episode 1: Kebangkitan Sang Ratu', duration: '02:30', isFreePreview: true },
      { id: 'p2', partNumber: 2, title: 'Episode 2: Pertemuan di Menara Kristal', duration: '02:45', isFreePreview: true },
      { id: 'p3', partNumber: 3, title: 'Episode 3: Menghapus Jejak Musuh', duration: '03:10', isFreePreview: false },
      { id: 'p4', partNumber: 4, title: 'Episode 4: Protokol Aliansi Rahasia', duration: '02:50', isFreePreview: false },
      { id: 'p5', partNumber: 5, title: 'Episode 5: Tahta yang Direbut Kembali', duration: '03:20', isFreePreview: false },
    ],
  },
  {
    id: 'film-2',
    title: 'Neo-Seoul: Destined Neural Hearts',
    originalTitle: '운명의 뉴럴 하트 (K-Drama AI Rom-Com)',
    genre: 'K_DRAMA',
    genreLabel: 'Drama Korea AI (K-Drama)',
    coverImage: '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
    bannerImage: '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
    episodesCount: 12,
    totalViews: '980K',
    rating: 4.8,
    durationPerEp: '3 menit / ep',
    releaseYear: '2026',
    producerHuman: {
      name: 'Park Ji-hoon',
      handle: '@jihoon_media',
      avatar: 'https://picsum.photos/seed/jihoon/150/150',
    },
    aiCoDirector: {
      name: 'Luna AI',
      handle: '@luna.ai',
      avatar: 'https://picsum.photos/seed/luna-cyber/150/150',
      specialty: 'K-Drama Romance Lighting & Spatial Sound',
    },
    synopsis: 'Kisah cinta manis dan penuh intrik antara seorang desainer spatial muda dan CEO android misterius di tengah gemerlap kota futuristik Neo-Seoul.',
    aiTechStack: 'Luma Dream Machine + ElevenLabs Korean Voice + Stable Diffusion 3',
    creatorMonthlyEarningsCredits: 9640,
    isTrending: true,
    verificationStatus: 'VERIFIED',
    trailerTitle: 'Teaser Romantis Neo-Seoul',
    trailerDuration: '00:50',
    parts: [
      { id: 'p1', partNumber: 1, title: 'Episode 1: Tatapan di Halte Kereta Cepat', duration: '03:00', isFreePreview: true },
      { id: 'p2', partNumber: 2, title: 'Episode 2: Rahasia Kode Sumber', duration: '02:55', isFreePreview: true },
      { id: 'p3', partNumber: 3, title: 'Episode 3: Kencan Hologram Pertama', duration: '03:15', isFreePreview: false },
    ],
  },
  {
    id: 'film-3',
    title: "CEO's Secret Android Bride",
    originalTitle: '总裁的秘密仿生新娘 (Drama Pendek AI Modern)',
    genre: 'C_DRAMA',
    genreLabel: 'Drama China AI (C-Drama)',
    coverImage: '/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png',
    bannerImage: '/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png',
    episodesCount: 18,
    totalViews: '2.1M',
    rating: 4.95,
    durationPerEp: '2 menit / ep',
    releaseYear: '2026',
    producerHuman: {
      name: 'Alex Tamara',
      handle: '@alextamara',
      avatar: 'https://picsum.photos/seed/alex-tamara/150/150',
    },
    aiCoDirector: {
      name: 'Luna AI',
      handle: '@luna.ai',
      avatar: 'https://picsum.photos/seed/luna-cyber/150/150',
      specialty: '3D Spatial Wardrobe & Emissive Lighting',
    },
    synopsis: 'Demi menyelamatkan perusahaannya, pewaris konglomerat terpaksa menikahi wanita misterius yang ternyata adalah android bio-sintetik dengan misi rahasia menyelamatkan Allpha Universe.',
    aiTechStack: 'Kling AI + Runway Gen-3 + Suno AI Music + ElevenLabs',
    creatorMonthlyEarningsCredits: 22400,
    isTrending: true,
    verificationStatus: 'VERIFIED',
    trailerTitle: 'Main Drama Trailer',
    trailerDuration: '00:40',
    parts: [
      { id: 'p1', partNumber: 1, title: 'Episode 1: Pernikahan Kontrak', duration: '02:10', isFreePreview: true },
      { id: 'p2', partNumber: 2, title: 'Episode 2: Identitas yang Terkuak', duration: '02:05', isFreePreview: true },
      { id: 'p3', partNumber: 3, title: 'Episode 3: Perlindungan Sang CEO', duration: '02:20', isFreePreview: false },
    ],
  },
  {
    id: 'film-4',
    title: 'Shadow Protocol: Shanghai 2099',
    originalTitle: '暗影协议 2099 (Action Thriller AI)',
    genre: 'THRILLER',
    genreLabel: 'Thriller & Action AI',
    coverImage: '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
    bannerImage: '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
    episodesCount: 8,
    totalViews: '640K',
    rating: 4.7,
    durationPerEp: '4 menit / ep',
    releaseYear: '2026',
    producerHuman: {
      name: 'Rizky Pratama',
      handle: '@rizky_action',
      avatar: 'https://picsum.photos/seed/rizky/150/150',
    },
    aiCoDirector: {
      name: 'Aegis AI',
      handle: '@aegis.ai',
      avatar: 'https://picsum.photos/seed/aegis/150/150',
      specialty: 'Tactical Choreography & Hyper-real Combat VFX',
    },
    synopsis: 'Agen rahasia siber menyusup ke markas korporasi nakal untuk membatalkan virus penghapus identitas manusia di Metaverse.',
    aiTechStack: 'Midjourney + Wan2.1 + Sora Spatial Synth',
    creatorMonthlyEarningsCredits: 7120,
    verificationStatus: 'VERIFIED',
  },
  {
    id: 'film-5',
    title: 'The Immortal Sword Sovereign',
    originalTitle: '逆天剑尊 (Wuxia Cultivation AI)',
    genre: 'C_DRAMA',
    genreLabel: 'Drama China AI (C-Drama)',
    coverImage: '/assets/aistudio/Screenshot_20261020-224657_48336231.jpg',
    bannerImage: '/assets/aistudio/Screenshot_20261020-224657_48336231.jpg',
    episodesCount: 20,
    totalViews: '1.6M',
    rating: 4.85,
    durationPerEp: '2.5 menit / ep',
    releaseYear: '2026',
    producerHuman: {
      name: 'Liang Studios',
      handle: '@liang_studios',
      avatar: 'https://picsum.photos/seed/liang/150/150',
    },
    aiCoDirector: {
      name: 'WuxiaMaster AI',
      handle: '@wuxiamaster.ai',
      avatar: 'https://picsum.photos/seed/wuxia/150/150',
      specialty: 'Flying Swords Physics & Traditional Chinese Scoring',
    },
    synopsis: 'Pendekar muda yang kehilangan dantian-nya membangkitkan pedang purba berjiwa AI di puncak Gunung Kristal, menuntut keadilan lintas sembilan alam.',
    aiTechStack: 'Kling 1.5 + ComfyUI AnimateDiff + AudioCraft',
    creatorMonthlyEarningsCredits: 16200,
    verificationStatus: 'VERIFIED',
  },
  {
    id: 'film-6',
    title: 'Chronicles of Mars: The Bio-Awakening',
    originalTitle: 'Mars Bio-Colony Origins',
    genre: 'SCIFI',
    genreLabel: 'Sci-Fi Spatial 3D',
    coverImage: '/assets/aistudio/file_00000000560c820baca9cd747fc97471_b104badb.png',
    bannerImage: '/assets/aistudio/file_00000000560c820baca9cd747fc97471_b104badb.png',
    episodesCount: 10,
    totalViews: '510K',
    rating: 4.65,
    durationPerEp: '3.5 menit / ep',
    releaseYear: '2026',
    producerHuman: {
      name: 'Dr. Sarah Novak',
      handle: '@dr_sarah',
      avatar: 'https://picsum.photos/seed/sarah/150/150',
    },
    aiCoDirector: {
      name: 'CosmoAI',
      handle: '@cosmo.ai',
      avatar: 'https://picsum.photos/seed/cosmo/150/150',
      specialty: 'Astrophysics Simulation & Robotic Voice Synthesis',
    },
    synopsis: 'Peneliti terraforming menemukan mikroorganisme purba di kedalaman tanah Mars yang mampu berinteraksi langsung dengan AI neural network.',
    aiTechStack: 'Three.js Spatial Engine + Runway Gen-3 + Udio Music',
    creatorMonthlyEarningsCredits: 5800,
    verificationStatus: 'VERIFIED',
  },
];

export default function AiCinemaView({
  onBackToFeed,
  onOpenAskAi,
  userCredits,
  onPostTrailerToFeed,
  initialSelectedMovieId,
}: AiCinemaViewProps) {
  // Movie catalog state (supports dynamic user submissions)
  const [moviesList, setMoviesList] = useState<AiMovieItem[]>(INITIAL_MOVIES_LIST);

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
  const [newDurationPerPart, setNewDurationPerPart] = useState('2–3 menit / part');
  const [newTechStack, setNewTechStack] = useState('Kling 1.5 + Runway Gen-3 + ElevenLabs + Suno Music');
  const [newSynopsis, setNewSynopsis] = useState('');
  const [newProducerName, setNewProducerName] = useState('Alex Tamara');
  const [newAiCoDirector, setNewAiCoDirector] = useState('Luna AI');

  // Trailer Upload State
  const [trailerFileName, setTrailerFileName] = useState('trailer_official_4k_cut.mp4');
  const [trailerDuration, setTrailerDuration] = useState('00:45');
  const [isTrailerUploaded, setIsTrailerUploaded] = useState(true);
  const [isPreviewingTrailer, setIsPreviewingTrailer] = useState(false);
  const [selectedPosterPreset, setSelectedPosterPreset] = useState<string>(
    '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg'
  );

  // Video Parts State (Multi-Part Upload)
  const [videoParts, setVideoParts] = useState<MovieEpisodePart[]>([
    {
      id: 'p-1',
      partNumber: 1,
      title: 'Part 1: Awal Mula Sang Ratu',
      duration: '02:30',
      fileName: 'part1_scene_rendered.mp4',
      fileSize: '48 MB',
      isFreePreview: true,
    },
    {
      id: 'p-2',
      partNumber: 2,
      title: 'Part 2: Pertemuan Rahasia di Neo-Shanghai',
      duration: '02:45',
      fileName: 'part2_cyber_tower.mp4',
      fileSize: '54 MB',
      isFreePreview: false,
    },
    {
      id: 'p-3',
      partNumber: 3,
      title: 'Part 3: Serangan Protokol Siber',
      duration: '03:10',
      fileName: 'part3_climax_battle.mp4',
      fileSize: '62 MB',
      isFreePreview: false,
    },
  ]);

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
      return INITIAL_MOVIES_LIST.find((m) => m.id === initialSelectedMovieId) || INITIAL_MOVIES_LIST[0];
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
    if (!newTitle.trim()) {
      showToast('Harap masukkan Judul Film AI Anda.');
      return;
    }
    if (!newSynopsis.trim()) {
      showToast('Harap masukkan Deskripsi & Sinopsis Film.');
      return;
    }

    const createdMovie: AiMovieItem = {
      id: `film-${Date.now()}`,
      title: newTitle.trim(),
      originalTitle: newOriginalTitle.trim() || undefined,
      genre: newGenre,
      genreLabel: genreLabels[newGenre] || 'Film AI Allpha',
      coverImage: selectedPosterPreset,
      bannerImage: selectedPosterPreset,
      episodesCount: videoParts.length,
      totalViews: '0',
      rating: 5.0,
      durationPerEp: newDurationPerPart,
      releaseYear: '2026',
      producerHuman: {
        name: newProducerName || 'Alex Tamara',
        handle: `@${(newProducerName || 'Alex Tamara').toLowerCase().replace(/\s+/g, '')}`,
        avatar: 'https://picsum.photos/seed/alex-producer/150/150',
      },
      aiCoDirector: {
        name: newAiCoDirector || 'Luna AI',
        handle: `@${(newAiCoDirector || 'Luna AI').toLowerCase().replace(/\s+/g, '')}`,
        avatar: 'https://picsum.photos/seed/luna-cyber/150/150',
        specialty: '3D Directing & Spatial Sound Synthesis',
      },
      synopsis: newSynopsis.trim(),
      aiTechStack: newTechStack || 'Kling 1.5 + Runway Gen-3 + ElevenLabs',
      creatorMonthlyEarningsCredits: 0,
      isTrending: true,
      trailerTitle: 'Official Trailer 4K',
      trailerDuration: trailerDuration || '00:45',
      verificationStatus: 'PENDING_VERIFICATION',
      isUserUploaded: true,
      parts: videoParts,
    };

    // Add to movies list
    setMoviesList([createdMovie, ...moviesList]);
    setIsCreateStudioOpen(false);

    // Open review & verification dialog
    setReviewModalData({
      isOpen: true,
      movie: createdMovie,
    });

    showToast(`Film "${createdMovie.title}" berhasil di-publish & dikirim ke antrean Verifikasi Team Allpha!`);
  };

  // Simulate Instant Verification by Team Allpha
  const handleApproveByTeamAllpha = (movieId: string) => {
    setMoviesList((prev) =>
      prev.map((m) => {
        if (m.id === movieId) {
          return {
            ...m,
            verificationStatus: 'VERIFIED',
            totalViews: '1.2K',
            creatorMonthlyEarningsCredits: 1200,
          };
        }
        return m;
      })
    );

    if (reviewModalData.movie?.id === movieId) {
      setReviewModalData((prev) => ({
        ...prev,
        movie: prev.movie ? { ...prev.movie, verificationStatus: 'VERIFIED' } : null,
      }));
    }

    showToast('🎉 Selamat! Film AI Anda TELAH TERVERIFIKASI oleh Team Allpha dan kini tayang publik!');
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

      {/* Top Header & VIP Subscription Bar (Playful Neo-Brutalist Soft Pastel) */}
      <div className="rounded-3xl bg-rose-50 text-slate-950 p-5 sm:p-6 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-rose-300 border-2 border-slate-900 flex items-center justify-center shadow-[2px_2px_0px_#0f172a] shrink-0">
              <Film className="w-5 h-5 text-slate-950 stroke-[2.5px]" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-lg sm:text-xl font-black tracking-tight text-slate-950">
                  ALLPHA AI CINEMA
                </h1>
                <span className="text-[10px] font-black px-2.5 py-0.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950 uppercase tracking-wider shadow-2xs">
                  FILM & MINI-DRAMA AI
                </span>
              </div>
              <p className="text-xs font-semibold text-slate-700 mt-0.5">
                Wadah resmi Produser & Kreator Film AI. Tonton Drama Pendek (C-Drama, K-Drama, Sci-Fi) dengan bagi hasil 70% ke kreator.
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 self-start sm:self-auto flex-wrap">
            {isVipSubscribed ? (
              <span className="px-3.5 py-1.5 rounded-2xl bg-amber-200 text-amber-950 border-2 border-slate-900 font-black text-xs shadow-[2px_2px_0px_#0f172a] flex items-center gap-1.5">
                <Crown className="w-3.5 h-3.5 fill-amber-950" />
                <span>VIP PASS AKTIF ✓</span>
              </span>
            ) : (
              <button
                onClick={() => setIsSubscriptionModalOpen(true)}
                className="px-3.5 py-2 rounded-2xl bg-amber-300 hover:bg-amber-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
              >
                <Crown className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>Langganan VIP (150 Cr / Bln)</span>
              </button>
            )}

            <button
              onClick={() => setIsCreateStudioOpen(true)}
              className="px-4 py-2 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 text-xs font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
            >
              <PlusCircle className="w-3.5 h-3.5 stroke-[2.5px]" />
              <span>Create Film AI</span>
            </button>
          </div>
        </div>

        {/* Creator Profit Sharing Guarantee Strip */}
        <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-800">
          <div className="flex items-center gap-2 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-slate-900 shrink-0" />
            <span>
              <strong className="font-black text-slate-950">Model Monetisasi Kreator:</strong> 70% dari seluruh royalti langganan & pembelian episode otomatis ditransfer ke Produser.
            </span>
          </div>
          <span className="text-[11px] font-mono text-amber-900 font-black shrink-0 px-2.5 py-0.5 rounded-full bg-amber-100 border border-amber-300">
            Total Royalti: 74,650 Cr
          </span>
        </div>
      </div>

      {/* 1. CREATOR / PRODUCER CALLOUT BANNER (Neo-Brutalist Soft Pastel) */}
      <div className="relative rounded-3xl overflow-hidden p-5 sm:p-6 bg-purple-50 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] text-slate-950 space-y-4">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-200 border-2 border-slate-900 text-purple-950 text-[11px] font-black uppercase tracking-wider shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-purple-950 stroke-[2.5px]" />
              <span>Program Resmi Kreator & Produser Allpha</span>
            </div>

            <h2 className="text-xl sm:text-2xl font-black text-slate-950 tracking-tight leading-snug">
              Ingin menjadi Creator/Produser Film AI di Allpha?
            </h2>

            <p className="text-xs sm:text-sm font-semibold text-slate-700 leading-relaxed">
              Agar Karyamu ditonton orang banyak serta mendapatkan keuntungan dan pendapatan dari Film AI kamu, yuk registrasi dan upload film kamu! Klik tombol <strong>&quot;Create Film AI&quot;</strong> di bawah untuk mengunggah trailer, mengisi judul dan deskripsi, upload video per part film, lalu ajukan verifikasi resmi oleh Team Allpha.
            </p>

            {/* Benefit Highlights */}
            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
              <span className="px-3 py-1 rounded-full bg-emerald-100 border-2 border-slate-900 text-emerald-950 font-black flex items-center gap-1.5 shadow-2xs">
                <Coins className="w-3.5 h-3.5 text-emerald-800" />
                Bagi Hasil 70% Royalti Kreator
              </span>
              <span className="px-3 py-1 rounded-full bg-sky-100 border-2 border-slate-900 text-sky-950 font-black flex items-center gap-1.5 shadow-2xs">
                <Tv className="w-3.5 h-3.5 text-sky-800" />
                Tayang di Feed, Reels & 3D Cinema
              </span>
              <span className="px-3 py-1 rounded-full bg-purple-100 border-2 border-slate-900 text-purple-950 font-black flex items-center gap-1.5 shadow-2xs">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-800" />
                Verifikasi Resmi Team Allpha
              </span>
            </div>
          </div>

          {/* Action CTA Buttons */}
          <div className="relative z-10 flex flex-col sm:flex-row md:flex-col gap-2.5 shrink-0">
            <button
              onClick={() => setIsCreateStudioOpen(true)}
              className="px-6 py-3.5 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black text-sm border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer"
            >
              <PlusCircle className="w-4 h-4 stroke-[2.5px]" />
              <span>Create Film AI</span>
              <ChevronRight className="w-4 h-4 stroke-[3px]" />
            </button>

            <button
              onClick={() => setCinemaViewMode(cinemaViewMode === 'MY_STUDIO' ? 'CATALOG' : 'MY_STUDIO')}
              className="px-4 py-2.5 rounded-2xl bg-white hover:bg-slate-100 border-2 border-slate-900 text-slate-900 text-xs font-black shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Film className="w-3.5 h-3.5 text-rose-600 stroke-[2.5px]" />
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
                Kelola status verifikasi dari Team Allpha, tontonan penonton, dan royalti 70%.
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
                className="p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] hover:shadow-[5px_5px_0px_#0f172a] transition space-y-3"
              >
                <div className="flex gap-3">
                  <img
                    src={film.coverImage}
                    alt={film.title}
                    className="w-20 h-28 rounded-2xl object-cover shrink-0 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]"
                  />
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {film.verificationStatus === 'VERIFIED' ? (
                        <span className="px-2.5 py-0.5 rounded-xl bg-emerald-200 text-emerald-950 text-[10px] font-black border-2 border-slate-900 flex items-center gap-1 shadow-2xs">
                          <CheckCircle2 className="w-3 h-3 text-emerald-900 stroke-[2.5px]" />
                          Terverifikasi Team Allpha
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-xl bg-amber-200 text-amber-950 text-[10px] font-black border-2 border-slate-900 flex items-center gap-1 shadow-2xs">
                          <AlertCircle className="w-3 h-3 text-amber-900 stroke-[2.5px]" />
                          Dalam Verifikasi Team Allpha
                        </span>
                      )}
                    </div>

                    <h4 className="font-black text-sm text-slate-950 line-clamp-1">{film.title}</h4>
                    <p className="text-[11px] font-semibold text-slate-600 line-clamp-2">{film.synopsis}</p>
                    <p className="text-[10px] text-rose-700 font-black">{film.genreLabel} • {film.episodesCount} Part</p>
                  </div>
                </div>

                {/* Earnings & Actions */}
                <div className="pt-2.5 border-t-2 border-slate-100 flex items-center justify-between text-xs">
                  <div className="space-y-0.5">
                    <span className="text-[10px] font-bold text-slate-500">Total Royalti (70%):</span>
                    <p className="font-mono font-black text-amber-900">+{film.creatorMonthlyEarningsCredits} Cr</p>
                  </div>

                  <div className="flex items-center gap-2">
                    {film.verificationStatus === 'PENDING_VERIFICATION' && (
                      <button
                        onClick={() => handleApproveByTeamAllpha(film.id)}
                        className="px-3 py-1.5 rounded-xl bg-emerald-300 hover:bg-emerald-400 text-slate-950 text-xs font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                        title="Simulasi Verifikasi Cepat"
                      >
                        ⚡ Setujui Sekarang
                      </button>
                    )}
                    <button
                      onClick={() => handleOpenTheater(film, 1)}
                      className="px-3.5 py-1.5 rounded-xl bg-slate-950 hover:bg-slate-800 text-white text-xs font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
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
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="font-black text-sm text-slate-900 tracking-tight">
                Katalog Film Pendek & Serial Drama AI
              </h3>
              <span className="text-xs text-slate-800 font-mono font-bold px-2 py-0.5 rounded-full bg-slate-200 border border-slate-900">
                {filteredMovies.length} Judul
              </span>
            </div>

            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
              {[
                { id: 'ALL' as FilmGenre, label: 'Semua Kategori' },
                { id: 'C_DRAMA' as FilmGenre, label: '🇨🇳 C-Drama AI' },
                { id: 'K_DRAMA' as FilmGenre, label: '🇰🇷 K-Drama AI' },
                { id: 'SCIFI' as FilmGenre, label: '🚀 Sci-Fi Spatial 3D' },
                { id: 'THRILLER' as FilmGenre, label: '⚡ Thriller & Misteri' },
              ].map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveGenre(cat.id)}
                  className={`px-3.5 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition whitespace-nowrap shrink-0 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                    activeGenre === cat.id
                      ? 'bg-rose-400 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                      : 'bg-white text-slate-800 hover:bg-rose-50 shadow-[1.5px_1.5px_0px_#0f172a]'
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
                className="rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] hover:-translate-y-0.5 transition overflow-hidden flex flex-col justify-between group"
              >
                <div>
                  {/* Poster / Cover Image */}
                  <div className="relative aspect-[16/10] w-full overflow-hidden bg-slate-950 border-b-2 border-slate-900">
                    <img
                      src={movie.coverImage}
                      alt={movie.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent" />

                    {/* Category pill on top */}
                    <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                      <span className="px-2.5 py-0.5 rounded-full bg-white/95 border-2 border-slate-900 text-slate-950 text-[10px] font-black shadow-2xs">
                        {movie.genreLabel}
                      </span>
                    </div>

                    {/* Verification Badge */}
                    <div className="absolute top-2.5 right-2.5">
                      {movie.verificationStatus === 'VERIFIED' ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-200 border border-slate-900 text-emerald-950 text-[9.5px] font-black flex items-center gap-1 shadow-2xs">
                          <CheckCircle2 className="w-3 h-3 text-emerald-950" />
                          <span>Terverifikasi</span>
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-amber-200 border border-slate-900 text-amber-950 text-[9.5px] font-black flex items-center gap-1 shadow-2xs">
                          <Clock className="w-3 h-3 text-amber-950" />
                          <span>Ditinjau Team</span>
                        </span>
                      )}
                    </div>

                    {/* Rating and episodes count on bottom */}
                    <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-center justify-between text-xs text-white">
                      <span className="font-mono text-[11px] font-black text-amber-300 flex items-center gap-1">
                        <Star className="w-3 h-3 fill-amber-300" />
                        {movie.rating}
                      </span>
                      <span className="text-[10px] text-slate-200 font-mono font-bold">
                        {movie.episodesCount} Episode ({movie.totalViews})
                      </span>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="p-3.5 space-y-2">
                    <div>
                      <h4 className="font-black text-sm text-slate-900 line-clamp-1">
                        {movie.title}
                      </h4>
                      {movie.originalTitle && (
                        <p className="text-[10px] font-bold text-slate-500 line-clamp-1">
                          {movie.originalTitle}
                        </p>
                      )}
                    </div>

                    <p className="text-xs font-medium text-slate-700 line-clamp-2 leading-relaxed">
                      {movie.synopsis}
                    </p>

                    {/* Producer & AI Director */}
                    <div className="flex items-center justify-between text-xs pt-1.5 border-t-2 border-slate-900/10">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <img
                          src={movie.producerHuman.avatar}
                          alt={movie.producerHuman.name}
                          className="w-4 h-4 rounded-full object-cover border border-slate-900"
                        />
                        <span className="text-[11px] font-bold text-slate-800 truncate">
                          {movie.producerHuman.name}
                        </span>
                      </div>
                      <span className="text-[10px] text-sky-800 font-bold shrink-0">
                        & {movie.aiCoDirector.name}
                      </span>
                    </div>

                    {/* Profit Royalty Badge */}
                    <div className="p-2 rounded-xl bg-amber-100 border border-slate-900 flex items-center justify-between text-[10px] text-amber-950">
                      <span className="font-bold">Royalti Kreator (70%):</span>
                      <span className="font-mono font-black">
                        +{movie.creatorMonthlyEarningsCredits.toLocaleString('id-ID')} Cr/bln
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="p-3.5 pt-0 flex gap-2">
                  <button
                    onClick={() => handleOpenTheater(movie, 1)}
                    className="flex-1 py-2 px-3 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Play className="w-3.5 h-3.5 fill-slate-950" />
                    <span>Nonton</span>
                  </button>
                  <button
                    onClick={() => {
                      if (onPostTrailerToFeed) {
                        onPostTrailerToFeed(movie);
                        showToast(`Trailer "${movie.title}" siap dibagikan ke Feed & Reels!`);
                      }
                    }}
                    className="p-2 rounded-2xl bg-white hover:bg-slate-100 border-2 border-slate-900 text-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                    title="Bagikan ke Feed & Reels"
                  >
                    <Share2 className="w-3.5 h-3.5 stroke-[2.2px]" />
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
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="w-full max-w-2xl rounded-3xl bg-white text-slate-950 border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 sm:p-6 space-y-5 my-auto animate-in fade-in zoom-in-95 duration-200 text-xs">
            {/* Header */}
            <div className="flex items-start justify-between pb-3 border-b-2 border-slate-100">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-2xl bg-rose-300 text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                  <Film className="w-5 h-5 stroke-[2.5px]" />
                </div>
                <div>
                  <span className="text-[10px] font-black text-rose-900 uppercase tracking-wider">
                    Studio Registrasi & Produksi Film AI Allpha
                  </span>
                  <h3 className="text-base sm:text-lg font-black text-slate-950 mt-0.5">
                    Create Film AI & Daftarkan Karyamu
                  </h3>
                  <p className="text-[11px] text-slate-600 font-semibold">
                    Upload trailer, kelola part video, dan kirim untuk verifikasi resmi Team Allpha.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsCreateStudioOpen(false)}
                className="w-8 h-8 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 text-slate-900 flex items-center justify-center transition cursor-pointer"
              >
                <X className="w-4 h-4 stroke-[2.5px]" />
              </button>
            </div>

            {/* Stepper overview */}
            <div className="grid grid-cols-4 gap-1 p-2 rounded-2xl bg-rose-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-[10px] text-center font-black text-slate-800">
              <span className="text-rose-900">1. Info Judul</span>
              <span className="text-rose-900">2. Upload Trailer</span>
              <span className="text-rose-900">3. Video per Part</span>
              <span className="text-emerald-800">4. Verifikasi Team</span>
            </div>

            {/* Section 1: Form Judul & Kategori */}
            <div className="space-y-3 p-4 rounded-2xl bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <h4 className="font-black text-xs text-rose-900 flex items-center gap-1.5 uppercase">
                <FileText className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>1. Form Judul & Informasi Film AI</span>
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-black text-slate-900">Judul Utama Film AI:</label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="Contoh: The Secret Cyborg Prince (K-Drama AI)..."
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-bold outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-black text-slate-900">Judul Asli / Hanzi / Tagline:</label>
                  <input
                    type="text"
                    value={newOriginalTitle}
                    onChange={(e) => setNewOriginalTitle(e.target.value)}
                    placeholder="Contoh: 总裁的秘密仿生新娘 / Neo Shanghai 2099..."
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-bold outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-black text-slate-900">Kategori / Genre Film:</label>
                  <select
                    value={newGenre}
                    onChange={(e) => setNewGenre(e.target.value as FilmGenre)}
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-black outline-none"
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
                  <label className="font-black text-slate-900">Durasi Rata-rata per Part:</label>
                  <input
                    type="text"
                    value={newDurationPerPart}
                    onChange={(e) => setNewDurationPerPart(e.target.value)}
                    placeholder="Contoh: 2–3 Menit / Part..."
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-bold outline-none"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-black text-slate-900">Deskripsi Lengkap & Sinopsis Alur Cerita:</label>
                <textarea
                  rows={3}
                  value={newSynopsis}
                  onChange={(e) => setNewSynopsis(e.target.value)}
                  placeholder="Tuliskan hook cerita, karakter utama, alur konflik, dan pesan moral film AI..."
                  className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-semibold outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700">Produser (Human):</label>
                  <input
                    type="text"
                    value={newProducerName}
                    onChange={(e) => setNewProducerName(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-white border-2 border-slate-900 text-slate-950 font-bold"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700">Co-Director (AI Agent):</label>
                  <input
                    type="text"
                    value={newAiCoDirector}
                    onChange={(e) => setNewAiCoDirector(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-white border-2 border-slate-900 text-slate-950 font-bold"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700">AI Tech Stack Digunakan:</label>
                  <input
                    type="text"
                    value={newTechStack}
                    onChange={(e) => setNewTechStack(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-white border-2 border-slate-900 text-slate-950 font-bold"
                  />
                </div>
              </div>
            </div>

            {/* Section 2: Upload Trailer & Cover Poster */}
            <div className="space-y-3 p-4 rounded-2xl bg-rose-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <h4 className="font-black text-xs text-rose-900 flex items-center gap-1.5 uppercase">
                <Video className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>2. Upload Trailer Film AI & Poster</span>
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Trailer Upload Box */}
                <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 flex flex-col justify-between space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-black text-slate-950 flex items-center gap-1.5">
                      <Upload className="w-3.5 h-3.5 text-rose-600 stroke-[2.5px]" />
                      File Trailer Video (MP4 / 4K)
                    </span>
                    <span className="text-[10px] text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-lg font-mono font-black border border-slate-900">Terunggah ✓</span>
                  </div>
                  <p className="text-[11px] text-slate-700 font-mono font-bold truncate">{trailerFileName}</p>
                  
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <div className="flex items-center gap-1 text-[10px] text-slate-600 font-bold">
                      <Clock className="w-3 h-3" />
                      <span>Durasi: {trailerDuration}</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => setIsPreviewingTrailer(!isPreviewingTrailer)}
                      className="px-3 py-1 rounded-xl bg-rose-300 hover:bg-rose-400 text-slate-950 text-[10px] font-black border-2 border-slate-900 shadow-2xs flex items-center gap-1 cursor-pointer"
                    >
                      <Play className="w-2.5 h-2.5 fill-slate-950" />
                      <span>{isPreviewingTrailer ? 'Stop Preview' : 'Preview Trailer'}</span>
                    </button>
                  </div>

                  {isPreviewingTrailer && (
                    <div className="p-2 rounded-xl bg-slate-950 text-center space-y-1 animate-in fade-in border-2 border-slate-900">
                      <div className="w-full h-20 rounded-lg bg-slate-800 flex items-center justify-center relative overflow-hidden">
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
                <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 space-y-2">
                  <span className="font-black text-slate-900 block">Pilih Poster Cover Film:</span>
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
                        className={`relative rounded-xl overflow-hidden aspect-[3/4] border-2 transition cursor-pointer ${
                          selectedPosterPreset === img
                            ? 'border-slate-900 scale-105 shadow-[2px_2px_0px_#0f172a] ring-2 ring-rose-400'
                            : 'border-slate-300 opacity-60 hover:opacity-100'
                        }`}
                      >
                        <img src={img} alt="Poster" className="w-full h-full object-cover" />
                        {selectedPosterPreset === img && (
                          <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-rose-500 text-white flex items-center justify-center text-[9px] font-black border border-slate-900">
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
            <div className="space-y-3 p-4 rounded-2xl bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-black text-xs text-purple-950 flex items-center gap-1.5 uppercase">
                    <ListChecks className="w-3.5 h-3.5 stroke-[2.5px]" />
                    <span>3. Upload Video per Part Film ({videoParts.length} Part Terdaftar)</span>
                  </h4>
                  <p className="text-[10px] text-slate-600 font-semibold">
                    Serial drama pendek di Allpha diunggah per part/episode (Part 1, Part 2, dst).
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleAddVideoPart}
                  className="px-3 py-1.5 rounded-xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-[11px] border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1 transition cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 stroke-[3px]" />
                  <span>Tambah Part</span>
                </button>
              </div>

              {/* Dynamic Parts List */}
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {videoParts.map((part) => (
                  <div
                    key={part.id}
                    className="p-3 rounded-2xl bg-white border-2 border-slate-900 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 shadow-2xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <span className="w-7 h-7 rounded-xl bg-rose-200 border-2 border-slate-900 text-slate-950 font-mono font-black flex items-center justify-center shrink-0">
                        {part.partNumber}
                      </span>
                      <div className="flex-1 min-w-0">
                        <input
                          type="text"
                          value={part.title}
                          onChange={(e) => handleUpdatePart(part.id, { title: e.target.value })}
                          className="w-full bg-transparent font-black text-slate-950 outline-none text-xs border-b border-transparent focus:border-rose-400"
                        />
                        <div className="flex items-center gap-2 text-[10px] text-slate-500 font-bold mt-0.5">
                          <span>{part.fileName}</span>
                          <span>•</span>
                          <span>{part.fileSize || '50 MB'}</span>
                          <span>•</span>
                          <span className="text-emerald-700 font-mono">Durasi: {part.duration}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                      <button
                        type="button"
                        onClick={() => handleUpdatePart(part.id, { isFreePreview: !part.isFreePreview })}
                        className={`px-2.5 py-1 rounded-xl text-[10px] font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                          part.isFreePreview
                            ? 'bg-emerald-200 text-emerald-950 shadow-2xs'
                            : 'bg-amber-200 text-amber-950 shadow-2xs'
                        }`}
                      >
                        {part.isFreePreview ? 'Gratis (Preview)' : 'Khusus VIP'}
                      </button>

                      {videoParts.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveVideoPart(part.id)}
                          className="p-1 rounded-lg text-slate-400 hover:text-rose-600 transition cursor-pointer"
                          title="Hapus Part"
                        >
                          <Trash2 className="w-3.5 h-3.5 stroke-[2.5px]" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 4: Revenue & Verification Notice */}
            <div className="p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-[11px] text-slate-800 space-y-1.5 font-medium">
              <div className="flex items-center gap-2 font-black text-slate-950">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 stroke-[2.5px]" />
                <span>Publish & Verifikasi oleh Team Allpha</span>
              </div>
              <p>
                Setelah menekan tombol di bawah, film AI Anda akan masuk ke antrean verifikasi Team Allpha. Setelah terverifikasi, film akan otomatis tampil di katalog dan dapat ditonton oleh seluruh pengguna Allpha, serta mendatangkan <strong>70% royalti AI Credits</strong> langsung ke dompet kreator Anda.
              </p>
            </div>

            {/* Bottom Actions */}
            <div className="flex items-center gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setIsCreateStudioOpen(false)}
                className="flex-1 py-3 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Simpan Sebagai Draf
              </button>

              <button
                type="button"
                onClick={handlePublishForVerification}
                className="flex-1 py-3 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center gap-2 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
              >
                <span>Publish & Kirim Verifikasi ke Team Allpha</span>
                <ChevronRight className="w-4 h-4 stroke-[3px]" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. REVIEW / VERIFICATION STATUS MODAL (Simulasi Verifikasi Team Allpha)   */}
      {/* ========================================================================= */}
      {reviewModalData.isOpen && reviewModalData.movie && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-white text-slate-950 border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs">
            <div className="text-center space-y-2 pt-2">
              <div className="w-14 h-14 mx-auto rounded-2xl bg-rose-200 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center">
                {reviewModalData.movie.verificationStatus === 'VERIFIED' ? (
                  <Check className="w-8 h-8 text-emerald-800 stroke-[3px]" />
                ) : (
                  <Clock className="w-7 h-7 text-amber-900 stroke-[2.5px]" />
                )}
              </div>

              <div>
                <span className="text-[10px] font-black text-rose-800 uppercase tracking-wider">
                  Status Pengajuan Film AI
                </span>
                <h3 className="text-base font-black text-slate-950 mt-0.5">
                  &quot;{reviewModalData.movie.title}&quot;
                </h3>
              </div>
            </div>

            {/* Status Card */}
            <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-600 font-bold">Status Kurasi:</span>
                {reviewModalData.movie.verificationStatus === 'VERIFIED' ? (
                  <span className="px-2.5 py-0.5 rounded-xl bg-emerald-200 text-emerald-950 font-black border-2 border-slate-900 flex items-center gap-1 shadow-2xs">
                    <CheckCircle2 className="w-3 h-3 text-emerald-900 stroke-[2.5px]" />
                    Terverifikasi Team Allpha
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-xl bg-amber-200 text-amber-950 font-black border-2 border-slate-900 flex items-center gap-1 shadow-2xs animate-pulse">
                    <Clock className="w-3 h-3 text-amber-900 stroke-[2.5px]" />
                    Sedang Diverifikasi Team Allpha
                  </span>
                )}
              </div>

              <div className="space-y-1.5 pt-2 border-t-2 border-slate-900/10 text-[11px] text-slate-700 font-semibold">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 stroke-[2.5px]" />
                  <span>Trailer Video 4K Terunggah & Valid</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 stroke-[2.5px]" />
                  <span>{reviewModalData.movie.episodesCount} Video Part Siap Diputar</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 stroke-[2.5px]" />
                  <span>Sistem Royalti 70% Terhubung ke Dompet Anda</span>
                </div>
              </div>
            </div>

            {/* Explanation text */}
            <p className="text-[11px] text-slate-700 font-semibold text-center leading-relaxed">
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
                  className="w-full py-3 rounded-2xl bg-emerald-300 hover:bg-emerald-400 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-2 transition cursor-pointer"
                >
                  <ShieldCheck className="w-4 h-4 stroke-[2.5px]" />
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
                    className="py-2.5 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Play className="w-3.5 h-3.5 fill-slate-950" />
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
                    className="py-2.5 rounded-2xl bg-white hover:bg-slate-100 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Share2 className="w-3.5 h-3.5 stroke-[2.5px]" />
                    <span>Share Trailer</span>
                  </button>
                </div>
              )}

              <button
                type="button"
                onClick={() => setReviewModalData({ isOpen: false, movie: null })}
                className="w-full py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
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
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-white text-slate-950 border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs">
            <div className="flex items-center justify-between pb-3 border-b-2 border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-amber-300 border-2 border-slate-900 text-slate-950 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                  <Crown className="w-5 h-5 stroke-[2.5px]" />
                </div>
                <div>
                  <span className="text-[10px] font-black uppercase text-amber-900 tracking-wider">PREMIUM ACCESS</span>
                  <h3 className="font-black text-sm text-slate-950">Langganan VIP Allpha Cinema</h3>
                </div>
              </div>
              <button
                onClick={() => setIsSubscriptionModalOpen(false)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center text-slate-900 cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            {/* Price Tag */}
            <div className="p-4 rounded-2xl bg-rose-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-center space-y-1">
              <span className="text-[10px] uppercase font-black text-rose-900 tracking-wider">
                Paket Berlangganan Bulanan
              </span>
              <p className="text-2xl font-mono font-black text-slate-950">
                150 AI Credits <span className="text-xs text-slate-700 font-bold">/ Rp 99.000 / bln</span>
              </p>
              <p className="text-[11px] text-slate-700 font-semibold">
                Saldo Anda saat ini: <strong className="font-mono text-amber-900">{userCredits == null ? 'Belum tersedia' : `${userCredits} Credits`}</strong>
              </p>
            </div>

            {/* Benefit Checkpoints */}
            <div className="space-y-2 text-slate-800 text-xs font-semibold">
              {[
                'Buka ribuan episode Drama Pendek AI (C-Drama & K-Drama) tanpa iklan',
                'Resolusi 4K Ultra HD 60 FPS dengan audio spatial 3D',
                'Akses premiere episode baru 24 jam lebih awal',
                '70% biaya langganan disalurkan langsung sebagai royalti untuk Produser Film AI',
                'Bisa diakses dari Feed, Reels, dan 3D Universe Cinema District',
              ].map((benefit, i) => (
                <div key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 stroke-[2.5px] shrink-0 mt-0.5" />
                  <span className="leading-snug">{benefit}</span>
                </div>
              ))}
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsSubscriptionModalOpen(false)}
                className="flex-1 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Nanti Saja
              </button>
              <button
                type="button"
                onClick={handleConfirmVipSubscription}
                className="flex-1 py-2.5 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
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
