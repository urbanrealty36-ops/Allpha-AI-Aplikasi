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
  Store
} from 'lucide-react';
import type { HumanProfile, AIAgentProfile, KnowledgeDocument, PostItem } from '@/lib/reference-store';
import AgentIdentityModal from './AgentIdentityModal';
import AgentGoalsTasksModal from './AgentGoalsTasksModal';
import StoreAndBoothModal from './StoreAndBoothModal';
import ThemeCatalogModal from './ThemeCatalogModal';
import CreatorStudioModal from './CreatorStudioModal';

interface ProfileViewProps {
  humanUser: HumanProfile;
  agentProfile: AIAgentProfile | null;
  ownedAgents?: Array<{ name: string; handle: string; specialty: string; avatar: string; status: string; credits?: number | null }>;
  showCredits?: boolean;
  showSocialCounts?: boolean;
  humanVerified?: boolean;
  agentStatusLabel?: string;
  onOpenAccountSettings?: () => void;
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
  onUpdateAgent?: (updatedAgent: AIAgentProfile) => void | Promise<void>;
}

export default function ProfileView({
  humanUser,
  agentProfile,
  ownedAgents: ownedAgentsFromApi = [],
  showCredits = false,
  showSocialCounts = false,
  humanVerified = false,
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
  onOpenAccountSettings,
}: ProfileViewProps) {
  // Tabs: Konten, AI Agent, Disukai, Tentang
  const [activeProfileTab, setActiveProfileTab] = useState<'KONTEN' | 'AGENTS' | 'LIKED' | 'ABOUT'>('KONTEN');
  
  // View mode for posts: List (Threads style) or Grid (Instagram style from screenshot 8)
  const [contentViewMode, setContentViewMode] = useState<'LIST' | 'GRID'>('LIST');

  // Threads-style Settings Drawer / Sheet State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [selectedSettingDetail, setSelectedSettingDetail] = useState<string | null>(null);

  // AI Agent Identity & Goals/Tasks Modals State
  const [isIdentityModalOpen, setIsIdentityModalOpen] = useState(false);
  const [isGoalsTasksModalOpen, setIsGoalsTasksModalOpen] = useState(false);
  const [isStoreModalOpen, setIsStoreModalOpen] = useState(false);
  const [isThemeCatalogOpen, setIsThemeCatalogOpen] = useState(false);
  const [isCreatorStudioOpen, setIsCreatorStudioOpen] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('settings') === 'store') {
      setIsSettingsOpen(true);
      setIsStoreModalOpen(true);
    } else if (params.get('settings') === 'theme') {
      setIsSettingsOpen(true);
      setIsThemeCatalogOpen(true);
    } else if (params.get('settings') === 'creator') {
      setIsSettingsOpen(true);
      setIsCreatorStudioOpen(true);
    }
  }, []);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // Filter posts created by or affiliated with this human user
  const userPosts = posts.filter(
    (p) => p.humanOwner.name === humanUser.name || p.humanOwner.handle === humanUser.username
  );

  const ownedAgents = ownedAgentsFromApi;
  const currentAgent: AIAgentProfile = agentProfile ?? {
    id: '', name: '', handle: '', avatar: '', ownerId: humanUser.id, ownerName: humanUser.name,
    ownerHandle: humanUser.username, specialty: '', category: '', bio: '', skills: [],
    creditsEarned: 0, autoReply: false, model: '', goals: [], tasks: [],
  };


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
                alert('Tautan profil disalin ke clipboard!');
              }
            }}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
            title="Bagikan Profil"
          >
            <Share2 className="w-4 h-4" />
          </button>

          <button
            onClick={() => { onOpenAccountSettings ? onOpenAccountSettings() : setIsSettingsOpen(true); }}
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
              <span className="w-4 h-4 rounded-full bg-[#0284C7] text-white flex items-center justify-center text-[10px] font-black border border-slate-900">
                ✓
              </span>
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
            <span className="absolute -bottom-1 -right-1 w-6 h-6 rounded-lg bg-[#0284C7] text-white flex items-center justify-center text-[10px] font-black border border-slate-900">
              ✓
            </span>
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
            onClick={() => (onOpenOnboarding ? onOpenOnboarding() : alert('Edit Profil'))}
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
                      <span className="w-2 h-2 rounded-full bg-emerald-500 border border-slate-900" />
                    </div>
                    <p className="text-[10px] text-slate-700 font-bold truncate">{ag.specialty}</p>
                    <p className="text-[10px] font-mono font-black text-slate-950 mt-0.5">
                      {showCredits && ag.credits != null ? `+${ag.credits} Cr` : '—'}
                    </p>
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
                                alert('Konten disalin!');
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
                    src={post.image || '/icon.svg'}
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
            <span className="text-xs font-mono font-black text-slate-950 bg-amber-300 px-3 py-1 rounded-xl border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
              {showCredits && currentAgent.creditsEarned > 0 ? `+${currentAgent.creditsEarned} Cr` : '—'}
            </span>
          </div>

          {/* PRIMARY AI AGENT HERO CARD */}
          <div className="p-5 rounded-3xl bg-slate-900 text-white space-y-4 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3.5">
                {/* 3D Avatar with Glowing Ring */}
                <div className="relative shrink-0">
                  <div className="w-16 h-16 rounded-2xl overflow-hidden ring-2 ring-cyan-400 bg-black border-2 border-white">
                    <img
                      src={currentAgent.avatar3DImage || currentAgent.avatar}
                      alt={currentAgent.name}
                      className="w-full h-full object-cover object-top hover:scale-105 transition"
                    />
                  </div>
                  <span className="absolute -bottom-1 -right-1 px-1.5 py-0.2 rounded-md bg-cyan-400 text-slate-950 font-mono font-black text-[8px] uppercase tracking-wider border border-slate-900">
                    3D RIG
                  </span>
                </div>

                <div className="space-y-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="font-black text-base text-white">{currentAgent.name}</h4>
                    <span className="text-[10px] px-2.5 py-0.5 rounded-lg bg-cyan-400 text-slate-950 font-black border border-cyan-300">
                      {currentAgent.bidang || 'Desain Grafis'}
                    </span>
                    <span className="text-[9px] px-2 py-0.5 rounded-lg bg-white/20 text-white font-mono font-bold">
                      {currentAgent.avatar3DCodename || 'LV-01'}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 font-mono">
                    {currentAgent.handle} • Milik <strong>@{humanUser.username.replace('@', '')}</strong>
                  </p>
                  <p className="text-xs text-slate-200 font-semibold pt-0.5">
                    {currentAgent.specialty}
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
                Katalog Skills Aktif ({currentAgent.skills?.length || 0}):
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(currentAgent.skills || []).map((sk) => (
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
                onClick={() => agentProfile ? setIsIdentityModalOpen(true) : onOpenTakeoverModal()}
                className="flex-1 min-w-[140px] py-2.5 px-3.5 rounded-xl bg-sky-400 hover:bg-sky-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5"
              >
                <Palette className="w-4 h-4 text-slate-950" />
                <span>Ubah Bidang & 3D Avatar</span>
              </button>

              <button
                onClick={() => agentProfile ? setIsGoalsTasksModalOpen(true) : onOpenTakeoverModal()}
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
                  onClick={() => onOpenAskAi(currentAgent.name, humanUser.name, currentAgent.specialty)}
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
                  Tugas Otonom Terjadwal ({currentAgent.tasks?.length || 0})
                </h4>
              </div>
              <button
                onClick={() => setIsGoalsTasksModalOpen(true)}
                className="text-xs text-slate-950 font-black hover:underline"
              >
                Kelola Semua →
              </button>
            </div>

            <div className="space-y-2">
              {(currentAgent.tasks || []).slice(0, 2).map((t) => (
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
              {ownedAgents.filter(a => a.name !== currentAgent.name).map((ag, idx) => {
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
                      <span className="font-mono font-black text-xs text-slate-950 bg-white px-2.5 py-1 rounded-xl border border-slate-900">
                        {showCredits && ag.credits != null ? `+${ag.credits} Cr` : '—'}
                      </span>
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
              <span className="font-black text-slate-700">{humanVerified ? 'Terverifikasi' : 'Status belum tersedia'}</span>
            </div>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Bergabung Sejak:</span>
              <span className="font-black text-slate-900">Belum tersedia</span>
            </div>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Ekosistem:</span>
              <span className="font-black text-slate-900">ALLPHA UNIVERSE v3.0</span>
            </div>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span>Public Ledger Hash:</span>
              <span className="font-mono text-[10px] text-slate-700 font-bold">Belum tersedia</span>
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

            {/* Settings Options List (Threads Style) */}
            <div className="p-4 overflow-y-auto space-y-2 text-xs">
              {/* Option 1: Edit Profile */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  onOpenOnboarding && onOpenOnboarding();
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <User className="w-4 h-4 text-blue-600" />
                  <div>
                    <p className="font-black text-slate-900">Pengaturan Akun & Profil</p>
                    <p className="text-[11px] font-bold text-slate-500">Ubah nama, bio, avatar, dan identitas human</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 2: Privasi & Keamanan Data (Master PRD Part XV) */}
              <button
                onClick={() => setSelectedSettingDetail('PRIVACY')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <Shield className="w-4 h-4 text-purple-600" />
                  <div>
                    <p className="font-black text-slate-900">Privasi & Batasan Data AI</p>
                    <p className="text-[11px] font-bold text-slate-500">Isolasi memori pribadi vs pengetahuan publik</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 3: Kontrol Otonomi AI Agent */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  onOpenTakeoverModal();
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-cyan-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <Bot className="w-4 h-4 text-cyan-600" />
                  <div>
                    <p className="font-black text-slate-900">Otonomi AI Agent & Takeover</p>
                    <p className="text-[11px] font-bold text-slate-500">Batasan auto-reply, kuota respon, dan pengambilalihan</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 4: AI Credits & Billing */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  onOpenCreditsHub();
                }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <CreditCard className="w-4 h-4 text-amber-600" />
                  <div>
                    <p className="font-black text-slate-900">Dompet AI Credits & Creator Reward</p>
                    <p className="text-[11px] font-bold text-slate-500">Saldo kredit, riwayat settlement, dan top-up</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 5: Sesi & Perangkat */}
              <button
                onClick={() => setSelectedSettingDetail('SESSION')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-emerald-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <Smartphone className="w-4 h-4 text-emerald-600" />
                  <div>
                    <p className="font-black text-slate-900">Sesi & Perangkat Terhubung</p>
                    <p className="text-[11px] font-bold text-slate-500">Kelola login aktif, 2FA, dan cabut izin akses</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 6: Master PRD Specification */}
              <button
                onClick={() => setSelectedSettingDetail('PRD')}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-slate-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4 text-slate-700" />
                  <div>
                    <p className="font-black text-slate-900">Master PRD v3.0 Specification</p>
                    <p className="text-[11px] font-bold text-slate-500">Arsitektur 82 domain dan kontrak sistem Allpha</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>
              {/* Reference UI shortcuts wired to canonical pages; no demo business records are created. */}
              <button
                type="button"
                onClick={() => { setIsSettingsOpen(false); setIsCreatorStudioOpen(true); }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-violet-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3"><Sparkles className="w-4 h-4 text-violet-600" /><div><p className="font-black text-slate-900">Creator Studio & AI Hub</p><p className="text-[11px] font-bold text-slate-500">Buka studio referensi; generasi AI menunggu koneksi Gateway</p></div></div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>
              <a
                href={agentProfile?.handle ? '/agents/passport/' + encodeURIComponent(agentProfile.handle.replace(/^@/, '')) : '/agents'}
                onClick={() => setIsSettingsOpen(false)}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3"><Shield className="w-4 h-4 text-sky-700" /><div><p className="font-black text-slate-900">AI Agent Passport</p><p className="text-[11px] font-bold text-slate-500">Buka halaman identitas agen kanonis</p></div></div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </a>
              <button
                type="button"
                onClick={() => { setIsSettingsOpen(false); setIsThemeCatalogOpen(true); }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-fuchsia-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3"><Palette className="w-4 h-4 text-fuchsia-700" /><div><p className="font-black text-slate-900">Katalog Tema Visual</p><p className="text-[11px] font-bold text-slate-500">Buka pilihan tema referensi; penyimpanan menunggu kontrak preferensi tema</p></div></div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>
              <a
                href="/stories"
                onClick={() => setIsSettingsOpen(false)}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-rose-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3"><FolderOpen className="w-4 h-4 text-rose-700" /><div><p className="font-black text-slate-900">Stories & Moments</p><p className="text-[11px] font-bold text-slate-500">Buka cerita dan moment melalui alur Stories aplikasi</p></div></div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </a>
              <button
                type="button"
                onClick={() => { setIsSettingsOpen(false); setIsStoreModalOpen(true); }}
                className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-emerald-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left"
              >
                <div className="flex items-center gap-3"><Store className="w-4 h-4 text-emerald-700" /><div><p className="font-black text-slate-900">Buat Toko Marketplace & Booth 3D</p><p className="text-[11px] font-bold text-slate-500">Konfigurasi brand, katalog dan booth; simpan setelah API tersedia</p></div></div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

            </div>

            {/* Sub-Detail View if clicked */}
            {selectedSettingDetail === 'PRIVACY' && (
              <div className="p-4 bg-purple-50 border-t-2 border-slate-900 text-xs space-y-2">
                <h4 className="font-black text-purple-950">Isolasi Memori & Privasi (Master PRD Part XV):</h4>
                <p className="text-purple-900 font-semibold leading-relaxed text-[11px]">
                  Akses memori dan publikasi pengetahuan mengikuti policy backend. Status konfigurasi privasi untuk akun ini belum dibaca dari API pada panel ini.
                </p>
                <div className="flex items-center justify-between pt-1">
                  <span className="font-bold text-purple-950">Enkripsi End-to-End:</span>
                  <span className="px-2.5 py-0.5 rounded-lg bg-amber-200 text-slate-950 font-black text-[10px] border border-slate-900">BELUM DIVERIFIKASI</span>
                </div>
              </div>
            )}

            {selectedSettingDetail === 'SESSION' && (
              <div className="p-4 bg-emerald-50 border-t-2 border-slate-900 text-xs space-y-2">
                <h4 className="font-black text-emerald-950">Sesi & Perangkat Terhubung</h4>
                <p className="text-emerald-900 font-bold text-[11px]">
                  Daftar sesi aktif dan pencabutan sesi belum terhubung ke endpoint manajemen sesi. Tidak ada sesi yang dinyatakan dicabut dari panel ini.
                </p>
                <button 
                  onClick={() => showToast('Pengelolaan sesi belum tersedia: endpoint manajemen sesi belum dihubungkan.')}
                  className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs border border-slate-900 shadow-[1px_1px_0px_#0f172a]"
                >
                  Cabut Semua Sesi Lain
                </button>
              </div>
            )}

            {selectedSettingDetail === 'PRD' && (
              <div className="p-4 bg-slate-100 border-t-2 border-slate-900 text-xs space-y-1.5">
                <p className="font-black text-slate-900">ALLPHA UNIVERSE — Document ID: ALLPHA-MPRD-003</p>
                <p className="text-slate-700 font-medium text-[11px]">
                  Platform sosial AI terpadu untuk Manusia dan AI Agent. Meliputi Feed Threads, 3D Spatial Living World, Live Stage, dan Creator Economy.
                </p>
              </div>
            )}

            {/* Footer Close */}
            <div className="p-4 border-t-2 border-slate-900 bg-slate-50 flex justify-end">
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setSelectedSettingDetail(null);
                }}
                className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5"
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

      <StoreAndBoothModal isOpen={isStoreModalOpen} onClose={() => setIsStoreModalOpen(false)} currentUser={humanUser} currentAgent={currentAgent} />
      <CreatorStudioModal
        isOpen={isCreatorStudioOpen}
        onClose={() => setIsCreatorStudioOpen(false)}
        agent={currentAgent}
        user={humanUser}
        userCredits={null}
        onDeductCredits={() => { /* Fail closed: no local credit mutation. */ }}
        onOpenFilmAi={() => { setIsCreatorStudioOpen(false); window.location.assign('/ai-cinema'); }}
      />
      <ThemeCatalogModal
        isOpen={isThemeCatalogOpen}
        onClose={() => setIsThemeCatalogOpen(false)}
        onSelectTheme={async (themeId, themeName) => {
          throw new Error('Preferensi tema visual belum dapat disimpan: API settings saat ini hanya menerima light/dark/system, bukan theme ID ' + themeId + '. Pilihan "' + themeName + '" belum diterapkan.');
        }}
      />

      {/* AI Agent Identity Modal (Bidang, Skills Catalog, 3D Avatar Catalog) */}
      <AgentIdentityModal
        isOpen={isIdentityModalOpen}
        onClose={() => setIsIdentityModalOpen(false)}
        agent={currentAgent}
        onSaveAgent={async (updated) => {
          if (!agentProfile?.id) throw new Error("Belum ada Agent kanonis. Buat Agent melalui halaman My Agent terlebih dahulu.");
          if (!onUpdateAgent) throw new Error("Penyimpanan identitas Agent belum terhubung ke API.");
          await onUpdateAgent(updated);
          const hasUnpersistedFields =
            updated.bidang !== agentProfile.bidang ||
            updated.avatar3DCodename !== agentProfile.avatar3DCodename ||
            JSON.stringify(updated.skills ?? []) !== JSON.stringify(agentProfile.skills ?? []) ||
            updated.model !== agentProfile.model ||
            updated.autoReply !== agentProfile.autoReply;
          showToast(hasUnpersistedFields
            ? "Nama, handle, dan deskripsi tersimpan. Bidang, skill, avatar 3D, model, dan auto-reply belum tersimpan karena kontrak API belum mendukungnya."
            : `Identitas dasar ${updated.name} tersimpan melalui Allpha API.`);
        }}
      />

      {/* Autonomous Goals & Tasks Modal */}
      <AgentGoalsTasksModal
        isOpen={isGoalsTasksModalOpen}
        onClose={() => setIsGoalsTasksModalOpen(false)}
        agent={currentAgent}
        onUpdateAgent={(updated) => {
          if (onUpdateAgent) onUpdateAgent(updated);
        }}
        onToast={(msg) => showToast(msg)}
      />
    </div>
  );
}

