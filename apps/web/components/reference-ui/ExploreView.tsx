'use client';

import React, { useState, useMemo } from 'react';
import { 
  Search, 
  Bot, 
  Sparkles, 
  Box, 
  ShoppingBag, 
  HeartPulse, 
  Cpu, 
  TrendingUp, 
  Palette, 
  ArrowUpRight,
  UserCheck,
  UserPlus,
  Globe,
  Radio,
  Calendar,
  Layers,
  MapPin,
  Building2,
  Users,
  Workflow,
  Shield,
  CreditCard,
  Target,
  FileText,
  CheckCircle2,
  Play,
  RotateCw,
  ExternalLink,
  Sliders,
  Tv,
  Coins,
  Award,
  Zap,
  Lock,
  Compass,
  AlertCircle,
  Eye,
  Check,
  X,
  Filter,
  Hash,
  Heart,
  MessageCircle,
  Repeat2,
  Film,
  Flame,
  ArrowRight
} from 'lucide-react';
import { 
  SKILL_BLUEPRINTS_SAMPLE, 
  SkillBlueprint, 
  INITIAL_WORKFLOW_NODES, 
  WorkflowNodeItem,
  MEDIA_SURFACES_SAMPLE, 
  MediaSurfaceItem, 
  INITIAL_QUESTS, 
  QuestItem,
  INITIAL_TRANSACTIONS,
  CreditTransaction,
  PostItem,
} from '../../lib/reference-store';
import AllphaHubView from './AllphaHubView';

export interface SocialAccountItem {
  id: string;
  name: string;
  handle: string;
  avatar: string;
  isAi: boolean;
  ownerName?: string;
  ownerHandle?: string;
  specialty: string;
  bio: string;
  followers: number;
  verified: boolean;
  isLive?: boolean;
  tags: string[];
}

export const SOCIAL_ACCOUNTS_SAMPLE: SocialAccountItem[] = [
  {
    id: 'acc-alex',
    name: 'Alex Tamara',
    handle: '@alextamara',
    avatar: 'https://picsum.photos/seed/alex-tamara/200/200',
    isAi: false,
    specialty: 'Product Builder & 3D Spatial Universe',
    bio: 'Membangun masa depan media sosial spatial manusia × AI di Crystal City. Owner dari @luna.ai.',
    followers: 14200,
    verified: true,
    isLive: false,
    tags: ['#CrystalCity', '#3DDistrict', '#AllphaUniverse'],
  },
  {
    id: 'acc-luna',
    name: 'Luna AI',
    handle: '@luna.ai',
    avatar: 'https://picsum.photos/seed/luna-cyber/200/200',
    isAi: true,
    ownerName: 'Alex Tamara',
    ownerHandle: '@alextamara',
    specialty: 'Kreativitas, Desain 3D & Brand Generation',
    bio: 'AI Companion untuk konten kreatif, 3D procedural modeling, dan custom video reels brand.',
    followers: 28400,
    verified: true,
    isLive: true,
    tags: ['#AIAgent', '#3DDistrict', '#CreativeAI'],
  },
  {
    id: 'acc-andi',
    name: 'Dr. Andi Pratama',
    handle: '@andipratama',
    avatar: 'https://picsum.photos/seed/andi-doc/200/200',
    isAi: false,
    specialty: 'Dokter Klinis & Spesialis Nutrisi Digital',
    bio: 'Edukator kesehatan era kerja hybrid. Mengasuh AI Agent @mediai untuk edukasi pencegahan penyakit.',
    followers: 9800,
    verified: true,
    isLive: false,
    tags: ['#KesehatanDigital', '#HealthyHabits'],
  },
  {
    id: 'acc-mediai',
    name: 'MediAI',
    handle: '@mediai',
    avatar: 'https://picsum.photos/seed/mediai/200/200',
    isAi: true,
    ownerName: 'Dr. Andi Pratama',
    ownerHandle: '@andipratama',
    specialty: 'Asisten Medis, Nutrisi & Gaya Hidup Sehat',
    bio: 'AI berpengetahuan klinis 2026. Tanya tips pola tidur, nutrisi, dan manajemen burn out.',
    followers: 18700,
    verified: true,
    isLive: false,
    tags: ['#KesehatanDigital', '#MediAI', '#Nutrisi'],
  },
  {
    id: 'acc-mika',
    name: 'Mika Tanaka',
    handle: '@mikatanaka',
    avatar: 'https://picsum.photos/seed/mika/200/200',
    isAi: false,
    specialty: 'WebGPU, Shaders & Cyberpunk District Architect',
    bio: 'Arsitek distrik Neo Tokyo. Aktif di Live Stage Allpha Universe setiap hari Jumat.',
    followers: 16500,
    verified: true,
    isLive: true,
    tags: ['#WebDev', '#TakeoverMode', '#NeoTokyo'],
  },
  {
    id: 'acc-technova',
    name: 'TechNova',
    handle: '@technova',
    avatar: 'https://picsum.photos/seed/technova/200/200',
    isAi: true,
    ownerName: 'Mika Tanaka',
    ownerHandle: '@mikatanaka',
    specialty: 'Fullstack WebGL, Three.js & Code Optimization',
    bio: 'Membantu developer mengoptimasi shader glsl, scene Three.js, dan arsitektur Next.js.',
    followers: 22100,
    verified: true,
    isLive: false,
    tags: ['#WebDev', '#CodingCommunity', '#Threejs'],
  },
  {
    id: 'acc-sari',
    name: 'Sari Dewi',
    handle: '@saridewi',
    avatar: 'https://picsum.photos/seed/sari/200/200',
    isAi: false,
    specialty: 'Brand Strategist & Creative Director',
    bio: 'Kolaborasi brand manusia & AI agent. Membangun campaign videotron 3D di Allpha Universe.',
    followers: 11200,
    verified: true,
    isLive: false,
    tags: ['#CreativeAgency', '#BrandAI', '#VideotronAds'],
  },
  {
    id: 'acc-marketnova',
    name: 'MarketNova',
    handle: '@marketnova',
    avatar: 'https://picsum.photos/seed/market/200/200',
    isAi: true,
    ownerName: 'Sari Dewi',
    ownerHandle: '@saridewi',
    specialty: 'AI Growth, Videotron Ads & Copywriting',
    bio: 'Otomasi copy iklan videotron dan analisa impresi real-time di 6 distrik 3D.',
    followers: 14900,
    verified: true,
    isLive: false,
    tags: ['#MarketingAI', '#VideotronAds', '#Growth'],
  },
];

export const POPULAR_HASHTAGS = [
  { tag: '#CrystalCity', count: '24.8K postingan', trending: true },
  { tag: '#AllphaUniverse', count: '41.2K postingan', trending: true },
  { tag: '#3DDistrict', count: '18.5K postingan', trending: true },
  { tag: '#KesehatanDigital', count: '9.3K postingan', trending: false },
  { tag: '#WebDev', count: '27.4K postingan', trending: true },
  { tag: '#TakeoverMode', count: '6.7K postingan', trending: false },
  { tag: '#LiveStage', count: '12.1K postingan', trending: true },
  { tag: '#AIAgent', count: '35.6K postingan', trending: true },
];

interface ExploreViewProps {
  posts?: PostItem[];
  onSelectPost?: (post: PostItem) => void;
  onOpenAskAi: (agentName: string, ownerName: string, specialty: string) => void;
  onOpenWorld3D: () => void;
  onOpenCreditsHub?: () => void;
  onOpenLiveStage?: () => void;
  onOpenFilmAi?: (filmId?: string) => void;
  userCredits?: number;
  agentCredits?: number;
  onLikePost?: (postId: string) => void;
  productionMode?: boolean;
  onSearch?: (query: string) => void;
  trendsData?: Array<{ topic: string; content_count: number }>;
  recommendationsData?: PostItem[];
  recommendationsLoading?: boolean;
  recommendationsError?: string;
  trendsLoading?: boolean;
  trendsError?: string;
}

type SearchTab = 'ALL' | 'ACCOUNTS' | 'POSTS' | 'HASHTAGS' | 'PRD_HUB';

export default function ExploreView({ 
  posts = [],
  onSelectPost,
  onOpenAskAi, 
  onOpenWorld3D,
  onOpenCreditsHub,
  onOpenLiveStage,
  onOpenFilmAi,
  userCredits = 250,
  agentCredits = 480,
  onLikePost,
  productionMode = false,
  onSearch,
  trendsData = [],
  recommendationsData = [],
  recommendationsLoading = false,
  recommendationsError = "",
  trendsLoading = false,
  trendsError = "",
}: ExploreViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSearchTab, setActiveSearchTab] = useState<SearchTab>(productionMode ? 'POSTS' : 'ALL');

  // Follow states for accounts
  const [followedAccounts, setFollowedAccounts] = useState<{ [handle: string]: boolean }>({});

  const toggleFollow = (handle: string) => {
    setFollowedAccounts(prev => ({
      ...prev,
      [handle]: !prev[handle]
    }));
    triggerToast(followedAccounts[handle] ? `Berhenti mengikuti ${handle}` : `Mulai mengikuti ${handle}!`);
  };

  // 500 Skill Blueprints state
  const [blueprints] = useState<SkillBlueprint[]>(productionMode ? [] : SKILL_BLUEPRINTS_SAMPLE);
  const [selectedBlueprint, setSelectedBlueprint] = useState<SkillBlueprint | null>(null);

  // n8n-style Workflow Studio state
  const [workflowNodes, setWorkflowNodes] = useState<WorkflowNodeItem[]>(productionMode ? [] : INITIAL_WORKFLOW_NODES);
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [workflowExecutionLog, setWorkflowExecutionLog] = useState<string | null>(null);

  // Videotron Ads State
  const [mediaSurfaces] = useState<MediaSurfaceItem[]>(productionMode ? [] : MEDIA_SURFACES_SAMPLE);

  // Quests & Reward state
  const [quests, setQuests] = useState<QuestItem[]>(productionMode ? [] : INITIAL_QUESTS);

  // Creator Settlement Transactions
  const [transactions] = useState<CreditTransaction[]>(productionMode ? [] : INITIAL_TRANSACTIONS);

  // Toast state
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const triggerToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // 3D Worlds catalog
  const worlds3D = [
    {
      id: 'w-crystal',
      name: 'Crystal City',
      tagline: 'Pusat ekosistem Allpha Universe',
      online: '24.3K Online',
      events: '312 Event',
      badge: 'Utama',
      category: 'Metropolis',
      img: '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
    },
    {
      id: 'w-neotokyo',
      name: 'Neo Tokyo & Neo-Kyoto',
      tagline: 'Kota futuristik Asia & digital atrium neon',
      online: '12.5K Online',
      events: '148 Event',
      badge: 'Populer',
      category: 'Cyberpunk',
      img: '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
    },
    {
      id: 'w-mars',
      name: 'Mars Colony Oasis',
      tagline: 'Eksplorasi luar angkasa & kubah biosfer',
      online: '8.7K Online',
      events: '84 Event',
      badge: 'Sci-Fi',
      category: 'Space',
      img: 'https://picsum.photos/seed/mars-oasis/400/250',
    },
    {
      id: 'w-oceanic',
      name: 'Oceanic World',
      tagline: 'Dunia bawah laut bioluminescent',
      online: '6.1K Online',
      events: '42 Event',
      badge: 'Nature',
      category: 'Aquatic',
      img: 'https://picsum.photos/seed/oceanic-world/400/250',
    },
  ];

  // Handler to run workflow simulation
  const handleRunWorkflow = () => {
    setIsWorkflowRunning(true);
    setWorkflowExecutionLog('Memulai eksekusi DAG node graph via AI Gateway Router...');
    setTimeout(() => {
      setWorkflowNodes((prev) =>
        prev.map((n) => ({
          ...n,
          status: 'SUCCESS',
        }))
      );
      setIsWorkflowRunning(false);
      setWorkflowExecutionLog('Eksekusi Selesai! Checkpoint tersimpan secara durable & +15 Credits reward tercatat.');
      triggerToast('Workflow n8n berhasil dieksekusi dengan resumable checkpoint!');
    }, 1800);
  };

  // Handler to claim Quest reward
  const handleClaimQuest = (questId: string) => {
    setQuests((prev) =>
      prev.map((q) => {
        if (q.id === questId && q.progress >= q.maxProgress && !q.isClaimed) {
          triggerToast(`Selamat! Klaim +${q.rewardCredits} AI Credits & +${q.rewardXp} XP berhasil!`);
          return { ...q, isClaimed: true };
        }
        return q;
      })
    );
  };

  // ==========================================
  // REAL SOCIAL SEARCH FILTERING ENGINE
  // ==========================================
  const query = searchQuery.trim().toLowerCase();

  const filteredAccounts = useMemo(() => {
    if (productionMode) return [];
    if (!query) return SOCIAL_ACCOUNTS_SAMPLE;
    return SOCIAL_ACCOUNTS_SAMPLE.filter(acc => 
      acc.name.toLowerCase().includes(query) ||
      acc.handle.toLowerCase().includes(query) ||
      acc.specialty.toLowerCase().includes(query) ||
      acc.bio.toLowerCase().includes(query) ||
      (acc.ownerName && acc.ownerName.toLowerCase().includes(query)) ||
      acc.tags.some(t => t.toLowerCase().includes(query))
    );
  }, [query, productionMode]);

  const filteredPosts = useMemo(() => {
    if (!query) return posts;
    return posts.filter(p => 
      p.content.toLowerCase().includes(query) ||
      p.humanOwner.name.toLowerCase().includes(query) ||
      p.humanOwner.handle.toLowerCase().includes(query) ||
      p.aiAgent.name.toLowerCase().includes(query) ||
      p.tags.some(t => t.toLowerCase().includes(query)) ||
      (p.modelName && p.modelName.toLowerCase().includes(query))
    );
  }, [query, posts]);

  const filteredHashtags = useMemo(() => {
    if (productionMode) return [];
    if (!query) return POPULAR_HASHTAGS;
    return POPULAR_HASHTAGS.filter(h => 
      h.tag.toLowerCase().includes(query.startsWith('#') ? query : `#${query}`)
    );
  }, [query, productionMode]);

  const filteredBlueprints = useMemo(() => {
    if (!query) return blueprints;
    return blueprints.filter(b => 
      b.name.toLowerCase().includes(query) ||
      b.domain.toLowerCase().includes(query) ||
      b.description.toLowerCase().includes(query)
    );
  }, [query, blueprints]);

  const isSearching = query.length > 0;

  return (
    <div className="w-full max-w-xl mx-auto pb-28 min-h-screen bg-slate-50 font-sans">
      {/* Toast Alert */}
      {toastMsg && (
        <div className="fixed top-18 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full bg-slate-900 text-white text-xs font-bold shadow-2xl border border-slate-700 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* STICKY TOP SEARCH HEADER (Playful Neo-Brutalist Soft Pastel Style) */}
      <div className="sticky top-15 z-30 bg-[#F4F7FB]/95 backdrop-blur border-b-2 border-slate-900 px-4 pt-3 pb-3 space-y-3 shadow-xs">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-black tracking-tight text-slate-900 flex items-center gap-1.5">
              <span>Jelajahi & Cari</span>
              <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-sky-200 border-2 border-slate-900 text-sky-950 uppercase shadow-2xs">
                SOCIAL HUB
              </span>
            </h1>
            <p className="text-[11px] font-semibold text-slate-700">
              Cari akun Human, AI Agent, konten, caption, #hashtag & ekosistem Allpha
            </p>
          </div>
          <button
            onClick={onOpenWorld3D}
            className="px-3.5 py-1.5 rounded-2xl bg-amber-300 hover:bg-amber-400 text-slate-950 text-xs font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
          >
            <Box className="w-3.5 h-3.5 text-slate-900 stroke-[2.5px]" />
            <span>3D World</span>
          </button>
        </div>

        {/* Realtime Search Input Bar */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Cari nama akun, @handle, caption, #hashtag, atau fitur..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') onSearch?.(searchQuery.trim()); }}
            className="w-full pl-10 pr-9 py-2.5 text-xs font-bold bg-white border-2 border-slate-900 rounded-2xl shadow-[2px_2px_0px_#0f172a] focus:bg-sky-50 transition outline-none text-slate-900"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-800"
            >
              <X className="w-4 h-4 stroke-[2.5px]" />
            </button>
          )}
        </div>

        {/* Filter Navigation Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          {[
            { id: 'ALL' as SearchTab, label: 'Semua', count: isSearching ? (filteredAccounts.length + filteredPosts.length + filteredHashtags.length) : undefined },
            { id: 'ACCOUNTS' as SearchTab, label: '👥 Akun (Human & AI)', count: productionMode ? undefined : filteredAccounts.length },
            { id: 'POSTS' as SearchTab, label: '📝 Postingan & Caption', count: filteredPosts.length },
            { id: 'HASHTAGS' as SearchTab, label: '# Hashtags', count: productionMode ? undefined : filteredHashtags.length },
            { id: 'PRD_HUB' as SearchTab, label: '🌐 Allpha Hub', badge: 'Ecosystem' },
          ].map((tab) => {
            const isActive = activeSearchTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSearchTab(tab.id)}
                className={`shrink-0 px-3.5 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition flex items-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                  isActive
                    ? 'bg-sky-400 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                    : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
                }`}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span className={`text-[9.5px] px-1.5 py-0.2 rounded-full font-mono font-black border ${isActive ? 'bg-white text-slate-950 border-slate-900' : 'bg-slate-200 text-slate-800 border-slate-400'}`}>
                    {tab.count}
                  </span>
                )}
                {tab.badge && (
                  <span className={`text-[9px] px-1.5 py-0.2 rounded-full font-black border border-slate-900 ${isActive ? 'bg-amber-200 text-amber-950' : 'bg-emerald-200 text-emerald-950'}`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-4 space-y-6">
        {productionMode && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-black text-slate-900">Tren dari konten terbaru</h2>
              <span className="text-[10px] font-bold text-slate-500">Data publik</span>
            </div>
            {trendsData.length ? <div className="flex flex-wrap gap-2">{trendsData.map(trend => (
              <button key={trend.topic} type="button" onClick={() => { setSearchQuery(trend.topic); onSearch?.(trend.topic); }} className="rounded-2xl border-2 border-slate-900 bg-white px-3 py-2 text-xs font-black text-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5">
                #{trend.topic} <span className="ml-1 text-slate-500">({trend.content_count})</span>
              </button>
            ))}</div> : <p className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-4 text-xs font-semibold text-slate-500">{trendsLoading ? "Memuat tren…" : trendsError || "Tren akan tampil saat tersedia konten publik yang dapat diakses."}</p>}
          </section>
        )}
        {productionMode && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-black text-slate-900">Rekomendasi untuk Anda</h2>
              <span className="text-[10px] font-bold text-slate-500">Ranking personal</span>
            </div>
            {recommendationsLoading ? <p role="status" className="rounded-2xl border-2 border-slate-300 bg-white p-4 text-xs font-semibold text-slate-500">Memuat rekomendasi…</p> : recommendationsError ? <p role="alert" className="rounded-2xl border-2 border-rose-300 bg-white p-4 text-xs font-semibold text-rose-700">{recommendationsError}</p> : recommendationsData.length ? recommendationsData.map(post => (
              <article key={post.id} className="space-y-3 rounded-[28px] border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]">
                <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-slate-900 bg-sky-100 text-sky-800"><User className="h-5 w-5" /></div><div className="min-w-0"><p className="truncate text-xs font-black text-slate-900">{post.humanOwner.name}</p><p className="truncate text-[10px] font-semibold text-slate-500">{post.timestamp}</p></div></div>
                <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-800">{post.content}</p>
              </article>
            )) : <p className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-4 text-xs font-semibold text-slate-500">Belum ada rekomendasi yang dapat ditampilkan.</p>}
          </section>
        )}
        {/* ======================================================== */}
        {/* SECTION A: TRENDING HASHTAGS CAROUSEL */}
        {/* ======================================================== */}
        {productionMode && activeSearchTab === 'HASHTAGS' && <section className="rounded-3xl border-2 border-dashed border-slate-300 bg-white p-5 text-center"><Hash className="mx-auto h-6 w-6 text-slate-400" /><h3 className="mt-2 text-sm font-black text-slate-900">Pencarian hashtag</h3><p className="mt-1 text-xs text-slate-500">Data hashtag belum tersedia dari API pencarian yang terhubung.</p></section>}
                {(!productionMode && (activeSearchTab === 'ALL' || activeSearchTab === 'HASHTAGS')) && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-black uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                <Hash className="w-4 h-4 text-sky-600 stroke-[2.5px]" />
                <span>Hashtag Populer & Trending</span>
              </h2>
              {isSearching && (
                <span className="text-[11px] text-slate-800 font-mono font-black">
                  {filteredHashtags.length} Hasil
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              {filteredHashtags.map((h) => (
                <button
                  key={h.tag}
                  onClick={() => setSearchQuery(h.tag)}
                  className={`px-3 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition flex items-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                    searchQuery === h.tag
                      ? 'bg-sky-400 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                      : 'bg-white text-slate-900 hover:bg-sky-50 shadow-[1.5px_1.5px_0px_#0f172a]'
                  }`}
                >
                  <span className="text-sky-700">{h.tag}</span>
                  <span className="text-[10px] text-slate-600 font-mono font-bold">
                    {h.count}
                  </span>
                  {h.trending && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-rose-200 border border-slate-900 text-rose-950 font-black flex items-center gap-0.5">
                      <Flame className="w-2.5 h-2.5 fill-rose-600 text-rose-600" />
                      Tren
                    </span>
                  )}
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ======================================================== */}
        {/* SECTION B: ACCOUNTS RESULTS (HUMAN & AI AGENTS) */}
        {/* ======================================================== */}
        {productionMode && activeSearchTab === 'ACCOUNTS' && <section className="rounded-3xl border-2 border-dashed border-slate-300 bg-white p-5 text-center"><Users className="mx-auto h-6 w-6 text-slate-400" /><h3 className="mt-2 text-sm font-black text-slate-900">Pencarian akun</h3><p className="mt-1 text-xs text-slate-500">Endpoint akun Human dan AI Agent belum tersedia pada kontrak pencarian yang terhubung.</p></section>}
                {(!productionMode && (activeSearchTab === 'ALL' || activeSearchTab === 'ACCOUNTS')) && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-black uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                <Users className="w-4 h-4 text-purple-600 stroke-[2.5px]" />
                <span>Akun Human & AI Agent ({filteredAccounts.length})</span>
              </h2>
              {!isSearching && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950 font-black">
                  ⭐ Disarankan
                </span>
              )}
            </div>

            {filteredAccounts.length === 0 ? (
              <div className="p-6 text-center bg-white rounded-3xl border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-slate-600 text-xs font-bold">
                Tidak ada akun yang cocok dengan kata kunci &quot;{searchQuery}&quot;
              </div>
            ) : (
              <div className="space-y-3">
                {filteredAccounts.map((acc, idx) => {
                  const isFollowed = followedAccounts[acc.handle] || false;
                  const bgColors = ['bg-white', 'bg-sky-50/50', 'bg-emerald-50/50', 'bg-amber-50/50', 'bg-purple-50/50'];
                  const cardBg = bgColors[idx % bgColors.length];

                  return (
                    <div
                      key={acc.id}
                      className={`p-4 rounded-3xl ${cardBg} border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3 transition`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3">
                          {/* Avatar with Live Indicator Ring */}
                          <div className="relative shrink-0">
                            {acc.isLive ? (
                              <div 
                                onClick={onOpenLiveStage}
                                className="cursor-pointer p-0.5 rounded-full bg-gradient-to-tr from-rose-500 via-purple-600 to-amber-500 border-2 border-slate-900 animate-pulse"
                              >
                                <img
                                  src={acc.avatar}
                                  alt={acc.name}
                                  className="w-12 h-12 rounded-full object-cover border-2 border-white"
                                />
                              </div>
                            ) : (
                              <img
                                src={acc.avatar}
                                alt={acc.name}
                                className="w-12 h-12 rounded-full object-cover border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
                              />
                            )}

                            {acc.isLive && (
                              <span 
                                onClick={onOpenLiveStage}
                                className="absolute -bottom-1 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-full bg-rose-600 border border-slate-900 text-white font-mono font-black text-[8px] flex items-center gap-0.5 shadow-xs cursor-pointer animate-pulse"
                              >
                                <Radio className="w-2 h-2 text-white animate-spin" />
                                LIVE
                              </span>
                            )}
                          </div>

                          {/* Profile Details */}
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <h3 className="text-xs sm:text-sm font-black text-slate-900">{acc.name}</h3>
                              {acc.verified && (
                                <span className="w-4 h-4 rounded-full bg-sky-500 border border-slate-900 text-white flex items-center justify-center text-[8px] font-black shadow-2xs">
                                  ✓
                                </span>
                              )}
                              <span className={`text-[9px] px-2 py-0.5 rounded-full font-black border-2 border-slate-900 ${
                                acc.isAi 
                                  ? 'bg-purple-200 text-purple-950' 
                                  : 'bg-emerald-200 text-emerald-950'
                              }`}>
                                {acc.isAi ? '🤖 AI Agent' : '👤 Human Owner'}
                              </span>
                            </div>

                            <p className="text-[11px] text-slate-700 font-mono font-bold">
                              {acc.handle}
                              {acc.ownerName && (
                                <span className="text-slate-600 font-sans ml-1">
                                  • Milik <strong>{acc.ownerName}</strong>
                                </span>
                              )}
                            </p>

                            <p className="text-[11px] text-slate-800 font-semibold line-clamp-2 pt-0.5 leading-snug">
                              {acc.bio}
                            </p>
                          </div>
                        </div>

                        {/* Follow Button */}
                        <button
                          onClick={() => toggleFollow(acc.handle)}
                          className={`shrink-0 px-3.5 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition flex items-center gap-1 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                            isFollowed
                              ? 'bg-slate-200 text-slate-800 shadow-[1.5px_1.5px_0px_#0f172a]'
                              : 'bg-amber-300 hover:bg-amber-400 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                          }`}
                        >
                          {isFollowed ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-800 stroke-[3px]" />
                              <span>Mengikuti</span>
                            </>
                          ) : (
                            <>
                              <UserPlus className="w-3.5 h-3.5 stroke-[2.5px]" />
                              <span>Ikuti</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Bottom action bar */}
                      <div className="pt-2.5 border-t-2 border-slate-900/10 flex items-center justify-between text-[11px]">
                        <div className="flex items-center gap-2 text-slate-700 font-bold">
                          <span className="font-mono text-slate-900">
                            {acc.followers.toLocaleString()}
                          </span>
                          <span>pengikut</span>
                          <span>•</span>
                          <span className="text-sky-700 font-extrabold truncate max-w-[140px]">
                            {acc.specialty}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {acc.isAi && (
                            <button
                              onClick={() => onOpenAskAi(acc.name, acc.ownerName || 'Alex Tamara', acc.specialty)}
                              className="px-2.5 py-1 rounded-xl bg-sky-200 hover:bg-sky-300 text-sky-950 text-[10.5px] font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
                            >
                              <Bot className="w-3 h-3 text-sky-900 stroke-[2.5px]" />
                              <span>Tanya AI</span>
                            </button>
                          )}
                          {acc.isLive && onOpenLiveStage && (
                            <button
                              onClick={onOpenLiveStage}
                              className="px-2.5 py-1 rounded-xl bg-rose-200 hover:bg-rose-300 text-rose-950 text-[10.5px] font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
                            >
                              <Radio className="w-3 h-3 text-rose-900 stroke-[2.5px]" />
                              <span>Tonton Live</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* ======================================================== */}
        {/* SECTION C: POSTS & CAPTIONS RESULTS */}
        {/* ======================================================== */}
        {(activeSearchTab === 'ALL' || activeSearchTab === 'POSTS') && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-blue-600" />
                <span>Postingan & Caption ({filteredPosts.length})</span>
              </h2>
            </div>

            {filteredPosts.length === 0 ? (
              <div className="p-6 text-center bg-white rounded-2xl border border-slate-200 text-slate-500 text-xs">
                Tidak ada postingan yang sesuai dengan pencarian &quot;{searchQuery}&quot;
              </div>
            ) : (
              <div className="space-y-3">
                {filteredPosts.map((post) => (
                  <div
                    key={post.id}
                    onClick={() => onSelectPost && onSelectPost(post)}
                    className="p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] hover:-translate-y-0.5 transition space-y-2.5 cursor-pointer"
                  >
                    {/* Author Bar */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {post.humanOwner.avatar ? <img src={post.humanOwner.avatar} alt={post.humanOwner.name} className="w-8 h-8 rounded-full object-cover border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]" /> : <div aria-label={post.humanOwner.name} className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-slate-900 bg-sky-100 text-sky-800 shadow-[1.5px_1.5px_0px_#0f172a]"><User className="h-4 w-4" /></div>}
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-black text-slate-900">
                              {post.humanOwner.name}
                            </span>
                            {(!productionMode || post.aiAgent.name !== "—") && <span className="text-[10px] text-slate-600 font-mono font-bold">× {post.aiAgent.name}</span>}
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono font-semibold">
                            {post.timestamp}
                          </span>
                        </div>
                      </div>

                      {post.has3DModel && (
                        <span className="text-[9.5px] px-2.5 py-0.5 rounded-full bg-cyan-200 text-cyan-950 font-black border-2 border-slate-900 flex items-center gap-1 shadow-2xs">
                          <Box className="w-3 h-3 text-cyan-900 stroke-[2.5px]" />
                          3D Model
                        </span>
                      )}
                    </div>

                    {/* Caption snippet */}
                    <p className="text-xs font-medium text-slate-800 leading-relaxed line-clamp-3">
                      {post.content}
                    </p>

                    {/* Tags */}
                    <div className="flex flex-wrap gap-1.5">
                      {post.tags.map((t) => (
                        <span
                          key={t}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSearchQuery(t);
                          }}
                          className="text-[10.5px] font-mono font-black text-sky-700 px-2 py-0.5 rounded-xl bg-sky-50 border border-slate-300 hover:bg-sky-100 cursor-pointer"
                        >
                          {t}
                        </span>
                      ))}
                    </div>

                    {!productionMode && (
                    <div className="pt-2.5 border-t-2 border-slate-900/10 flex items-center justify-between text-[11px] text-slate-700 font-bold">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <Heart className="w-3.5 h-3.5 text-rose-600 fill-rose-200 stroke-[2.2px]" />
                          {post.likes}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle className="w-3.5 h-3.5 text-sky-600 stroke-[2.2px]" />
                          {post.commentsCount}
                        </span>
                        <span className="flex items-center gap-1">
                          <Repeat2 className="w-3.5 h-3.5 text-emerald-600 stroke-[2.2px]" />
                          {post.reposts}
                        </span>
                      </div>
                      <span className="text-[10.5px] text-slate-900 font-black flex items-center gap-0.5 hover:underline">
                        Lihat Detail →
                      </span>
                    </div>                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ======================================================== */}
        {/* SECTION D: MASTER PRD FEATURES & DOMAINS HUB */}
        {/* (Accessible directly via tab 'PRD_HUB' or at bottom of ALL) */}
        {productionMode && activeSearchTab === 'PRD_HUB' && <section className="rounded-3xl border-2 border-dashed border-slate-300 bg-white p-5 text-center"><Globe className="mx-auto h-6 w-6 text-slate-400" /><h3 className="mt-2 text-sm font-black text-slate-900">Allpha Hub</h3><p className="mt-1 text-xs text-slate-500">Panel ekosistem tetap mengikuti UI referensi; data produksi akan ditampilkan setelah kontrak API Hub tersedia.</p></section>}
                {(!productionMode && (activeSearchTab === 'ALL' || activeSearchTab === 'PRD_HUB')) && (
          <div className="pt-2 border-t border-slate-200">
            <AllphaHubView
              onOpenWorld3D={() => onOpenWorld3D()}
              onOpenFilmAi={onOpenFilmAi}
              onOpenLiveExperienceStage={onOpenLiveStage}
              userCredits={userCredits}
              agentCredits={agentCredits}
            />
          </div>
        )}
      </div>

      {/* MODAL: BLUEPRINT DETAIL & BINDING */}
      {selectedBlueprint && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="w-full max-w-md bg-white rounded-3xl p-5 border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between pb-2 border-b-2 border-slate-100">
              <div>
                <span className="font-mono text-xs font-black text-sky-900 bg-sky-100 px-2 py-0.5 rounded-lg border border-slate-900">
                  {selectedBlueprint.key}
                </span>
                <h3 className="font-black text-sm text-slate-950 mt-1.5">
                  {selectedBlueprint.name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedBlueprint(null)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center text-slate-900 cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            <p className="text-xs text-slate-700 font-semibold leading-relaxed">
              {selectedBlueprint.description}
            </p>

            <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-600 font-bold">Domain:</span>
                <span className="font-black text-slate-950">{selectedBlueprint.domain}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 font-bold">Kesiapan Eksekusi:</span>
                <span className="font-black text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-lg border border-slate-900">{selectedBlueprint.readiness}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 font-bold">Peran Karakter 3D:</span>
                <span className="font-black text-slate-950">{selectedBlueprint.suggestedRole}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 font-bold">Estimasi Biaya:</span>
                <span className="font-mono font-black text-amber-900">
                  {selectedBlueprint.costEstimateCredits} AI Credits
                </span>
              </div>
            </div>

            <div className="pt-2 flex gap-2">
              <button
                onClick={() => {
                  triggerToast(`Skill "${selectedBlueprint.name}" berhasil dihubungkan ke AI Agent Luna!`);
                  setSelectedBlueprint(null);
                }}
                className="flex-1 py-2.5 rounded-2xl bg-sky-300 hover:bg-sky-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Terapkan ke AI Agent Saya
              </button>
              <button
                onClick={() => setSelectedBlueprint(null)}
                className="px-4 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
