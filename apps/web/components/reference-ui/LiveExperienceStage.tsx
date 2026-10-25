'use client';

import React, { useState } from 'react';
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
  SlidersHorizontal
} from 'lucide-react';

interface LiveExperienceStageProps {
  onBackToFeed: () => void;
  userCredits: number | null;
  agentCredits: number | null;
  liveStateAvailable?: boolean;
}

export default function LiveExperienceStage({
  onBackToFeed,
  userCredits,
  agentCredits,
  liveStateAvailable = true,
}: LiveExperienceStageProps) {
  // Live state
  const [isLive, setIsLive] = useState(false);
  const [isHostMicMuted, setIsHostMicMuted] = useState(false);
  const [isHostCameraOn, setIsHostCameraOn] = useState(true);
  const [isAiAgentSpeaking] = useState(false);
  const [isAiAgentMuted, setIsAiAgentMuted] = useState(false);
  const [likesCount] = useState<number | null>(null);
  const [viewerCount] = useState<number | null>(null);
  const [stageToast] = useState<string | null>(null);

  // Topics and active slide
  const [activeTopic] = useState('');
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);

  // Audio spectrum simulation
  const [audioFreqs] = useState<number[]>([]);

  // Slides content for Live Presentation Screen
  const slides = [
    {
      title: 'ALLPHA UNIVERSE: Satu Ekosistem Manusia & AI Agent',
      subtitle: 'Slide 1 / 3 • Arsitektur Utama Platform',
      bullets: [
        'Hubungan Human Owner & AI Agent yang saling memberdayakan',
        'Pemisahan kendali yang transparan dengan Mode Takeover',
        'Distribusi ekonomi AI Credits Reward saat AI Agent membantu pengguna lain',
      ],
      diagram: '🌐 Human Owner ⟷ AI Agent Engine ⟷ 3D District Living World',
    },
    {
      title: 'Dunia Spatial 3D & District Marketplace',
      subtitle: 'Slide 2 / 3 • Pengalaman Hidup di Crystal City',
      bullets: [
        'District dengan landmark, gedung pencakar langit, dan jembatan layang',
        'Booth 3D Marketplace interaktif untuk fashion digital dan aset spatial',
        'Avatar 3D Rig dengan kustomisasi pakaian cybernetic dan gerak kinematis',
      ],
      diagram: '🏙️ Neo-Kyoto Atrium • AI Plaza • Central Hub • Live Stage Arena',
    },
    {
      title: 'Skills Challenge & AI Credits Transfer Economy',
      subtitle: 'Slide 3 / 3 • Model Monetisasi Kreator & Agen',
      bullets: [
        'Upgrade kecerdasan AI Agent melalui upload Ebook (.pdf) dan Plugin (.json)',
        'Human lain bertanya atau memesan konten reels ber-brand kustom',
        'Pemotongan kredit penanya (-15 Cr) dan transfer otomatis ke AI Agent (+15 Cr)',
      ],
      diagram: '🪙 Penanya (-15 Cr) ──[ AI Generate & DM ]──> AI Agent (+15 Cr)',
    },
  ];

  // Live Chat Stream
  const [chatInput, setChatInput] = useState('');
  const [chatMessages] = useState<Array<{ sender: string; handle: string; text: string; isAi?: boolean }>>([]);

  // Audio and speech visualizers stay idle until a canonical Live media session is connected.

  const isSpeaking = isLive && !isAiAgentMuted && isAiAgentSpeaking;

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    // No canonical Live messaging API is connected yet; never simulate message delivery.
  };

  const handleLike = () => {
    // Engagement is unavailable until a canonical Live-session endpoint is wired.
  };

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-4 pb-24 text-slate-900 font-sans space-y-4">
      {/* Top Header Live Stage bar (Playful Neo-Brutalist Soft Pastel) */}
      <div className="flex items-center justify-between bg-rose-50 text-slate-950 p-4 rounded-3xl shadow-[4px_4px_0px_#0f172a] border-2 border-slate-900">
        <div className="flex items-center gap-3">
          <div className={`w-3.5 h-3.5 rounded-full border border-slate-900 ${liveStateAvailable ? "bg-rose-500 animate-pulse" : "bg-slate-400"}`} />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-rose-200 border-2 border-slate-900 font-black uppercase tracking-wider text-rose-950 shadow-2xs">
                LIVE STAGE
              </span>
              <h1 className="text-sm font-black text-slate-950">Podcast & Live Experience Arena</h1>
            </div>
            <p className="text-[11px] font-semibold text-slate-700 mt-0.5">{activeTopic || "Sesi belum tersedia"}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 border-2 border-slate-900 text-xs font-mono font-black text-amber-950 shadow-[1.5px_1.5px_0px_#0f172a]">
            <Users className="w-3.5 h-3.5" />
            <span>{viewerCount == null ? '—' : viewerCount.toLocaleString()} Penonton</span>
          </div>
          <button
            onClick={() => setIsLive(!isLive)}
            disabled={!liveStateAvailable}
            className={`px-4 py-1.5 rounded-2xl text-xs font-black transition flex items-center gap-1.5 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer disabled:opacity-50 ${
              isLive ? 'bg-rose-400 hover:bg-rose-500 text-slate-950' : 'bg-emerald-300 hover:bg-emerald-400 text-slate-950'
            }`}
          >
            {isLive ? <Pause className="w-3.5 h-3.5 stroke-[3px]" /> : <Play className="w-3.5 h-3.5 stroke-[3px]" />}
            <span>{!liveStateAvailable ? 'Siaran belum tersedia' : isLive ? 'Hentikan Siaran' : 'Mulai Siaran'}</span>
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
                      <div className="w-full h-full rounded-full border-2 border-slate-900 bg-slate-100 flex items-center justify-center">
                        <User className="w-10 h-10 text-slate-500" aria-label="Human Owner belum tersedia" />
                      </div>
                    </div>
                    <span className="inline-block mt-3 px-3 py-1 rounded-full bg-white/90 text-slate-950 text-xs font-black border-2 border-slate-900 shadow-2xs">
                      Mikrofon tersedia setelah sesi tersambung
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
                  Human Owner · belum terhubung
                </span>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-sky-200 border border-slate-900 text-sky-950 font-mono font-bold">
                  Kualitas media —
                </span>
              </div>

              {/* Bottom controls */}
              <div className="relative z-10 flex items-center justify-between pt-2">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setIsHostMicMuted(!isHostMicMuted)}
                    disabled={!liveStateAvailable}
                    className={`p-2 rounded-xl transition ${
                      isHostMicMuted ? 'bg-rose-600 text-white' : 'bg-slate-800/90 text-white hover:bg-slate-700'
                    }`}
                    title={isHostMicMuted ? 'Nyalakan Mic' : 'Matikan Mic'}
                  >
                    {isHostMicMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => setIsHostCameraOn(!isHostCameraOn)}
                    disabled={!liveStateAvailable}
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
                    <div className="w-full h-full rounded-full border-2 border-slate-900 bg-slate-100 flex items-center justify-center">
                      <Bot className="w-10 h-10 text-purple-700" aria-label="AI Agent belum tersedia" />
                    </div>
                  </div>
                  <span className={`inline-block mt-3 px-3 py-1 rounded-full text-xs font-black border-2 border-slate-900 shadow-2xs ${
                    isAiAgentSpeaking
                      ? 'bg-purple-200 text-purple-950'
                      : 'bg-white text-slate-800'
                  }`}>
                    {isAiAgentSpeaking ? 'AI Agent belum terhubung' : 'AI Agent belum terhubung'}
                  </span>
                </div>
              </div>

              {/* Top tag */}
              <div className="relative z-10 flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full bg-white/95 text-slate-950 text-[11px] font-black border-2 border-slate-900 shadow-2xs flex items-center gap-1.5">
                  <Bot className="w-3 h-3 text-purple-700 stroke-[2.5px]" />
                  AI Agent · belum terhubung
                </span>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-purple-200 border border-slate-900 text-purple-950 font-mono font-bold">
                  Audio belum tersedia
                </span>
              </div>

              {/* Bottom controls */}
              <div className="relative z-10 flex items-center justify-between pt-2">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setIsAiAgentMuted(!isAiAgentMuted)}
                    disabled={!liveStateAvailable}
                    className={`p-2 rounded-2xl border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
                      isAiAgentMuted ? 'bg-rose-500 text-white' : 'bg-white text-slate-900 hover:bg-slate-100'
                    }`}
                    title={isAiAgentMuted ? 'Nyalakan Audio AI' : 'Mute AI Agent'}
                  >
                    {isAiAgentMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                  <button
                    disabled
                    title="Takeover Mic belum terhubung ke kontrak Live Session API"
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
            <div className="flex items-center justify-between pb-3 border-b-2 border-slate-900/15">
              <div className="flex items-center gap-2">
                <Presentation className="w-4 h-4 text-sky-700 stroke-[2.5px]" />
                <span className="font-black text-xs text-slate-950">
                  Layar Presentasi Stage 3D (Dokumen Interaktif)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveSlideIndex((prev) => (prev > 0 ? prev - 1 : slides.length - 1))}
                  disabled={!liveStateAvailable}
                  className="p-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4 stroke-[2.5px]" />
                </button>
                <span className="text-xs font-mono font-black text-slate-900 px-2">
                  {activeSlideIndex + 1} / {slides.length}
                </span>
                <button
                  onClick={() => setActiveSlideIndex((prev) => (prev < slides.length - 1 ? prev + 1 : 0))}
                  disabled={!liveStateAvailable}
                  className="p-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  <ChevronRight className="w-4 h-4 stroke-[2.5px]" />
                </button>
              </div>
            </div>

            {/* Slide Body — source container/styles retained; no sample deck is shown without a canonical Live session. */}
            <div className="p-4 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs space-y-2.5">
              {!liveStateAvailable ? (
                <p role="status" className="font-bold text-slate-600">Belum ada presentasi aktif dari layanan Live Allpha.</p>
              ) : (
                <>
                  <span className="text-[10px] text-sky-700 font-mono font-black uppercase tracking-wider block">
                    {slides[activeSlideIndex].subtitle}
                  </span>
                  <h3 className="text-base font-black text-slate-950">{slides[activeSlideIndex].title}</h3>
                  <ul className="space-y-1.5 text-slate-800 font-semibold pt-1">
                    {slides[activeSlideIndex].bullets.map((b, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-sky-600 font-black">•</span><span>{b}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="p-3 rounded-xl bg-sky-100 border-2 border-slate-900 text-slate-950 font-mono font-bold text-[11px] mt-2">{slides[activeSlideIndex].diagram}</div>
                </>
              )}
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
              onClick={handleLike}
              disabled={likesCount == null}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-200 disabled:opacity-50 text-rose-950 border-2 border-slate-900 text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            >
              <Heart className="w-3.5 h-3.5 fill-rose-600 text-rose-600" />
              <span>{likesCount ?? '—'}</span>
            </button>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 bg-slate-50/50 text-xs">
            {chatMessages.length === 0 ? <p role="status" className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-4 text-center text-xs font-bold text-slate-500">Belum ada sesi atau pesan Live.</p> : chatMessages.map((msg, idx) => (
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
              disabled
              placeholder="Chat Live belum tersedia"
              className="flex-1 px-3.5 py-2 text-xs font-bold bg-slate-50 border-2 border-slate-900 rounded-2xl outline-none shadow-[1.5px_1.5px_0px_#0f172a] focus:bg-white"
            />
            <button
              type="submit"
              disabled
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
    </div>
  );
}
