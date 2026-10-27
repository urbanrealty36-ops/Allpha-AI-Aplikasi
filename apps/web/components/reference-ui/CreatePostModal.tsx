'use client';

import React, { useState, useRef, useEffect } from 'react';
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
  Camera,
  Upload,
  ShoppingBag,
  FileText,
  CheckCircle2,
  Trash2,
  Store
} from 'lucide-react';
import type { PostItem, AIAgentProfile, HumanProfile } from '../../lib/reference-store';

type CreateMode = 'FEED_POST' | 'STORY' | 'LIVE_STAGE' | 'LIVE_STREAMING' | 'LIVE_COLLAB';

export interface LiveAttachedProduct {
  id: string;
  title: string;
  priceIdr: number;
  priceCredits: number;
  image: string;
  type: 'DIGITAL' | 'PHYSICAL';
  category: string;
}

export interface LiveSlideItem {
  title: string;
  subtitle: string;
  bullets: string[];
  diagram?: string;
}

interface CreatePostModalProps {
  isOpen: boolean;
  onClose: () => void;
  humanUser: HumanProfile;
  agentProfile: AIAgentProfile | null;
  onCreatePost: (newPost: PostItem, visibility: 'PUBLIC' | 'FOLLOWERS' | 'PRIVATE', mediaFile: File | null) => Promise<{ accepted: boolean; message?: string }>;
  onLaunchLiveStage?: (
    title: string, 
    mode: string, 
    customSlides?: LiveSlideItem[], 
    attachedProducts?: LiveAttachedProduct[]
  ) => void;
}

export default function CreatePostModal({
  isOpen,
  onClose,
  humanUser,
  agentProfile: selectedAgentProfile,
  onCreatePost,
  onLaunchLiveStage,
}: CreatePostModalProps) {
  const hasAgentProfile = Boolean(selectedAgentProfile);
  const agentProfile: AIAgentProfile = selectedAgentProfile ?? {
    id: '', name: '', handle: '', avatar: '', ownerId: humanUser.id,
    ownerName: humanUser.name, ownerHandle: humanUser.username, specialty: '',
    category: '', bio: '', skills: [], creditsEarned: 0, autoReply: false, model: ''
  };
  const [createMode, setCreateMode] = useState<CreateMode>('FEED_POST');

  // Feed Post state
  const [postAs, setPostAs] = useState<'HUMAN' | 'AI_AGENT' | 'CO_POST'>(selectedAgentProfile ? 'CO_POST' : 'HUMAN');
  const [content, setContent] = useState('');
  const [has3D, setHas3D] = useState(false);
  const [modelName, setModelName] = useState('');
  const [audience, setAudience] = useState<'PUBLIC' | 'FOLLOWERS' | 'PRIVATE'>('PUBLIC');
  const [taggedAgents, setTaggedAgents] = useState<Array<{ name: string; specialty: string }>>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const postMediaInputRef = useRef<HTMLInputElement | null>(null);
  const [postMediaFile, setPostMediaFile] = useState<File | null>(null);
  const [postMediaPreview, setPostMediaPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!postMediaFile) { setPostMediaPreview(null); return; }
    const previewUrl = URL.createObjectURL(postMediaFile);
    setPostMediaPreview(previewUrl);
    return () => URL.revokeObjectURL(previewUrl);
  }, [postMediaFile]);

  // Story state
  const [storyCaption, setStoryCaption] = useState('');
  const [storyMedia, setStoryMedia] = useState<string>('');

  // Live Stage / Streaming state
  const [liveTitle, setLiveTitle] = useState('');
  const [liveStageTemplate, setLiveStageTemplate] = useState<'PODCAST' | 'TALKSHOW' | 'CLASSROOM' | 'PITCHING'>('PODCAST');
  const [aiRoleInLive, setAiRoleInLive] = useState<'CO_HOST' | 'PRESENTER' | 'MODERATOR'>('CO_HOST');

  // File Manager Document Upload State
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadedDocument, setUploadedDocument] = useState<{
    fileName: string;
    fileSize: string;
    pageCount: number;
    slides: LiveSlideItem[];
  } | null>(null);

  // Store Marketplace Catalog Attachment State
  // Canonical product adapter is not connected here yet; preserve the reference catalog UI without seeded demo products.
  const STORE_CATALOG_PRESETS: LiveAttachedProduct[] = [];

  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [integrationNotice, setIntegrationNotice] = useState<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    const fileName = file.name;
    const baseName = fileName.replace(/\.[^/.]+$/, "");

    // File selection is local-only. Do not claim parsing or invent presentation slides without the canonical document pipeline.
    const generatedSlides: LiveSlideItem[] = [];
    setUploadedDocument({
      fileName,
      fileSize: `${sizeMb} MB`,
      pageCount: 0,
      slides: generatedSlides,
    });
  };

  const handleToggleProduct = (prodId: string) => {
    setSelectedProductIds(prev => 
      prev.includes(prodId) ? prev.filter(id => id !== prodId) : [...prev, prodId]
    );
  };

  if (!isOpen) return null;

  const sampleImages: string[] = [];

  const handlePostSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    const newPost: PostItem = {
      id: '',
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
      timestamp: 'Baru saja',
      content: content.trim(),
      tags: [],
      image: selectedImage || postMediaPreview || undefined,
      has3DModel: has3D,
      modelName: has3D ? modelName : undefined,
      likes: 0,
      commentsCount: 0,
      reposts: 0,
      isLiked: false,
      comments: [],
    };

    setIntegrationNotice(null);
    try {
      const result = await onCreatePost(newPost, audience, postMediaFile);
      if (!result.accepted) {
        setIntegrationNotice(result.message || 'Konten belum dikonfirmasi oleh API kanonis. Form tetap terbuka dan tidak menampilkan status publikasi.');
        return;
      }
      setContent('');
      setSelectedImage(null);
      setPostMediaFile(null);
      onClose();
    } catch {
      setIntegrationNotice('Konten belum tersimpan. Periksa koneksi API sebelum mencoba kembali.');
    }
  };

  const handleLaunchLive = () => {
    if (!onLaunchLiveStage || !liveTitle.trim()) {
      setIntegrationNotice('Pembuatan sesi Live belum terhubung ke layanan sesi kanonis.');
      return;
    }
    const attached = STORE_CATALOG_PRESETS.filter(p => selectedProductIds.includes(p.id));
    onLaunchLiveStage(liveTitle, liveStageTemplate, uploadedDocument?.slides, attached);
    onClose();
  };

  const handleStoryPublish = () => {
    setIntegrationNotice('Publikasi Story belum terhubung ke endpoint Story kanonis. Tidak ada Story yang dipublikasikan.');
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

        {integrationNotice && <div role="status" className="mx-4 mt-3 rounded-2xl border-2 border-slate-900 bg-amber-100 px-3 py-2 text-xs font-bold text-slate-900 shadow-[2px_2px_0px_#0f172a]">{integrationNotice}</div>}

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
                  onClick={() => setPostAs('CO_POST')} disabled={!hasAgentProfile}
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
                  onClick={() => setPostAs('AI_AGENT')} disabled={!hasAgentProfile}
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
                      <span className="absolute top-1 right-1 w-5 h-5 rounded-full bg-sky-400 text-slate-950 flex items-center justify-center text-[10px] font-black border border-slate-900">✓</span>
                    )}
                  </div>
                ))}
                <input
                  ref={postMediaInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/wav,audio/webm"
                  className="hidden"
                  onChange={(event) => setPostMediaFile(event.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => postMediaInputRef.current?.click()}
                  className="relative shrink-0 w-22 h-18 rounded-2xl overflow-hidden cursor-pointer border-2 border-slate-900 bg-sky-100 text-sky-900 transition active:translate-x-0.5 active:translate-y-0.5 shadow-[1.5px_1.5px_0px_#0f172a] flex flex-col items-center justify-center gap-1"
                >
                  <ImageIcon className="w-5 h-5 stroke-[2.5px]" />
                  <span className="text-[9px] font-black">Pilih Media</span>
                </button>
              </div>
              {postMediaFile && (
                <div className="mt-2 flex items-center gap-2 rounded-xl border-2 border-slate-900 bg-white p-2 shadow-[1.5px_1.5px_0px_#0f172a]">
                  {postMediaFile.type.startsWith("image/") && postMediaPreview
                    ? <img src={postMediaPreview} alt="Pratinjau lampiran" className="h-12 w-12 rounded-lg border border-slate-300 object-cover" />
                    : <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-sky-100"><ImageIcon className="h-5 w-5" /></div>}
                  <div className="min-w-0 flex-1"><p className="truncate text-[10px] font-black">{postMediaFile.name}</p><p className="text-[9px] font-semibold text-slate-500">{(postMediaFile.size / (1024 * 1024)).toFixed(2)} MB · divalidasi API saat kirim</p></div>
                  <button type="button" onClick={() => { setPostMediaFile(null); if (postMediaInputRef.current) postMediaInputRef.current.value = ""; }} className="rounded-lg border border-slate-900 px-2 py-1 text-[10px] font-black">Hapus</button>
                </div>
              )}
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

            {/* Hidden Document File Input */}
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.pptx,.ppt,.docx,.doc,.md,.txt"
              onChange={handleFileUpload}
              className="hidden"
            />

            {/* SECTION: Upload Dokumen dari File Manager untuk Slide Live */}
            <div className="p-4 rounded-3xl bg-sky-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-950 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-sky-700 stroke-[2.5px]" />
                  <span>Upload Dokumen / Slide dari File Manager</span>
                </span>
                <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-sky-200 border border-slate-900 text-sky-950">
                  PDF • PPTX • DOCX
                </span>
              </div>
              <p className="text-[11px] font-semibold text-slate-600 leading-relaxed">
                Lampirkan slide presentasi, dokumen pitch deck, atau materi kurikulum untuk dibahas live bersama AI Agent di panggung virtual 3D.
              </p>

              {uploadedDocument ? (
                <div className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-8 h-8 rounded-xl bg-emerald-100 border border-slate-900 flex items-center justify-center shrink-0">
                        <CheckCircle2 className="w-4 h-4 text-emerald-700 stroke-[2.5px]" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-black text-xs text-slate-950 truncate">{uploadedDocument.fileName}</p>
                        <p className="text-[10px] font-mono text-slate-500 font-bold">
                          {uploadedDocument.fileSize} • {uploadedDocument.pageCount > 0 ? `${uploadedDocument.pageCount} slide terdeteksi oleh pipeline dokumen` : "Pemrosesan dokumen belum terhubung"}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUploadedDocument(null)}
                      className="w-7 h-7 rounded-xl bg-rose-100 hover:bg-rose-200 text-rose-900 border border-slate-900 flex items-center justify-center cursor-pointer shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Slide cards preview */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 pt-1">
                    {uploadedDocument.slides.map((s, idx) => (
                      <div key={idx} className="p-2 rounded-xl bg-sky-50 border border-slate-900 text-[10px]">
                        <span className="font-mono font-black text-sky-800 block">Slide {idx + 1}</span>
                        <p className="font-bold text-slate-900 truncate">{s.title}</p>
                      </div>
                    ))}
                    {uploadedDocument.slides.length === 0 && (
                      <p className="col-span-full rounded-xl border border-dashed border-slate-400 bg-white/70 p-2 text-[10px] font-bold text-slate-600">
                        File hanya dipilih secara lokal. Slide belum dibuat atau diunggah karena pipeline dokumen belum terhubung.
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full py-3 px-4 rounded-2xl bg-white hover:bg-slate-100 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Upload className="w-4 h-4 stroke-[2.5px] text-sky-700" />
                  <span>Pilih File Dokumen / Slide dari Device</span>
                </button>
              )}
            </div>

            {/* SECTION: Lampirkan Katalog Produk Toko Marketplace untuk Checkout Langsung */}
            <div className="p-4 rounded-3xl bg-[#FEF08A] border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-950 flex items-center gap-1.5">
                  <ShoppingBag className="w-4 h-4 text-slate-950 stroke-[2.5px]" />
                  <span>Lampirkan Katalog Toko untuk Checkout Langsung</span>
                </span>
                <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-white border border-slate-900 text-slate-950">
                  {selectedProductIds.length} Terpilih
                </span>
              </div>
              <p className="text-[11px] font-semibold text-slate-800 leading-relaxed">
                Produk terpilih akan disematkan di etalase panggung live, sehingga penonton dapat langsung <strong>&quot;Checkout Langsung&quot;</strong> saat siaran berlangsung.
              </p>

              {/* Product Checkbox Selection */}
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {STORE_CATALOG_PRESETS.map((prod) => {
                  const isChecked = selectedProductIds.includes(prod.id);
                  return (
                    <div
                      key={prod.id}
                      onClick={() => handleToggleProduct(prod.id)}
                      className={`p-2 rounded-2xl border-2 border-slate-900 flex items-center justify-between gap-2.5 cursor-pointer transition ${
                        isChecked ? 'bg-white shadow-[2px_2px_0px_#0f172a]' : 'bg-white/60 opacity-80 hover:opacity-100'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <img
                          src={prod.image}
                          alt={prod.title}
                          className="w-9 h-9 rounded-xl object-cover border border-slate-900 shrink-0"
                        />
                        <div className="min-w-0">
                          <p className="font-black text-xs text-slate-950 truncate">{prod.title}</p>
                          <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold text-slate-600">
                            <span className="text-emerald-800">Rp {prod.priceIdr.toLocaleString('id-ID')}</span>
                            <span>•</span>
                            <span className="text-amber-900">{prod.priceCredits} Cr</span>
                            <span>•</span>
                            <span className="text-sky-900 font-sans font-black">{prod.type}</span>
                          </div>
                        </div>
                      </div>

                      <div className={`w-5 h-5 rounded-lg border-2 border-slate-900 flex items-center justify-center shrink-0 ${
                        isChecked ? 'bg-emerald-400 text-slate-950' : 'bg-white'
                      }`}>
                        {isChecked && <Check className="w-3.5 h-3.5 stroke-[3px]" />}
                      </div>
                    </div>
                  );
                })}
                {STORE_CATALOG_PRESETS.length === 0 && (
                  <p className="rounded-2xl border-2 border-dashed border-slate-900 bg-white/70 px-3 py-3 text-[11px] font-bold text-slate-700">
                    Katalog produk kanonis belum tersedia. Produk contoh tidak ditampilkan dan tidak dapat disematkan ke sesi Live.
                  </p>
                )}
              </div>
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

            {/* Quick Attachments for Live Streaming */}
            <div className="p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-black text-slate-950 flex items-center gap-1.5">
                  <ShoppingBag className="w-3.5 h-3.5" />
                  <span>Katalog Produk Live Checkout:</span>
                </span>
                <span className="font-mono font-bold text-amber-950 bg-amber-200 px-2 py-0.5 rounded-md border border-slate-900 text-[10px]">
                  {selectedProductIds.length} Terpilih
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-black text-slate-950 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" />
                  <span>Dokumen Slide AI:</span>
                </span>
                <span className="font-mono font-bold text-sky-950 bg-sky-200 px-2 py-0.5 rounded-md border border-slate-900 text-[10px]">
                  {uploadedDocument ? uploadedDocument.fileName : 'Belum diunggah'}
                </span>
              </div>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full py-2 px-3 rounded-xl bg-white hover:bg-slate-50 border border-slate-900 text-[11px] font-black text-slate-900 flex items-center justify-center gap-1.5 cursor-pointer shadow-2xs"
              >
                <Upload className="w-3 h-3 text-sky-700" />
                <span>{uploadedDocument ? 'Ganti File Dokumen' : 'Upload File Presentasi dari Device'}</span>
              </button>
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
