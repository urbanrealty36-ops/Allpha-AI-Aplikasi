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
  const [taggedAgents, setTaggedAgents] = useState<Array<{ name: string; specialty: string }>>([
    { name: '@TechNova', specialty: 'IT & Teknologi' },
    { name: '@DesignAI', specialty: 'Content Creator' },
  ]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  // Story state
  const [storyCaption, setStoryCaption] = useState('');
  const [storyMedia, setStoryMedia] = useState<string>('/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg');

  // Live Stage / Streaming state
  const [liveTitle, setLiveTitle] = useState('Podcast Interaktif: Kolaborasi Human × AI Agent 2026');
  const [liveStageTemplate, setLiveStageTemplate] = useState<'PODCAST' | 'TALKSHOW' | 'CLASSROOM' | 'PITCHING'>('PODCAST');
  const [aiRoleInLive, setAiRoleInLive] = useState<'CO_HOST' | 'PRESENTER' | 'MODERATOR'>('CO_HOST');

  if (!isOpen) return null;

  const sampleImages = [
    '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
    '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
    'https://picsum.photos/seed/future-tech/600/400',
    'https://picsum.photos/seed/luna-cyber/600/400',
  ];

  const handlePostSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    const newPost: PostItem = {
      id: `p-${Date.now()}`,
      humanOwner: {
        name: humanUser.name,
        handle: humanUser.username,
        avatar: humanUser.avatar,
        verified: true,
      },
      aiAgent: {
        name: agentProfile.name,
        handle: agentProfile.handle,
        avatar: agentProfile.avatar,
        specialty: agentProfile.specialty,
      },
      takeoverMode: postAs === 'HUMAN',
      timestamp: 'Baru saja',
      content: content.trim(),
      tags: ['#AllphaUniverse', '#AIAgent', '#CrystalCity'],
      image: selectedImage || undefined,
      has3DModel: has3D,
      modelName: has3D ? modelName : undefined,
      likes: 1,
      commentsCount: 0,
      reposts: 0,
      isLiked: true,
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
    alert(`Story "${storyCaption || 'Story Baru'}" berhasil diunggah dengan durasi 24 jam!`);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-xs">
              <Plus className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900">Pusat Pembuatan Konten (Create)</h2>
              <p className="text-[10px] text-slate-500">Postingan, Story, Live Streaming & Stage 3D</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-slate-800 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Create Mode Switcher Tabs */}
        <div className="px-4 py-2 border-b border-slate-100 bg-white flex gap-1.5 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setCreateMode('FEED_POST')}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              createMode === 'FEED_POST'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Box className="w-3.5 h-3.5" />
            <span>Postingan Feed</span>
          </button>

          <button
            onClick={() => setCreateMode('STORY')}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              createMode === 'STORY'
                ? 'bg-rose-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Camera className="w-3.5 h-3.5" />
            <span>Story / Moment</span>
          </button>

          <button
            onClick={() => setCreateMode('LIVE_STAGE')}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              createMode === 'LIVE_STAGE'
                ? 'bg-purple-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Radio className="w-3.5 h-3.5 animate-pulse text-amber-300" />
            <span>Mulai Live Stage 3D</span>
            <span className="text-[9px] px-1 rounded-full bg-white/20 text-white">LIVE</span>
          </button>

          <button
            onClick={() => setCreateMode('LIVE_STREAMING')}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              createMode === 'LIVE_STREAMING'
                ? 'bg-rose-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Video className="w-3.5 h-3.5" />
            <span>Live Streaming</span>
          </button>

          <button
            onClick={() => setCreateMode('LIVE_COLLAB')}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              createMode === 'LIVE_COLLAB'
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Live Collab</span>
          </button>
        </div>

        {/* ========================================================= */}
        {/* MODE 1: FEED POST */}
        {/* ========================================================= */}
        {createMode === 'FEED_POST' && (
          <form onSubmit={handlePostSubmit} className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Identity Switcher */}
            <div className="flex items-center justify-between p-2.5 rounded-2xl bg-slate-50 border border-slate-200">
              <span className="text-xs font-bold text-slate-700">Posting sebagai:</span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setPostAs('CO_POST')}
                  className={`px-2.5 py-1 rounded-xl text-[11px] font-bold transition ${
                    postAs === 'CO_POST' ? 'bg-blue-600 text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  Bersama (Human × AI)
                </button>
                <button
                  type="button"
                  onClick={() => setPostAs('HUMAN')}
                  className={`px-2.5 py-1 rounded-xl text-[11px] font-bold transition ${
                    postAs === 'HUMAN' ? 'bg-blue-600 text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  Human Saja
                </button>
                <button
                  type="button"
                  onClick={() => setPostAs('AI_AGENT')}
                  className={`px-2.5 py-1 rounded-xl text-[11px] font-bold transition ${
                    postAs === 'AI_AGENT' ? 'bg-purple-600 text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  AI Agent Saja
                </button>
              </div>
            </div>

            {/* Caption Input */}
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Tulis sesuatu tentang ide, pemikiran 3D, atau kolaborasi AI Anda..."
              rows={4}
              className="w-full p-3.5 rounded-2xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none text-xs leading-relaxed resize-none transition"
              required
            />

            {/* Media Image Selection */}
            <div>
              <p className="text-[11px] font-bold text-slate-700 mb-1.5 flex items-center gap-1">
                <ImageIcon className="w-3.5 h-3.5 text-blue-600" />
                <span>Lampirkan Gambar atau Pratinjau 3D:</span>
              </p>
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                {sampleImages.map((img, i) => (
                  <div
                    key={i}
                    onClick={() => setSelectedImage(selectedImage === img ? null : img)}
                    className={`relative shrink-0 w-20 h-16 rounded-xl overflow-hidden cursor-pointer border-2 transition ${
                      selectedImage === img ? 'border-blue-600 ring-2 ring-blue-200' : 'border-slate-200 hover:opacity-80'
                    }`}
                  >
                    <img src={img} alt="Thumb" className="w-full h-full object-cover" />
                    {selectedImage === img && (
                      <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-bold">
                        ✓
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 3D Model Attachment */}
            <div className="p-3 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Box className="w-4 h-4 text-cyan-400" />
                <div>
                  <p className="text-xs font-bold text-white">Sematkan Objek 3D Crystal City</p>
                  <p className="text-[10px] text-slate-300">Format Three.js GLB / RoomEnvironment PBR</p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={has3D}
                onChange={(e) => setHas3D(e.target.checked)}
                className="w-4 h-4 accent-cyan-400 cursor-pointer"
              />
            </div>

            <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
              >
                Batal
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-md"
              >
                <Send className="w-3.5 h-3.5" />
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
              <span className="text-xs font-bold text-rose-600 uppercase tracking-wider">
                Story 24 Jam
              </span>
              <h3 className="text-sm font-black text-slate-900">
                Bagikan Momen Singkat bersama AI Agent
              </h3>
              <p className="text-xs text-slate-500">
                Story akan muncul di lingkaran atas header beranda selama 24 jam
              </p>
            </div>

            <div className="rounded-2xl overflow-hidden border border-slate-200 bg-slate-950 relative h-48 flex items-center justify-center">
              <img src={storyMedia} alt="Story Media" className="w-full h-full object-cover opacity-80" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-3">
                <p className="text-white text-xs font-bold truncate">
                  {storyCaption || 'Pratinjau Story Anda...'}
                </p>
              </div>
            </div>

            <input
              type="text"
              value={storyCaption}
              onChange={(e) => setStoryCaption(e.target.value)}
              placeholder="Tambahkan teks/caption story..."
              className="w-full p-3 rounded-xl border border-slate-200 text-xs outline-none focus:border-rose-500"
            />

            <div className="flex gap-2">
              <button
                onClick={handleStoryPublish}
                className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-purple-600 text-white font-bold text-xs shadow-md transition"
              >
                Kirim ke Story
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2.5 rounded-xl bg-slate-100 text-slate-700 font-semibold text-xs"
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
            <div className="p-3.5 rounded-2xl bg-gradient-to-r from-purple-900 via-indigo-950 to-slate-900 text-white space-y-1">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-rose-400 animate-pulse" />
                <span className="text-xs font-bold uppercase tracking-wider text-rose-300">
                  Panggung Virtual 3D
                </span>
              </div>
              <h3 className="text-sm font-black text-white">
                Mulai Live Stage 3D dengan AI Co-Presenter
              </h3>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                Audiens dapat menyaksikan avatar 3D Anda dan AI Agent berdiskusi di panggung, membedah slide presentasi, dan menjawab pertanyaan penonton.
              </p>
            </div>

            {/* Live Title */}
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">
                Judul Sesi Live Stage:
              </label>
              <input
                type="text"
                value={liveTitle}
                onChange={(e) => setLiveTitle(e.target.value)}
                placeholder="Contoh: Podcast Ekosistem Masa Depan..."
                className="w-full p-3 rounded-xl border border-slate-200 text-xs font-medium outline-none focus:border-purple-500"
              />
            </div>

            {/* Template selector */}
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1.5">
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
                    className={`p-2.5 rounded-xl border cursor-pointer transition ${
                      liveStageTemplate === tmpl.id
                        ? 'bg-purple-50 border-purple-500 text-purple-900 font-bold'
                        : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    <p className="font-bold text-xs">{tmpl.label}</p>
                    <p className="text-[10px] text-slate-500">{tmpl.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Agent Role */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs flex items-center justify-between">
              <div>
                <p className="font-bold text-slate-900">Peran AI Agent ({agentProfile.name}):</p>
                <p className="text-[11px] text-slate-500">Sinkronisasi suara & bibir (viseme) aktif</p>
              </div>
              <select
                value={aiRoleInLive}
                onChange={(e) => setAiRoleInLive(e.target.value as typeof aiRoleInLive)}
                className="px-2.5 py-1 rounded-lg border border-slate-300 text-xs font-semibold bg-white"
              >
                <option value="CO_HOST">Co-Host Pendamping</option>
                <option value="PRESENTER">Presenter Utama Slide</option>
                <option value="MODERATOR">Moderator Tanya-Jawab</option>
              </select>
            </div>

            <div className="pt-2 flex gap-2">
              <button
                onClick={handleLaunchLive}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 text-white font-black text-xs shadow-lg transition flex items-center justify-center gap-2 hover:scale-[1.01]"
              >
                <Radio className="w-4 h-4 text-rose-300 animate-pulse" />
                <span>🚀 Luncurkan Live Stage Sekarang</span>
              </button>
              <button
                onClick={onClose}
                className="px-4 py-3 rounded-xl bg-slate-100 text-slate-700 font-bold text-xs"
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
            <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 space-y-1 text-xs">
              <div className="flex items-center gap-1.5 text-rose-700 font-bold">
                <Video className="w-4 h-4" />
                <span>Siaran Langsung Realtime (Live Streaming)</span>
              </div>
              <p className="text-rose-900 leading-relaxed text-[11px]">
                Saat Anda live, lencana <strong>🔴 LIVE</strong> akan otomatis muncul di lingkaran stories profil Anda pada header beranda, linimasa feed, dan scrolling reels!
              </p>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">Topik Siaran:</label>
              <input
                type="text"
                value={liveTitle}
                onChange={(e) => setLiveTitle(e.target.value)}
                className="w-full p-3 rounded-xl border border-slate-200 text-xs font-medium outline-none focus:border-rose-500"
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={handleLaunchLive}
                className="flex-1 py-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-md transition flex items-center justify-center gap-1.5"
              >
                <Radio className="w-4 h-4 animate-pulse" />
                <span>Mulai Siaran Live Streaming</span>
              </button>
              <button
                onClick={onClose}
                className="px-4 py-3 rounded-xl bg-slate-100 text-slate-700 font-bold text-xs"
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
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <Users className="w-4 h-4 text-emerald-600" />
                <span>Ruang Kolaborasi 3D Multi-User</span>
              </p>
              <p className="text-[11px] leading-relaxed">
                Bekerja bersama di kanvas 3D, menyusun workflow n8n secara serentak, atau mengedit dokumen RAG bersama rekan dan AI Agent Anda.
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => {
                  alert('Ruang Kolaborasi 3D telah dibuka!');
                  onClose();
                }}
                className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-md"
              >
                Buka Ruang Kolaborasi
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2.5 rounded-xl bg-slate-100 text-slate-700 font-bold text-xs"
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
