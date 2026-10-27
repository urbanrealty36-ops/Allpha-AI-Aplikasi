'use client';

import React, { useState, useRef } from 'react';
import { 
  Radio, 
  Play, 
  Pause, 
  Mic, 
  MicOff, 
  Volume2, 
  VolumeX, 
  Video, 
  VideoOff, 
  Share2, 
  Heart, 
  Send, 
  ChevronRight, 
  ChevronLeft, 
  User, 
  Bot, 
  Sparkles, 
  FileText, 
  Settings, 
  Maximize2, 
  Users, 
  Flame, 
  Layers,
  Presentation,
  CheckCircle2,
  SlidersHorizontal,
  ShoppingBag,
  Store,
  Upload,
  X,
  CreditCard,
  QrCode,
  Truck,
  Box,
  Plus,
  ArrowRight,
  ShieldCheck,
  Tag
} from 'lucide-react';

export interface StageProductItem {
  id: string;
  title: string;
  priceIdr: number;
  priceCredits: number;
  image: string;
  type: 'DIGITAL' | 'PHYSICAL';
  category?: string;
  stock?: number;
}

export interface StageSlideItem {
  title: string;
  subtitle: string;
  bullets: string[];
  diagram?: string;
}

interface LiveExperienceStageProps {
  onBackToFeed: () => void;
  userCredits: number | null;
  agentCredits: number | null;
  liveStateAvailable?: boolean;
  initialTopic?: string;
  initialSlides?: StageSlideItem[];
  initialAttachedProducts?: StageProductItem[];
  onOpenStoreAndBoothModal?: () => void;
  onOpenMarketplace?: () => void;
  onDeductCredits?: (amount: number, reason: string) => void;
}

const DEFAULT_SLIDES: StageSlideItem[] = [];

const DEFAULT_ATTACHED_PRODUCTS: StageProductItem[] = [];

export default function LiveExperienceStage({
  onBackToFeed,
  userCredits,
  agentCredits,
  liveStateAvailable = false,
  initialTopic,
  initialSlides,
  initialAttachedProducts,
  onOpenStoreAndBoothModal,
  onOpenMarketplace,
  onDeductCredits,
}: LiveExperienceStageProps) {
  // Live state
  const [isLive, setIsLive] = useState(false);
  const [isHostMicMuted, setIsHostMicMuted] = useState(false);
  const [isHostCameraOn, setIsHostCameraOn] = useState(true);
  const [isAiAgentSpeaking, setIsAiAgentSpeaking] = useState(false);
  const [isAiAgentMuted, setIsAiAgentMuted] = useState(false);
  const [likesCount, setLikesCount] = useState<number | null>(null);
  const [viewerCount, setViewerCount] = useState<number | null>(null);
  const [stageToast, setStageToast] = useState<string | null>(null);

  // Topics and active slide
  const [activeTopic, setActiveTopic] = useState(initialTopic || '');
  const [stageSlides, setStageSlides] = useState<StageSlideItem[]>(initialSlides ?? DEFAULT_SLIDES);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);

  // Attached Store Catalog State for Direct Checkout
  const [attachedCatalog, setAttachedCatalog] = useState<StageProductItem[]>(initialAttachedProducts ?? DEFAULT_ATTACHED_PRODUCTS);
  const [isCatalogExpanded, setIsCatalogExpanded] = useState(true);
  const [checkoutModalProduct, setCheckoutModalProduct] = useState<StageProductItem | null>(null);
  const [checkoutQuantity, setCheckoutQuantity] = useState(1);
  const [checkoutPaymentMethod, setCheckoutPaymentMethod] = useState<'AI_CREDITS' | 'QRIS' | 'VA'>('AI_CREDITS');
  const [destinationAddress, setDestinationAddress] = useState('');
  const [isProcessingCheckout, setIsProcessingCheckout] = useState(false);

  // File Manager Upload Ref on Stage
  const stageFileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadedDocName, setUploadedDocName] = useState<string | null>(null);

  // Audio spectrum simulation
  const [audioFreqs] = useState<number[]>([]);

  // Live Chat Stream
  const [chatInput, setChatInput] = useState('');
  const [chatMessages] = useState<Array<{ sender: string; handle: string; text: string; isAi?: boolean }>>([]);

  // Local file selection is not a document-ingestion result. The canonical pipeline must parse and authorize the file before slides can appear.
  const handleStageDocUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedDocName(file.name);
    setStageToast('File dipilih. Pemrosesan dokumen dan pembuatan slide belum terhubung.');
  };

  // Checkout is fail-closed until a canonical order/payment adapter is connected.
  const handleConfirmDirectCheckout = (e: React.FormEvent) => {
    e.preventDefault();
    setStageToast('Checkout Live belum terhubung ke layanan pesanan dan pembayaran.');
  };

  // Audio and AI speech state must come from the real Live transport; no local simulation.
  const isSpeaking = false;

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    setStageToast('Live Chat belum terhubung ke layanan sesi.');
  };

  const handleLike = () => {
    setStageToast('Interaksi Live belum terhubung ke layanan sesi.');
  };

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-4 pb-24 text-slate-900 font-sans space-y-4">
      {/* Top Header Live Stage bar (Playful Neo-Brutalist Soft Pastel) */}
      <div className="flex items-center justify-between bg-rose-50 text-slate-950 p-4 rounded-3xl shadow-[4px_4px_0px_#0f172a] border-2 border-slate-900">
        <div className="flex items-center gap-3">
          <div className="w-3.5 h-3.5 rounded-full bg-rose-500 border border-slate-900 animate-pulse" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-rose-200 border-2 border-slate-900 font-black uppercase tracking-wider text-rose-950 shadow-2xs">
                LIVE STAGE
              </span>
              <h1 className="text-sm font-black text-slate-950">Podcast & Live Experience Arena</h1>
            </div>
            <p className="text-[11px] font-semibold text-slate-700 mt-0.5">{activeTopic}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 border-2 border-slate-900 text-xs font-mono font-black text-amber-950 shadow-[1.5px_1.5px_0px_#0f172a]">
            <Users className="w-3.5 h-3.5" />
            <span>{viewerCount === null ? '—' : viewerCount.toLocaleString()} Penonton</span>
          </div>
          <button
            onClick={() => setIsLive(!isLive)} disabled={!liveStateAvailable}
            className={`px-4 py-1.5 rounded-2xl text-xs font-black transition flex items-center gap-1.5 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
              isLive ? 'bg-rose-400 hover:bg-rose-500 text-slate-950' : 'bg-emerald-300 hover:bg-emerald-400 text-slate-950'
            }`}
          >
            {isLive ? <Pause className="w-3.5 h-3.5 stroke-[3px]" /> : <Play className="w-3.5 h-3.5 stroke-[3px]" />}
            <span>{isLive ? 'Hentikan Siaran' : 'Mulai Siaran'}</span>
          </button>
        </div>
      </div>

      {/* Main Live Stage Display Arena (Split: Human Host Slot & AI Agent Avatar Slot) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Column (2 Cols): Dual Stage Slots & Shared Presentation Screen */}
        <div className="lg:col-span-2 space-y-4">
          {/* Dual Speaker Video Slots (Human Owner ⟷ AI Agent) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Slot 1: Human Owner (Host Camera Slot) */}
            <div className="relative h-64 rounded-3xl bg-slate-950 overflow-hidden border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex flex-col justify-between p-4 group">
              {/* Camera background simulation */}
              <div className="absolute inset-0 bg-gradient-to-tr from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center">
                {isHostCameraOn ? (
                  <div className="text-center">
                    <div className="w-24 h-24 mx-auto rounded-full ring-4 ring-sky-300 p-1 bg-gradient-to-tr from-blue-600 to-cyan-500 shadow-2xl">
                      <img
                        src="/icon.svg"
                        alt="Alex Tamara"
                        className="w-full h-full rounded-full object-cover border-2 border-slate-900"
                      />
                    </div>
                    <span className="inline-block mt-3 px-3 py-1 rounded-full bg-white/90 text-slate-950 text-xs font-black border-2 border-slate-900 shadow-2xs">
                      🎤 Host Microphone Active
                    </span>
                  </div>
                ) : (
                  <div className="text-center text-slate-400 text-xs font-bold">
                    <VideoOff className="w-8 h-8 mx-auto mb-1 opacity-50" />
                    <span>Kamera Host Dimatikan</span>
                  </div>
                )}
              </div>

              {/* Top tag */}
              <div className="relative z-10 flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full bg-white/95 text-slate-950 text-[11px] font-black border-2 border-slate-900 shadow-2xs flex items-center gap-1.5">
                  <User className="w-3 h-3 text-sky-600 stroke-[2.5px]" />
                  Alex Tamara · Human Owner
                </span>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-sky-200 border border-slate-900 text-sky-950 font-mono font-bold">
                  1080p 60fps
                </span>
              </div>

              {/* Bottom controls */}
              <div className="relative z-10 flex items-center justify-between pt-2">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setIsHostMicMuted(!isHostMicMuted)} disabled={!liveStateAvailable}
                    className={`p-2 rounded-xl transition ${
                      isHostMicMuted ? 'bg-rose-600 text-white' : 'bg-slate-800/90 text-white hover:bg-slate-700'
                    }`}
                    title={isHostMicMuted ? 'Nyalakan Mic' : 'Matikan Mic'}
                  >
                    {isHostMicMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => setIsHostCameraOn(!isHostCameraOn)} disabled={!liveStateAvailable}
                    className={`p-2 rounded-xl transition ${
                      !isHostCameraOn ? 'bg-rose-600 text-white' : 'bg-slate-800/90 text-white hover:bg-slate-700'
                    }`}
                    title={isHostCameraOn ? 'Matikan Kamera' : 'Nyalakan Kamera'}
                  >
                    {isHostCameraOn ? <Video className="w-4 h-4" /> : <VideoOff className="w-4 h-4" />}
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  {audioFreqs.slice(0, 5).map((f, i) => (
                    <span
                      key={i}
                      className="w-1 bg-cyan-400 rounded-full transition-all duration-150"
                      style={{ height: `${f * 0.25}px` }}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Slot 2: AI Agent (Holographic Virtual Camera / Avatar Feed) */}
            <div className="relative h-64 rounded-3xl bg-slate-950 overflow-hidden border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex flex-col justify-between p-4 group">
              {/* 3D Holographic AI Agent Simulator */}
              <div className="absolute inset-0 bg-gradient-to-tr from-purple-950 via-slate-900 to-indigo-950 flex items-center justify-center">
                <div className="text-center">
                  <div className={`w-24 h-24 mx-auto rounded-full ring-4 ${isAiAgentSpeaking ? 'ring-purple-300 animate-pulse' : 'ring-purple-500/40'} p-1 bg-gradient-to-tr from-cyan-400 to-purple-500 shadow-2xl`}>
                    <img
                      src="/icon.svg"
                      alt="Luna AI"
                      className="w-full h-full rounded-full object-cover border-2 border-slate-900"
                    />
                  </div>
                  <span className={`inline-block mt-3 px-3 py-1 rounded-full text-xs font-black border-2 border-slate-900 shadow-2xs ${
                    isAiAgentSpeaking
                      ? 'bg-purple-200 text-purple-950'
                      : 'bg-white text-slate-800'
                  }`}>
                    {isAiAgentSpeaking ? '🤖 Luna AI Berbicara...' : 'Luna AI Standby'}
                  </span>
                </div>
              </div>

              {/* Top tag */}
              <div className="relative z-10 flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full bg-white/95 text-slate-950 text-[11px] font-black border-2 border-slate-900 shadow-2xs flex items-center gap-1.5">
                  <Bot className="w-3 h-3 text-purple-700 stroke-[2.5px]" />
                  Luna AI · AI Agent milik @alextamara
                </span>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-purple-200 border border-slate-900 text-purple-950 font-mono font-bold">
                  Neural Audio 48kHz
                </span>
              </div>

              {/* Bottom controls */}
              <div className="relative z-10 flex items-center justify-between pt-2">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setIsAiAgentMuted(!isAiAgentMuted)} disabled={!liveStateAvailable}
                    className={`p-2 rounded-2xl border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
                      isAiAgentMuted ? 'bg-rose-500 text-white' : 'bg-white text-slate-900 hover:bg-slate-100'
                    }`}
                    title={isAiAgentMuted ? 'Nyalakan Audio AI' : 'Mute AI Agent'}
                  >
                    {isAiAgentMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => {
                      setStageToast('Takeover mikrofon belum terhubung ke layanan sesi Live.');
                    }}
                    className="px-3 py-1.5 rounded-2xl bg-sky-300 hover:bg-sky-400 border-2 border-slate-900 text-slate-950 text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                  >
                    Takeover Mic
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  {audioFreqs.slice(6, 11).map((f, i) => (
                    <span
                      key={i}
                      className="w-1.5 bg-purple-400 rounded-full transition-all duration-150 border border-slate-900"
                      style={{ height: `${f * 0.28}px` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Shared Stage Presentation Screen (Document / Slide Viewer on Stage) */}
          <div className="p-5 rounded-3xl bg-sky-50 border-2 border-slate-900 text-slate-950 shadow-[4px_4px_0px_#0f172a] space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b-2 border-slate-900/15">
              <div className="flex items-center gap-2">
                <Presentation className="w-4 h-4 text-sky-700 stroke-[2.5px]" />
                <span className="font-black text-xs text-slate-950">
                  Layar Presentasi Stage 3D {uploadedDocName && `• ${uploadedDocName}`}
                </span>
              </div>

              {/* Slide controls & Upload file manager button */}
              <div className="flex items-center gap-2">
                <input
                  type="file"
                  disabled={!liveStateAvailable}
                  ref={stageFileInputRef}
                  accept=".pdf,.pptx,.ppt,.docx,.doc,.md,.txt"
                  onChange={handleStageDocUpload}
                  className="hidden"
                />

                <button
                  onClick={() => stageFileInputRef.current?.click()} disabled={!liveStateAvailable}
                  className="px-2.5 py-1.5 rounded-xl bg-sky-200 hover:bg-sky-300 text-sky-950 font-black text-[11px] border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
                  title="Upload Slide Baru dari File Manager"
                >
                  <Upload className="w-3 h-3 stroke-[2.5px]" />
                  <span>Upload Dokumen</span>
                </button>

                <button
                  onClick={() => setActiveSlideIndex((prev) => (prev > 0 ? prev - 1 : stageSlides.length - 1))} disabled={!liveStateAvailable || stageSlides.length === 0}
                  className="p-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4 stroke-[2.5px]" />
                </button>
                <span className="text-xs font-mono font-black text-slate-900 px-1.5">
                  {activeSlideIndex + 1} / {stageSlides.length}
                </span>
                <button
                  onClick={() => setActiveSlideIndex((prev) => (prev < stageSlides.length - 1 ? prev + 1 : 0))} disabled={!liveStateAvailable || stageSlides.length === 0}
                  className="p-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  <ChevronRight className="w-4 h-4 stroke-[2.5px]" />
                </button>
              </div>
            </div>

            {/* Slide Body */}
            {stageSlides[activeSlideIndex] ? (
              <div className="p-4 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs space-y-2.5">
                <span className="text-[10px] text-sky-700 font-mono font-black uppercase tracking-wider block">
                  {stageSlides[activeSlideIndex].subtitle}
                </span>
                <h3 className="text-base font-black text-slate-950">
                  {stageSlides[activeSlideIndex].title}
                </h3>
                <ul className="space-y-1.5 text-slate-800 font-semibold pt-1">
                  {stageSlides[activeSlideIndex].bullets.map((b, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-sky-600 font-black">•</span>
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
                {stageSlides[activeSlideIndex].diagram && (
                  <div className="p-3 rounded-xl bg-sky-100 border-2 border-slate-900 text-slate-950 font-mono font-bold text-[11px] mt-2">
                    {stageSlides[activeSlideIndex].diagram}
                  </div>
                )}
              </div>
            ) : (
              <p className="px-5 py-8 text-center text-sm font-bold text-slate-600">Belum ada sesi atau pesan Live. Belum ada presentasi aktif dari layanan Live Allpha.</p>
            )}
          </div>

          {/* ======================================================== */}
          {/* PINNED STORE CATALOG BAR: CHECKOUT LANGSUNG (User Request) */}
          {/* ======================================================== */}
          <div className="p-4 rounded-3xl bg-[#FEF08A] border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-xl bg-white border-2 border-slate-900 flex items-center justify-center shadow-[1px_1px_0px_#0f172a]">
                  <ShoppingBag className="w-3.5 h-3.5 text-slate-950 stroke-[2.5px]" />
                </span>
                <div>
                  <h3 className="text-xs sm:text-sm font-black text-slate-950">
                    Etalase Produk Live • Checkout Langsung
                  </h3>
                  <p className="text-[10px] font-semibold text-slate-800">
                    Beli aset 3D & merchandise resmi tanpa meninggalkan siaran panggung
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {onOpenStoreAndBoothModal && (
                  <button
                    onClick={onOpenStoreAndBoothModal}
                    className="px-2.5 py-1 rounded-xl bg-white hover:bg-slate-100 text-slate-950 text-[10px] font-black border border-slate-900 shadow-2xs flex items-center gap-1 cursor-pointer"
                  >
                    <Store className="w-3 h-3" />
                    <span className="hidden sm:inline">Kelola Toko</span>
                  </button>
                )}
                <span className="text-[10px] font-mono font-black px-2 py-0.5 rounded-full bg-white border border-slate-900 text-slate-950">
                  {attachedCatalog.length} Produk Live
                </span>
              </div>
            </div>

            {/* Catalog Grid Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {attachedCatalog.map((prod) => (
                <div
                  key={prod.id}
                  className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col justify-between space-y-2 hover:shadow-[3px_3px_0px_#0f172a] transition"
                >
                  <div className="space-y-1.5">
                    <div className="relative h-24 rounded-xl overflow-hidden border border-slate-900">
                      <img src={prod.image} alt={prod.title} className="w-full h-full object-cover" />
                      <span className="absolute top-1 left-1 px-1.5 py-0.2 rounded font-mono text-[8px] font-black bg-white/90 border border-slate-900 text-slate-950">
                        {prod.type}
                      </span>
                    </div>

                    <h4 className="font-black text-xs text-slate-950 line-clamp-1 leading-snug">{prod.title}</h4>
                    <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold">
                      <span className="text-emerald-800 font-black">Rp {prod.priceIdr.toLocaleString('id-ID')}</span>
                      <span>•</span>
                      <span className="text-amber-900">{prod.priceCredits} Cr</span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setCheckoutModalProduct(prod);
                      setCheckoutQuantity(1);
                    }}
                    className="w-full py-1.5 px-3 rounded-xl bg-[#BBF7D0] hover:bg-emerald-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <span>Checkout Langsung</span>
                    <ArrowRight className="w-3 h-3 stroke-[2.5px]" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Live Chat & Audience Feedback */}
        <div className="flex flex-col h-[520px] rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] overflow-hidden">
          {/* Live Chat Header */}
          <div className="p-3.5 border-b-2 border-slate-900 flex items-center justify-between bg-amber-50">
            <div className="flex items-center gap-2">
              <span className="font-black text-xs text-slate-950">Live Chat Pemirsa</span>
              <span className="text-[9.5px] px-2 py-0.5 rounded-full bg-emerald-200 border border-slate-900 text-emerald-950 font-black">
                ● Aktif
              </span>
            </div>
            <button
              onClick={handleLike} disabled={!liveStateAvailable}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-200 text-rose-950 border-2 border-slate-900 text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            >
              <Heart className="w-3.5 h-3.5 fill-rose-600 text-rose-600" />
              <span>{likesCount === null ? '—' : likesCount}</span>
            </button>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 bg-slate-50/50 text-xs">
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-2xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] ${
                  msg.isAi
                    ? 'bg-purple-100 text-purple-950'
                    : 'bg-white text-slate-900'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-black text-[11px]">
                    {msg.sender}
                    {msg.isAi && (
                      <span className="ml-1 text-[9px] px-1.5 py-0.2 rounded-full bg-purple-300 border border-purple-800 text-purple-950 font-black">
                        AI Agent
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono font-bold">{msg.handle}</span>
                </div>
                <p className="leading-relaxed text-[11.5px] font-semibold">{msg.text}</p>
              </div>
            ))}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleSendChat} className="p-3 bg-white border-t-2 border-slate-900 flex items-center gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Tulis pesan atau pertanyaan..."
              className="flex-1 px-3.5 py-2 text-xs font-bold bg-slate-50 border-2 border-slate-900 rounded-2xl outline-none shadow-[1.5px_1.5px_0px_#0f172a] focus:bg-white"
            />
            <button
              type="submit"
              disabled={!liveStateAvailable || !chatInput.trim()}
              className="p-2.5 rounded-2xl bg-sky-400 hover:bg-sky-500 disabled:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            >
              <Send className="w-4 h-4 stroke-[2.5px]" />
            </button>
          </form>
        </div>
      </div>

      {/* Live Stage Toast */}
      {stageToast && (
        <div className="fixed bottom-6 right-6 z-50 p-4 rounded-2xl bg-amber-100 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] text-slate-950 font-black text-xs flex items-center gap-2 animate-bounce">
          <span>🎙️</span>
          <span>{stageToast}</span>
        </div>
      )}

      {/* ========================================================= */}
      {/* DIRECT CHECKOUT MODAL IN LIVE STAGE (User Request) */}
      {/* ========================================================= */}
      {checkoutModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in zoom-in-95 duration-150">
          <div className="w-full max-w-md bg-white rounded-3xl border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 space-y-4 text-xs">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b-2 border-slate-100">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-xl bg-[#FEF08A] border-2 border-slate-900 flex items-center justify-center shadow-2xs">
                  <ShoppingBag className="w-3.5 h-3.5 text-slate-950 stroke-[2.5px]" />
                </span>
                <div>
                  <h3 className="font-black text-sm text-slate-950">Checkout Langsung di Live</h3>
                  <p className="text-[10px] font-semibold text-slate-600">Beli tanpa keluar dari panggung siaran</p>
                </div>
              </div>
              <button
                onClick={() => setCheckoutModalProduct(null)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            {/* Product Summary */}
            <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center gap-3">
              <img
                src={checkoutModalProduct.image}
                alt={checkoutModalProduct.title}
                className="w-14 h-14 rounded-xl object-cover border-2 border-slate-900 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <span className="text-[9px] font-black px-1.5 py-0.2 rounded-md bg-white border border-slate-900 text-slate-900">
                  {checkoutModalProduct.type}
                </span>
                <h4 className="font-black text-xs text-slate-950 truncate mt-0.5">{checkoutModalProduct.title}</h4>
                <div className="flex items-center gap-2 font-mono font-black mt-1">
                  <span className="text-emerald-800 text-xs">
                    Rp {(checkoutModalProduct.priceIdr * checkoutQuantity).toLocaleString('id-ID')}
                  </span>
                  <span className="text-slate-400 font-bold">•</span>
                  <span className="text-amber-900 text-xs">
                    {checkoutModalProduct.priceCredits * checkoutQuantity} Cr
                  </span>
                </div>
              </div>
            </div>

            {/* Quantity Stepper */}
            <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-900">
              <span className="font-black text-slate-900">Jumlah Pembelian:</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setCheckoutQuantity(prev => Math.max(1, prev - 1))}
                  className="w-7 h-7 rounded-lg bg-white border border-slate-900 font-black flex items-center justify-center cursor-pointer shadow-2xs"
                >
                  -
                </button>
                <span className="font-mono font-black text-xs px-2">{checkoutQuantity}</span>
                <button
                  type="button"
                  onClick={() => setCheckoutQuantity(prev => prev + 1)}
                  className="w-7 h-7 rounded-lg bg-white border border-slate-900 font-black flex items-center justify-center cursor-pointer shadow-2xs"
                >
                  +
                </button>
              </div>
            </div>

            {/* Shipping Address for Physical Goods */}
            {checkoutModalProduct.type === 'PHYSICAL' && (
              <div className="space-y-1">
                <label className="font-black text-slate-900 flex items-center gap-1">
                  <Truck className="w-3.5 h-3.5 text-sky-700 stroke-[2.5px]" />
                  <span>Alamat Pengiriman Kurir:</span>
                </label>
                <input
                  type="text"
                  value={destinationAddress}
                  onChange={(e) => setDestinationAddress(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-semibold text-slate-900 bg-slate-50 focus:bg-white text-xs outline-none shadow-2xs"
                />
              </div>
            )}

            {/* Payment Method Selector */}
            <div className="space-y-1.5">
              <span className="font-black text-slate-900 block">Pilih Metode Pembayaran:</span>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'AI_CREDITS', label: 'AI Credits', sub: `${userCredits} Cr`, icon: Sparkles, color: 'bg-amber-100' },
                  { id: 'QRIS', label: 'Midtrans QRIS', sub: 'Instant', icon: QrCode, color: 'bg-rose-100' },
                  { id: 'VA', label: 'Virtual Account', sub: 'BCA / Mandiri', icon: CreditCard, color: 'bg-sky-100' },
                ].map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setCheckoutPaymentMethod(m.id as any)}
                    className={`p-2 rounded-xl border-2 border-slate-900 text-left transition cursor-pointer ${
                      checkoutPaymentMethod === m.id
                        ? `${m.color} shadow-[2px_2px_0px_#0f172a] font-black`
                        : 'bg-white hover:bg-slate-50 shadow-2xs'
                    }`}
                  >
                    <p className="font-black text-[11px] text-slate-950 truncate">{m.label}</p>
                    <p className="text-[9px] text-slate-600 font-bold">{m.sub}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Guarantees */}
            <div className="p-2.5 rounded-xl bg-emerald-50 border border-slate-900 flex items-center gap-2 text-[10px] text-emerald-950 font-bold">
              <ShieldCheck className="w-4 h-4 text-emerald-700 stroke-[2.5px] shrink-0" />
              <span>Garansi 100% Aman • 85% Royalti diteruskan langsung ke penjual</span>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={() => setCheckoutModalProduct(null)}
                className="flex-1 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleConfirmDirectCheckout}
                disabled={isProcessingCheckout}
                className="flex-1 py-2.5 rounded-xl bg-[#BBF7D0] hover:bg-emerald-300 font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer flex items-center justify-center gap-1.5"
              >
                {isProcessingCheckout ? (
                  <span>Memproses...</span>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 stroke-[2.5px] text-slate-950" />
                    <span>Bayar Sekarang</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
