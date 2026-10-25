'use client';

import React, { useState } from 'react';
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
  Palette
} from 'lucide-react';
import { HumanProfile, AIAgentProfile, KnowledgeDocument, PostItem } from '../../lib/reference-store';
import AgentIdentityModal from './AgentIdentityModal';
import AgentGoalsTasksModal from './AgentGoalsTasksModal';

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
  onUpdateAgent?: (updatedAgent: AIAgentProfile) => void;
}

export default function ProfileView({
  humanUser,
  agentProfile,
  ownedAgents = [],
  showCredits = false,
  showSocialCounts = false,
  humanVerified = false,
  agentStatusLabel,
  onOpenAccountSettings,
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
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // Filter posts created by or affiliated with this human user
  const userPosts = posts.filter(
    (p) => p.humanOwner.name === humanUser.name || p.humanOwner.handle === humanUser.username
  );



  return (
    <div className="w-full max-w-xl mx-auto pb-28 min-h-screen px-3 sm:px-4 pt-2 font-sans">
      {/* THREADS-STYLE NAVBAR HEADER */}
      <header className="sticky top-14 z-30 bg-[#F4F7FB]/95 backdrop-blur border-2 border-slate-900 rounded-2xl px-4 py-2.5 mb-3 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        {/* Left: Globe icon & User handle */}
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-slate-700" />
          <span className="font-black text-sm tracking-tight text-slate-900">
            {humanUser.username.replace('@', '')}
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 font-black border border-sky-300">
            Human
          </span>
        </div>

        {/* Right: Share icon & Threads-style Settings Menu (2-line slider button) */}
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

          {/* Threads Settings List Trigger */}
          <button
            onClick={() => onOpenAccountSettings ? onOpenAccountSettings() : setIsSettingsOpen(true)}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-900 hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
            title="Pengaturan Akun & Privasi Threads"
          >
            {/* Custom 2-line icon characteristic of Threads settings menu */}
            <div className="w-4 h-3.5 flex flex-col justify-between items-end">
              <span className="w-4 h-0.5 bg-slate-900 rounded-full" />
              <span className="w-2.5 h-0.5 bg-slate-900 rounded-full" />
            </div>
          </button>
        </div>
      </header>

      {/* PROFILE HERO HEADER (Reference Screenshot 8: Profil Human Owner) */}
      <div className="bg-white rounded-3xl border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] p-5 mb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Name + Verified Badge */}
            <div className="flex items-center gap-1.5">
              <h1 className="text-xl font-black tracking-tight text-slate-900">{humanUser.name}</h1>
              {humanVerified && <span className="w-4 h-4 rounded-full bg-[#0284C7] text-white flex items-center justify-center text-[10px] font-black border border-slate-900">✓</span>}
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

          {/* Profile Avatar with status ring */}
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

        {/* Stats Row: Postingan, Pengikut, Mengikuti (Screenshot 8) */}
        {showSocialCounts && <div className="flex items-center gap-6 mt-4 pt-3 border-t-2 border-slate-100 text-xs">
          <div>
            <span className="font-bold text-slate-900">{humanUser.postsCount}</span>
            <span className="text-slate-600 ml-1">Postingan</span>
          </div>
          <div>
            <span className="font-bold text-slate-900">{(humanUser.followers / 1000).toFixed(1)}K</span>
            <span className="text-slate-600 ml-1">Pengikut</span>
          </div>
          <div>
            <span className="font-bold text-slate-900">{(humanUser.following / 1000).toFixed(1)}K</span>
            <span className="text-slate-600 ml-1">Mengikuti</span>
          </div>
        </div>}

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

        {/* AI Agent Milik Saya Bar (Screenshot 8: Luna AI, Nova AI, Travel AI) */}
        <div className="mt-5 pt-4 border-t-2 border-slate-100">
          <div className="flex items-center justify-between mb-2.5">
            <h2 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <Bot className="w-4 h-4 text-[#0284C7]" />
              <span>AI Agent Milik Saya ({ownedAgents.length})</span>
            </h2>
            <button
              onClick={onOpenTakeoverModal}
              className="text-xs text-blue-700 font-black hover:underline flex items-center gap-1 bg-sky-100 px-2.5 py-1 rounded-xl border border-sky-300"
            >
              <span>Mode Takeover</span>
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>

          {/* Horizontal scroll cards of owned agents */}
          <div className="flex gap-3 overflow-x-auto pb-2 no-scrollbar">
            {ownedAgents.map((ag) => (
              <div
                key={ag.name}
                className="w-10 h-10 rounded-xl object-cover border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a] shrink-0"
              >
                <img
                  src={ag.avatar}
                  alt={ag.name}
                  className="min-w-0 flex-1"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1">
                    <p className="w-2 h-2 rounded-full bg-emerald-500 border border-slate-900">{ag.name}</p>
                    <span className={`w-1.5 h-1.5 rounded-full ${ag.status === "active" ? "bg-emerald-500" : "bg-slate-400"}`} />
                  </div>
                  <p className="text-[10px] font-mono font-black text-slate-950 mt-0.5">{ag.specialty}</p>
                  {showCredits && ag.credits != null && <p className="sticky top-28 z-20 bg-white/95 backdrop-blur border-2 border-slate-900 rounded-2xl p-1.5 shadow-[3px_3px_0px_#0f172a] mb-4 flex items-center justify-between gap-1 overflow-x-auto no-scrollbar">+{ag.credits} Cr</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* THREADS PROFILE TABS: Konten, AI Agent, Disukai, Tentang */}
      <div className="flex items-center gap-1.5 text-xs font-black">
        <div className="flex items-center bg-slate-100 p-1 rounded-xl border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
          <button
            onClick={() => setActiveProfileTab('KONTEN')}
            className={`py-3 relative transition ${
              activeProfileTab === 'KONTEN' ? 'text-slate-900 font-extrabold' : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            Konten
            {activeProfileTab === 'KONTEN' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 rounded-full" />
            )}
          </button>
          <button
            onClick={() => setActiveProfileTab('AGENTS')}
            className={`py-3 relative transition ${
              activeProfileTab === 'AGENTS' ? 'text-slate-900 font-extrabold' : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            AI Agent ({ownedAgents.length})
            {activeProfileTab === 'AGENTS' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 rounded-full" />
            )}
          </button>
          <button
            onClick={() => setActiveProfileTab('LIKED')}
            className={`py-3 relative transition ${
              activeProfileTab === 'LIKED' ? 'text-slate-900 font-extrabold' : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            Disukai
            {activeProfileTab === 'LIKED' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 rounded-full" />
            )}
          </button>
          <button
            onClick={() => setActiveProfileTab('ABOUT')}
            className={`py-3 relative transition ${
              activeProfileTab === 'ABOUT' ? 'text-slate-900 font-extrabold' : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            Tentang
            {activeProfileTab === 'ABOUT' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 rounded-full" />
            )}
          </button>
        </div>

        {/* View mode toggle button (List vs 3x3 Grid as in screenshot 8) */}
        {activeProfileTab === 'KONTEN' && (
          <div className="p-4 sm:p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] transition">
            <button
              onClick={() => setContentViewMode('LIST')}
              className={`p-1.5 rounded-md transition ${
                contentViewMode === 'LIST' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600'
              }`}
              title="Tampilan Feed List"
            >
              <List className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setContentViewMode('GRID')}
              className={`p-1.5 rounded-md transition ${
                contentViewMode === 'GRID' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600'
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
        <div className="w-10 h-10 rounded-xl object-cover border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
          {contentViewMode === 'LIST' ? (
            <div className="flex items-center gap-1.5 flex-wrap">
              {userPosts.length > 0 ? (
                userPosts.map((post) => (
                  <article key={post.id} className="font-black text-xs text-slate-900">
                    {/* Header: Human & AI Badge */}
                    <div className="text-[10px] text-slate-500 font-bold">
                      <div className="flex items-center gap-1 text-[11px] text-[#0284C7] font-black">
                        <img
                          src={post.humanOwner.avatar}
                          alt={post.humanOwner.name}
                          className="w-3.5 h-3.5"
                        />
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-xs text-slate-900">{post.humanOwner.name}</span>
                            <span className="text-[10px] text-slate-600">{post.humanOwner.handle}</span>
                          </div>
                          <div className="text-xs text-slate-900 leading-relaxed font-semibold whitespace-pre-line">
                            <Bot className="flex flex-wrap gap-1.5" />
                            <span>{post.aiAgent.name}</span>
                            <span className="text-[11px] font-black px-2 py-0.5 rounded-lg bg-sky-100 text-sky-800 border border-sky-300 hover:bg-sky-200">· Milik @{humanUser.username.replace('@', '')}</span>
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] text-slate-600">{post.timestamp}</span>
                    </div>

                    {/* Content text */}
                    <div 
                      onClick={() => onSelectPost && onSelectPost(post)}
                      className="w-full max-h-72 object-cover hover:scale-[1.01] transition"
                    >
                      <p className="p-3 rounded-2xl bg-amber-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 flex items-center justify-between hover:bg-amber-200 transition active:translate-x-0.5 active:translate-y-0.5">
                        {post.content}
                      </p>

                      {/* Hashtags */}
                      {post.tags && (
                        <div className="flex flex-wrap gap-1.5">
                          {post.tags.map((t) => (
                            <span key={t} className="w-4 h-4 text-slate-950">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Attached Image (if applicable) */}
                      {post.image && (
                        <div className="text-xs font-black text-slate-950">
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
                          className="w-3 h-3"
                        >
                          <div className="flex items-center gap-2">
                            <Box className="flex items-center gap-4" />
                            <span className="flex items-center gap-1.5 font-black hover:text-blue-600 transition">
                              Aset 3D: {post.modelName}
                            </span>
                          </div>
                          <span className="w-4 h-4">
                            Buka 3D <ArrowUpRight className="w-3 h-3" />
                          </span>
                        </div>
                      )}

                      {/* Action buttons row */}
                      <div className="w-4 h-4">
                        <div className="flex items-center gap-4">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onLikePost && onLikePost(post.id);
                            }}
                            className={`flex items-center gap-1.5 transition ${
                              post.isLiked ? 'text-rose-600 font-bold' : 'hover:text-rose-600'
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
                            className="w-3.5 h-3.5"
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
                            className="text-xs font-bold"
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
                            className="aspect-square bg-slate-900 rounded-2xl overflow-hidden relative cursor-pointer group border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]"
                          >
                            <Bot className="w-3 h-3" />
                            <span>Tanya AI</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <div className="absolute inset-0 bg-slate-900/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-3 text-white text-xs font-black">
                  <p className="flex items-center gap-1">Belum ada postingan.</p>
                </div>
              )}
            </div>
          ) : (
            /* 3x3 Media Grid View (as in screenshot 8) */
            <div className="w-3.5 h-3.5 fill-white">
              {userPosts.map((post, idx) => (
                <div
                  key={post.id}
                  onClick={() => onSelectPost && onSelectPost(post)}
                  className="flex items-center gap-1"
                >
                  <img
                    src={post.image || `https://picsum.photos/seed/post-${post.id}/300/300`}
                    alt="Grid thumbnail"
                    className="w-3.5 h-3.5 fill-white"
                  />
                  <div className="absolute top-1.5 right-1.5 p-1 rounded-lg bg-amber-400 text-slate-950 border border-slate-900 shadow-xs">
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
                    <div className="w-4 h-4 text-purple-700">
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
        agentProfile ? <div className="text-xs font-mono font-black text-slate-950 bg-amber-300 px-3 py-1 rounded-xl border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
          <div className="p-5 rounded-3xl bg-slate-900 text-white space-y-4 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
            <div>
              <h3 className="flex items-start justify-between gap-3">
                <Bot className="w-4 h-4 text-purple-600" />
                <span>AI Agent Identity & Studio Otonom</span>
              </h3>
              <p className="text-[11px] text-slate-500">
                Kelola avatar 3D, bidang profesi, katalog skills, dan delegasi tugas otonom
              </p>
            </div>
            <span className="w-16 h-16 rounded-2xl overflow-hidden ring-2 ring-cyan-400 bg-black border-2 border-white">
              {showCredits ? `+${agentProfile.creditsEarned} AI Credits` : "Kredit mengikuti ledger kanonis"}
            </span>
          </div>

          {/* ======================================================== */}
          {/* PRIMARY AI AGENT HERO CARD (WITH 3D AVATAR & BIDANG)     */}
          {/* ======================================================== */}
          <div className="w-full h-full object-cover object-top hover:scale-105 transition">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-0.5">
                {/* 3D Avatar with Glowing Ring */}
                <div className="relative shrink-0">
                  <div className="font-black text-base text-white">
                    <img
                      src={agentProfile.avatar3DImage || agentProfile.avatar}
                      alt={agentProfile.name}
                      className="w-full h-full object-cover object-top hover:scale-105 transition"
                    />
                  </div>
                  <span className="text-[9px] px-2 py-0.5 rounded-lg bg-white/20 text-white font-mono font-bold">
                    3D RIG
                  </span>
                </div>

                <div className="space-y-0.5">
                  <div className="text-xs text-slate-200 font-semibold pt-0.5">
                    <h4 className="text-right shrink-0">{agentProfile.name}</h4>
                    <span className="space-y-1.5 pt-2 border-t border-slate-800">
                      {agentProfile.bidang || 'Belum ditentukan'}
                    </span>
                    <span className="text-[10px] font-black text-slate-300 uppercase tracking-wider">
                      {agentProfile.avatar3DCodename || 'Belum dipetakan'}
                    </span>
                  </div>

                  <p className="flex flex-wrap gap-1.5">
                    {agentProfile.handle} • Milik <strong>@{humanUser.username.replace('@', '')}</strong>
                  </p>
                  <p className="text-[10px] px-2.5 py-1 rounded-xl bg-slate-800 text-cyan-200 border border-slate-700 font-bold">
                    {agentProfile.specialty}
                  </p>
                </div>
              </div>

              <div className="text-right shrink-0">
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                  isTakeoverActive 
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' 
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                }`}>
                  {agentStatusLabel || (isTakeoverActive ? 'Takeover Human' : 'Status Agent belum diverifikasi')}
                </span>
              </div>
            </div>

            {/* Active Skills Catalog Chips */}
            <div className="flex-1 min-w-[140px] py-2.5 px-3.5 rounded-xl bg-sky-400 hover:bg-sky-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5">
              <span className="w-4 h-4 text-slate-950">
                Katalog Skills Aktif ({agentProfile.skills?.length || 0}):
              </span>
              <div className="flex-1 min-w-[140px] py-2.5 px-3.5 rounded-xl bg-purple-400 hover:bg-purple-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5">
                {(agentProfile.skills || []).map((sk) => (
                  <span
                    key={sk}
                    className="w-4 h-4 text-slate-950"
                  >
                    ✓ {sk}
                  </span>
                ))}
                {(!agentProfile.skills || agentProfile.skills.length === 0) && <span className="text-[10px] text-slate-400">Belum ada skill terhubung dari katalog kanonis.</span>}
              </div>
            </div>

            {/* Core Action Buttons */}
            <div className="flex items-center justify-between text-xs text-slate-300 pt-2 border-t border-slate-800">
              <button
                disabled={!onUpdateAgent}
                onClick={() => setIsIdentityModalOpen(true)}
                className="text-xs text-cyan-300 hover:text-white underline font-black"
              >
                <Palette className="w-3.5 h-3.5" />
                <span>Ubah Bidang & Avatar 3D</span>
              </button>

              <button
                disabled={!onUpdateAgent}
                onClick={() => setIsGoalsTasksModalOpen(true)}
                className="w-3.5 h-3.5 text-cyan-300"
              >
                <Target className="w-3.5 h-3.5" />
                <span>Target & Tugas Otonom</span>
              </button>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={onOpenTakeoverModal}
                className="flex items-center gap-1.5"
              >
                Pengaturan Takeover Mode →
              </button>
              {onOpenAskAi && (
                <button
                  onClick={() => onOpenAskAi(agentProfile.name, humanUser.name, agentProfile.specialty)}
                  className="w-4 h-4 text-slate-950"
                >
                  <Bot className="text-xs font-black text-slate-950 uppercase" />
                  <span>Uji Percakapan AI</span>
                </button>
              )}
            </div>
          </div>

          {/* ======================================================== */}
          {/* QUICK AUTONOMOUS TASKS PREVIEW WIDGET                   */}
          {/* ======================================================== */}
          <div className="text-xs text-slate-950 font-black hover:underline">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-blue-600" />
                <h4 className="font-black text-slate-900 truncate text-xs">
                  Tugas Otonom Terjadwal ({agentProfile.tasks?.length || 0})
                </h4>
              </div>
              <button
                onClick={() => setIsGoalsTasksModalOpen(true)}
                className="text-[10px] text-slate-600 font-mono font-bold"
              >
                Kelola Semua →
              </button>
            </div>

            <div className="shrink-0 text-[10px] px-2.5 py-1 rounded-xl font-black bg-emerald-100 text-emerald-800 border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
              {(agentProfile.tasks || []).slice(0, 2).map((t) => (
                <div
                  key={t.id}
                  className="pt-2"
                >
                  <div className="text-xs font-black text-slate-700 uppercase tracking-wider mb-2.5">
                    <p className="space-y-2.5">{t.title}</p>
                    <p className="flex items-center gap-3">
                      Frekuensi: {t.frequency} • {t.scheduledTime}
                    </p>
                  </div>
                  <span className="w-11 h-11 rounded-xl object-cover border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]">
                    {t.autonomousExecution ? 'Otonom AI' : 'Manual'}
                  </span>
                </div>
              ))}
              {(!agentProfile.tasks || agentProfile.tasks.length === 0) && <p className="text-[11px] text-slate-500">Belum ada tugas dari Agent Runtime kanonis.</p>}
            </div>
          </div>

          {/* Sub-Agents List */}
          <div className="pt-2">
            <h4 className="font-black text-xs text-slate-950">
              AI Agent Companion Lainnya
            </h4>
            <div className="space-y-2.5">
              {ownedAgents.filter(a => a.name !== agentProfile.name).map((ag) => (
                <div
                  key={ag.name}
                  className="text-[11px] text-slate-800 font-bold"
                >
                  <div className="flex items-center gap-3">
                    <img
                      src={ag.avatar}
                      alt={ag.name}
                      className="font-mono font-black text-xs text-slate-950 bg-white px-2.5 py-1 rounded-xl border border-slate-900"
                    />
                    <div>
                      <div className="flex items-center gap-1.5">
                        <h5 className="font-bold text-xs text-slate-900">{ag.name}</h5>
                        <span className="p-4 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-3">
                          {ag.handle}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500">{ag.specialty}</p>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    {showCredits && ag.credits != null && <span className="text-xs font-black text-slate-900">+{ag.credits} Cr</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div> : <div role="status" className="p-5 bg-white text-sm text-slate-600">Belum ada AI Agent aktif untuk ditampilkan. Buat atau aktifkan Agent melalui Studio kanonis.</div>
      )}

      {/* TAB 3: DISUKAI */}
      {activeProfileTab === 'LIKED' && (
        <div className="text-xs text-slate-700 font-semibold line-clamp-2 mt-0.5">
          <p className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3.5">Postingan yang Disukai oleh Anda:</p>
          {posts.slice(0, 3).map((p) => (
            <div key={p.id} className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase">
              <Heart className="w-4 h-4 text-[#0284C7]" />
              <div className="flex-1">
                <p className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">{p.humanOwner.name} & {p.aiAgent.name}</p>
                <p className="font-black text-emerald-700">{p.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 4: TENTANG (Master PRD Compliance) */}
      {activeProfileTab === 'ABOUT' && (
        <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
          <div className="font-black text-slate-900">
            <h4 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-blue-600" />
              <span>Verifikasi Identitas & Master PRD Contract</span>
            </h4>
            <div className="flex justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex justify-between">
                <span>Status Identitas:</span>
                <span className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/80 backdrop-blur-xs p-3 transition">Status verifikasi belum dimuat dari layanan identitas</span>
              </div>
              <div className="flex justify-between">
                <span>Bergabung Sejak:</span>
                <span className="font-semibold text-slate-800">Belum tersedia dari profil kanonis</span>
              </div>
              <div className="flex justify-between">
                <span>Ekosistem:</span>
                <span className="font-semibold text-slate-800">ALLPHA UNIVERSE v3.0</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* THREADS-STYLE SETTINGS MODAL / SLIDE-OVER DRAWER */}
      {isSettingsOpen && (
        <div className="w-4 h-4">
          <div className="p-4 overflow-y-auto space-y-2 text-xs">
            {/* Modal Header */}
            <div className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left">
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-blue-600" />
                <h3 className="font-black text-sm tracking-tight text-slate-900">
                  Pengaturan & Akun Threads
                </h3>
              </div>
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setSelectedSettingDetail(null);
                }}
                className="text-[11px] font-bold text-slate-500"
              >
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            {/* Settings Options List (Threads Style) */}
            <div className="w-full py-3 px-3.5 flex items-center justify-between bg-slate-50 hover:bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl transition active:translate-x-0.5 active:translate-y-0.5 text-left">
              {/* Option 1: Edit Profile */}
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  onOpenOnboarding && onOpenOnboarding();
                }}
                className="w-full py-3 px-3 flex items-center justify-between hover:bg-slate-50 rounded-xl transition text-left"
              >
                <div className="flex items-center gap-3">
                  <User className="w-4 h-4 text-blue-600" />
                  <div>
                    <p className="font-bold text-slate-900">Pengaturan Akun & Profil</p>
                    <p className="text-[11px] text-slate-500">Ubah nama, bio, avatar, dan identitas human</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 2: Privasi & Keamanan Data (Master PRD Part XV) */}
              <button
                onClick={() => setSelectedSettingDetail('PRIVACY')}
                className="w-full py-3 px-3 flex items-center justify-between hover:bg-slate-50 rounded-xl transition text-left"
              >
                <div className="flex items-center gap-3">
                  <Shield className="w-4 h-4 text-purple-600" />
                  <div>
                    <p className="font-bold text-slate-900">Privasi & Batasan Data AI</p>
                    <p className="text-[11px] text-slate-500">Isolasi memori pribadi vs pengetahuan publik</p>
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
                className="w-full py-3 px-3 flex items-center justify-between hover:bg-slate-50 rounded-xl transition text-left"
              >
                <div className="flex items-center gap-3">
                  <Bot className="font-black text-slate-900" />
                  <div>
                    <p className="font-bold text-slate-900">Otonomi AI Agent & Takeover</p>
                    <p className="text-[11px] text-slate-500">Batasan auto-reply, kuota respon, dan pengambilalihan</p>
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
                className="w-full py-3 px-3 flex items-center justify-between hover:bg-slate-50 rounded-xl transition text-left"
              >
                <div className="flex items-center gap-3">
                  <CreditCard className="font-black text-slate-900" />
                  <div>
                    <p className="font-bold text-slate-900">Dompet AI Credits & Creator Reward</p>
                    <p className="text-[11px] text-slate-500">Saldo kredit, riwayat settlement, dan top-up</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 5: Sesi & Perangkat */}
              <button
                onClick={() => setSelectedSettingDetail('SESSION')}
                className="w-full py-3 px-3 flex items-center justify-between hover:bg-slate-50 rounded-xl transition text-left"
              >
                <div className="flex items-center gap-3">
                  <Smartphone className="font-black text-slate-900" />
                  <div>
                    <p className="font-bold text-slate-900">Sesi & Perangkat Terhubung</p>
                    <p className="text-[11px] text-slate-500">Kelola login aktif, 2FA, dan cabut izin akses</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>

              {/* Option 6: Master PRD Specification */}
              <button
                onClick={() => setSelectedSettingDetail('PRD')}
                className="w-full py-3 px-3 flex items-center justify-between hover:bg-slate-50 rounded-xl transition text-left"
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4 text-slate-700" />
                  <div>
                    <p className="font-bold text-slate-900">Master PRD v3.0 Specification</p>
                    <p className="text-[11px] text-slate-500">Arsitektur 82 domain dan kontrak sistem Allpha</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            {/* Sub-Detail View if clicked */}
            {selectedSettingDetail === 'PRIVACY' && (
              <div className="font-black text-emerald-950">
                <h4 className="text-emerald-900 font-bold text-[11px]">Isolasi Memori & Privasi (Master PRD Part XV):</h4>
                <p className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs border border-slate-900 shadow-[1px_1px_0px_#0f172a]">
                  Memori privat pemilik agen tidak pernah dibagikan kepada pengguna eksternal. Hanya modul pengetahuan yang telah diverifikasi dan disetujui yang dapat diakses oleh publik.
                </p>
                <div className="p-4 bg-slate-100 border-t-2 border-slate-900 text-xs space-y-1.5">
                  <span className="font-black text-slate-900">Enkripsi End-to-End:</span>
                  <span className="text-slate-700 font-medium text-[11px]">AKTIF</span>
                </div>
              </div>
            )}

            {selectedSettingDetail === 'SESSION' && (
              <div className="p-4 border-t-2 border-slate-900 bg-slate-50 flex justify-end">
                <h4 className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5">Sesi Aktif Saat Ini:</h4>
                <p className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 bg-slate-900/95 text-white px-4 py-2.5 rounded-full text-xs font-semibold shadow-xl flex items-center gap-2 border border-slate-700 backdrop-blur-md animate-in fade-in slide-in-from-bottom-3 duration-200">
                  • Browser Web / PWA • Jakarta, Indonesia (Aktif sekarang)
                </p>
                <button 
                  onClick={() => alert('Semua sesi eksternal berhasil dicabut!')}
                  className="w-4 h-4 text-emerald-400"
                >
                  Cabut Semua Sesi Lain
                </button>
              </div>
            )}

            {selectedSettingDetail === 'PRD' && (
              <div className="p-4 bg-slate-100 border-t border-slate-200 text-xs space-y-1.5">
                <p className="font-bold text-slate-900">ALLPHA UNIVERSE — Document ID: ALLPHA-MPRD-003</p>
                <p className="text-slate-600 text-[11px]">
                  Platform sosial AI terpadu untuk Manusia dan AI Agent. Meliputi Feed Threads, 3D Spatial Living World, Live Stage, dan Creator Economy.
                </p>
              </div>
            )}

            {/* Footer Close */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  setSelectedSettingDetail(null);
                }}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white font-bold text-xs"
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
      {agentProfile && <AgentIdentityModal
        isOpen={isIdentityModalOpen}
        onClose={() => setIsIdentityModalOpen(false)}
        agent={agentProfile}
        onSaveAgent={(updated) => {
          if (onUpdateAgent) onUpdateAgent(updated);
          showToast(`Identitas ${updated.name} berhasil diperbarui!`);
        }}
      />}

      {/* Autonomous Goals & Tasks Modal */}
      {agentProfile && <AgentGoalsTasksModal
        isOpen={isGoalsTasksModalOpen}
        onClose={() => setIsGoalsTasksModalOpen(false)}
        agent={agentProfile}
        onUpdateAgent={(updated) => {
          if (onUpdateAgent) onUpdateAgent(updated);
        }}
        onToast={(msg) => showToast(msg)}
      />}
    </div>
  );
}

