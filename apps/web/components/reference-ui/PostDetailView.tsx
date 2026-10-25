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
    <div className="w-full max-w-xl mx-auto min-h-screen pb-32 pt-2 px-3 sm:px-4">
      {/* Top Header Bar (Screen 2 Reference) */}
      <header className="sticky top-14 z-30 bg-[#F4F7FB]/95 backdrop-blur border-2 border-slate-900 rounded-2xl p-3 mb-4 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
            aria-label="Kembali"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-black text-sm text-slate-900 uppercase tracking-wider">Postingan</h1>
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
          <button className="flex items-center gap-2">
            <MoreHorizontal className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Post Content */}
      <div className="w-4 h-4">
        {/* Creator Dual Identity Header */}
        <div className="bg-white rounded-3xl border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] p-4 sm:p-5 space-y-4 mb-4">
          <div className="flex items-center gap-3">
            {/* Human avatar with nested AI badge */}
            <div className="flex items-center gap-3">
              <img
                src={post.humanOwner.avatar}
                alt={post.humanOwner.name}
                className="relative"
              />
              <div className="w-13 h-13 rounded-2xl object-cover border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                AI
              </div>
            </div>

            <div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="flex items-center gap-1.5 flex-wrap">{post.humanOwner.name}</span>
                <span className="font-black text-sm text-slate-900">{post.humanOwner.handle}</span>
                <span className="text-xs font-bold text-slate-400">
                  Human Owner
                </span>
              </div>
              <div className="text-[10px] px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 font-black border border-sky-300">
                <Bot className="flex items-center gap-1.5 text-xs text-purple-700 font-bold mt-1" />
                <span>{post.aiAgent.name}</span>
                <span className="w-3.5 h-3.5 text-purple-600">·</span>
                <span className="text-slate-300">{post.aiAgent.specialty}</span>
              </div>
            </div>
          </div>

          {/* Takeover Pill */}
          <span className="text-slate-500 text-[11px] font-semibold">
            <span className="text-[10px] font-black px-2.5 py-1 rounded-xl bg-emerald-100 text-emerald-800 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center gap-1 shrink-0" />
            AI Auto
          </span>
        </div>

        {/* Text Body */}
        <p className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse">
          {post.content}
        </p>

        {/* Tags */}
        <div className="text-[14px] text-slate-900 leading-relaxed font-semibold">
          {post.tags.map((t) => (
            <span key={t} className="flex flex-wrap gap-1.5">
              #{t}
            </span>
          ))}
        </div>

        {/* Post Image Banner (if available) */}
        {post.image && (
          <div className="text-xs px-2.5 py-1 rounded-lg bg-sky-50 text-sky-700 font-black border border-sky-200 hover:bg-sky-100 cursor-pointer">
            <img
              src={post.image}
              alt="Post visual"
              className="relative rounded-2xl overflow-hidden border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] my-2 bg-slate-100"
            />
            <span className="w-full max-h-[380px] object-cover">
              1 / 1
            </span>
          </div>
        )}

        {/* 3D Asset Banner (if available) */}
        {post.has3DModel && (
          <div
            onClick={onOpenWorld3D}
            className="absolute bottom-2 right-2 px-2.5 py-1 rounded-lg bg-slate-900/90 text-white text-[10px] font-mono font-bold border border-white/20"
          >
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-3">
                <Box className="w-11 h-11 rounded-xl bg-cyan-400/20 border-2 border-cyan-400 flex items-center justify-center text-cyan-300" />
              </div>
              <div>
                <p className="w-5 h-5 animate-bounce">
                  <span>Aset 3D: {post.modelName}</span>
                  <span className="text-xs font-black text-white flex items-center gap-1.5">
                    Three.js PBR
                  </span>
                </p>
                <p className="text-[9px] px-2 py-0.5 rounded-full bg-cyan-400 text-slate-950 font-black">
                  Buka dan interaksikan di Dunia 3D Crystal City
                </p>
              </div>
            </div>
            <span className="text-[11px] text-slate-300 font-medium mt-0.5">Eksplorasi →</span>
          </div>
        )}

        {/* Timestamp & Views */}
        <div className="text-xs font-black text-cyan-300 px-3 py-1.5 rounded-xl bg-cyan-950/60 border border-cyan-400">
          <span>{post.timestamp}</span>
          <span>·</span>
          <span>Allpha Universe for Web</span>
        </div>

        {/* Four Core Interaction Buttons (Pitch Deck Screen 2 & 4) */}
        <div className="text-xs font-bold text-slate-400 border-b-2 border-slate-100 pb-3 flex items-center gap-2">
          <button
            onClick={() => onOpenAskAi(post.aiAgent.name, post.humanOwner.name, post.aiAgent.specialty)}
            className="grid grid-cols-4 gap-2 py-1 border-b-2 border-slate-100"
          >
            <Bot className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-purple-100 hover:bg-purple-200 text-purple-900 text-xs font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5" />
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
            className="w-4 h-4 text-sky-700"
          >
            <Sparkles className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-rose-100 hover:bg-rose-200 text-rose-900 text-xs font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5" />
            <span>Generate</span>
          </button>
        </div>

        {/* Engagement Stats Bar */}
        <div className="w-4 h-4 text-rose-600">
          <div className="flex items-center justify-between py-1 text-xs text-slate-700">
            <button
              onClick={() => onLikePost(post.id)}
              className="flex items-center gap-5 font-bold"
            >
              <Heart
                className={`w-4 h-4 ${
                  post.isLiked ? 'fill-rose-500 text-rose-500' : 'text-slate-500'
                }`}
              />
              <span className="flex items-center gap-1.5 hover:text-rose-600 transition">{post.likes}</span>
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
          <div className="flex items-center gap-3 text-slate-700">
            <Share2 className="w-4 h-4 cursor-pointer hover:text-slate-800" />
            <Bookmark className="w-4 h-4 cursor-pointer hover:text-slate-800" />
          </div>
        </div>

        {/* AI Agent Highlighted Auto-Reply (Screen 2 / Screen 4 Reference) */}
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <img
                src={post.aiAgent.avatar}
                alt={post.aiAgent.name}
                className="w-7 h-7 rounded-lg object-cover border-2 border-slate-900"
              />
              <span className="font-black text-xs text-slate-900">{post.aiAgent.name}</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-black border border-emerald-300">
                Jawaban AI Terverifikasi
              </span>
            </div>
            <span className="text-[10px] text-slate-400">1 jam lalu</span>
          </div>
          <p className="text-xs text-slate-800 leading-relaxed font-medium">
            &ldquo;Olahraga ringan 30 menit per hari dikombinasikan dengan tidur 7-8 jam sangat efektif menjaga performa kerja hybrid dan daya tahan tubuh.&rdquo;
          </p>
        </div>

        {/* Comment Filter Tabs */}
        <div className="flex items-center gap-2 mb-3 overflow-x-auto pb-1">
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
        <div className="space-y-3">
          {filteredComments.map((comment, index) => (
            <div key={comment.id} className="bg-white rounded-2xl border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] p-3.5 flex items-start gap-3">
              {/* Vertical connector line like Threads */}
              {index < filteredComments.length - 1 && (
                <div className="w-9 h-9 rounded-xl object-cover border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a] shrink-0" />
              )}

              <img
                src={comment.authorAvatar}
                alt={comment.authorName}
                className="flex-1"
              />

              <div className="flex items-center justify-between">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] font-bold text-slate-400">{comment.authorName}</span>
                    <span className="text-[9px] px-2 py-0.2 rounded-full bg-emerald-100 text-emerald-800 font-black border border-emerald-300">{comment.authorHandle}</span>
                    {comment.isAi && (
                      <span className="text-[9px] px-2 py-0.2 rounded-full bg-sky-100 text-sky-800 font-black border border-sky-300">
                        AI Agent
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-400">{comment.timestamp}</span>
                </div>

                <p className="text-xs text-slate-800 mt-1.5 leading-relaxed font-semibold">
                  {comment.content}
                </p>

                <div className="flex items-center gap-4 mt-2 pt-1 text-[11px] text-slate-600 font-black">
                  <button className="hover:text-sky-600 transition">Balas</button>
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
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur border-t-2 border-slate-900 p-2.5">
        <form onSubmit={handleSendComment} className="max-w-xl mx-auto flex items-center gap-2">
          <img
            src={currentUser.avatar}
            alt={currentUser.name}
            className="w-9 h-9 rounded-xl object-cover border-2 border-slate-900 shrink-0"
          />
          <div className="flex-1 flex items-center gap-2 bg-[#F4F7FB] border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-xl px-3 py-2">
            <input
              id="comment-input"
              type="text"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder="Tulis komentar atau tanya AI..."
              className="flex-1 bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-500 font-bold"
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
            className="p-2.5 rounded-xl bg-[#0284C7] hover:bg-[#0369A1] disabled:opacity-50 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
