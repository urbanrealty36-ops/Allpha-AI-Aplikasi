'use client';

import React, { useEffect, useState, useMemo } from 'react';
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
  User,
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
  ArrowRight,
  Store
} from 'lucide-react';
import type {
  SkillBlueprint,
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
  followers?: number;
  verified?: boolean;
  publicPostCount?: number;
  isLive?: boolean;
  tags: string[];
}

export const SOCIAL_ACCOUNTS_SAMPLE: SocialAccountItem[] = [];
export const POPULAR_HASHTAGS: Array<{ tag: string; count: string; trending: boolean }> = [];

export interface ExploreMarketplaceItem {
  id: string;
  name: string;
  type: string;
  price?: string | null;
  credits?: number | null;
  seller?: string | null;
  image?: string | null;
  badge?: string | null;
  booth?: string | null;
}

interface ExploreViewProps {
  marketplaceItems?: ExploreMarketplaceItem[];
  onOpenMarketplace?: () => void;
  onOpenStoreAndBoothModal?: () => void;
  posts?: PostItem[];
  onSelectPost?: (post: PostItem) => void;
  onOpenAskAi: (agentName: string, ownerName: string, specialty: string) => void;
  onOpenWorld3D: () => void;
  userCredits?: number | null;
  agentCredits?: number | null;
  onOpenCreditsHub?: () => void;
  onOpenLiveStage?: () => void;
  onOpenFilmAi?: (filmId?: string) => void;
  onLikePost?: (postId: string) => void;
  productionMode?: boolean;
  onSearch?: (query: string) => void;
  onRetrySearch?: () => void;
  onRetryTrends?: () => void;
  onRetryRecommendations?: () => void;
  trendsData?: Array<{ topic: string; content_count: number }>;
  recommendationsData?: PostItem[];
  accountsData?: SocialAccountItem[];
  accountsLoading?: boolean;
  accountsError?: string;
  relationshipError?: string;
  onRetryAccounts?: () => void;
  followedAccountIds?: string[];
  pendingFollowAccountIds?: string[];
  onFollowAccount?: (accountId: string, currentlyFollowed: boolean, currentlyPending?: boolean) => void;
  recommendationsLoading?: boolean;
  recommendationsError?: string;
  trendsLoading?: boolean;
  trendsError?: string;
  initialSearchQuery?: string;
  searchLoading?: boolean;
  searchError?: string;
  searchEmpty?: boolean;
  searchPrompt?: boolean;
}

type SearchTab = 'ALL' | 'ACCOUNTS' | 'POSTS' | 'HASHTAGS' | 'PRD_HUB';

export default function ExploreView({ 
  posts = [],
  onSelectPost,
  onOpenAskAi, 
  onOpenWorld3D,
  userCredits = null,
  agentCredits = null,
  onOpenCreditsHub,
  onOpenLiveStage,
  onOpenFilmAi,
  onLikePost,
  productionMode = false,
  onSearch,
  onRetrySearch,
  onRetryTrends,
  onRetryRecommendations,
  trendsData = [],
  recommendationsData = [],
  accountsData = [],
  accountsLoading = false,
  accountsError = "",
  relationshipError = "",
  onRetryAccounts,
  followedAccountIds = [],
  pendingFollowAccountIds = [],
  onFollowAccount,
  recommendationsLoading = false,
  recommendationsError = "",
  trendsLoading = false,
  trendsError = "",
  initialSearchQuery = '',
  searchLoading = false,
  searchError = '',
  searchEmpty = false,
  searchPrompt = false,
  marketplaceItems = [],
  onOpenMarketplace,
  onOpenStoreAndBoothModal,
}: ExploreViewProps) {
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  useEffect(() => { setSearchQuery(initialSearchQuery); }, [initialSearchQuery]);
  const [activeSearchTab, setActiveSearchTab] = useState<SearchTab>(productionMode ? 'POSTS' : 'ALL');

  // Follow states for accounts
  const [followedAccounts, setFollowedAccounts] = useState<{ [handle: string]: boolean }>({});

  const toggleFollow = (handle: string, accountId?: string) => {
    if (productionMode && accountId) {
      onFollowAccount?.(accountId, followedAccountIds.includes(accountId), pendingFollowAccountIds.includes(accountId));
      return;
    }
    setFollowedAccounts(prev => ({
      ...prev,
      [handle]: !prev[handle]
    }));
    triggerToast(followedAccounts[handle] ? `Berhenti mengikuti ${handle}` : `Mulai mengikuti ${handle}!`);
  };

  // 500 Skill Blueprints state
  const [blueprints] = useState<SkillBlueprint[]>([]);
  const [selectedBlueprint, setSelectedBlueprint] = useState<SkillBlueprint | null>(null);

  // n8n-style Workflow Studio state

  // Videotron Ads State

  // Quests & Reward state

  // Creator Settlement Transactions

  // Toast state
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const triggerToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // ==========================================
  // REAL SOCIAL SEARCH FILTERING ENGINE
  // ==========================================
  const query = searchQuery.trim().toLowerCase();

  const filteredAccounts = useMemo(() => {
    if (productionMode) {
      if (!query) return accountsData;
      return accountsData.filter(acc =>
        acc.name.toLowerCase().includes(query) ||
        acc.handle.toLowerCase().includes(query) ||
        acc.specialty.toLowerCase().includes(query) ||
        acc.bio.toLowerCase().includes(query)
      );
    }
    if (!query) return SOCIAL_ACCOUNTS_SAMPLE;
    return SOCIAL_ACCOUNTS_SAMPLE.filter(acc => 
      acc.name.toLowerCase().includes(query) ||
      acc.handle.toLowerCase().includes(query) ||
      acc.specialty.toLowerCase().includes(query) ||
      acc.bio.toLowerCase().includes(query) ||
      (acc.ownerName && acc.ownerName.toLowerCase().includes(query)) ||
      acc.tags.some(t => t.toLowerCase().includes(query))
    );
  }, [query, productionMode, accountsData]);

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
        {activeSearchTab === 'POSTS' && searchError && <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border-2 border-rose-400 bg-white p-3 text-xs font-bold text-rose-700"><span>{searchError}</span>{onRetrySearch && <button type="button" onClick={onRetrySearch} disabled={searchLoading} className="shrink-0 rounded-xl border-2 border-slate-900 bg-white px-3 py-1.5 text-xs font-black text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] disabled:opacity-50">Coba lagi</button>}</div>}
        {activeSearchTab === 'POSTS' && searchLoading && <p role="status" className="rounded-xl border-2 border-slate-300 bg-white p-4 text-xs font-semibold text-slate-600">Mencari konten…</p>}
        {activeSearchTab === 'POSTS' && searchEmpty && !searchLoading && !searchError && <p role="status" className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-5 text-center text-xs font-bold text-slate-600">Belum ada konten yang cocok dengan kata kunci tersebut.</p>}
        {activeSearchTab === 'POSTS' && searchPrompt && !searchLoading && !searchError && <p className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-4 text-xs font-semibold text-slate-600">Tekan Enter setelah memasukkan kata kunci untuk mencari konten yang dapat Anda akses.</p>}
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
            ))}</div> : <div className="flex items-center justify-between gap-3 rounded-2xl border-2 border-dashed border-slate-300 bg-white p-4 text-xs font-semibold text-slate-500"><span>{trendsLoading ? "Memuat tren…" : trendsError || "Tren akan tampil saat tersedia konten publik yang dapat diakses."}</span>{trendsError && onRetryTrends && <button type="button" onClick={onRetryTrends} disabled={trendsLoading} className="shrink-0 rounded-xl border-2 border-slate-900 bg-white px-3 py-1.5 text-xs font-black text-slate-900 disabled:opacity-50">Coba lagi</button>}</div>}
          </section>
        )}
        {productionMode && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-black text-slate-900">Rekomendasi untuk Anda</h2>
              <span className="text-[10px] font-bold text-slate-500">Ranking personal</span>
            </div>
            {recommendationsLoading ? <p role="status" className="rounded-2xl border-2 border-slate-300 bg-white p-4 text-xs font-semibold text-slate-500">Memuat rekomendasi…</p> : recommendationsError ? <div role="alert" className="flex items-center justify-between gap-3 rounded-2xl border-2 border-rose-300 bg-white p-4 text-xs font-semibold text-rose-700"><span>{recommendationsError}</span>{onRetryRecommendations && <button type="button" onClick={onRetryRecommendations} disabled={recommendationsLoading} className="shrink-0 rounded-xl border-2 border-slate-900 bg-white px-3 py-1.5 text-xs font-black text-slate-900 disabled:opacity-50">Coba lagi</button>}</div> : recommendationsData.length ? recommendationsData.map(post => (
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
        {/* SECTION A.2: MARKETPLACE & 3D BOOTH SPOTLIGHT (JELAJAHI) */}
        {/* ======================================================== */}
        {activeSearchTab === 'ALL' && (
          <section className="space-y-3.5">
            <div className="p-4 sm:p-5 rounded-3xl bg-[#FEF08A] border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="w-7 h-7 rounded-xl bg-white border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                      <ShoppingBag className="w-3.5 h-3.5 text-slate-950 stroke-[2.5px]" />
                    </span>
                    <h2 className="text-sm sm:text-base font-black text-slate-950 tracking-tight">
                      Marketplace & Stan Booth 3D Spatial
                    </h2>
                  </div>
                  <p className="text-[11.5px] font-semibold text-slate-800">
                    Beli aset 3D, companion AI Agent, merchandise fisik & kunjungi stan pameran di distrik 3D
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {onOpenStoreAndBoothModal && (
                    <button onClick={onOpenStoreAndBoothModal} className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer">
                      <Store className="w-3.5 h-3.5 text-slate-900 stroke-[2.5px]" />
                      <span>Buat Toko & Booth</span>
                    </button>
                  )}
                  {onOpenMarketplace && (
                    <button onClick={onOpenMarketplace} className="px-3.5 py-1.5 rounded-xl bg-slate-950 hover:bg-slate-800 text-white font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer">
                      <span>Buka Marketplace</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto no-scrollbar text-[10px] font-black text-slate-900 pt-0.5">
                <span className="px-2 py-0.5 rounded-lg bg-white/80 border border-slate-900 shrink-0">✨ Royalti seller mengikuti ketentuan kanonis</span>
                <span className="px-2 py-0.5 rounded-lg bg-white/80 border border-slate-900 shrink-0">📦 Pengiriman sesuai layanan yang tersedia</span>
                <span className="px-2 py-0.5 rounded-lg bg-white/80 border border-slate-900 shrink-0">💳 Pembayaran sesuai konfigurasi aktif</span>
                <span className="px-2 py-0.5 rounded-lg bg-white/80 border border-slate-900 shrink-0">🎪 Warp Pad 3D Districts</span>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {marketplaceItems.map((item) => (
                <div key={item.id} className="p-2.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-1.5 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <div className="relative h-24 rounded-xl overflow-hidden border border-slate-900">
                      {item.image ? <img src={item.image} alt={item.name} className="w-full h-full object-cover" /> : <div className="flex h-full w-full items-center justify-center bg-slate-100"><Box className="w-7 h-7 text-slate-400" /></div>}
                      <span className="absolute top-1 left-1 px-1.5 py-0.2 rounded font-mono text-[8px] font-black bg-white/90 border border-slate-900 text-slate-950">{item.type}</span>
                    </div>
                    <h4 className="font-black text-xs text-slate-950 line-clamp-1 leading-snug">{item.name}</h4>
                    <p className="text-[10px] font-semibold text-slate-500 line-clamp-1">{item.seller || "Penjual belum tersedia"}</p>
                  </div>
                  <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between">
                    <div>
                      <p className="font-mono font-black text-emerald-700 text-[11px] leading-tight">{item.price || "Harga belum tersedia"}</p>
                      <span className="font-mono text-[9px] text-amber-900 font-bold block">{item.credits == null ? "—" : item.credits} Cr</span>
                    </div>
                    {onOpenMarketplace && <button onClick={onOpenMarketplace} className="px-2 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-black text-[10px] border border-slate-900 cursor-pointer">Beli</button>}
                  </div>
                </div>
              ))}
              {marketplaceItems.length === 0 && (
                <div className="col-span-full rounded-2xl border-2 border-dashed border-slate-900 bg-white/70 p-5 text-center">
                  <ShoppingBag className="mx-auto mb-2 h-6 w-6 text-slate-500" />
                  <p className="text-xs font-black text-slate-900">Katalog Marketplace belum tersedia.</p>
                  <p className="mt-1 text-[10px] font-semibold text-slate-600">Produk contoh tidak ditampilkan. Item akan muncul setelah API katalog kanonis mengembalikan data.</p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ======================================================== */}
        {/* SECTION B: ACCOUNTS RESULTS (HUMAN & AI AGENTS) */}
        {/* ======================================================== */}
                {((productionMode && activeSearchTab === 'ACCOUNTS') || (!productionMode && (activeSearchTab === 'ALL' || activeSearchTab === 'ACCOUNTS'))) && (
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

            {productionMode && relationshipError && (
              <div role="alert" className="mb-3 rounded-2xl border-2 border-amber-700 bg-amber-50 p-3 text-xs font-bold text-amber-950">
                <p>{relationshipError}</p>
                {onRetryAccounts && <button type="button" onClick={onRetryAccounts} className="mt-2 rounded-xl border-2 border-amber-900 px-3 py-2">Muat ulang status relasi</button>}
              </div>
            )}
            {productionMode && accountsLoading ? (
              <div role="status" className="p-6 text-center bg-white rounded-3xl border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-slate-600 text-xs font-bold">Memuat akun publik…</div>
            ) : productionMode && accountsError ? (
              <div role="alert" className="p-6 text-center bg-white rounded-3xl border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-slate-600 text-xs font-bold"><p>{accountsError}</p>{onRetryAccounts && <button type="button" onClick={onRetryAccounts} className="mt-3 rounded-xl border-2 border-slate-900 px-3 py-2">Coba lagi</button>}</div>
            ) : filteredAccounts.length === 0 ? (
              <div role="status" className="p-6 text-center bg-white rounded-3xl border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-slate-600 text-xs font-bold">
                {productionMode ? "Belum ada akun publik yang memiliki konten publik yang memenuhi syarat." : `Tidak ada akun yang cocok dengan kata kunci "${searchQuery}"`}
              </div>
            ) : (
              <div className="space-y-3">
                {filteredAccounts.map((acc, idx) => {
                  const isFollowed = productionMode ? followedAccountIds.includes(acc.id) : (followedAccounts[acc.handle] || false);
                  const isPending = productionMode && pendingFollowAccountIds.includes(acc.id);
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
                          onClick={() => toggleFollow(acc.handle, acc.id)}
                          title={isPending ? "Batalkan permintaan mengikuti" : isFollowed ? "Berhenti mengikuti" : "Ikuti akun"}
                          aria-label={isPending ? `Batalkan permintaan mengikuti ${acc.handle}` : isFollowed ? `Berhenti mengikuti ${acc.handle}` : `Ikuti ${acc.handle}`}
                          className={`shrink-0 px-3.5 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition flex items-center gap-1 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                            isFollowed
                              ? 'bg-slate-200 text-slate-800 shadow-[1.5px_1.5px_0px_#0f172a]'
                              : isPending
                                ? 'bg-amber-200 hover:bg-amber-300 text-amber-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                                : 'bg-amber-300 hover:bg-amber-400 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                          }`}
                        >
                          {isPending ? (
                            <>
                              <X className="w-3.5 h-3.5 stroke-[3px]" />
                              <span>Menunggu</span>
                            </>
                          ) : isFollowed ? (
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
                            {acc.followers !== undefined ? acc.followers.toLocaleString() : (acc.publicPostCount !== undefined ? acc.publicPostCount : "—")}
                          </span>
                          <span>{acc.followers !== undefined ? "pengikut" : (acc.publicPostCount !== undefined ? "post publik" : "aktivitas")}</span>
                          <span>•</span>
                          <span className="text-sky-700 font-extrabold truncate max-w-[140px]">
                            {acc.specialty}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {acc.isAi && (
                            <button
                              onClick={() => onOpenAskAi(acc.name, acc.ownerName || 'Pemilik Agent', acc.specialty)}
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
                {!productionMode && (activeSearchTab === 'ALL' || activeSearchTab === 'PRD_HUB') && (
          <section className="rounded-3xl border-2 border-dashed border-slate-300 bg-white p-5 text-center">
            <Globe className="mx-auto h-6 w-6 text-slate-400" />
            <h3 className="mt-2 text-sm font-black text-slate-900">Allpha Hub</h3>
            <p className="mt-1 text-xs text-slate-500">Hub produksi memerlukan kontrak API untuk event, district, dan saldo kanonis; data demo tidak digunakan.</p>
          </section>
        )}
      </div>

      {/* SECTION D: MASTER PRD FEATURES & DOMAINS HUB — source reference integration */}
      {(activeSearchTab === 'ALL' || activeSearchTab === 'PRD_HUB') && (
        <div className="pt-2 border-t border-slate-200">
          <AllphaHubView
            onOpenWorld3D={() => onOpenWorld3D()}
            onOpenFilmAi={onOpenFilmAi}
            onOpenLiveExperienceStage={onOpenLiveStage}
            userCredits={userCredits}
            agentCredits={agentCredits}
            productionMode={productionMode}
          />
        </div>
      )}

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
