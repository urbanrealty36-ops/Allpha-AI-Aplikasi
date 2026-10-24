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
  INITIAL_POSTS
} from '@/lib/reference-store';
import AllphaHubView from '@/components/reference-ui/AllphaHubView';

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
}

type SearchTab = 'ALL' | 'ACCOUNTS' | 'POSTS' | 'HASHTAGS' | 'PRD_HUB';

export default function ExploreView({ 
  posts = INITIAL_POSTS,
  onSelectPost,
  onOpenAskAi, 
  onOpenWorld3D,
  onOpenCreditsHub,
  onOpenLiveStage,
  onOpenFilmAi,
  userCredits = 250,
  agentCredits = 480,
  onLikePost,
}: ExploreViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSearchTab, setActiveSearchTab] = useState<SearchTab>('ALL');

  // Follow states for accounts
  const [followedAccounts, setFollowedAccounts] = useState<{ [handle: string]: boolean }>({
    '@luna.ai': true,
    '@technova': false,
    '@mediai': false,
    '@andipratama': true,
    '@mikatanaka': false,
  });

  const toggleFollow = (handle: string) => {
    setFollowedAccounts(prev => ({
      ...prev,
      [handle]: !prev[handle]
    }));
    triggerToast(followedAccounts[handle] ? `Berhenti mengikuti ${handle}` : `Mulai mengikuti ${handle}!`);
  };

  // 500 Skill Blueprints state
  const [blueprints] = useState<SkillBlueprint[]>(SKILL_BLUEPRINTS_SAMPLE);
  const [selectedBlueprint, setSelectedBlueprint] = useState<SkillBlueprint | null>(null);

  // n8n-style Workflow Studio state
  const [workflowNodes, setWorkflowNodes] = useState<WorkflowNodeItem[]>(INITIAL_WORKFLOW_NODES);
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [workflowExecutionLog, setWorkflowExecutionLog] = useState<string | null>(null);

  // Videotron Ads State
  const [mediaSurfaces] = useState<MediaSurfaceItem[]>(MEDIA_SURFACES_SAMPLE);

  // Quests & Reward state
  const [quests, setQuests] = useState<QuestItem[]>(INITIAL_QUESTS);

  // Creator Settlement Transactions
  const [transactions] = useState<CreditTransaction[]>(INITIAL_TRANSACTIONS);

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
    if (!query) return SOCIAL_ACCOUNTS_SAMPLE;
    return SOCIAL_ACCOUNTS_SAMPLE.filter(acc => 
      acc.name.toLowerCase().includes(query) ||
      acc.handle.toLowerCase().includes(query) ||
      acc.specialty.toLowerCase().includes(query) ||
      acc.bio.toLowerCase().includes(query) ||
      (acc.ownerName && acc.ownerName.toLowerCase().includes(query)) ||
      acc.tags.some(t => t.toLowerCase().includes(query))
    );
  }, [query]);

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
    if (!query) return POPULAR_HASHTAGS;
    return POPULAR_HASHTAGS.filter(h => 
      h.tag.toLowerCase().includes(query.startsWith('#') ? query : `#${query}`)
    );
  }, [query]);

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

      {/* STICKY TOP SEARCH HEADER (Instagram & Threads Style) */}
      <div className="sticky top-15 z-30 bg-white/95 backdrop-blur border-b border-slate-200 px-4 pt-3 pb-2.5 space-y-2.5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-black tracking-tight text-slate-900 flex items-center gap-1.5">
              <span>Jelajahi & Cari</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-bold">
                Social Hub
              </span>
            </h1>
            <p className="text-[11px] text-slate-500">
              Cari akun Human, AI Agent, konten, caption, hashtag & ekosistem Allpha
            </p>
          </div>
          <button
            onClick={onOpenWorld3D}
            className="px-3 py-1.5 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition flex items-center gap-1 shadow-xs"
          >
            <Box className="w-3.5 h-3.5 text-cyan-400" />
            <span>3D World</span>
          </button>
        </div>

        {/* Realtime Search Input Bar */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Cari nama akun, @handle, caption, #hashtag, atau fitur..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-9 py-2 text-xs bg-slate-100 hover:bg-slate-100/80 focus:bg-white border border-slate-200 focus:border-blue-500 rounded-xl transition outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter Navigation Tabs */}
        <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar">
          {[
            { id: 'ALL' as SearchTab, label: 'Semua', count: isSearching ? (filteredAccounts.length + filteredPosts.length + filteredHashtags.length) : undefined },
            { id: 'ACCOUNTS' as SearchTab, label: 'Akun (Human & AI)', count: filteredAccounts.length },
            { id: 'POSTS' as SearchTab, label: 'Postingan & Caption', count: filteredPosts.length },
            { id: 'HASHTAGS' as SearchTab, label: 'Hashtags (#)', count: filteredHashtags.length },
            { id: 'PRD_HUB' as SearchTab, label: 'Allpha Hub', badge: 'Ecosystem' },
          ].map((tab) => {
            const isActive = activeSearchTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSearchTab(tab.id)}
                className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${isActive ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-600'}`}>
                    {tab.count}
                  </span>
                )}
                {tab.badge && (
                  <span className={`text-[9px] px-1.5 py-0.2 rounded-full font-bold ${isActive ? 'bg-white/20 text-white' : 'bg-blue-100 text-blue-700'}`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* ======================================================== */}
        {/* SECTION A: TRENDING HASHTAGS CAROUSEL (When not filtered or when on HASHTAGS) */}
        {/* ======================================================== */}
        {(activeSearchTab === 'ALL' || activeSearchTab === 'HASHTAGS') && (
          <section className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-blue-600" />
                <span>Hashtag Populer & Trending</span>
              </h2>
              {isSearching && (
                <span className="text-[11px] text-slate-400 font-mono">
                  {filteredHashtags.length} Hasil
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              {filteredHashtags.map((h) => (
                <button
                  key={h.tag}
                  onClick={() => setSearchQuery(h.tag)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition flex items-center gap-1.5 ${
                    searchQuery === h.tag
                      ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                      : 'bg-white text-slate-800 border-slate-200 hover:border-blue-300 hover:bg-blue-50/50'
                  }`}
                >
                  <span className="text-blue-600">{h.tag}</span>
                  <span className="text-[10px] text-slate-400 font-mono font-normal">
                    {h.count}
                  </span>
                  {h.trending && (
                    <span className="text-[9px] px-1 py-0.2 rounded bg-rose-50 text-rose-600 font-bold flex items-center gap-0.5">
                      <Flame className="w-2.5 h-2.5 fill-rose-500 text-rose-500" />
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
        {(activeSearchTab === 'ALL' || activeSearchTab === 'ACCOUNTS') && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-purple-600" />
                <span>Akun Human & AI Agent ({filteredAccounts.length})</span>
              </h2>
              {!isSearching && (
                <span className="text-[10px] text-blue-600 font-bold">Disarankan</span>
              )}
            </div>

            {filteredAccounts.length === 0 ? (
              <div className="p-6 text-center bg-white rounded-2xl border border-slate-200 text-slate-500 text-xs">
                Tidak ada akun yang cocok dengan kata kunci &quot;{searchQuery}&quot;
              </div>
            ) : (
              <div className="space-y-2.5">
                {filteredAccounts.map((acc) => {
                  const isFollowed = followedAccounts[acc.handle] || false;

                  return (
                    <div
                      key={acc.id}
                      className="p-3.5 rounded-2xl bg-white border border-slate-200 hover:border-blue-300 hover:shadow-xs transition space-y-2.5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3">
                          {/* Avatar with Live Indicator Ring */}
                          <div className="relative shrink-0">
                            {acc.isLive ? (
                              <div 
                                onClick={onOpenLiveStage}
                                className="cursor-pointer p-0.5 rounded-full bg-gradient-to-tr from-rose-500 via-purple-600 to-amber-500 animate-pulse"
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
                                className="w-12 h-12 rounded-full object-cover border border-slate-200"
                              />
                            )}

                            {acc.isLive && (
                              <span 
                                onClick={onOpenLiveStage}
                                className="absolute -bottom-1 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-full bg-rose-600 text-white font-mono font-bold text-[8px] flex items-center gap-0.5 shadow-xs cursor-pointer animate-pulse"
                              >
                                <Radio className="w-2 h-2 text-white animate-spin" />
                                LIVE
                              </span>
                            )}
                          </div>

                          {/* Profile Details */}
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <h3 className="text-xs font-black text-slate-900">{acc.name}</h3>
                              {acc.verified && (
                                <span className="w-3.5 h-3.5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[8px] font-bold">
                                  ✓
                                </span>
                              )}
                              <span className={`text-[9px] px-1.5 py-0.2 rounded-full font-bold ${
                                acc.isAi 
                                  ? 'bg-purple-100 text-purple-700 border border-purple-200' 
                                  : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                              }`}>
                                {acc.isAi ? '🤖 AI Agent' : '👤 Human Owner'}
                              </span>
                            </div>

                            <p className="text-[11px] text-slate-500 font-mono">
                              {acc.handle}
                              {acc.ownerName && (
                                <span className="text-slate-400 font-sans ml-1">
                                  • Milik <strong>{acc.ownerName}</strong>
                                </span>
                              )}
                            </p>

                            <p className="text-[11px] text-slate-700 font-medium line-clamp-2 pt-0.5">
                              {acc.bio}
                            </p>
                          </div>
                        </div>

                        {/* Follow Button */}
                        <button
                          onClick={() => toggleFollow(acc.handle)}
                          className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1 ${
                            isFollowed
                              ? 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200'
                              : 'bg-blue-600 text-white hover:bg-blue-700 shadow-xs'
                          }`}
                        >
                          {isFollowed ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                              <span>Mengikuti</span>
                            </>
                          ) : (
                            <>
                              <UserPlus className="w-3.5 h-3.5" />
                              <span>Ikuti</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Bottom action bar */}
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                        <div className="flex items-center gap-2 text-slate-500">
                          <span className="font-semibold text-slate-700">
                            {acc.followers.toLocaleString()}
                          </span>
                          <span>pengikut</span>
                          <span>•</span>
                          <span className="text-blue-600 truncate max-w-[140px]">
                            {acc.specialty}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {acc.isAi && (
                            <button
                              onClick={() => onOpenAskAi(acc.name, acc.ownerName || 'Alex Tamara', acc.specialty)}
                              className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-[10px] font-bold transition flex items-center gap-1"
                            >
                              <Bot className="w-3 h-3 text-blue-600" />
                              <span>Tanya AI</span>
                            </button>
                          )}
                          {acc.isLive && onOpenLiveStage && (
                            <button
                              onClick={onOpenLiveStage}
                              className="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 text-[10px] font-bold transition flex items-center gap-1"
                            >
                              <Radio className="w-3 h-3 text-rose-600" />
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
                    className="p-3.5 rounded-2xl bg-white border border-slate-200 hover:border-blue-400 hover:shadow-xs transition space-y-2 cursor-pointer"
                  >
                    {/* Author Bar */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <img
                          src={post.humanOwner.avatar}
                          alt={post.humanOwner.name}
                          className="w-7 h-7 rounded-full object-cover border border-slate-200"
                        />
                        <div>
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-bold text-slate-900">
                              {post.humanOwner.name}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              × {post.aiAgent.name}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {post.timestamp}
                          </span>
                        </div>
                      </div>

                      {post.has3DModel && (
                        <span className="text-[9px] px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-800 font-bold border border-cyan-200 flex items-center gap-1">
                          <Box className="w-3 h-3 text-cyan-600" />
                          3D Model
                        </span>
                      )}
                    </div>

                    {/* Caption snippet */}
                    <p className="text-xs text-slate-800 leading-relaxed line-clamp-3">
                      {post.content}
                    </p>

                    {/* Tags */}
                    <div className="flex flex-wrap gap-1">
                      {post.tags.map((t) => (
                        <span
                          key={t}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSearchQuery(t);
                          }}
                          className="text-[10px] font-mono text-blue-600 hover:underline cursor-pointer"
                        >
                          {t}
                        </span>
                      ))}
                    </div>

                    {/* Engagement Counts */}
                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-50" />
                          {post.likes}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle className="w-3.5 h-3.5 text-blue-500" />
                          {post.commentsCount}
                        </span>
                        <span className="flex items-center gap-1">
                          <Repeat2 className="w-3.5 h-3.5 text-emerald-500" />
                          {post.reposts}
                        </span>
                      </div>
                      <span className="text-[10px] text-blue-600 font-bold hover:underline">
                        Lihat Postingan →
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ======================================================== */}
        {/* SECTION D: MASTER PRD FEATURES & DOMAINS HUB */}
        {/* (Accessible directly via tab 'PRD_HUB' or at bottom of ALL) */}
        {(activeSearchTab === 'ALL' || activeSearchTab === 'PRD_HUB') && (
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

        {/* Legacy PRD content disabled in favor of dedicated AllphaHubView */}
        {false && (
          <div className="hidden">
            {/* 1. 500 AI AGENT SKILL BLUEPRINTS */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
                    <Bot className="w-4 h-4 text-blue-600" />
                    <span>500 AI Agent Skill Blueprints</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                      Master PRD App. B
                    </span>
                  </h3>
                  <p className="text-xs text-slate-500">
                    Katalog blueprint terstruktur lintas 25 domain siap pasang ke AI Agent Anda
                  </p>
                </div>
                <span className="text-xs font-mono font-bold text-slate-600">
                  {filteredBlueprints.length} Tersedia
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {filteredBlueprints.map((bp) => (
                  <div
                    key={bp.key}
                    onClick={() => setSelectedBlueprint(bp)}
                    className="p-3.5 rounded-2xl bg-white border border-slate-200 hover:border-blue-400 hover:shadow-md cursor-pointer transition space-y-2 group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-mono text-[10px] text-blue-600 font-bold">
                        {bp.key}
                      </span>
                      <span
                        className={`text-[9px] px-2 py-0.5 rounded-full font-bold ${
                          bp.readiness === 'Execution-ready'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {bp.readiness}
                      </span>
                    </div>

                    <h4 className="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition line-clamp-1">
                      {bp.name}
                    </h4>
                    <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                      {bp.description}
                    </p>

                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
                      <span>Peran: <strong className="text-slate-700">{bp.suggestedRole}</strong></span>
                      <span className="font-mono font-semibold text-amber-600">
                        {bp.costEstimateCredits} Cr/run
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* 2. VISUAL WORKFLOW STUDIO (n8n-style) */}
            <section className="p-4 rounded-3xl bg-slate-900 text-white space-y-4 shadow-xl border border-slate-800">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Workflow className="w-5 h-5 text-cyan-400" />
                    <h3 className="text-sm font-black text-white">
                      Visual Workflow Studio (n8n-Style)
                    </h3>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Eksekusi otomatis DAG node graf multi-agent dengan durable checkpointing (PRD §26)
                  </p>
                </div>

                <button
                  onClick={handleRunWorkflow}
                  disabled={isWorkflowRunning}
                  className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-bold text-xs shadow-lg transition flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isWorkflowRunning ? (
                    <>
                      <RotateCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Mengeksekusi...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-white" />
                      <span>Uji Jalankan DAG</span>
                    </>
                  )}
                </button>
              </div>

              <div className="space-y-2">
                {workflowNodes.map((node, index) => (
                  <div
                    key={node.id}
                    className="p-3 rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-between gap-3"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-slate-700 text-cyan-300 font-mono text-xs flex items-center justify-center font-bold">
                        {index + 1}
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-bold text-white">{node.name}</p>
                          <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 font-mono">
                            {node.type}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 line-clamp-1">{node.description}</p>
                      </div>
                    </div>

                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold font-mono ${
                        node.status === 'SUCCESS'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : node.status === 'CHECKPOINT'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-slate-700 text-slate-400'
                      }`}
                    >
                      {node.status}
                    </span>
                  </div>
                ))}
              </div>

              {workflowExecutionLog && (
                <div className="p-3 rounded-xl bg-black/60 border border-slate-800 font-mono text-[11px] text-cyan-300">
                  {workflowExecutionLog}
                </div>
              )}
            </section>

            {/* 3. 3D WORLDS DIRECTORY */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
                    <Box className="w-4 h-4 text-blue-600" />
                    <span>Jelajahi Dunia 3D (Worlds Directory)</span>
                  </h3>
                  <p className="text-xs text-slate-500">
                    Daftar dunia virtual, distrik kota, dan area publik Allpha Universe
                  </p>
                </div>
                <button
                  onClick={onOpenWorld3D}
                  className="text-xs text-blue-600 font-bold hover:underline"
                >
                  Buka Peta 3D →
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {worlds3D.map((w) => (
                  <div
                    key={w.id}
                    className="rounded-3xl overflow-hidden bg-white border border-slate-200 shadow-xs hover:shadow-md transition group"
                  >
                    <div className="relative h-28 bg-slate-900 overflow-hidden">
                      <img
                        src={w.img}
                        alt={w.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                      />
                      <div className="absolute top-2 left-2 flex gap-1">
                        <span className="px-2 py-0.5 rounded-full bg-blue-600 text-white font-bold text-[9px]">
                          {w.badge}
                        </span>
                      </div>
                      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-white text-[9px] bg-black/50 backdrop-blur px-2 py-0.5 rounded-lg">
                        <span className="flex items-center gap-1">
                          <Users className="w-3 h-3 text-cyan-400" />
                          {w.online}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-amber-400" />
                          {w.events}
                        </span>
                      </div>
                    </div>

                    <div className="p-3 space-y-1.5">
                      <h4 className="font-extrabold text-xs text-slate-900">{w.name}</h4>
                      <p className="text-[10px] text-slate-600 line-clamp-1">{w.tagline}</p>
                      <button
                        onClick={onOpenWorld3D}
                        className="w-full py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition flex items-center justify-center gap-1"
                      >
                        <span>Masuk 3D</span>
                        <ArrowUpRight className="w-3 h-3 text-cyan-400" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* 4. 3D VIDEOTRON & MEDIA SURFACES (PRD §51) */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
                    <Tv className="w-4 h-4 text-purple-600" />
                    <span>3D Videotron & Media Surfaces Engine</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 font-bold border border-purple-200">
                      PRD §51
                    </span>
                  </h3>
                  <p className="text-xs text-slate-500">
                    Pasang iklan dan pesan brand pada videotron 4K di Crystal City
                  </p>
                </div>
              </div>

              <div className="space-y-2.5">
                {mediaSurfaces.map((surf) => (
                  <div
                    key={surf.id}
                    className="p-3.5 rounded-2xl bg-white border border-slate-200 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between shadow-xs hover:border-purple-300 transition"
                  >
                    <div className="flex items-start gap-3">
                      <img
                        src={surf.previewImage}
                        alt={surf.name}
                        className="w-14 h-14 rounded-2xl object-cover shrink-0 ring-1 ring-slate-200"
                      />
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h4 className="font-bold text-xs text-slate-900">{surf.name}</h4>
                          <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-purple-100 text-purple-700 font-bold">
                            {surf.type}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          {surf.district} • {surf.location}
                        </p>
                        <div className="flex items-center gap-2 text-[10px] text-slate-600 mt-0.5">
                          <span>Impresi: <strong>{surf.dailyImpressions}</strong></span>
                        </div>
                      </div>
                    </div>

                    <div className="w-full sm:w-auto flex sm:flex-col items-center sm:items-end justify-between gap-1 border-t sm:border-t-0 pt-2 sm:pt-0">
                      <span className="font-mono font-bold text-xs text-amber-600">
                        {surf.priceCreditsPerDay} Cr/hari
                      </span>
                      <button
                        onClick={() => triggerToast(`Slot "${surf.name}" siap dijadwalkan!`)}
                        className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs transition shadow-xs"
                      >
                        Pesan Slot Iklan
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* 5. QUEST & XP REWARDS */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
                    <Award className="w-4 h-4 text-amber-600" />
                    <span>Quest Harian & Reward XP</span>
                  </h3>
                  <p className="text-xs text-slate-500">
                    Selesaikan misi harian untuk mendapatkan bonus AI Credits dan XP
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                {quests.map((q) => {
                  const isCompleted = q.progress >= q.maxProgress;

                  return (
                    <div
                      key={q.id}
                      className="p-3 rounded-2xl bg-white border border-slate-200 flex items-center justify-between gap-3 shadow-xs"
                    >
                      <div className="space-y-1 flex-1">
                        <div className="flex items-center gap-1.5">
                          <h4 className="font-bold text-xs text-slate-900">{q.title}</h4>
                          <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-700 font-bold">
                            {q.type}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500">{q.description}</p>

                        <div className="flex items-center gap-2 max-w-xs pt-0.5">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-600 rounded-full transition-all duration-500"
                              style={{
                                width: `${Math.min(100, (q.progress / q.maxProgress) * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="font-mono text-[9px] text-slate-600 font-semibold">
                            {q.progress}/{q.maxProgress}
                          </span>
                        </div>
                      </div>

                      <div className="text-right shrink-0 space-y-1">
                        <div className="text-[10px] font-mono font-bold text-emerald-600">
                          +{q.rewardCredits} Cr
                        </div>
                        <button
                          onClick={() => handleClaimQuest(q.id)}
                          disabled={!isCompleted || q.isClaimed}
                          className={`px-3 py-1 rounded-xl text-xs font-bold transition ${
                            q.isClaimed
                              ? 'bg-slate-100 text-slate-400 cursor-default'
                              : isCompleted
                              ? 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs'
                              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          }`}
                        >
                          {q.isClaimed ? 'Diklaim' : isCompleted ? 'Klaim' : 'Berjalan'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* 6. SETTLEMENT LEDGER */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
                    <CreditCard className="w-4 h-4 text-emerald-600" />
                    <span>Buku Besar Mutasi & Settlement Creator</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                      PRD §64
                    </span>
                  </h3>
                  <p className="text-xs text-slate-500">
                    Catatan audit transparan dari reward pertanyaan AI dan brand share
                  </p>
                </div>
                {onOpenCreditsHub && (
                  <button
                    onClick={onOpenCreditsHub}
                    className="text-xs text-blue-600 font-bold hover:underline"
                  >
                    Dompet →
                  </button>
                )}
              </div>

              <div className="space-y-2">
                {transactions.map((tx) => (
                  <div
                    key={tx.id}
                    className="p-3 rounded-2xl bg-white border border-slate-200 flex items-start justify-between gap-3 shadow-2xs"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[9px] text-blue-600 font-bold">
                          {tx.id}
                        </span>
                        <span className="text-[8px] px-1.5 py-0.2 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                          {tx.status}
                        </span>
                      </div>
                      <p className="text-xs font-bold text-slate-900">{tx.querySummary}</p>
                      <p className="text-[10px] text-slate-500">
                        {tx.fromUser} → {tx.toAgent} ({tx.timestamp})
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="font-mono font-black text-emerald-600 text-xs">
                        +{tx.amount} Cr
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>

      {/* MODAL: BLUEPRINT DETAIL & BINDING */}
      {selectedBlueprint && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white rounded-3xl p-5 border border-slate-200 shadow-2xl space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-xs font-bold text-blue-600">
                  {selectedBlueprint.key}
                </span>
                <h3 className="font-black text-sm text-slate-900 mt-0.5">
                  {selectedBlueprint.name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedBlueprint(null)}
                className="p-1 text-slate-400 hover:text-slate-900 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed">
              {selectedBlueprint.description}
            </p>

            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Domain:</span>
                <span className="font-bold text-slate-800">{selectedBlueprint.domain}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Kesiapan Eksekusi:</span>
                <span className="font-bold text-emerald-600">{selectedBlueprint.readiness}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Peran Karakter 3D:</span>
                <span className="font-bold text-slate-800">{selectedBlueprint.suggestedRole}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Estimasi Biaya:</span>
                <span className="font-mono font-bold text-amber-600">
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
                className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md transition"
              >
                Terapkan ke AI Agent Saya
              </button>
              <button
                onClick={() => setSelectedBlueprint(null)}
                className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition"
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
