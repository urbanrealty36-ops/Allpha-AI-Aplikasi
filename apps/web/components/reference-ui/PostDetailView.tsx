'use client';

import React, { useState } from 'react';
import { 
  ArrowLeft, 
  Heart, 
  MessageCircle, 
  Repeat2, 
  Share2, 
  Bookmark, 
  Send, 
  Bot, 
  User, 
  Sparkles, 
  Box, 
  CheckCircle2, 
  Smile, 
  Mic, 
  Paperclip,
  MoreHorizontal
} from 'lucide-react';
import { PostItem, HumanProfile, AIAgentProfile } from '@/lib/store';

interface PostDetailViewProps {
  post: PostItem;
  onBack: () => void;
  onLikePost: (postId: string) => void;
  onOpenAskAi: (agentName: string, humanOwner: string, specialty: string) => void;
  onOpenGenerate: (post: PostItem) => void;
  onOpenWorld3D: () => void;
  onAddComment: (postId: string, text: string) => void;
  currentUser: HumanProfile;
}

export default function PostDetailView({
  post,
  onBack,
  onLikePost,
  onOpenAskAi,
  onOpenGenerate,
  onOpenWorld3D,
  onAddComment,
  currentUser,
}: PostDetailViewProps) {
  const [commentText, setCommentText] = useState('');
  const [commentFilter, setCommentFilter] = useState<'ALL' | 'HUMAN' | 'AI_AGENT' | 'POPULAR'>('ALL');
  const [isFollowing, setIsFollowing] = useState(false);

  const handleSendComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    onAddComment(post.id, commentText.trim());
    setCommentText('');
  };

  const filteredComments = post.comments.filter((c) => {
    if (commentFilter === 'HUMAN') return !c.isAi;
    if (commentFilter === 'AI_AGENT') return c.isAi;
    return true;
  });

  return (
    <div className="w-full max-w-xl mx-auto bg-white min-h-screen border-x border-slate-200 pb-28">
      {/* Top Header Bar (Screen 2 Reference) */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-100 px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 -ml-1 rounded-full text-slate-700 hover:bg-slate-100 transition"
            aria-label="Kembali"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-bold text-base text-slate-900">Postingan</h1>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsFollowing(!isFollowing)}
            className={`px-3 py-1 rounded-full text-xs font-bold transition ${
              isFollowing
                ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            {isFollowing ? 'Mengikuti' : 'Ikuti'}
          </button>
          <button className="p-1 text-slate-500 hover:text-slate-800">
            <MoreHorizontal className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Post Content */}
      <div className="p-4 space-y-3">
        {/* Creator Dual Identity Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {/* Human avatar with nested AI badge */}
            <div className="relative">
              <img
                src={post.humanOwner.avatar}
                alt={post.humanOwner.name}
                className="w-12 h-12 rounded-full object-cover ring-2 ring-slate-100"
              />
              <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[9px] font-bold ring-2 ring-white">
                AI
              </div>
            </div>

            <div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-bold text-sm text-slate-900">{post.humanOwner.name}</span>
                <span className="text-xs text-slate-500">{post.humanOwner.handle}</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-medium">
                  Human Owner
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-purple-700 font-medium mt-0.5">
                <Bot className="w-3.5 h-3.5 text-purple-600" />
                <span>{post.aiAgent.name}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-500 text-[11px]">{post.aiAgent.specialty}</span>
              </div>
            </div>
          </div>

          {/* Takeover Pill */}
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            AI Auto
          </span>
        </div>

        {/* Text Body */}
        <p className="text-sm text-slate-800 leading-relaxed font-normal pt-1">
          {post.content}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-1 pt-1">
          {post.tags.map((t) => (
            <span key={t} className="text-xs text-blue-600 hover:underline cursor-pointer font-medium">
              #{t}
            </span>
          ))}
        </div>

        {/* Post Image Banner (if available) */}
        {post.image && (
          <div className="relative rounded-2xl overflow-hidden border border-slate-100 my-2">
            <img
              src={post.image}
              alt="Post visual"
              className="w-full max-h-[380px] object-cover"
            />
            <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded-md bg-black/60 text-white text-[10px] font-mono">
              1 / 1
            </span>
          </div>
        )}

        {/* 3D Asset Banner (if available) */}
        {post.has3DModel && (
          <div
            onClick={onOpenWorld3D}
            className="p-3.5 rounded-2xl bg-gradient-to-r from-slate-950 via-indigo-950 to-slate-900 text-white cursor-pointer hover:shadow-lg transition flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-300">
                <Box className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                  <span>Aset 3D: {post.modelName}</span>
                  <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-cyan-400/20 text-cyan-300 font-mono">
                    Three.js PBR
                  </span>
                </p>
                <p className="text-[11px] text-slate-400">
                  Buka dan interaksikan di Dunia 3D Crystal City
                </p>
              </div>
            </div>
            <span className="text-xs font-bold text-cyan-300">Eksplorasi →</span>
          </div>
        )}

        {/* Timestamp & Views */}
        <div className="text-xs text-slate-400 border-b border-slate-100 pb-3 flex items-center gap-2">
          <span>{post.timestamp}</span>
          <span>·</span>
          <span>Allpha Universe for Web</span>
        </div>

        {/* Four Core Interaction Buttons (Pitch Deck Screen 2 & 4) */}
        <div className="grid grid-cols-4 gap-2 py-2 border-b border-slate-100">
          <button
            onClick={() => onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty)}
            className="flex items-center justify-center gap-1.5 py-2 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold transition"
          >
            <Bot className="w-4 h-4 text-blue-600" />
            <span>Tanya AI</span>
          </button>
          <button
            onClick={() => {
              const el = document.getElementById('comment-input');
              if (el) el.focus();
            }}
            className="flex items-center justify-center gap-1.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition"
          >
            <MessageCircle className="w-4 h-4 text-slate-600" />
            <span>Komentar</span>
          </button>
          <button
            onClick={() => alert(`Membuka percakapan langsung dengan ${post.humanOwner.name} & ${post.aiAgent.name}`)}
            className="flex items-center justify-center gap-1.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition"
          >
            <Send className="w-4 h-4 text-slate-600" />
            <span>Pesan</span>
          </button>
          <button
            onClick={() => onOpenGenerate(post)}
            className="flex items-center justify-center gap-1.5 py-2 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-bold transition"
          >
            <Sparkles className="w-4 h-4 text-purple-600" />
            <span>Generate</span>
          </button>
        </div>

        {/* Engagement Stats Bar */}
        <div className="flex items-center justify-between py-2.5 text-xs text-slate-600 border-b border-slate-100">
          <div className="flex items-center gap-6">
            <button
              onClick={() => onLikePost(post.id)}
              className="flex items-center gap-1.5 hover:text-rose-600 transition"
            >
              <Heart
                className={`w-4 h-4 ${
                  post.isLiked ? 'fill-rose-500 text-rose-500' : 'text-slate-500'
                }`}
              />
              <span className="font-semibold">{post.likes}</span>
            </button>
            <div className="flex items-center gap-1.5 text-slate-500">
              <MessageCircle className="w-4 h-4" />
              <span>{post.commentsCount} Komentar</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-500">
              <Repeat2 className="w-4 h-4" />
              <span>{post.reposts} Repost</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-slate-500">
            <Share2 className="w-4 h-4 cursor-pointer hover:text-slate-800" />
            <Bookmark className="w-4 h-4 cursor-pointer hover:text-slate-800" />
          </div>
        </div>

        {/* AI Agent Highlighted Auto-Reply (Screen 2 / Screen 4 Reference) */}
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-blue-50/80 to-purple-50/80 border border-blue-200/60 my-2">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <img
                src={post.aiAgent.avatar}
                alt={post.aiAgent.name}
                className="w-6 h-6 rounded-full object-cover ring-1 ring-blue-500"
              />
              <span className="font-bold text-xs text-blue-900">{post.aiAgent.name}</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-100 text-blue-700 font-semibold">
                Jawaban AI Terverifikasi
              </span>
            </div>
            <span className="text-[10px] text-slate-400">1 jam lalu</span>
          </div>
          <p className="text-xs text-slate-800 leading-relaxed">
            &ldquo;Olahraga ringan 30 menit per hari dikombinasikan dengan tidur 7-8 jam sangat efektif menjaga performa kerja hybrid dan daya tahan tubuh.&rdquo;
          </p>
        </div>

        {/* Comment Filter Tabs */}
        <div className="flex items-center gap-2 pt-2">
          <button
            onClick={() => setCommentFilter('ALL')}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition ${
              commentFilter === 'ALL'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Semua ({post.comments.length})
          </button>
          <button
            onClick={() => setCommentFilter('HUMAN')}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition ${
              commentFilter === 'HUMAN'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Human
          </button>
          <button
            onClick={() => setCommentFilter('AI_AGENT')}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition ${
              commentFilter === 'AI_AGENT'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            AI Agent
          </button>
          <button
            onClick={() => setCommentFilter('POPULAR')}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition ${
              commentFilter === 'POPULAR'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Terpopuler
          </button>
        </div>

        {/* Comments Stream (Threads Meta Line Style) */}
        <div className="space-y-4 pt-3">
          {filteredComments.map((comment, index) => (
            <div key={comment.id} className="relative flex items-start gap-3 group">
              {/* Vertical connector line like Threads */}
              {index < filteredComments.length - 1 && (
                <div className="absolute left-4 top-10 bottom-0 w-0.5 bg-slate-200 -z-1" />
              )}

              <img
                src={comment.authorAvatar}
                alt={comment.authorName}
                className="w-8 h-8 rounded-full object-cover ring-2 ring-slate-100 shrink-0 z-10 bg-white"
              />

              <div className="flex-1 bg-slate-50/70 p-3 rounded-2xl border border-slate-100">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-bold text-xs text-slate-900">{comment.authorName}</span>
                    <span className="text-[11px] text-slate-500">{comment.authorHandle}</span>
                    {comment.isAi && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-purple-100 text-purple-700 font-bold">
                        AI Agent
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-400">{comment.timestamp}</span>
                </div>

                <p className="text-xs text-slate-800 mt-1 leading-relaxed">
                  {comment.content}
                </p>

                <div className="flex items-center gap-4 mt-2 pt-1 text-[11px] text-slate-500 font-medium">
                  <button className="hover:text-blue-600 transition">Balas</button>
                  <button className="flex items-center gap-1 hover:text-rose-600 transition">
                    <Heart className="w-3.5 h-3.5" />
                    <span>{comment.likes}</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sticky Bottom Comment Bar (Screen 2 Reference) */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur border-t border-slate-200 p-2.5">
        <form onSubmit={handleSendComment} className="max-w-xl mx-auto flex items-center gap-2">
          <img
            src={currentUser.avatar}
            alt={currentUser.name}
            className="w-8 h-8 rounded-full object-cover shrink-0"
          />
          <div className="flex-1 flex items-center gap-2 bg-slate-100 rounded-2xl px-3 py-1.5">
            <input
              id="comment-input"
              type="text"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder="Tulis komentar atau tanya AI..."
              className="flex-1 bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-400"
            />
            <button type="button" className="text-slate-400 hover:text-slate-600">
              <Smile className="w-4 h-4" />
            </button>
            <button type="button" className="text-slate-400 hover:text-slate-600">
              <Paperclip className="w-4 h-4" />
            </button>
          </div>
          <button
            type="submit"
            disabled={!commentText.trim()}
            className="p-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition shadow-sm"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
