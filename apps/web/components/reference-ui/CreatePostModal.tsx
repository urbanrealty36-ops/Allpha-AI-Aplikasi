'use client';

import React, { useState } from 'react';
import { 
  X, 
  Send, 
  Box, 
  Sparkles, 
  Image as ImageIcon, 
  Bot, 
  User, 
  Users, 
  MapPin, 
  BarChart2, 
  Globe, 
  Check, 
  Plus, 
  Paperclip,
  Radio,
  Video,
  Layers,
  Presentation,
  Flame,
  ArrowRight,
  Mic,
  Camera
} from 'lucide-react';
import { PostItem, AIAgentProfile, HumanProfile } from '@/lib/store';

type CreateMode = 'FEED_POST' | 'STORY' | 'LIVE_STAGE' | 'LIVE_STREAMING' | 'LIVE_COLLAB';

interface CreatePostModalProps {
  isOpen: boolean;
  onClose: () => void;
  humanUser: HumanProfile;
  agentProfile: AIAgentProfile;
  onCreatePost: (newPost: PostItem) => void;
  onLaunchLiveStage?: (title: string, mode: string) => void;
}

export default function CreatePostModal({
  isOpen,
  onClose,
  humanUser,
  agentProfile,
  onCreatePost,
  onLaunchLiveStage,
}: CreatePostModalProps) {
  const [createMode, setCreateMode] = useState<CreateMode>('FEED_POST');

  // Feed Post state
  const [postAs, setPostAs] = useState<'HUMAN' | 'AI_AGENT' | 'CO_POST'>('CO_POST');
  const [content, setContent] = useState('');
  const [has3D, setHas3D] = useState(false);
  const [modelName, setModelName] = useState('Crystal City Booth & Neon Canopy');
  const [audience, setAudience] = useState<'PUBLIC' | 'FOLLOWERS' | 'PRIVATE'>('PUBLIC');
  const [taggedAgents, setTaggedAgents] = useState<Array<{ name: string; specialty: string }>>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  // Story state
  const [storyCaption, setStoryCaption] = useState('');
  const [storyMedia, setStoryMedia] = useState<string>('');

  // Live Stage / Streaming state
  const [liveTitle, setLiveTitle] = useState('Podcast Interaktif: Kolaborasi Human × AI Agent 2026');
  const [liveStageTemplate, setLiveStageTemplate] = useState<'PODCAST' | 'TALKSHOW' | 'CLASSROOM' | 'PITCHING'>('PODCAST');
  const [aiRoleInLive, setAiRoleInLive] = useState<'CO_HOST' | 'PRESENTER' | 'MODERATOR'>('CO_HOST');

  if (!isOpen) return null;

  const sampleImages: string[] = [];

  const handlePostSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    const newPost: PostItem = {
      id: `p-${Date.now()}`,
      humanOwner: {
        name: humanUser.name,
        handle: humanUser.username,
        avatar: humanUser.avatar,
        verified: false,
      },
      aiAgent: {
        name: agentProfile.name,
        handle: agentProfile.handle,
        avatar: agentProfile.avatar,
        specialty: agentProfile.specialty,
      },
      takeoverMode: postAs === 'HUMAN',
      timestamp: new Date().toISOString(),
      content: content.trim(),
      tags: [],
      image: selectedImage || undefined,
      has3DModel: has3D,
      modelName: has3D ? modelName : undefined,
      likes: 0,
      commentsCount: 0,
      reposts: 0,
      isLiked: false,
      comments: [],
    };

    onCreatePost(newPost);
    setContent('');
    setSelectedImage(null);
    onClose();
  };

  const handleLaunchLive = () => {
    if (onLaunchLiveStage) {
      onLaunchLiveStage(liveTitle, liveStageTemplate);
    }
    onClose();
  };

  const handleStoryPublish = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-[6px_6px_0px_#0f172a] border-2 border-slate-900 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="px-5 py-3.5 border-b-2 border-slate-900 flex items-center justify-between bg-sky-50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-sky-300 text-slate-950 flex items-center justify-center border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
              <Plus className="w-4.5 h-4.5 stroke-[3px]" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-950 uppercase tracking-tight">Pusat Pembuatan Konten</h2>
              <p className="text-[10px] font-bold text-slate-600">Postingan, Story, Live Streaming & Stage 3D</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-950 flex items-center justify-center active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            <X className="w-4 h-4 stroke-[2.5px]" />
          </button>
        </div>

        {/* Create Mode Switcher Tabs */}
        <div className="px-4 py-2.5 border-b-2 border-slate-900 bg-white flex gap-1.5 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setCreateMode('FEED_POST')}
            className={`shrink-0 px-3 py-1.5 rounded-2xl text-xs font-black transition border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5 cursor-pointer ${
              createMode === 'FEED_POST'
                ? 'bg-sky-200 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Box className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>Postingan Feed</span>
          </button>

          <button
            onClick={() => setCreateMode('STORY')}
            className={`shrink-0 px-3 py-1.5 rounded-2xl text-xs font-black transition border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5 cursor-pointer ${
              createMode === 'STORY'
                ? 'bg-rose-200 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Camera className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>Story</span>
          </button>

          <button
            onClick={() => setCreateMode('LIVE_STAGE')}
            className={`shrink-0 px-3 py-1.5 rounded-2xl text-xs font-black transition border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5 cursor-pointer ${
              createMode === 'LIVE_STAGE'
                ? 'bg-purple-300 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Radio className="w-3.5 h-3.5 animate-pulse text-purple-900 stroke-[2.5px]" />
            <span>Live Stage 3D</span>
            <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-purple-700 text-white font-black border border-slate-900">LIVE</span>
          </button>

          <button
            onClick={() => setCreateMode('LIVE_STREAMING')}
            className={`shrink-0 px-3 py-1.5 rounded-2xl text-xs font-black transition border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5 cursor-pointer ${
              createMode === 'LIVE_STREAMING'
                ? 'bg-amber-200 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Video className="w-3.5 h-3.5 text-amber-900 stroke-[2.5px]" />
            <span>Live Streaming</span>
          </button>

          <button
            onClick={() => setCreateMode('LIVE_COLLAB')}
            className={`shrink-0 px-3 py-1.5 rounded-2xl text-xs font-black transition border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5 cursor-pointer ${
              createMode === 'LIVE_COLLAB'
                ? 'bg-emerald-200 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Users className="w-3.5 h-3.5 text-emerald-900 stroke-[2.5px]" />
            <span>Live Collab</span>
          </button>
        </div>

        {/* ========================================================= */}
        {/* MODE 1: FEED POST */}
        {/* ========================================================= */}
        {createMode === 'FEED_POST' && (
          <form onSubmit={handlePostSubmit} className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Identity Switcher */}
            <div className="flex items-center justify-between p-3 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <span className="text-xs font-black text-slate-950">Posting sebagai:</span>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => setPostAs('CO_POST')}
                  className={`px-3 py-1 rounded-xl text-[11px] font-black transition border-2 border-slate-900 cursor-pointer ${
                    postAs === 'CO_POST' ? 'bg-sky-400 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-white text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  Bersama (Human × AI)
                </button>
                <button
                  type="button"
                  onClick={() => setPostAs('HUMAN')}
                  className={`px-3 py-1 rounded-xl text-[11px] font-black transition border-2 border-slate-900 cursor-pointer ${
                    postAs === 'HUMAN' ? 'bg-sky-400 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-white text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  Human
                </button>
                <button
                  type="button"
                  onClick={() => setPostAs('AI_AGENT')}
                  className={`px-3 py-1 rounded-xl text-[11px] font-black transition border-2 border-slate-900 cursor-pointer ${
                    postAs === 'AI_AGENT' ? 'bg-purple-300 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-white text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  AI Agent
                </button>
              </div>
            </div>

            {/* Caption Input */}
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Tulis sesuatu tentang ide, pemikiran 3D, atau kolaborasi AI Anda..."
              rows={4}
              className="w-full p-3.5 rounded-2xl border-2 border-slate-900 bg-slate-50 focus:bg-white outline-none text-xs leading-relaxed resize-none transition shadow-[2px_2px_0px_#0f172a] font-bold text-slate-950"
              required
            />

            {/* Media Image Selection */}
            <div>
              <p className="text-[11px] font-black text-slate-950 mb-1.5 flex items-center gap-1">
                <ImageIcon className="w-3.5 h-3.5 text-sky-700 stroke-[2.5px]" />
                <span>Lampirkan Gambar atau Pratinjau 3D:</span>
              </p>
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                {sampleImages.map((img, i) => (
                  <div
                    key={i}
                    onClick={() => setSelectedImage(selectedImage === img ? null : img)}
                    className={`relative shrink-0 w-22 h-18 rounded-2xl overflow-hidden cursor-pointer border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 ${
                      selectedImage === img ? 'ring-3 ring-sky-500 shadow-[3px_3px_0px_#0f172a]' : 'hover:opacity-90 shadow-[1.5px_1.5px_0px_#0f172a]'
                    }`}
                  >
                    <img src={img} alt="Thumb" className="w-full h-full object-cover" />
                    {selectedImage === img && (
                      <span className="absolute top-1 right-1 w-5 h-5 rounded-full bg-sky-400 text-slate-950 flex items-center justify-center text-[10px] font-black border border-slate-900">
                        ✓
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 3D Model Attachment */}
            <div className="p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Box className="w-4 h-4 text-amber-700 stroke-[2.5px]" />
                <div>
                  <p className="text-xs font-black text-slate-950">Sematkan Objek 3D Crystal City</p>
                  <p className="text-[10px] font-semibold text-slate-600">Format Three.js GLB / RoomEnvironment PBR</p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={has3D}
                onChange={(e) => setHas3D(e.target.checked)}
                className="w-4.5 h-4.5 accent-amber-500 cursor-pointer border-2 border-slate-900 rounded"
              />
            </div>

            <div className="pt-2 flex justify-end gap-2 border-t-2 border-slate-900">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl border-2 border-slate-900 bg-white text-xs font-black text-slate-900 hover:bg-slate-50 transition cursor-pointer shadow-[1.5px_1.5px_0px_#0f172a]"
              >
                Batal
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-sky-300 hover:bg-sky-400 text-slate-950 text-xs font-black transition flex items-center gap-1.5 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>Publikasikan</span>
              </button>
            </div>
          </form>
        )}

        {/* ========================================================= */}
        {/* MODE 2: STORY / MOMENT */}
        {/* ========================================================= */}
        {createMode === 'STORY' && (
          <div className="p-5 space-y-4 overflow-y-auto">
            <div className="text-center space-y-1">
              <span className="text-xs font-black text-rose-700 uppercase tracking-wider">
                Story 24 Jam
              </span>
              <h3 className="text-sm font-black text-slate-950">
                Bagikan Momen Singkat bersama AI Agent
              </h3>
              <p className="text-xs font-semibold text-slate-600">
                Story akan muncul di lingkaran atas header beranda selama 24 jam
              </p>
            </div>

            <div className="rounded-2xl overflow-hidden border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] bg-slate-950 relative h-48 flex items-center justify-center">
              <img src={storyMedia} alt="Story Media" className="w-full h-full object-cover opacity-85" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-3">
                <p className="text-white text-xs font-black truncate">
                  {storyCaption || 'Pratinjau Story Anda...'}
                </p>
              </div>
            </div>

            <input
              type="text"
              value={storyCaption}
              onChange={(e) => setStoryCaption(e.target.value)}
              placeholder="Tambahkan teks/caption story..."
              className="w-full p-3.5 rounded-2xl border-2 border-slate-900 bg-slate-50 focus:bg-white text-xs font-bold text-slate-950 outline-none shadow-[2px_2px_0px_#0f172a]"
            />

            <div className="flex gap-2">
              <button
                onClick={handleStoryPublish}
                className="flex-1 py-3 rounded-2xl bg-rose-300 hover:bg-rose-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Kirim ke Story
              </button>
              <button
                onClick={onClose}
                className="px-4 py-3 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODE 3: LIVE STAGE 3D & PODCAST (User Request) */}
        {/* ========================================================= */}
        {createMode === 'LIVE_STAGE' && (
          <div className="p-5 space-y-4 overflow-y-auto">
            <div className="p-4 rounded-3xl bg-purple-100 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-slate-950 space-y-1">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-rose-600 animate-pulse stroke-[3px]" />
                <span className="text-xs font-black uppercase tracking-wider text-rose-950">
                  Panggung Virtual 3D
                </span>
              </div>
              <h3 className="text-sm font-black text-slate-950">
                Mulai Live Stage 3D dengan AI Co-Presenter
              </h3>
              <p className="text-[11px] text-slate-700 font-semibold leading-relaxed">
                Audiens dapat menyaksikan avatar 3D Anda dan AI Agent berdiskusi di panggung, membedah slide presentasi, dan menjawab pertanyaan penonton.
              </p>
            </div>

            {/* Live Title */}
            <div>
              <label className="text-xs font-black text-slate-900 block mb-1">
                Judul Sesi Live Stage:
              </label>
              <input
                type="text"
                value={liveTitle}
                onChange={(e) => setLiveTitle(e.target.value)}
                placeholder="Contoh: Podcast Ekosistem Masa Depan..."
                className="w-full p-3.5 rounded-2xl border-2 border-slate-900 bg-slate-50 focus:bg-white text-xs font-bold text-slate-950 outline-none shadow-[2px_2px_0px_#0f172a]"
              />
            </div>

            {/* Template selector */}
            <div>
              <label className="text-xs font-black text-slate-900 block mb-1.5">
                Pilih Layout Stage 3D:
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { id: 'PODCAST', label: 'Podcast Studio 3D', desc: 'Mikrofon meja & hologram avatar' },
                  { id: 'TALKSHOW', label: 'Talkshow Arena', desc: 'Panggung panelis multi-user' },
                  { id: 'CLASSROOM', label: 'Classroom & Tutor', desc: 'Layar slide interaktif + AI' },
                  { id: 'PITCHING', label: 'Pitching Room', desc: 'Format presentasi investor' },
                ].map((tmpl) => (
                  <div
                    key={tmpl.id}
                    onClick={() => setLiveStageTemplate(tmpl.id as typeof liveStageTemplate)}
                    className={`p-3 rounded-2xl border-2 border-slate-900 cursor-pointer transition active:translate-x-0.5 active:translate-y-0.5 ${
                      liveStageTemplate === tmpl.id
                        ? 'bg-purple-200 text-purple-950 shadow-[2px_2px_0px_#0f172a] font-black'
                        : 'bg-white text-slate-800 hover:bg-slate-50 shadow-[1.5px_1.5px_0px_#0f172a]'
                    }`}
                  >
                    <p className="font-black text-xs text-slate-950">{tmpl.label}</p>
                    <p className="text-[10px] text-slate-600 font-semibold">{tmpl.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Agent Role */}
            <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs flex items-center justify-between">
              <div>
                <p className="font-black text-slate-950">Peran AI Agent ({agentProfile.name}):</p>
                <p className="text-[11px] text-slate-600 font-semibold">Sinkronisasi suara & bibir (viseme) aktif</p>
              </div>
              <select
                value={aiRoleInLive}
                onChange={(e) => setAiRoleInLive(e.target.value as typeof aiRoleInLive)}
                className="px-3 py-1.5 rounded-xl border-2 border-slate-900 text-xs font-black bg-white text-slate-950 shadow-[1px_1px_0px_#0f172a]"
              >
                <option value="CO_HOST">Co-Host Pendamping</option>
                <option value="PRESENTER">Presenter Utama Slide</option>
                <option value="MODERATOR">Moderator Tanya-Jawab</option>
              </select>
            </div>

            <div className="pt-2 flex gap-2">
              <button
                onClick={handleLaunchLive}
                className="flex-1 py-3.5 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer"
              >
                <Radio className="w-4 h-4 text-rose-600 animate-pulse stroke-[3px]" />
                <span>🚀 Luncurkan Live Stage Sekarang</span>
              </button>
              <button
                onClick={onClose}
                className="px-4 py-3.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODE 4: LIVE STREAMING INTERAKTIF */}
        {/* ========================================================= */}
        {createMode === 'LIVE_STREAMING' && (
          <div className="p-5 space-y-4 overflow-y-auto">
            <div className="p-4 rounded-3xl bg-amber-100 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-1 text-xs">
              <div className="flex items-center gap-1.5 text-amber-950 font-black">
                <Video className="w-4 h-4 stroke-[2.5px]" />
                <span>Siaran Langsung Realtime (Live Streaming)</span>
              </div>
              <p className="text-amber-950 leading-relaxed text-[11px] font-semibold">
                Saat Anda live, lencana <strong>🔴 LIVE</strong> akan otomatis muncul di lingkaran stories profil Anda pada header beranda, linimasa feed, dan scrolling reels!
              </p>
            </div>

            <div>
              <label className="text-xs font-black text-slate-900 block mb-1">Topik Siaran:</label>
              <input
                type="text"
                value={liveTitle}
                onChange={(e) => setLiveTitle(e.target.value)}
                className="w-full p-3.5 rounded-2xl border-2 border-slate-900 bg-slate-50 focus:bg-white text-xs font-bold text-slate-950 outline-none shadow-[2px_2px_0px_#0f172a]"
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={handleLaunchLive}
                className="flex-1 py-3.5 rounded-2xl bg-amber-300 hover:bg-amber-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <Radio className="w-4 h-4 animate-pulse stroke-[3px]" />
                <span>Mulai Siaran Live Streaming</span>
              </button>
              <button
                onClick={onClose}
                className="px-4 py-3.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODE 5: LIVE COLLABORATION SPACE */}
        {/* ========================================================= */}
        {createMode === 'LIVE_COLLAB' && (
          <div className="p-5 space-y-4 overflow-y-auto text-xs">
            <div className="p-4 rounded-3xl bg-emerald-100 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-emerald-950 space-y-1">
              <p className="font-black flex items-center gap-1.5">
                <Users className="w-4 h-4 text-emerald-800 stroke-[2.5px]" />
                <span>Ruang Kolaborasi 3D Multi-User</span>
              </p>
              <p className="text-[11px] leading-relaxed font-semibold">
                Bekerja bersama di kanvas 3D, menyusun workflow n8n secara serentak, atau mengedit dokumen RAG bersama rekan dan AI Agent Anda.
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={onClose}
                className="flex-1 py-3.5 rounded-2xl bg-emerald-300 hover:bg-emerald-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Buka Ruang Kolaborasi
              </button>
              <button
                onClick={onClose}
                className="px-4 py-3.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
