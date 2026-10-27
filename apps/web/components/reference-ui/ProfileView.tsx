'use client';

import React, { useEffect, useState } from 'react';
import { 
  User, 
  Bot, 
  Coins, 
  Settings, 
  Edit3, 
  CheckCircle2, 
  Sparkles, 
  Box, 
  Upload, 
  Layers, 
  SlidersHorizontal,
  FolderOpen,
  Globe,
  Share2,
  Menu,
  Shield,
  ShieldCheck,
  CreditCard,
  Bell,
  Smartphone,
  SunMoon,
  FileText,
  LogOut,
  X,
  Heart,
  MessageCircle,
  Repeat2,
  Bookmark,
  Grid3X3,
  List,
  ArrowUpRight,
  ExternalLink,
  ChevronRight,
  Lock,
  Target,
  Zap,
  Play,
  Palette,
  BarChart2,
  DollarSign,
  Archive,
  Plug,
  Wand2,
  Wallet,
  TrendingUp,
  DownloadCloud,
  Store,
  ShoppingBag
} from 'lucide-react';
import type { HumanProfile, AIAgentProfile, KnowledgeDocument, PostItem } from '../../lib/reference-store';
import AgentIdentityModal from './AgentIdentityModal';
import AgentGoalsTasksModal from './AgentGoalsTasksModal';
import AgentPassportModal from './AgentPassportModal';
import CreatorStudioModal from './CreatorStudioModal';
import ThemeCatalogModal from './ThemeCatalogModal';
import StoreAndBoothModal from './StoreAndBoothModal';

interface ProfileViewProps {
  humanUser: HumanProfile;
  agentProfile: AIAgentProfile | null;
  ownedAgents?: Array<{ name: string; handle: string; specialty: string; avatar: string; status: string; credits?: number | null }>;
  showCredits?: boolean;
  showSocialCounts?: boolean;
  humanVerified?: boolean;
  agentStatusLabel?: string;
  onOpenAccountSettings?: (tab?: "profile" | "settings" | "social" | "consents") => void;
  onLogout?: () => Promise<void>;
  onRevokeOtherSessions?: () => Promise<void>;
  knowledgeDocs: KnowledgeDocument[];
  posts: PostItem[];
  isTakeoverActive: boolean;
  onOpenTakeoverModal: () => void;
  onOpenCreditsHub: () => void;
  onOpenWorld3D: () => void;
  onOpenOnboarding?: () => void;
  onLikePost?: (postId: string) => void;
  onSelectPost?: (post: PostItem) => void;
  onOpenAskAi?: (agentName: string, ownerName: string, specialty: string) => void;
  onOpenGenerate?: (contextPost: PostItem) => void;
  onUpdateAgent?: (updatedAgent: AIAgentProfile) => void;
  onOpenFilmAi?: () => void;
  userCredits?: number;
  onDeductCredits?: (amount: number, reason: string) => void;
  onOpenNotifications?: () => void;
  onOpenStoreAndBooth?: () => void;
  initialOpenStoreAndBooth?: boolean;
}

export default function ProfileView({
  humanUser,
  agentProfile: selectedAgentProfile,
  ownedAgents: ownedAgentsFromApi = [],
  showCredits = false,
  showSocialCounts = false,
  humanVerified = false,
  agentStatusLabel = 'Status Agent belum tersedia',
  onOpenAccountSettings,
  onLogout,
  onRevokeOtherSessions,
  knowledgeDocs,
  posts,
  isTakeoverActive,
  onOpenTakeoverModal,
  onOpenCreditsHub,
  onOpenWorld3D,
  onOpenOnboarding,
  onLikePost,
  onSelectPost,
  onOpenAskAi,
  onOpenGenerate,
  onUpdateAgent,
  onOpenFilmAi,
  userCredits = 0,
  onDeductCredits,
  onOpenNotifications,
  onOpenStoreAndBooth,
  initialOpenStoreAndBooth = false,
}: ProfileViewProps) {
  const hasAgentProfile = Boolean(selectedAgentProfile);
  const agentProfile: AIAgentProfile = selectedAgentProfile ?? {
    id: '', name: '', handle: '', avatar: humanUser.avatar, ownerId: humanUser.id,
    ownerName: humanUser.name, ownerHandle: humanUser.username, specialty: '', category: '',
    bio: '', skills: [], creditsEarned: 0, autoReply: false, model: ''
  };
  // Tabs: Konten, AI Agent, Disukai, Tentang
  const [activeProfileTab, setActiveProfileTab] = useState<'KONTEN' | 'AGENTS' | 'LIKED' | 'ABOUT'>('KONTEN');
  
  // View mode for posts: List (Threads style) or Grid (Instagram style from screenshot 8)
  const [contentViewMode, setContentViewMode] = useState<'LIST' | 'GRID'>('LIST');

  // Threads-style Settings Drawer / Sheet State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [selectedSettingDetail, setSelectedSettingDetail] = useState<string | null>(null);

  // Modals State
  const [isIdentityModalOpen, setIsIdentityModalOpen] = useState(false);
  const [isGoalsTasksModalOpen, setIsGoalsTasksModalOpen] = useState(false);
  const [isPassportOpen, setIsPassportOpen] = useState(false);
  const [isCreatorStudioOpen, setIsCreatorStudioOpen] = useState(false);
  const [isThemeCatalogOpen, setIsThemeCatalogOpen] = useState(false);
  const [isStoreAndBoothModalOpen, setIsStoreAndBoothModalOpen] = useState(false);
  useEffect(() => { if (initialOpenStoreAndBooth) setIsStoreAndBoothModalOpen(true); }, [initialOpenStoreAndBooth]);

  // Financial & Withdraw Form State
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawBank, setWithdrawBank] = useState('BCA');
  const [withdrawAccount, setWithdrawAccount] = useState('');
  const [settingsLang, setSettingsLang] = useState<'id' | 'en' | 'ja'>('id');
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // Filter posts created by or affiliated with this human user
  const userPosts = posts.filter(
    (p) => p.humanOwner.name === humanUser.name || p.humanOwner.handle === humanUser.username
  );

  // Agent cards are derived only from the canonical API adapter; no sample agents are seeded.
  const ownedAgents = ownedAgentsFromApi.map((agent, index) => ({
    ...agent,
    badgeColor: ['bg-cyan-50 text-cyan-700 border-cyan-200', 'bg-purple-50 text-purple-700 border-purple-200', 'bg-amber-50 text-amber-900 border-amber-200'][index % 3],
  }));

  return (
    <div className="w-full max-w-xl mx-auto pb-28 min-h-screen px-3 sm:px-4 pt-2 font-sans">
      {/* THREADS-STYLE NAVBAR HEADER */}
      <header className="sticky top-14 z-30 bg-[#F4F7FB]/95 backdrop-blur border-2 border-slate-900 rounded-2xl px-4 py-2.5 mb-3 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        {/* Left: Globe icon & User handle */}
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-slate-800" />
          <span className="font-black text-sm tracking-tight text-slate-900">
            {humanUser.username.replace('@', '')}
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 font-black border border-sky-300">
            HUMAN OWNER
          </span>
        </div>

        {/* Right: Share icon & Settings */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => {
              if (navigator.share) {
                navigator.share({
                  title: `${humanUser.name} di ALLPHA UNIVERSE`,
                  url: window.location.href,
                }).catch(() => {});
              } else {
                navigator.clipboard.writeText(window.location.href);
                showToast('Tautan profil disalin ke clipboard!');
              }
            }}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
            title="Bagikan Profil"
          >
            <Share2 className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-900 hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
            title="Pengaturan Akun"
          >
            <div className="w-4 h-3.5 flex flex-col justify-between items-end">
              <span className="w-4 h-0.5 bg-slate-900 rounded-full" />
              <span className="w-2.5 h-0.5 bg-slate-900 rounded-full" />
            </div>
          </button>
        </div>
      </header>

      {/* PROFILE HERO HEADER */}
      <div className="bg-white rounded-3xl border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] p-5 mb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Name + Verified Badge */}
            <div className="flex items-center gap-1.5">
              <h1 className="text-xl font-black tracking-tight text-slate-900">{humanUser.name}</h1>
              {humanVerified && (
                <span className="w-4 h-4 rounded-full bg-[#0284C7] text-white flex items-center justify-center text-[10px] font-black border border-slate-900">
                  ✓
                </span>
              )}
            </div>

            {/* Handle & Badge */}
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-slate-500 font-bold">{humanUser.username}</span>
              <span className="text-slate-300">•</span>
              <span className="text-xs text-slate-700 font-black">{humanUser.badge}</span>
            </div>

            {/* Bio text */}
            <p className="text-xs text-slate-800 mt-3 leading-relaxed font-semibold max-w-sm">
              {humanUser.bio}
            </p>
          </div>

          {/* Profile Avatar */}
          <div className="relative shrink-0">
            <img
              src={humanUser.avatar}
              alt={humanUser.name}
              className="w-18 h-18 rounded-2xl object-cover border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]"
            />
            {humanVerified && (
              <span aria-label="Akun terverifikasi" title="Akun terverifikasi" className="absolute -bottom-1 -right-1 w-6 h-6 rounded-lg bg-[#0284C7] text-white flex items-center justify-center text-[10px] font-black border border-slate-900">
                ✓
              </span>
            )}
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-6 mt-4 pt-3 border-t-2 border-slate-100 text-xs">
          <div>
            <span className="font-black text-slate-900">{showSocialCounts ? humanUser.postsCount : '—'}</span>
            <span className="text-slate-500 font-bold ml-1">Postingan</span>
          </div>
          <div>
            <span className="font-black text-slate-900">{showSocialCounts ? `${(humanUser.followers / 1000).toFixed(1)}K` : '—'}</span>
            <span className="text-slate-500 font-bold ml-1">Pengikut</span>
          </div>
          <div>
            <span className="font-black text-slate-900">{showSocialCounts ? `${(humanUser.following / 1000).toFixed(1)}K` : '—'}</span>
            <span className="text-slate-500 font-bold ml-1">Mengikuti</span>
          </div>
        </div>

        {/* Action Button: Edit Profil */}
        <div className="mt-4 flex gap-2">
          <button
            onClick={() => (onOpenOnboarding ? onOpenOnboarding() : showToast('Membuka formulir identitas profil'))}
            className="flex-1 py-2.5 px-4 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50 text-slate-900 text-xs font-black transition active:translate-x-0.5 active:translate-y-0.5"
          >
            Edit Profil
          </button>
          <button
            onClick={onOpenCreditsHub}
            className="py-2.5 px-4 rounded-xl bg-[#FEF08A] hover:bg-amber-300 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 text-xs font-black transition active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5"
            title="Kelola Knowledge & Credits"
          >
            <Coins className="w-3.5 h-3.5 text-slate-950" />
            <span>AI Credits</span>
          </button>
          <button
            onClick={() => {
              if (onOpenStoreAndBooth) {
                onOpenStoreAndBooth();
              } else {
                setIsStoreAndBoothModalOpen(true);
              }
            }}
            className="py-2.5 px-3.5 rounded-xl bg-[#BBF7D0] hover:bg-emerald-300 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 text-xs font-black transition active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5 cursor-pointer"
            title="Kelola Toko Marketplace & Booth 3D"
          >
            <Store className="w-3.5 h-3.5 text-slate-950 stroke-[2.5px]" />
            <span>Toko & Booth 3D</span>
          </button>
        </div>

        {/* AI Agent Milik Saya Bar (Luna AI, Nova AI, Travel AI) */}
        <div className="mt-5 pt-4 border-t-2 border-slate-100">
          <div className="flex items-center justify-between mb-2.5">
            <h2 className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase tracking-wide">
              <Bot className="w-4 h-4 text-[#0284C7]" />
              <span>AI Agent Milik Saya ({ownedAgents.length})</span>
            </h2>
            <button
              onClick={onOpenTakeoverModal}
              className="text-xs text-blue-700 font-black hover:underline flex items-center gap-1 bg-sky-100 px-2.5 py-1 rounded-xl border border-sky-300"
            >
              <span>Mode Takeover</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Horizontal scroll cards of owned agents */}
          <div className="flex gap-3 overflow-x-auto pb-2 no-scrollbar">
            {ownedAgents.map((ag, idx) => {
              const bgColors = ['bg-[#BAE6FD]', 'bg-[#DDD6FE]', 'bg-[#FEF08A]'];
              const cardBg = bgColors[idx % bgColors.length];
              return (
                <div
                  key={ag.name}
                  onClick={() => setActiveProfileTab('AGENTS')}
                  className={`shrink-0 w-48 p-3 rounded-2xl ${cardBg} border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:brightness-95 transition flex items-center gap-3 cursor-pointer active:translate-x-0.5 active:translate-y-0.5`}
                >
                  <img
                    src={ag.avatar}
                    alt={ag.name}
                    className="w-10 h-10 rounded-xl object-cover border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a] shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1">
                      <p className="text-xs font-black text-slate-950 truncate">{ag.name}</p>
                      <span aria-label={ag.status} title={ag.status} className={`w-2 h-2 rounded-full border border-slate-900 ${ag.status === 'active' ? 'bg-emerald-500' : ag.status === 'draft' ? 'bg-amber-400' : 'bg-slate-400'}`} />
                    </div>
                    <p className="text-[10px] text-slate-700 font-bold truncate">{ag.specialty}</p>
                    <p className="text-[9px] text-slate-600 font-semibold">{ag.status === 'active' ? 'Aktif' : ag.status === 'draft' ? 'Draft' : ag.status === 'archived' ? 'Diarsipkan' : 'Status tidak tersedia'}</p>
                    {showCredits && ag.credits != null && (
                      <p className="text-[10px] font-mono font-black text-slate-950 mt-0.5">
                        +{ag.credits} Cr
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* THREADS PROFILE TABS: Konten, AI Agent, Disukai, Tentang */}
      <div className="sticky top-28 z-20 bg-white/95 backdrop-blur border-2 border-slate-900 rounded-2xl p-1.5 shadow-[3px_3px_0px_#0f172a] mb-4 flex items-center justify-between gap-1 overflow-x-auto no-scrollbar">
        <div className="flex items-center gap-1.5 text-xs font-black">
          <button
            onClick={() => setActiveProfileTab('KONTEN')}
            className={`px-3 py-1.5 rounded-xl border-2 transition active:translate-x-0.5 active:translate-y-0.5 ${
              activeProfileTab === 'KONTEN'
                ? 'bg-slate-900 text-white border-slate-900 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 border-transparent hover:bg-slate-100'
            }`}
          >
            Konten Feed
          </button>
          <button
            onClick={() => setActiveProfileTab('AGENTS')}
            className={`px-3 py-1.5 rounded-xl border-2 transition active:translate-x-0.5 active:translate-y-0.5 ${
              activeProfileTab === 'AGENTS'
                ? 'bg-[#0284C7] text-white border-slate-900 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 border-transparent hover:bg-slate-100'
            }`}
          >
            AI Agent ({ownedAgents.length})
          </button>
          <button
            onClick={() => setActiveProfileTab('LIKED')}
            className={`px-3 py-1.5 rounded-xl border-2 transition active:translate-x-0.5 active:translate-y-0.5 ${
              activeProfileTab === 'LIKED'
                ? 'bg-rose-500 text-white border-slate-900 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 border-transparent hover:bg-slate-100'
            }`}
          >
            Disukai
          </button>
          <button
            onClick={() => setActiveProfileTab('ABOUT')}
            className={`px-3 py-1.5 rounded-xl border-2 transition active:translate-x-0.5 active:translate-y-0.5 ${
              activeProfileTab === 'ABOUT'
                ? 'bg-amber-400 text-slate-950 border-slate-900 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 border-transparent hover:bg-slate-100'
            }`}
          >
            Tentang
          </button>
        </div>

        {/* View mode toggle button (List vs 3x3 Grid) */}
        {activeProfileTab === 'KONTEN' && (
          <div className="flex items-center bg-slate-100 p-1 rounded-xl border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
            <button
              onClick={() => setContentViewMode('LIST')}
              className={`p-1.5 rounded-lg transition ${
                contentViewMode === 'LIST' ? 'bg-white text-slate-950 font-black shadow-xs' : 'text-slate-600'
              }`}
              title="Tampilan Feed List"
            >
              <List className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setContentViewMode('GRID')}
              className={`p-1.5 rounded-lg transition ${
                contentViewMode === 'GRID' ? 'bg-white text-slate-950 font-black shadow-xs' : 'text-slate-600'
              }`}
              title="Tampilan Grid 3x3"
            >
              <Grid3X3 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* TAB 1: KONTEN / POSTINGAN SAYA (Feed Threads & Media Grid) */}
      {activeProfileTab === 'KONTEN' && (
        <div className="w-full">
          {contentViewMode === 'LIST' ? (
            <div className="space-y-3.5">
              {userPosts.length > 0 ? (
                userPosts.map((post) => (
                  <article key={post.id} className="p-4 sm:p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] transition">
                    {/* Header: Human & AI Badge */}
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="flex items-center gap-3">
                        <img
                          src={post.humanOwner.avatar}
                          alt={post.humanOwner.name}
                          className="w-10 h-10 rounded-xl object-cover border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
                        />
                        <div>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-black text-xs text-slate-900">{post.humanOwner.name}</span>
                            <span className="text-[10px] text-slate-500 font-bold">{post.humanOwner.handle}</span>
                          </div>
                          <div className="flex items-center gap-1 text-[11px] text-[#0284C7] font-black">
                            <Bot className="w-3.5 h-3.5" />
                            <span>{post.aiAgent.name}</span>
                            <span className="text-slate-500 font-bold">· Milik @{humanUser.username.replace('@', '')}</span>
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] font-bold text-slate-500 px-2 py-0.5 bg-slate-100 rounded-md border border-slate-300">
                        {post.timestamp}
                      </span>
                    </div>

                    {/* Content text */}
                    <div 
                      onClick={() => onSelectPost && onSelectPost(post)}
                      className="cursor-pointer space-y-2.5"
                    >
                      <p className="text-xs text-slate-900 leading-relaxed font-semibold whitespace-pre-line">
                        {post.content}
                      </p>

                      {/* Hashtags */}
                      {post.tags && (
                        <div className="flex flex-wrap gap-1.5">
                          {post.tags.map((t) => (
                            <span key={t} className="text-[11px] font-black px-2 py-0.5 rounded-lg bg-sky-100 text-sky-800 border border-sky-300 hover:bg-sky-200">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Attached Image (if applicable) */}
                      {post.image && (
                        <div className="rounded-2xl overflow-hidden border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] mt-2 bg-slate-950">
                          <img
                            src={post.image}
                            alt="Media Preview"
                            className="w-full max-h-72 object-cover hover:scale-[1.01] transition"
                          />
                        </div>
                      )}

                      {/* Attached 3D Model Card */}
                      {post.has3DModel && (
                        <div 
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenWorld3D();
                          }}
                          className="p-3 rounded-2xl bg-amber-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 flex items-center justify-between hover:bg-amber-200 transition active:translate-x-0.5 active:translate-y-0.5"
                        >
                          <div className="flex items-center gap-2">
                            <Box className="w-4 h-4 text-slate-950" />
                            <span className="text-xs font-black text-slate-950">
                              Aset 3D: {post.modelName}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-950 font-black flex items-center gap-0.5 bg-white px-2 py-0.5 rounded-lg border border-slate-900">
                            Buka 3D <ArrowUpRight className="w-3 h-3" />
                          </span>
                        </div>
                      )}

                      {/* Action buttons row */}
                      <div className="flex items-center justify-between pt-2 text-slate-800 text-xs border-t border-slate-100">
                        <div className="flex items-center gap-4">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onLikePost && onLikePost(post.id);
                            }}
                            className={`flex items-center gap-1.5 font-black transition active:scale-95 ${
                              post.isLiked ? 'text-rose-600' : 'hover:text-rose-600'
                            }`}
                          >
                            <Heart className={`w-4 h-4 ${post.isLiked ? 'fill-rose-600' : ''}`} />
                            <span>{post.likes}</span>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectPost && onSelectPost(post);
                            }}
                            className="flex items-center gap-1.5 font-black hover:text-blue-600 transition"
                          >
                            <MessageCircle className="w-4 h-4" />
                            <span>{post.commentsCount}</span>
                          </button>
                          <button 
                            onClick={(e) => {
                              e.stopPropagation();
                              if (navigator.clipboard) {
                                navigator.clipboard.writeText(post.content);
                                showToast('Konten postingan berhasil disalin ke clipboard!');
                              }
                            }}
                            className="flex items-center gap-1.5 font-black hover:text-emerald-600 transition"
                          >
                            <Repeat2 className="w-4 h-4" />
                            <span>{post.reposts}</span>
                          </button>
                        </div>

                        {onOpenAskAi && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty);
                            }}
                            className="px-3 py-1 rounded-xl bg-sky-100 hover:bg-sky-200 text-sky-900 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] font-black text-xs transition flex items-center gap-1 active:translate-x-0.5 active:translate-y-0.5"
                          >
                            <Bot className="w-3.5 h-3.5" />
                            <span>Tanya AI</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <div className="p-8 text-center text-slate-600 bg-white rounded-3xl border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
                  <p className="text-xs font-bold">Belum ada postingan di profil ini.</p>
                </div>
              )}
            </div>
          ) : (
            /* 3x3 Media Grid View */
            <div className="grid grid-cols-3 gap-2.5">
              {userPosts.map((post) => (
                <div
                  key={post.id}
                  onClick={() => onSelectPost && onSelectPost(post)}
                  className="aspect-square bg-slate-900 rounded-2xl overflow-hidden relative cursor-pointer group border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]"
                >
                  <img
                    src={post.image || "/icon.svg"}
                    alt="Grid thumbnail"
                    className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                  />
                  <div className="absolute inset-0 bg-slate-900/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-3 text-white text-xs font-black">
                    <span className="flex items-center gap-1">
                      <Heart className="w-3.5 h-3.5 fill-white" />
                      {post.likes}
                    </span>
                    <span className="flex items-center gap-1">
                      <MessageCircle className="w-3.5 h-3.5 fill-white" />
                      {post.commentsCount}
                    </span>
                  </div>
                  {post.has3DModel && (
                    <div className="absolute top-1.5 right-1.5 p-1 rounded-lg bg-amber-400 text-slate-950 border border-slate-900 shadow-xs">
                      <Box className="w-3 h-3" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: AI AGENT (3) DETAIL CARDS & 3D IDENTITY STUDIO */}
      {activeProfileTab === 'AGENTS' && (
        <div className="space-y-4">
          <div className="p-3.5 rounded-2xl bg-purple-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between">
            <div>
              <h3 className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase">
                <Bot className="w-4 h-4 text-purple-700" />
                <span>AI Agent Identity & Studio Otonom</span>
              </h3>
              <p className="text-[11px] text-slate-700 font-semibold">
                Kelola avatar 3D, bidang profesi, katalog skills, dan delegasi tugas otonom
              </p>
            </div>
            {showCredits && hasAgentProfile && (
              <span className="text-xs font-mono font-black text-slate-950 bg-amber-300 px-3 py-1 rounded-xl border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
                +{agentProfile.creditsEarned} Cr
              </span>
            )}
          </div>

          {/* PRIMARY AI AGENT HERO CARD */}
          <div className="p-5 rounded-3xl bg-slate-900 text-white space-y-4 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3.5">
                {/* 3D Avatar with Glowing Ring */}
                <div className="relative shrink-0">
                  <div className="w-16 h-16 rounded-2xl overflow-hidden ring-2 ring-cyan-400 bg-black border-2 border-white">
                    <img
                      src={hasAgentProfile ? (agentProfile.avatar3DImage || agentProfile.avatar) : "/icon.svg"}
                      alt={hasAgentProfile ? agentProfile.name : agentStatusLabel}
                      className="w-full h-full object-cover object-top hover:scale-105 transition"
                    />
                  </div>
                  <span className="absolute -bottom-1 -right-1 px-1.5 py-0.2 rounded-md bg-cyan-400 text-slate-950 font-mono font-black text-[8px] uppercase tracking-wider border border-slate-900">
                    3D RIG
                  </span>
                </div>

                <div className="space-y-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="font-black text-base text-white">{hasAgentProfile ? agentProfile.name : agentStatusLabel}</h4>
                    <span className="text-[10px] px-2.5 py-0.5 rounded-lg bg-cyan-400 text-slate-950 font-black border border-cyan-300">
                      {agentProfile.bidang || 'Desain Grafis'}
                    </span>
                    <span className="text-[9px] px-2 py-0.5 rounded-lg bg-white/20 text-white font-mono font-bold">
                      {agentProfile.avatar3DCodename || (hasAgentProfile ? '—' : 'Belum ada Agent')}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 font-mono">
                    {agentProfile.handle} • Milik <strong>@{humanUser.username.replace('@', '')}</strong>
                  </p>
                  <p className="text-xs text-slate-200 font-semibold pt-0.5">
                    {agentProfile.specialty}
                  </p>
                </div>
              </div>

              <div className="text-right shrink-0">
                <span className={`text-[10px] px-2.5 py-1 rounded-xl font-black border border-slate-900 ${
                  isTakeoverActive 
                    ? 'bg-amber-400 text-slate-950' 
                    : 'bg-emerald-400 text-slate-950'
                }`}>
                  {isTakeoverActive ? 'Takeover Human' : 'Auto-Reply Aktif'}
                </span>
              </div>
            </div>

            {/* Active Skills Catalog Chips */}
            <div className="space-y-1.5 pt-2 border-t border-slate-800">
              <span className="text-[10px] font-black text-slate-300 uppercase tracking-wider">
                Katalog Skills Aktif ({agentProfile.skills?.length || 0}):
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(agentProfile.skills || []).map((sk) => (
                  <span
                    key={sk}
                    className="text-[10px] px-2.5 py-1 rounded-xl bg-slate-800 text-cyan-200 border border-slate-700 font-bold"
                  >
                    ✓ {sk}
                  </span>
                ))}
              </div>
            </div>

            {/* Core Action Buttons */}
            <div className="pt-2 flex flex-wrap gap-2.5">
              <button
                onClick={() => { if (hasAgentProfile && onUpdateAgent) setIsIdentityModalOpen(true); else showToast('Identitas Agent belum tersedia atau endpoint penyimpanan belum terhubung.'); }}
                className="flex-1 min-w-[140px] py-2.5 px-3.5 rounded-xl bg-sky-400 hover:bg-sky-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5"
              >
                <Palette className="w-4 h-4 text-slate-950" />
                <span>Ubah Bidang & 3D Avatar</span>
              </button>

              <button
                onClick={() => { if (hasAgentProfile && onUpdateAgent) setIsGoalsTasksModalOpen(true); else showToast('Goals & Tasks belum terhubung ke Agent Runtime API.'); }}
                className="flex-1 min-w-[140px] py-2.5 px-3.5 rounded-xl bg-purple-400 hover:bg-purple-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5"
              >
                <Target className="w-4 h-4 text-slate-950" />
                <span>Target & Tugas Otonom</span>
              </button>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-300 pt-2 border-t border-slate-800">
              <button
                onClick={onOpenTakeoverModal}
                className="text-xs text-cyan-300 hover:text-white underline font-black"
              >
                Pengaturan Takeover Mode →
              </button>
              {onOpenAskAi && (
                <button
                  onClick={() => onOpenAskAi(agentProfile.name, humanUser.name, agentProfile.specialty)}
                  className="px-3 py-1.5 rounded-xl bg-white/20 hover:bg-white/30 text-white text-xs font-black transition flex items-center gap-1 border border-white/30"
                >
                  <Bot className="w-3.5 h-3.5 text-cyan-300" />
                  <span>Uji Percakapan AI</span>
                </button>
              )}
            </div>
          </div>

          {/* QUICK AUTONOMOUS TASKS PREVIEW WIDGET */}
          <div className="p-4 rounded-3xl bg-[#FEF08A] border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-slate-950" />
                <h4 className="text-xs font-black text-slate-950 uppercase">
                  Tugas Otonom Terjadwal ({agentProfile.tasks?.length || 4})
                </h4>
              </div>
              <button
                onClick={() => { if (hasAgentProfile && onUpdateAgent) setIsGoalsTasksModalOpen(true); else showToast('Goals & Tasks belum terhubung ke Agent Runtime API.'); }}
                className="text-xs text-slate-950 font-black hover:underline"
              >
                Kelola Semua →
              </button>
            </div>

            <div className="space-y-2">
              {(agentProfile.tasks || []).slice(0, 2).map((t) => (
                <div
                  key={t.id}
                  className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-between gap-2 text-xs"
                >
                  <div className="space-y-0.5 min-w-0">
                    <p className="font-black text-slate-900 truncate text-xs">{t.title}</p>
                    <p className="text-[10px] text-slate-600 font-mono font-bold">
                      Frekuensi: {t.frequency} • {t.scheduledTime}
                    </p>
                  </div>
                  <span className="shrink-0 text-[10px] px-2.5 py-1 rounded-xl font-black bg-emerald-100 text-emerald-800 border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
                    {t.autonomousExecution ? 'Otonom AI' : 'Manual'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Sub-Agents List */}
          <div className="pt-2">
            <h4 className="text-xs font-black text-slate-700 uppercase tracking-wider mb-2.5">
              AI Agent Companion Lainnya
            </h4>
            <div className="space-y-2.5">
              {ownedAgents.filter(a => a.name !== agentProfile.name).map((ag, idx) => {
                const bgColors = ['bg-[#DDD6FE]', 'bg-[#BAE6FD]'];
                const cardBg = bgColors[idx % bgColors.length];
                return (
                  <div
                    key={ag.name}
                    className={`p-3.5 rounded-2xl ${cardBg} border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between gap-3`}
                  >
                    <div className="flex items-center gap-3">
                      <img
                        src={ag.avatar}
                        alt={ag.name}
                        className="w-11 h-11 rounded-xl object-cover border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]"
                      />
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h5 className="font-black text-xs text-slate-950">{ag.name}</h5>
                          <span className="text-[9px] px-2 py-0.5 rounded-md bg-white text-slate-900 font-mono font-black border border-slate-900">
                            {ag.handle}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-800 font-bold">{ag.specialty}</p>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      {showCredits && ag.credits != null && (
                        <span className="font-mono font-black text-xs text-slate-950 bg-white px-2.5 py-1 rounded-xl border border-slate-900">
                          +{ag.credits} Cr
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: DISUKAI */}
      {activeProfileTab === 'LIKED' && (
        <div className="space-y-3">
          <p className="text-xs text-slate-700 font-black px-1">Postingan yang Disukai oleh Anda:</p>
          {posts.slice(0, 3).map((p) => (
            <div key={p.id} className="p-4 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-3">
              <Heart className="w-5 h-5 text-rose-500 fill-rose-500 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-black text-slate-900">{p.humanOwner.name} & {p.aiAgent.name}</p>
                <p className="text-xs text-slate-700 font-semibold line-clamp-2 mt-0.5">{p.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 4: TENTANG (Master PRD Compliance) */}
      {activeProfileTab === 'ABOUT' && (
        <div className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3.5">
          <h4 className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase">
            <Shield className="w-4 h-4 text-[#0284C7]" />
            <span>Verifikasi Identitas & Master PRD Contract</span>
          </h4>
          <div className="text-xs text-slate-700 font-semibold space-y-2">
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Status Identitas:</span>
              <span className="font-black text-emerald-700">Terverifikasi (KYC L2)</span>
            </div>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Bergabung Sejak:</span>
              <span className="font-black text-slate-900">Oktober 2026</span>
            </div>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Ekosistem:</span>
              <span className="font-black text-slate-900">ALLPHA UNIVERSE v3.0</span>
            </div>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Public Ledger Hash:</span>
              <span className="font-mono text-[10px] text-slate-700 font-bold">Belum terhubung</span>
            </div>
          </div>
        </div>
      )}

      {/* THREADS-STYLE SETTINGS MODAL / SLIDE-OVER DRAWER */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/80 backdrop-blur-xs p-3 transition">
          <div className="w-full max-w-lg bg-white rounded-3xl shadow-[6px_6px_0px_#0f172a] border-3 border-slate-900 overflow-hidden max-h-[90vh] flex flex-col animate-in fade-in slide-in-from-bottom-6 duration-200">
            {/* Modal Header */}
            <div className="px-5 py-4 border-b-2 border-slate-900 flex items-center justify-between bg-[#F4F7FB]">
              <div className="flex items-center gap-2">
                <Settings className="w-5 h-5 text-slate-900" />
                <h3 className="font-black text-sm tracking-tight text-slate-900 uppercase">
                  Pengaturan & Akun Threads
                </h3>
              </div>
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setSelectedSettingDetail(null);
                }}
                className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-100 transition active:translate-x-0.5 active:translate-y-0.5"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Settings Options List (Instagram / Threads Style Complete Suite) */}
            <div className="p-4 overflow-y-auto space-y-2 text-xs">
              
              {/* 1. CREATOR STUDIO HUB (Featured Option) */}
              <button
                onClick={() => { if (showCredits && onDeductCredits) setIsCreatorStudioOpen(true); else showToast('Creator Studio belum terhubung ke saldo dan billing kanonis.'); }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-[#FEF08A]/70 hover:bg-[#FEF08A] border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Wand2 className="w-4.5 h-4.5 text-purple-800" />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <p className="font-black text-slate-900">Creator Studio & AI Hub</p>
                      <span className="text-[9px] font-black px-1.5 py-0.2 rounded bg-purple-600 text-white uppercase">Multi-Modal</span>
                    </div>
                    <p className="text-[11px] font-bold text-slate-700">Generate Image, Text, Video, Docs, Coding, & Film AI</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-900" />
              </button>

              {/* 1.5 BUAT TOKO MARKETPLACE & BOOTH 3D SPATIAL */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  if (onOpenStoreAndBooth) {
                    onOpenStoreAndBooth();
                  } else {
                    setIsStoreAndBoothModalOpen(true);
                  }
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-[#BBF7D0]/70 hover:bg-[#BBF7D0] border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Store className="w-4.5 h-4.5 text-emerald-800" />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <p className="font-black text-slate-900">Buat Toko Marketplace & Booth 3D</p>
                      <span className="text-[9px] font-black px-1.5 py-0.2 rounded bg-emerald-700 text-white uppercase">3D Spatial</span>
                    </div>
                    <p className="text-[11px] font-bold text-slate-700">Atur brand, produk digital & fisik, serta stan pameran di distrik 3D</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-900" />
              </button>

              {/* 2. DASHBOARD ANALYTICS INSIGHT KUNJUNGAN */}
              <button
                onClick={() => setSelectedSettingDetail('ANALYTICS_VISITS')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <BarChart2 className="w-4.5 h-4.5 text-sky-600" />
                  <div>
                    <p className="font-black text-slate-900">Dashboard Analytics & Insight Kunjungan</p>
                    <p className="text-[11px] font-bold text-slate-500">Statistik pengunjung profil, jangkauan post, & followers</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 3. DASHBOARD FINANCIAL, REVENUE & WITHDRAW */}
              <button
                onClick={() => setSelectedSettingDetail('FINANCIAL_WITHDRAW')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-emerald-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <DollarSign className="w-4.5 h-4.5 text-emerald-600" />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <p className="font-black text-slate-900">Pendapatan, Unit Economics & Withdraw</p>
                      <span className="text-[9px] font-black px-1.5 py-0.2 rounded bg-emerald-200 text-emerald-950 uppercase border border-emerald-400">85% Share</span>
                    </div>
                    <p className="text-[11px] font-bold text-slate-500">Bagi hasil royalti kreator, rekening bank, & tarik saldo</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 4. TOPUP AI CREDITS & PEMAKAIAN */}
              <button
                onClick={() => setSelectedSettingDetail('TOPUP_CREDITS')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Coins className="w-4.5 h-4.5 text-amber-600" />
                  <div>
                    <p className="font-black text-slate-900">Top-Up AI Credits & Mutasi Ledger</p>
                    <p className="text-[11px] font-bold text-slate-500">Saldo saat ini, paket beli kredit IDR, & riwayat pemakaian</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 5. ARSIP KONTEN (POST, STORIES, REELS) */}
              <button
                onClick={() => setSelectedSettingDetail('ARCHIVE')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Archive className="w-4.5 h-4.5 text-purple-600" />
                  <div>
                    <p className="font-black text-slate-900">Arsip Konten & Moment</p>
                    <p className="text-[11px] font-bold text-slate-500">Postingan, reels, dan stories yang diarsipkan</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* TOKO MARKETPLACE & BOOTH 3D SPATIAL */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  if (onOpenStoreAndBooth) {
                    onOpenStoreAndBooth();
                  } else {
                    setIsStoreAndBoothModalOpen(true);
                  }
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-emerald-50 hover:bg-emerald-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Store className="w-4.5 h-4.5 text-emerald-800 stroke-[2.5px]" />
                  <div>
                    <p className="font-black text-slate-900">Buat Toko Marketplace & Booth 3D</p>
                    <p className="text-[11px] font-bold text-slate-600">Atur nama brand, etalase produk digital/fisik, & stan pameran 3D distrik</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 6. SETTING BIO, AVATAR, BIDANG & SKILLS */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setIsIdentityModalOpen(true);
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-pink-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <User className="w-4.5 h-4.5 text-pink-600" />
                  <div>
                    <p className="font-black text-slate-900">Setting Bio, Avatar, Bidang & Skills</p>
                    <p className="text-[11px] font-bold text-slate-500">Katalog avatar 3D, bidang profesi, & konfigurasi skill</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 7. OFFICIAL AGENT PASSPORT */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  if (hasAgentProfile) setIsPassportOpen(true); else showToast('Agent Passport belum tersedia karena belum ada Agent aktif.');
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-indigo-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <ShieldCheck className="w-4.5 h-4.5 text-indigo-600" />
                  <div>
                    <p className="font-black text-slate-900">AI Agent Passport & ERC-6551</p>
                    <p className="text-[11px] font-bold text-slate-500">Sertifikat identitas resmi, chip digital, & matrix radar</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 8. PLUGIN, CONNECTOR & DOKUMEN RAG */}
              <button
                onClick={() => setSelectedSettingDetail('PLUGINS_RAG')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-cyan-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Plug className="w-4.5 h-4.5 text-cyan-600" />
                  <div>
                    <p className="font-black text-slate-900">Plugin, Connector & Dokumen RAG</p>
                    <p className="text-[11px] font-bold text-slate-500">Upload PDF, hubungkan REST API, & basis pengetahuan</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 9. KATALOG TEMA SPATIAL & UI */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setIsThemeCatalogOpen(true);
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Palette className="w-4.5 h-4.5 text-amber-600" />
                  <div>
                    <p className="font-black text-slate-900">Katalog Tema & Tampilan Spatial</p>
                    <p className="text-[11px] font-bold text-slate-500">Pilih tema Soft Pastel Menggu, Neo-Brutal, Cyberpunk</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 10. PILIHAN BAHASA / LANGUAGE */}
              <button
                onClick={() => onOpenAccountSettings ? onOpenAccountSettings("profile") : setSelectedSettingDetail('LANGUAGE')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-slate-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Globe className="w-4.5 h-4.5 text-slate-700" />
                  <div>
                    <p className="font-black text-slate-900">Bahasa / Language: 🇮🇩 Indonesia</p>
                    <p className="text-[11px] font-bold text-slate-500">Ganti ke Bahasa Inggris atau Jepang</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 11. PRIVASI & DATA MASTER PRD */}
              <button
                onClick={() => onOpenAccountSettings ? onOpenAccountSettings("settings") : setSelectedSettingDetail('PRIVACY')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Shield className="w-4.5 h-4.5 text-purple-600" />
                  <div>
                    <p className="font-black text-slate-900">Privasi & Isolasi Memori (Part XV)</p>
                    <p className="text-[11px] font-bold text-slate-500">Isolasi data pribadi vs memori publik</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* 12. LOGOUT & CABUT SESI */}
              <button
                onClick={() => setSelectedSettingDetail('SESSION')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-rose-50 hover:bg-rose-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <LogOut className="w-4.5 h-4.5 text-rose-600" />
                  <div>
                    <p className="font-black text-rose-950">Keamanan Sesi & Logout</p>
                    <p className="text-[11px] font-bold text-rose-700">Cabut izin perangkat & keluar akun</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

            </div>

            {/* SUB-DETAIL PANELS */}
            
            {/* SUB-DETAIL 1: ANALYTICS VISITS */}
            {selectedSettingDetail === 'ANALYTICS_VISITS' && (
              <div className="p-4 bg-sky-50 border-t-2 border-slate-900 text-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-black text-sky-950 text-xs uppercase flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4 text-sky-700" />
                    <span>Statistik & Insight Kunjungan</span>
                  </h4>
                  <span className="text-[10px] font-bold text-sky-800">30 Hari Terakhir</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900">
                    <p className="text-[9.5px] font-bold text-slate-500 uppercase">Total Profil Views</p>
                    <p className="text-base font-black text-slate-900 font-mono">142.840</p>
                    <span className="text-[9px] text-emerald-600 font-bold">▲ +24.8% bln ini</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900">
                    <p className="text-[9.5px] font-bold text-slate-500 uppercase">Jangkauan Postingan</p>
                    <p className="text-base font-black text-slate-900 font-mono">489.200</p>
                    <span className="text-[9px] text-emerald-600 font-bold">▲ +38.1% bln ini</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900">
                    <p className="text-[9.5px] font-bold text-slate-500 uppercase">Pertumbuhan Followers</p>
                    <p className="text-base font-black text-slate-900 font-mono">+12.450</p>
                    <span className="text-[9px] text-emerald-600 font-bold">▲ 18.2% conversion</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900">
                    <p className="text-[9.5px] font-bold text-slate-500 uppercase">Tanya Jawab AI Agent</p>
                    <p className="text-base font-black text-slate-900 font-mono">1.820 Sesi</p>
                    <span className="text-[9px] text-purple-600 font-bold">🪙 Saldo belum tersedia</span>
                  </div>
                </div>
              </div>
            )}

            {/* SUB-DETAIL 2: FINANCIAL, REVENUE & WITHDRAW */}
            {selectedSettingDetail === 'FINANCIAL_WITHDRAW' && (
              <div className="p-4 bg-emerald-50 border-t-2 border-slate-900 text-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-black text-emerald-950 text-xs uppercase flex items-center gap-1.5">
                    <Wallet className="w-4 h-4 text-emerald-700" />
                    <span>Unit Economics & Penarikan Saldo</span>
                  </h4>
                  <span className="text-[9px] font-black px-2 py-0.5 rounded-md bg-emerald-200 text-emerald-950 border border-emerald-400">
                    Royalti Kreator: 85%
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-white border-2 border-slate-900 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600 font-bold">Total Pendapatan Akumulasi:</span>
                    <span className="font-mono font-black text-slate-900">Belum tersedia</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600 font-bold">Platform Fee (15%):</span>
                    <span className="font-mono font-black text-slate-400">Belum tersedia</span>
                  </div>
                  <div className="flex justify-between items-center border-t border-slate-200 pt-1.5">
                    <span className="text-emerald-950 font-black">Saldo Bersih Siap Ditarik:</span>
                    <span className="font-mono font-black text-base text-emerald-700">Belum tersedia</span>
                  </div>
                </div>

                {/* Withdraw Form */}
                <div className="space-y-2 pt-1">
                  <label className="text-[11px] font-black text-slate-900 block">Formulir Penarikan Saldo (Withdraw):</label>
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={withdrawBank}
                      onChange={(e) => setWithdrawBank(e.target.value)}
                      className="px-2.5 py-1.5 bg-white rounded-xl border border-slate-900 font-bold"
                    >
                      <option value="BCA">Bank BCA</option>
                      <option value="Mandiri">Bank Mandiri</option>
                      <option value="BNI">Bank BNI</option>
                      <option value="GoPay">GoPay (0812-xxxx)</option>
                    </select>
                    <input
                      type="text"
                      value={withdrawAccount}
                      onChange={(e) => setWithdrawAccount(e.target.value)}
                      placeholder="Nomor Rekening"
                      className="px-2.5 py-1.5 bg-white rounded-xl border border-slate-900 font-mono font-bold"
                    />
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={withdrawAmount}
                      onChange={(e) => setWithdrawAmount(e.target.value)}
                      placeholder="Jumlah Penarikan (Rp)"
                      className="flex-1 px-3 py-1.5 bg-white rounded-xl border border-slate-900 font-mono font-bold"
                    />
                    <button
                      onClick={() => {
                        showToast('Penarikan belum terhubung ke layanan keuangan. Tidak ada transaksi yang dibuat.');
                      }}
                      className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-black rounded-xl border border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
                    >
                      Tarik Dana
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* SUB-DETAIL 3: TOPUP CREDITS */}
            {selectedSettingDetail === 'TOPUP_CREDITS' && (
              <div className="p-4 bg-amber-50 border-t-2 border-slate-900 text-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-black text-amber-950 text-xs uppercase flex items-center gap-1.5">
                    <Coins className="w-4 h-4 text-amber-600" />
                    <span>Top-Up AI Credits & Mutasi</span>
                  </h4>
                  <span className="font-mono font-black text-xs text-amber-900">Saldo: {showCredits ? userCredits.toLocaleString('id-ID') : '—'} Cr</span>
                </div>

                <div className="space-y-1.5">
                  <p className="text-[11px] font-bold text-slate-700">Pilih Paket Isi Ulang AI Credits:</p>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { cr: null, price: 'Harga belum tersedia' },
                      { cr: null, price: 'Harga belum tersedia' },
                      { cr: null, price: 'Harga belum tersedia' }
                    ].map((pkg) => (
                      <button
                        key={pkg.cr}
                        onClick={() => {
                          showToast('Pembelian AI Credits belum terhubung ke payment provider. Tidak ada kredit yang ditambahkan.');
                        }}
                        className="p-2.5 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] hover:bg-amber-100 text-center cursor-pointer transition active:translate-x-0.5 active:translate-y-0.5"
                      >
                        <p className="font-mono font-black text-sm text-slate-900">{pkg.cr == null ? "— Cr" : `+${pkg.cr} Cr`}</p>
                        <p className="text-[10px] font-bold text-slate-600 mt-0.5">{pkg.price}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-DETAIL 4: ARSIP KONTEN */}
            {selectedSettingDetail === 'ARCHIVE' && (
              <div className="p-4 bg-purple-50 border-t-2 border-slate-900 text-xs space-y-2.5">
                <h4 className="font-black text-purple-950 text-xs uppercase flex items-center gap-1.5">
                  <Archive className="w-4 h-4 text-purple-700" />
                  <span>Arsip Konten & Media Anda</span>
                </h4>
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900 text-center">
                    <p className="text-base font-black text-slate-900">12</p>
                    <p className="text-[10px] font-bold text-slate-500">Postingan Arsip</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900 text-center">
                    <p className="text-base font-black text-slate-900">28</p>
                    <p className="text-[10px] font-bold text-slate-500">Stories Arsip</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white border border-slate-900 text-center">
                    <p className="text-base font-black text-slate-900">5</p>
                    <p className="text-[10px] font-bold text-slate-500">Reels Arsip</p>
                  </div>
                </div>
                <p className="text-[10.5px] text-purple-800 font-medium">
                  Hanya Anda yang dapat melihat konten yang diarsipkan. Konten dapat dipulihkan ke profil kapan saja.
                </p>
              </div>
            )}

            {/* SUB-DETAIL 5: PLUGIN & RAG KNOWLEDGE */}
            {selectedSettingDetail === 'PLUGINS_RAG' && (
              <div className="p-4 bg-cyan-50 border-t-2 border-slate-900 text-xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <h4 className="font-black text-cyan-950 text-xs uppercase flex items-center gap-1.5">
                    <Plug className="w-4 h-4 text-cyan-700" />
                    <span>Knowledge Base & Connectors RAG</span>
                  </h4>
                  <span className="text-[10px] font-bold text-cyan-800">{knowledgeDocs.length} Terindeks</span>
                </div>
                <p className="text-[11px] text-slate-700 font-semibold leading-relaxed">
                  Unggah file PDF atau sambungkan API eksternal agar AI Agent dapat menjawab pertanyaan pengguna dengan data spesifik Anda.
                </p>
                <button
                  onClick={() => {
                    setIsSettingsOpen(false);
                    onOpenCreditsHub();
                  }}
                  className="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-black text-xs border border-slate-900 shadow-[1px_1px_0px_#0f172a]"
                >
                  Buka Knowledge & Skills Challenge Hub →
                </button>
              </div>
            )}

            {/* SUB-DETAIL 6: LANGUAGE SELECTOR */}
            {selectedSettingDetail === 'LANGUAGE' && (
              <div className="p-4 bg-slate-100 border-t-2 border-slate-900 text-xs space-y-2.5">
                <h4 className="font-black text-slate-900 text-xs uppercase flex items-center gap-1.5">
                  <Globe className="w-4 h-4 text-slate-700" />
                  <span>Pilihan Bahasa Sistem & AI:</span>
                </h4>
                <div className="space-y-1.5">
                  {[
                    { code: 'id', name: 'Bahasa Indonesia', flag: '🇮🇩' },
                    { code: 'en', name: 'English (US)', flag: '🇺🇸' },
                    { code: 'ja', name: '日本語 (Japanese)', flag: '🇯🇵' },
                  ].map((lang) => (
                    <button
                      key={lang.code}
                      onClick={() => {
                        setSettingsLang(lang.code as any);
                        showToast(`Bahasa diatur ke ${lang.name} ${lang.flag}`);
                        setSelectedSettingDetail(null);
                      }}
                      className={`w-full p-2.5 rounded-xl border-2 border-slate-900 flex items-center justify-between transition ${
                        settingsLang === lang.code ? 'bg-[#FEF08A] font-black' : 'bg-white hover:bg-slate-50 font-bold'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span>{lang.flag}</span>
                        <span>{lang.name}</span>
                      </span>
                      {settingsLang === lang.code && <span>✓ Aktif</span>}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* SUB-DETAIL 7: PRIVACY (Part XV) */}
            {selectedSettingDetail === 'PRIVACY' && (
              <div className="p-4 bg-purple-50 border-t-2 border-slate-900 text-xs space-y-2">
                <h4 className="font-black text-purple-950">Isolasi Memori & Privasi (Master PRD Part XV):</h4>
                <p className="text-purple-900 font-semibold leading-relaxed text-[11px]">
                  Memori privat pemilik agen tidak pernah dibagikan kepada pengguna eksternal. Hanya modul pengetahuan yang telah diverifikasi dan disetujui yang dapat diakses oleh publik.
                </p>
                <div className="flex items-center justify-between pt-1">
                  <span className="font-bold text-purple-950">Enkripsi End-to-End:</span>
                  <span className="px-2.5 py-0.5 rounded-lg bg-emerald-300 text-slate-950 font-black text-[10px] border border-slate-900">BELUM DIVERIFIKASI</span>
                </div>
              </div>
            )}

            {/* SUB-DETAIL 8: SESSION & LOGOUT */}
            {selectedSettingDetail === 'SESSION' && (
              <div className="p-4 bg-rose-50 border-t-2 border-slate-900 text-xs space-y-2.5">
                <h4 className="font-black text-rose-950">Sesi Login Aktif & Keamanan:</h4>
                <p className="text-rose-900 font-bold text-[11px]">
                  • Status sesi aktif akan ditampilkan setelah layanan keamanan terhubung.
                </p>
                <div className="flex gap-2 pt-1">
                  <button 
                    onClick={() => {
                      if (!onRevokeOtherSessions) { showToast("Pencabutan sesi lain belum tersedia."); return; }
                      void onRevokeOtherSessions().then(() => showToast("Sesi perangkat lain berhasil dicabut.")).catch((cause) => showToast(cause instanceof Error ? cause.message : "Pencabutan sesi gagal."));
                    }}
                    className="flex-1 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-black text-xs border border-slate-900 shadow-[1px_1px_0px_#0f172a]"
                  >
                    Cabut Sesi Lain
                  </button>
                  <button 
                    onClick={() => {
                      if (!onLogout) { showToast("Logout belum tersedia pada adapter autentikasi."); return; }
                      void onLogout().catch((cause) => showToast(cause instanceof Error ? cause.message : "Logout gagal."));
                    }}
                    className="flex-1 px-3 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs border border-slate-900 shadow-[1px_1px_0px_#0f172a]"
                  >
                    Logout Akun
                  </button>
                </div>
              </div>
            )}

            {/* Footer Close */}
            <div className="p-3.5 border-t-2 border-slate-900 bg-slate-50 flex justify-end">
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setSelectedSettingDetail(null);
                }}
                className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Toast Notification */}
      {toastMsg && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 bg-slate-900/95 text-white px-4 py-2.5 rounded-full text-xs font-semibold shadow-xl flex items-center gap-2 border border-slate-700 backdrop-blur-md animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* AI Agent Identity Modal (Bidang, Skills Catalog, 3D Avatar Catalog) */}
      <AgentIdentityModal
        isOpen={isIdentityModalOpen}
        onClose={() => setIsIdentityModalOpen(false)}
        agent={agentProfile}
        onSaveAgent={(updated) => {
          if (onUpdateAgent) onUpdateAgent(updated);
          showToast(onUpdateAgent ? `Perubahan identitas ${updated.name} diteruskan ke adapter.` : "Endpoint penyimpanan identitas Agent belum terhubung.");
        }}
      />

      {/* Autonomous Goals & Tasks Modal */}
      <AgentGoalsTasksModal
        isOpen={isGoalsTasksModalOpen}
        onClose={() => setIsGoalsTasksModalOpen(false)}
        agent={agentProfile}
        onUpdateAgent={(updated) => {
          if (onUpdateAgent) onUpdateAgent(updated);
        }}
        onToast={(msg) => showToast(msg)}
      />

      {/* AI Agent Passport Modal */}
      <AgentPassportModal
        isOpen={isPassportOpen}
        onClose={() => setIsPassportOpen(false)}
        agent={agentProfile}
        owner={humanUser}
      />

      {/* Allpha Creator Studio Modal */}
      <CreatorStudioModal
        isOpen={isCreatorStudioOpen}
        onClose={() => setIsCreatorStudioOpen(false)}
        agent={agentProfile}
        user={humanUser}
        userCredits={userCredits}
        onDeductCredits={(amount, reason) => {
          if (onDeductCredits) {
            onDeductCredits(amount, reason);
          }
        }}
        onOpenFilmAi={onOpenFilmAi}
      />

      {/* Theme Catalog Modal */}
      <ThemeCatalogModal
        isOpen={isThemeCatalogOpen}
        onClose={() => setIsThemeCatalogOpen(false)}
        onSelectTheme={(_id, _name) => {
          showToast("Penerapan tema belum terhubung ke layanan tema kanonis.");
          return false;
        }}
      />

    </div>
  );
}

