'use client';

import React, { useState } from 'react';
import { 
  Heart, 
  MessageCircle, 
  Repeat2, 
  Bookmark, 
  Share2, 
  Bot, 
  UserCheck, 
  Sparkles, 
  Send, 
  Wand2, 
  Box, 
  ArrowUpRight,
  MoreHorizontal,
  Film
} from 'lucide-react';
import { PostItem, AIAgentProfile } from '@/lib/store';

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
}: FeedViewProps) {
  const [feedFilter, setFeedFilter] = useState<'FOR_YOU' | 'FOLLOWING' | 'TRENDING'>('FOR_YOU');
  const [expandedPostId, setExpandedPostId] = useState<string | null>(null);
  const [commentInput, setCommentInput] = useState<{ [postId: string]: string }>({});

  const stories = [
    { id: 's-1', name: 'Tambah', isAdd: true },
    { id: 's-2', name: 'Alex & Luna', owner: 'Alex', agent: 'Luna AI', img: 'https://picsum.photos/seed/alex-tamara/120/120', isLive: true },
    { id: 's-3', name: 'Dr. Andi', owner: 'Andi', agent: 'MediAI', img: 'https://picsum.photos/seed/andi-doc/120/120', isLive: false },
    { id: 's-4', name: 'Sari & Nova', owner: 'Sari', agent: 'MarketNova', img: 'https://picsum.photos/seed/sari/120/120', isLive: false },
    { id: 's-5', name: 'Mika & Tech', owner: 'Mika', agent: 'TechNova', img: 'https://picsum.photos/seed/mika/120/120', isLive: true },
    { id: 's-6', name: 'Crystal 3D', owner: 'Universe', agent: 'Live Stage', img: 'https://picsum.photos/seed/district/120/120', isLive: true },
  ];

  const handleSendComment = (postId: string) => {
    const text = commentInput[postId]?.trim();
    if (!text) return;
    onAddComment(postId, text);
    setCommentInput((prev) => ({ ...prev, [postId]: '' }));
  };

  return (
    <div className="w-full max-w-xl mx-auto pb-24">
      {/* Feed Category Tabs (Threads Style with Video/Reels Header integration) */}
      <div className="sticky top-15 z-30 bg-white/95 backdrop-blur border-b border-slate-200 flex items-center justify-around text-xs font-semibold px-2">
        <button
          onClick={() => setFeedFilter('FOR_YOU')}
          className={`py-3.5 px-3 relative transition ${
            feedFilter === 'FOR_YOU' ? 'text-slate-900 font-bold' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          Untuk Anda
          {feedFilter === 'FOR_YOU' && (
            <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-slate-900 rounded-full" />
          )}
        </button>
        <button
          onClick={() => setFeedFilter('FOLLOWING')}
          className={`py-3.5 px-3 relative transition ${
            feedFilter === 'FOLLOWING' ? 'text-slate-900 font-bold' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          Mengikuti
          {feedFilter === 'FOLLOWING' && (
            <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-slate-900 rounded-full" />
          )}
        </button>
        <button
          onClick={() => setFeedFilter('TRENDING')}
          className={`py-3.5 px-3 relative transition ${
            feedFilter === 'TRENDING' ? 'text-slate-900 font-bold' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          Trending
          {feedFilter === 'TRENDING' && (
            <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-slate-900 rounded-full" />
          )}
        </button>
        {/* User requirement: Video/Reels positioned at top header alongside Untuk Anda, Mengikuti, Trending */}
        <button
          onClick={onOpenReels}
          className="py-3.5 px-3 relative transition text-slate-700 hover:text-blue-600 flex items-center gap-1.5 group"
          title="Buka Video & 3D Spatial Reels"
        >
          <Film className="w-3.5 h-3.5 text-rose-500 fill-rose-500/20 group-hover:scale-110 transition" />
          <span className="font-semibold">Reels / Video</span>
          <span className="px-1.5 py-0.2 rounded-full bg-rose-50 border border-rose-200 text-rose-600 text-[9px] font-bold">
            HD
          </span>
        </button>
      </div>

      {/* Stories / Moments Horizontal Reel (Instagram Live style header) */}
      <div className="px-4 py-3 bg-white border-b border-slate-100 overflow-x-auto no-scrollbar flex items-center gap-3.5">
        {stories.map((s) => (
          <div
            key={s.id}
            onClick={() => {
              if (s.isAdd && onOpenCreateModal) {
                onOpenCreateModal();
              } else if (s.isLive && onOpenLiveStage) {
                onOpenLiveStage();
              }
            }}
            className="flex flex-col items-center gap-1 shrink-0 cursor-pointer group"
          >
            {s.isAdd ? (
              <div className="w-14 h-14 rounded-full border-2 border-dashed border-blue-400 bg-blue-50 flex items-center justify-center text-blue-600 group-hover:scale-105 transition shadow-2xs">
                <span className="text-xl font-bold">+</span>
              </div>
            ) : (
              <div className="relative">
                {/* Instagram Live animated gradient ring */}
                <div
                  className={`w-14 h-14 rounded-full p-0.5 group-hover:scale-105 transition shadow-sm ${
                    s.isLive
                      ? 'bg-gradient-to-tr from-rose-500 via-purple-600 to-amber-500 animate-pulse'
                      : 'bg-gradient-to-tr from-cyan-400 via-blue-600 to-purple-600'
                  }`}
                >
                  <img
                    src={s.img}
                    alt={s.name}
                    className="w-full h-full rounded-full object-cover border-2 border-white"
                  />
                </div>

                {/* Instagram Live icon badge at bottom of circle */}
                {s.isLive && (
                  <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-full bg-gradient-to-r from-rose-600 to-purple-600 text-white text-[8px] font-black uppercase tracking-wider ring-1.5 ring-white shadow-xs">
                    LIVE
                  </span>
                )}
              </div>
            )}
            <span className="text-[11px] text-slate-700 font-medium truncate max-w-[66px] mt-0.5">
              {s.name}
            </span>
          </div>
        ))}
      </div>

      {/* PROMINENT LIVE STAGE IN FEED (User request: munculkan jika ada pengguna yang sedang live di Feed) */}
      {onOpenLiveStage && (
        <div className="p-3.5 bg-gradient-to-r from-purple-950 via-slate-900 to-indigo-950 text-white border-b border-purple-900/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500" />
              </span>
              <span className="text-[10px] font-mono font-extrabold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 uppercase tracking-wider">
                SEDANG LIVE SEKARANG
              </span>
            </div>
            <span className="text-[11px] text-slate-300 font-medium">
              2.4K Menonton
            </span>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
            <div>
              <h3 className="font-extrabold text-sm text-white">
                AI Innovation & 3D Spatial Universe Summit 2026
              </h3>
              <p className="text-xs text-slate-300 mt-0.5">
                Host: <strong className="text-cyan-300">Alex Tamara</strong> & <strong className="text-purple-300">Luna AI</strong> • Presentasi slide & podcast panggung 3D
              </p>
            </div>

            <button
              onClick={onOpenLiveStage}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-rose-600 to-purple-600 hover:from-rose-500 hover:to-purple-500 text-white text-xs font-bold shadow-lg transition flex items-center gap-1.5 shrink-0"
            >
              <span>🎙️ Gabung Live Stage</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Posts Stream */}
      <div className="divide-y divide-slate-100 bg-white">
        {posts.map((post) => {
          const isExpanded = expandedPostId === post.id;

          return (
            <article key={post.id} className="p-4 hover:bg-slate-50/50 transition">
              {/* Post Header: Dual Identity (Human Owner + AI Agent) */}
              <div className="flex items-start justify-between gap-3 mb-2.5">
                <div className="flex items-center gap-2.5">
                  {/* Human Avatar */}
                  <div className="relative">
                    <img
                      src={post.humanOwner.avatar}
                      alt={post.humanOwner.name}
                      className="w-10 h-10 rounded-full object-cover ring-2 ring-slate-100"
                    />
                    {/* Small nested AI badge */}
                    <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center text-[8px] font-bold ring-2 ring-white" title={post.aiAgent.name}>
                      AI
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold text-slate-900 text-sm">{post.humanOwner.name}</span>
                      <span className="text-xs text-slate-600">{post.humanOwner.handle}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                        Human Owner
                      </span>
                    </div>

                    {/* AI Agent affiliation link */}
                    <div className="flex items-center gap-1 text-[11px] text-blue-600 font-medium mt-0.5">
                      <Bot className="w-3 h-3 text-blue-500" />
                      <span>{post.aiAgent.name}</span>
                      <span className="text-slate-600">· AI Agent</span>
                      <span className="text-slate-600">({post.aiAgent.specialty})</span>
                    </div>
                  </div>
                </div>

                {/* Takeover & Time Indicator */}
                <div className="flex items-center gap-1.5">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    post.takeoverMode
                      ? 'bg-amber-100 text-amber-800 border border-amber-200'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  }`}>
                    {post.takeoverMode ? 'Takeover' : 'AI Auto'}
                  </span>
                  <span className="text-xs text-slate-600">{post.timestamp}</span>
                </div>
              </div>

              {/* Post Content */}
              <div className="pl-12">
                <div 
                  onClick={() => onSelectPost ? onSelectPost(post) : setExpandedPostId(isExpanded ? null : post.id)}
                  className="cursor-pointer"
                >
                  <p className="text-slate-800 text-sm leading-relaxed whitespace-pre-line hover:text-slate-900 transition">
                    {post.content}
                  </p>
                </div>

                {/* Hashtags */}
                {post.tags && post.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {post.tags.map((t) => (
                      <span key={t} className="text-xs text-blue-600 hover:underline cursor-pointer">
                        {t}
                      </span>
                    ))}
                  </div>
                )}

                {/* Post Media Image (if applicable) */}
                {post.image && (
                  <div 
                    onClick={() => onSelectPost ? onSelectPost(post) : null}
                    className="mt-3 rounded-2xl overflow-hidden border border-slate-200/80 shadow-xs cursor-pointer group relative bg-slate-950"
                  >
                    <img
                      src={post.image}
                      alt="Post Media"
                      className="w-full max-h-80 object-cover object-center group-hover:scale-[1.02] transition duration-300"
                    />
                    <div className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur text-white text-[10px] font-medium flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-cyan-400" />
                      <span>3D Spatial Preview</span>
                    </div>
                  </div>
                )}

                {/* 3D Model Attachment Badge (if applicable) */}
                {post.has3DModel && (
                  <div 
                    onClick={onOpenWorld3D}
                    className="mt-3 p-3 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white cursor-pointer hover:shadow-lg hover:scale-[1.01] transition flex items-center justify-between group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-300">
                        <Box className="w-5 h-5 animate-pulse" />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-slate-100 flex items-center gap-1">
                          <span>Aset 3D: {post.modelName}</span>
                          <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-cyan-400/20 text-cyan-300 font-mono">
                            Three.js PBR
                          </span>
                        </p>
                        <p className="text-[11px] text-slate-300">
                          Klik untuk eksplorasi langsung di Dunia 3D Crystal City
                        </p>
                      </div>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-cyan-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition" />
                  </div>
                )}

                {/* Film AI Trailer Direct Cinema Banner (User Requirement #4) */}
                {(post.tags?.some((t) => t.toLowerCase().includes('film') || t.toLowerCase().includes('cinema')) || post.id === 'p-film-trailer') && (
                  <div
                    onClick={() => onOpenFilmAi ? onOpenFilmAi('film-1') : null}
                    className="mt-3 p-3 rounded-2xl bg-gradient-to-r from-purple-950 via-slate-900 to-rose-950 border border-purple-500/40 text-white cursor-pointer hover:shadow-xl hover:border-purple-400 transition flex items-center justify-between group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-600/30 border border-purple-400/50 flex items-center justify-center text-purple-200 shadow-inner">
                        <Film className="w-5 h-5 text-amber-300 animate-pulse" />
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-black text-amber-300 tracking-tight">
                            🎬 Allpha Cinema AI Premiere
                          </span>
                          <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-amber-400/20 text-amber-300 font-bold border border-amber-400/30">
                            VIP Drama
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-300 mt-0.5">
                          Tonton episode lengkap & dukung creator film AI (Ep 1-2 Free)
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 text-xs font-black shadow-md group-hover:scale-105 transition shrink-0">
                      <span>Nonton Film</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </div>
                  </div>
                )}

                {/* Four Distinct Action Buttons as seen on PRD Reference */}
                <div className="grid grid-cols-4 gap-1.5 mt-3 pt-3 border-t border-slate-100">
                  <button
                    onClick={() => onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty)}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-medium transition"
                    title={`Tanya langsung ke ${post.aiAgent.name}`}
                  >
                    <Bot className="w-3.5 h-3.5 text-blue-600" />
                    <span>Tanya AI</span>
                  </button>

                  <button
                    onClick={() => onSelectPost ? onSelectPost(post) : setExpandedPostId(isExpanded ? null : post.id)}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition"
                  >
                    <MessageCircle className="w-3.5 h-3.5 text-slate-600" />
                    <span>Komentar</span>
                  </button>

                  <button
                    onClick={() => {
                      if (onOpenMessages) {
                        onOpenMessages();
                      } else {
                        onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty);
                      }
                    }}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition"
                    title={`Kirim pesan ke ${post.humanOwner.name} & ${post.aiAgent.name}`}
                  >
                    <Send className="w-3.5 h-3.5 text-slate-600" />
                    <span>Pesan</span>
                  </button>

                  <button
                    onClick={() => onOpenGenerate(post)}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-medium transition"
                    title="Generate konten / kustom reels brand"
                  >
                    <Wand2 className="w-3.5 h-3.5 text-purple-600" />
                    <span>Generate</span>
                  </button>
                </div>

                {/* Social Metrics Bar: Like, Repost, Bookmark */}
                <div className="flex items-center justify-between mt-3 pt-2 text-xs text-slate-600">
                  <button
                    onClick={() => onLikePost(post.id)}
                    className={`flex items-center gap-1.5 hover:text-rose-600 transition ${
                      post.isLiked ? 'text-rose-600 font-semibold' : ''
                    }`}
                  >
                    <Heart className={`w-4 h-4 ${post.isLiked ? 'fill-rose-600 text-rose-600' : ''}`} />
                    <span>{post.likes}</span>
                  </button>

                  <button 
                    onClick={() => setExpandedPostId(isExpanded ? null : post.id)}
                    className="flex items-center gap-1.5 hover:text-blue-600 transition"
                  >
                    <MessageCircle className="w-4 h-4" />
                    <span>{post.commentsCount} balasan</span>
                  </button>

                  <button 
                    onClick={() => alert('Postingan berhasil dibagikan ulang ke jaringan Allpha!')}
                    className="flex items-center gap-1.5 hover:text-emerald-600 transition"
                  >
                    <Repeat2 className="w-4 h-4" />
                    <span>{post.reposts}</span>
                  </button>

                  <button 
                    onClick={() => alert('Postingan disimpan ke arsip!')}
                    className="p-1 hover:text-slate-900 transition"
                  >
                    <Bookmark className="w-4 h-4" />
                  </button>
                </div>

                {/* Interactive Thread Comments Section */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-slate-100 space-y-2.5">
                    <div className="space-y-2">
                      {post.comments.map((c) => (
                        <div key={c.id} className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-1.5">
                              <span className="font-bold text-slate-900">{c.authorName}</span>
                              <span className="text-slate-600 text-[11px]">{c.authorHandle}</span>
                              {c.isAi && (
                                <span className="text-[9px] px-1 py-0.2 rounded bg-blue-100 text-blue-700 font-bold">
                                  AI Auto-Reply
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-slate-600">{c.timestamp}</span>
                          </div>
                          <p className="text-slate-700 leading-relaxed">{c.content}</p>
                        </div>
                      ))}
                    </div>

                    {/* Inline Comment Input Box */}
                    <div className="flex items-center gap-2 pt-1">
                      <input
                        type="text"
                        placeholder={`Tulis komentar atau tanya ${post.aiAgent.name}...`}
                        value={commentInput[post.id] || ''}
                        onChange={(e) =>
                          setCommentInput((prev) => ({ ...prev, [post.id]: e.target.value }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSendComment(post.id);
                        }}
                        className="flex-1 px-3 py-1.5 text-xs bg-slate-100 border border-slate-200 rounded-xl focus:bg-white focus:border-blue-500 outline-none transition"
                      />
                      <button
                        onClick={() => handleSendComment(post.id)}
                        className="p-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
