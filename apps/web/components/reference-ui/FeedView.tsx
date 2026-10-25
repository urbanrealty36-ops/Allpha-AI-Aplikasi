'use client';

import React, { useEffect, useState } from 'react';
import { 
  Heart, 
  MessageCircle, 
  Repeat2, 
  Share2, 
  Bot, 
  Sparkles, 
  Send, 
  Box, 
  ArrowRight,
  MoreHorizontal,
  Film,
  Users,
  CheckCircle2,
  ChevronRight,
  SlidersHorizontal,
  Radio
} from 'lucide-react';
import type { PostItem } from '../../lib/reference-store';

interface FeedViewProps {
  posts: PostItem[];
  onLikePost: (postId: string) => void;
  onOpenAskAi: (agentName: string, ownerName: string, specialty: string) => void;
  onOpenGenerate: (contextPost: PostItem) => void;
  onOpenWorld3D: () => void;
  onAddComment: (postId: string, text: string) => void;
  onSelectPost?: (post: PostItem) => void;
  onOpenReels?: () => void;
  onOpenLiveStage?: () => void;
  onOpenCreateModal?: () => void;
  onOpenFilmAi?: (filmId?: string) => void;
  onOpenMessages?: () => void;
  storiesData?: Array<{ id: string; name: string; img?: string; isAdd?: boolean; isLive?: boolean; ringColor?: string }>;
  productionMode?: boolean;
  onSharePost?: (postId: string) => void;
  onRepostPost?: (postId: string) => void;
  onLoadComments?: (postId: string) => void;
  initialCommentsPostId?: string | null;
}

export default function FeedView({
  posts,
  onLikePost,
  onOpenAskAi,
  onOpenGenerate,
  onOpenWorld3D,
  onAddComment,
  onSelectPost,
  onOpenReels,
  onOpenLiveStage,
  onOpenCreateModal,
  onOpenFilmAi,
  onOpenMessages,
  storiesData,
  productionMode = false,
  onSharePost,
  onRepostPost,
  onLoadComments,
  initialCommentsPostId,
}: FeedViewProps) {
  const [feedFilter, setFeedFilter] = useState<'FOR_YOU' | 'FOLLOWING' | 'AI_AGENTS'>('FOR_YOU');
  const [commentInput, setCommentInput] = useState<{ [postId: string]: string }>({});
  const [expandedCommentsPostId, setExpandedCommentsPostId] = useState<string | null>(null);
  const [initialCommentsHandled, setInitialCommentsHandled] = useState(false);

  // Production stories come from the authenticated API; never seed demo identities.
  const stories = storiesData ?? [];
  const visiblePosts = productionMode && feedFilter !== 'FOR_YOU' ? [] : posts;

  useEffect(() => {
    if (initialCommentsHandled || !initialCommentsPostId || !posts.some(post => post.id === initialCommentsPostId)) return;
    setExpandedCommentsPostId(initialCommentsPostId);
    setInitialCommentsHandled(true);
    onLoadComments?.(initialCommentsPostId);
  }, [initialCommentsHandled, initialCommentsPostId, posts.length, onLoadComments]);

  const handleSendComment = (postId: string) => {
    const text = commentInput[postId]?.trim();
    if (!text) return;
    onAddComment(postId, text);
    setCommentInput((prev) => ({ ...prev, [postId]: '' }));
  };

  return (
    <div className="w-full max-w-xl mx-auto px-3.5 sm:px-4 pt-3.5 pb-24 space-y-4 font-sans">
      
      {/* ========================================================================= */}
      {/* 1. NEO-BRUTALIST CATEGORY TABS (Sesuai Gambar Referensi)                   */}
      {/* ========================================================================= */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
        {/* '✨ Untuk Anda' (Active / Dark Pill) */}
        <button
          onClick={() => setFeedFilter('FOR_YOU')}
          className={`px-4 py-2 rounded-full text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
            feedFilter === 'FOR_YOU'
              ? 'bg-slate-900 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]'
              : 'bg-white text-slate-800 border-2 border-slate-900 hover:bg-slate-50'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-white" />
          <span>Untuk Anda</span>
        </button>

        {/* '👥 Mengikuti' */}
        <button
          onClick={() => setFeedFilter('FOLLOWING')}
          className={`px-4 py-2 rounded-full text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
            feedFilter === 'FOLLOWING'
              ? 'bg-slate-900 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]'
              : 'bg-white text-slate-800 border-2 border-slate-900 hover:bg-slate-50'
          }`}
        >
          <Users className="w-3.5 h-3.5 text-slate-700" />
          <span>Mengikuti</span>
        </button>

        {/* '🤖 AI Agents' */}
        <button
          onClick={() => setFeedFilter('AI_AGENTS')}
          className={`px-4 py-2 rounded-full text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
            feedFilter === 'AI_AGENTS'
              ? 'bg-slate-900 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]'
              : 'bg-white text-slate-800 border-2 border-slate-900 hover:bg-slate-50'
          }`}
        >
          <Bot className="w-3.5 h-3.5 text-slate-700" />
          <span>AI Agents</span>
        </button>

        {/* '🎞️ Reels / Video' (Soft Pastel Pink/Rose Pill) */}
        <button
          onClick={onOpenReels}
          className="px-4 py-2 rounded-full text-xs font-bold bg-rose-50 text-rose-600 border-2 border-rose-300 hover:bg-rose-100 transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer shadow-2xs"
          title="Buka Video & 3D Spatial Reels"
        >
          <Film className="w-3.5 h-3.5 text-rose-500 fill-rose-500" />
          <span>Reels / Video</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* 2. STORIES / AVATARS HORIZONTAL REEL (Sesuai Gambar Referensi)            */}
      {/* ========================================================================= */}
      <div className="flex items-center gap-3.5 overflow-x-auto no-scrollbar py-2 px-1">
        {stories.map((story) => (
          <div
            key={story.id}
            onClick={() => {
              if (story.isAdd && onOpenCreateModal) {
                onOpenCreateModal();
              } else if (story.isLive && onOpenLiveStage) {
                onOpenLiveStage();
              } else if (story.id === 's-3d-world') {
                onOpenWorld3D();
              }
            }}
            className="flex flex-col items-center gap-1 shrink-0 cursor-pointer group active:scale-95 transition"
          >
            {story.isAdd ? (
              /* '+' Tambah Story circle with blue dashed border */
              <div className="w-15 h-15 rounded-full border-2 border-dashed border-blue-400 bg-blue-50/70 flex items-center justify-center text-blue-600 shadow-2xs group-hover:bg-blue-100 transition">
                <span className="text-2xl font-light leading-none">+</span>
              </div>
            ) : (
              <div className="relative">
                {/* Ring border */}
                <div className={`w-15 h-15 rounded-full p-0.5 bg-gradient-to-tr ${story.ringColor} shadow-2xs`}>
                  <img
                    src={story.img || undefined}
                    alt={story.name}
                    className="w-full h-full rounded-full object-cover border-2 border-white"
                  />
                </div>

                {/* Pink 'LIVE' badge pill if live */}
                {story.isLive && (
                  <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 px-2 py-0.2 rounded-full bg-rose-600 text-white text-[8px] font-black uppercase tracking-wider ring-2 ring-white shadow-xs">
                    LIVE
                  </span>
                )}
              </div>
            )}
            <span className="text-[11px] font-semibold text-slate-800 truncate max-w-[68px] mt-0.5">
              {story.name}
            </span>
          </div>
        ))}
      </div>

      {/* ========================================================================= */}
      {/* 3. PROMINENT LIVE STAGE HERO BANNER (Sesuai Gambar Referensi)              */}
      {/* ========================================================================= */}
      <div className="relative rounded-3xl overflow-hidden border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] bg-gradient-to-r from-purple-950 via-indigo-950 to-slate-950 text-white p-4.5 sm:p-5">
        
        {/* Top Badges Row */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-950/80 border border-rose-500/50 text-rose-300 text-[10px] font-black uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            <span>{productionMode ? "LIVE STAGE" : "SEDANG LIVE SEKARANG"}</span>
          </div>
          {!productionMode && <span className="text-xs font-semibold text-slate-300">2.4K Menonton</span>}
        </div>

        {/* Title & Host info */}
        <div className="relative z-10 space-y-1 max-w-sm">
          <h3 className="text-base sm:text-lg font-black text-white leading-tight">
            {productionMode ? "Live Stage & 3D Spatial Universe" : "AI Innovation & 3D Spatial Universe Summit 2026"}
          </h3>
          <p className="text-xs text-slate-300 leading-snug">
            Jelajahi panggung pengalaman, acara, dan dunia 3D Allpha Universe.
          </p>
        </div>

        {/* Join Button & Background Graphics */}
        <div className="flex items-center justify-between mt-3.5 pt-1 relative z-10">
          <button
            onClick={onOpenLiveStage}
            className="px-4 py-2 rounded-full bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-400 hover:to-rose-400 text-white font-extrabold text-xs shadow-md border border-pink-400/40 flex items-center gap-1.5 cursor-pointer active:scale-95 transition"
          >
            <span>🎙️ Gabung Live Stage</span>
            <span className="text-sm">↗</span>
          </button>

          {/* Right Holographic 3D Crystal 'A' Pyramid & Avatars */}
          <div className="flex items-center -space-x-2 shrink-0" aria-hidden="true">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-indigo-100 text-indigo-700 shadow-md"><Sparkles className="h-4 w-4" /></div>
            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-cyan-400 bg-sky-100 text-sky-700 shadow-md"><Bot className="h-4 w-4" /></div>
          </div>
        </div>

        {/* Ambient background glow */}
        <div className="absolute right-0 top-0 bottom-0 w-44 bg-gradient-to-l from-cyan-500/20 via-purple-500/10 to-transparent pointer-events-none" />
      </div>

      {/* ========================================================================= */}
      {/* 4. FEED POSTS STREAM (Neo-Brutalist Soft Pastel Cards Sesuai Referensi)     */}
      {/* ========================================================================= */}
      <div className="space-y-4.5">
        {productionMode && feedFilter !== 'FOR_YOU' && <section className="rounded-3xl border-2 border-dashed border-slate-300 bg-white p-5 text-center"><p className="text-sm font-black text-slate-900">{feedFilter === 'FOLLOWING' ? 'Feed Mengikuti belum tersedia' : 'Feed AI Agents belum tersedia'}</p><p className="mt-1 text-xs text-slate-500">{feedFilter === 'FOLLOWING' ? 'API feed belum menyediakan filter relasi mengikuti. Konten tidak diganti dengan feed umum.' : 'API konten belum mengembalikan atribusi AI Agent yang terverifikasi.'}</p></section>}
        {visiblePosts.map((post) => {
          const isCommentsOpen = expandedCommentsPostId === post.id;

          return (
            <article
              key={post.id}
              className="bg-white rounded-[28px] p-4.5 sm:p-5 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3.5 transition"
            >
              {/* Row 1: Human Owner Header */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-3 min-w-0">
                  {post.humanOwner.avatar ? <img src={post.humanOwner.avatar} alt={post.humanOwner.name} className="w-11 h-11 rounded-full object-cover border border-slate-300 shrink-0" /> : <div aria-label={post.humanOwner.name} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-300 bg-sky-100 text-sky-800"><Sparkles className="h-5 w-5" /></div>}
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <h4 className="font-extrabold text-sm text-slate-900 tracking-tight truncate">
                        {post.humanOwner.name}
                      </h4>
                      {/* Blue Verified Badge */}
                      {post.humanOwner.verified && <span className="w-4 h-4 rounded-full bg-blue-500 text-white flex items-center justify-center text-[10px] font-black shrink-0">✓</span>}
                    </div>
                    <p className="text-xs text-slate-500 truncate">
                      {post.humanOwner.handle} · {post.timestamp}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {/* Pastel Blue Pill: HUMAN OWNER */}
                  <span className="px-3 py-1 rounded-full bg-sky-100 text-sky-700 text-[10px] font-black uppercase tracking-wider">
                    {productionMode ? "KREATOR" : "HUMAN OWNER"}
                  </span>
                  <button className="text-slate-400 hover:text-slate-800 p-1">
                    <MoreHorizontal className="w-4.5 h-4.5" />
                  </button>
                </div>
              </div>

              {(!productionMode || post.aiAgent.name !== "—") && <>
              {/* Row 2: AI Agent Co-Creator Section */}
              <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-100">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="relative shrink-0">
                    {post.aiAgent.avatar ? <img src={post.aiAgent.avatar} alt={post.aiAgent.name} className="w-11 h-11 rounded-full object-cover border-2 border-cyan-400" /> : <div aria-label={post.aiAgent.name} className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-cyan-400 bg-sky-100 text-sky-800"><Bot className="h-5 w-5" /></div>}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-extrabold text-sm text-slate-900 truncate">
                        {post.aiAgent.name}
                      </span>
                      {/* Blue Verified Badge */}
                      <span className="w-3.5 h-3.5 rounded-full bg-blue-500 text-white flex items-center justify-center text-[9px] font-black shrink-0">
                        ✓
                      </span>
                      {/* Pastel Green Pill: AI AGENT */}
                      <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[9px] font-black uppercase tracking-wider">
                        AI AGENT
                      </span>
                      {/* Green Online Dot */}
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Online
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 truncate">
                      {post.aiAgent.specialty}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                  {/* Pastel Purple Pill: AI AUTO-REPLY AKTIF */}
                  <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-purple-100 text-purple-700 text-[10px] font-bold">
                    <span>⚡</span>
                    <span>AI AUTO-REPLY AKTIF</span>
                  </span>

                  {/* Take Over Button */}
                  <button
                    onClick={() => onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty)}
                    className="px-2.5 py-1 rounded-xl bg-white hover:bg-slate-50 border-2 border-slate-900 text-slate-900 font-black text-xs shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
                  >
                    <span className="text-[11px]">👤</span>
                    <span>TAKE OVER</span>
                  </button>
                </div>
              </div>
              </>}

              {/* Row 3: Content Body Text */}
              <div 
                onClick={() => onSelectPost ? onSelectPost(post) : null}
                className="cursor-pointer"
              >
                <p className="text-slate-900 text-sm leading-relaxed whitespace-pre-line font-medium">
                  {post.content}
                </p>
              </div>

              {/* Row 4: Embedded 3D District / Media Card (Sesuai Referensi Gambar) */}
              {post.has3DModel && (
                <div className="relative rounded-2xl overflow-hidden border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] aspect-[21/9] sm:aspect-[23/9] bg-slate-950 group">
                  <img
                    src={post.image || undefined}
                    alt={post.modelName || '3D District'}
                    className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950/70 via-transparent to-black/20" />

                  {/* Floating badge on top left: [A] Crystal District / Pusat Kreator & Inovasi */}
                  <div className="absolute top-3 left-3 flex items-center gap-2 p-1.5 pr-3 rounded-xl bg-white/95 backdrop-blur-md border border-slate-200 shadow-sm">
                    <div className="w-7 h-7 rounded-lg bg-slate-900 text-white flex items-center justify-center font-black text-xs">
                      A
                    </div>
                    <div>
                      <h5 className="font-extrabold text-xs text-slate-900 leading-tight">
                        {post.modelName || 'Crystal District'}
                      </h5>
                      <p className="text-[10px] text-slate-500 font-medium">
                        {post.modelSub || 'Pusat Kreator & Inovasi'}
                      </p>
                    </div>
                  </div>

                  {/* Floating button on bottom right: [BUKA 3D WORLD →] */}
                  <div className="absolute bottom-3 right-3 flex items-center gap-2">
                    <button
                      onClick={onOpenWorld3D}
                      className="px-4 py-2 rounded-full bg-white hover:bg-purple-50 text-purple-700 border-2 border-slate-900 font-black text-xs shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                    >
                      <span>BUKA 3D WORLD</span>
                      <span>→</span>
                    </button>
                  </div>

                  {/* Next carousel chevron button on right */}
                  <button 
                    onClick={onOpenWorld3D}
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-white/90 hover:bg-white border border-slate-300 text-slate-800 flex items-center justify-center shadow-sm"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Row 5: Action & Engagement Bar */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-4 text-xs font-bold text-slate-700">
                  {/* Like Button */}
                  <button
                    onClick={() => onLikePost(post.id)}
                    className="flex items-center gap-1.5 hover:text-rose-600 transition cursor-pointer"
                  >
                    <Heart className={`w-4.5 h-4.5 ${post.isLiked ? 'fill-rose-500 text-rose-500' : 'text-slate-700 hover:text-rose-500'}`} />
                    <span>{post.likes}</span>
                  </button>

                  {/* Comment Button */}
                  <button
                    onClick={() => { setExpandedCommentsPostId(isCommentsOpen ? null : post.id); if (!isCommentsOpen) onLoadComments?.(post.id); }}
                    className="flex items-center gap-1.5 hover:text-blue-600 transition cursor-pointer"
                  >
                    <MessageCircle className="w-4.5 h-4.5 text-slate-700 hover:text-blue-600" />
                    <span>{post.commentsCount}</span>
                  </button>

                  {/* Repost Button */}
                  <button
                    onClick={() => onRepostPost?.(post.id)}
                    disabled={!onRepostPost}
                    title={onRepostPost ? "Repost konten" : "Repost belum tersedia pada API produksi"}
                    className="flex items-center gap-1.5 hover:text-emerald-600 transition cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Repeat2 className="w-4.5 h-4.5 text-slate-700 hover:text-emerald-600" />
                    {!productionMode && <span>{post.reposts}</span>}
                  </button>

                  {/* Share Button */}
                  <button
                    onClick={() => onSharePost?.(post.id)}
                    disabled={!onSharePost}
                    title={onSharePost ? "Bagikan konten" : "Berbagi belum tersedia"}
                    className="hover:text-slate-900 transition cursor-pointer"
                  >
                    <Share2 className="w-4.5 h-4.5 text-slate-700" />
                  </button>
                </div>

                {/* Right CTA Button: [💬 Tanya Luna] (Playful Neo-Brutalist Soft Pastel Purple Pill) */}
                {(!productionMode || post.aiAgent.name !== "—") && <button
                  onClick={() => onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty)}
                  className="px-4 py-1.5 rounded-full bg-purple-100 hover:bg-purple-200 text-purple-800 border-2 border-purple-600 font-extrabold text-xs shadow-[1.5px_1.5px_0px_#7c3aed] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                >
                  <MessageCircle className="w-3.5 h-3.5 text-purple-700 fill-purple-700/20" />
                  <span>Tanya {post.aiAgent.name.split(' ')[0]}</span>
                </button>}
              </div>

              {/* Row 6: Hashtags Pills (Neo-Brutalist Soft Pastel Pills Sesuai Referensi) */}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {post.tags && post.tags.map((tag, idx) => {
                  const colors = [
                    'bg-sky-50 text-sky-700 border-sky-200',
                    'bg-purple-50 text-purple-700 border-purple-200',
                    'bg-cyan-50 text-cyan-700 border-cyan-200',
                    'bg-slate-50 text-slate-700 border-slate-200',
                  ];
                  const colorClass = colors[idx % colors.length];

                  return (
                    <span
                      key={tag}
                      className={`px-3 py-1 rounded-full text-xs font-semibold border ${colorClass} hover:opacity-80 transition cursor-pointer`}
                    >
                      {tag}
                    </span>
                  );
                })}

                {!productionMode && <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200 cursor-pointer">+3</span>}
              </div>

              {/* Expandable Comments Drawer */}
              {isCommentsOpen && (
                <div className="pt-3 border-t-2 border-slate-100 space-y-3 animate-in fade-in duration-200">
                  <div className="space-y-2">
                    {post.comments.map((c) => (
                      <div key={c.id} className="p-2.5 rounded-2xl bg-slate-50 border border-slate-200 flex items-start gap-2.5 text-xs">
                        {c.authorAvatar ? <img src={c.authorAvatar} alt={c.authorName} className="w-7 h-7 rounded-full object-cover" /> : <div aria-label={c.authorName} className="w-7 h-7 rounded-full bg-sky-100 text-sky-800 flex items-center justify-center"><Sparkles className="w-3.5 h-3.5" /></div>}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-900">{c.authorName}</span>
                            <span className="text-[10px] text-slate-500">{c.timestamp}</span>
                            {c.isAi && (
                              <span className="px-1.5 py-0.2 rounded-full bg-emerald-100 text-emerald-800 text-[8px] font-bold">
                                AI
                              </span>
                            )}
                          </div>
                          <p className="text-slate-700 mt-0.5">{c.content}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add Comment Input */}
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Tulis komentar publik..."
                      value={commentInput[post.id] || ''}
                      onChange={(e) => setCommentInput({ ...commentInput, [post.id]: e.target.value })}
                      onKeyDown={(e) => e.key === 'Enter' && handleSendComment(post.id)}
                      className="flex-1 px-3.5 py-2 rounded-full bg-slate-50 border-2 border-slate-900 text-xs font-medium outline-none focus:bg-white"
                    />
                    <button
                      onClick={() => handleSendComment(post.id)}
                      className="px-4 py-2 rounded-full bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5"
                    >
                      Kirim
                    </button>
                  </div>
                </div>
              )}

            </article>
          );
        })}
      </div>

    </div>
  );
}
