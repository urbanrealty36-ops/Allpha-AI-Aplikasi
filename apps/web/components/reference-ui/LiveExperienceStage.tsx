'use client';

import React, { useState, useEffect } from 'react';
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
  userCredits: number;
  agentCredits: number;
  liveStateAvailable?: boolean;
}

export default function LiveExperienceStage({
  onBackToFeed,
  userCredits,
  agentCredits,
  liveStateAvailable = false,
}: LiveExperienceStageProps) {
  // Live state
  const [isLive, setIsLive] = useState(false);
  const [isHostMicMuted, setIsHostMicMuted] = useState(false);
  const [isHostCameraOn, setIsHostCameraOn] = useState(false);
  const [isAiAgentSpeaking, setIsAiAgentSpeaking] = useState(false);
  const [isAiAgentMuted, setIsAiAgentMuted] = useState(false);
  const [likesCount, setLikesCount] = useState(0);
  const [viewerCount, setViewerCount] = useState(0);

  // Topics and active slide
  const [activeTopic, setActiveTopic] = useState('');
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);

  // Audio spectrum simulation
  const [audioFreqs, setAudioFreqs] = useState<number[]>([]);

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
  const [chatMessages, setChatMessages] = useState<Array<{ sender: string; handle: string; text: string; isAi?: boolean }>>([]);

  // Audio frequency pulsation effect
  useEffect(() => {
    if (!liveStateAvailable || !isLive) return;
    const interval = setInterval(() => {
      setAudioFreqs((prev) =>
        prev.map(() => Math.floor(25 + Math.random() * 70))
      );
    }, 180);
    return () => clearInterval(interval);
  }, [isLive, liveStateAvailable]);

  // AI Agent turn-taking speech simulator
  useEffect(() => {
    if (!liveStateAvailable || !isLive || isAiAgentMuted) return;
    const interval = setInterval(() => {
      setIsAiAgentSpeaking((prev) => !prev);
    }, 4000);
    return () => clearInterval(interval);
  }, [isLive, isAiAgentMuted, liveStateAvailable]);

  const isSpeaking = isLive && !isAiAgentMuted && isAiAgentSpeaking;

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!liveStateAvailable) return;
    // Chat submission is intentionally disabled until a canonical Live chat API adapter is supplied.
  };

  const handleLike = () => {
    if (!liveStateAvailable) return;
    setLikesCount((prev) => prev + 1);
  };

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-4 pb-24 text-slate-900 font-sans space-y-4">
      {/* Top Header Live Stage bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between min-w-0 bg-slate-900 text-white p-4 rounded-3xl shadow-xl border border-slate-800">
        <div className="flex items-center gap-3 min-w-0 w-full sm:w-auto">
          <div className="w-3 h-3 shrink-0 rounded-full bg-rose-500 animate-pulse" />
          <div>
            <div className="flex flex-wrap items-center gap-2 min-w-0">
              <span className="text-xs px-2 py-0.5 rounded-full bg-rose-600 font-bold uppercase tracking-wider">
                {liveStateAvailable ? 'LIVE STAGE' : 'LIVE STAGE · BELUM TERHUBUNG'}
              </span>
              <h1 className="min-w-0 break-words text-sm font-black text-white">Podcast & Live Experience Arena</h1>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">{activeTopic || 'Sesi live dan data peserta akan ditampilkan setelah layanan Live terhubung.'}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-xs font-mono text-emerald-400">
            <Users className="w-3.5 h-3.5" />
            <span>{liveStateAvailable ? viewerCount.toLocaleString() : '—'} Penonton</span>
          </div>
          <button
            disabled={!liveStateAvailable}
            onClick={() => setIsLive(!isLive)}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition flex items-center gap-1.5 shadow ${
              isLive ? 'bg-rose-600 hover:bg-rose-700 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'
            }`}
          >
            {isLive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
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
            <div className="relative h-64 rounded-3xl bg-slate-950 overflow-hidden border border-slate-800 shadow-xl flex flex-col justify-between p-4 group">
              {/* Camera background simulation */}
              <div className="absolute inset-0 bg-gradient-to-tr from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center">
                {isHostCameraOn && liveStateAvailable ? (
                  <div className="text-center">
                    <div className="w-24 h-24 mx-auto rounded-full ring-4 ring-blue-500/40 p-1 bg-gradient-to-tr from-blue-600 to-cyan-500 shadow-2xl">
                      <img
                        src="/icon.svg"
                        alt="Host"
                        className="w-full h-full rounded-full object-cover"
                      />
                    </div>
                    <span className="inline-block mt-3 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs font-bold border border-blue-400/30">
                      Host Microphone Active
                    </span>
                  </div>
                ) : (
                  <div className="text-center text-slate-500 text-xs">
                    <VideoOff className="w-8 h-8 mx-auto mb-1 opacity-50" />
                    <span>Kamera Host Dimatikan</span>
                  </div>
                )}
              </div>

              {/* Top tag */}
              <div className="relative z-10 flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full bg-slate-900/80 text-white text-[11px] font-bold border border-slate-700 flex items-center gap-1.5">
                  <User className="w-3 h-3 text-blue-400" />
                  {liveStateAvailable ? 'Host terhubung' : 'Slot Host'}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-600/30 text-blue-300 font-mono">
                  1080p 60fps
                </span>
              </div>

              {/* Bottom controls */}
              <div className="relative z-10 flex items-center justify-between pt-2">
                <div className="flex items-center gap-1.5">
                  <button
                    disabled={!liveStateAvailable}
                    onClick={() => setIsHostMicMuted(!isHostMicMuted)}
                    className={`p-2 rounded-xl transition ${
                      isHostMicMuted ? 'bg-rose-600 text-white' : 'bg-slate-800/90 text-white hover:bg-slate-700'
                    }`}
                    title={isHostMicMuted ? 'Nyalakan Mic' : 'Matikan Mic'}
                  >
                    {isHostMicMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                  <button
                    disabled={!liveStateAvailable}
                    onClick={() => setIsHostCameraOn(!isHostCameraOn)}
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
            <div className="relative h-64 rounded-3xl bg-slate-950 overflow-hidden border border-purple-500/40 shadow-xl flex flex-col justify-between p-4 group">
              {/* 3D Holographic AI Agent Simulator */}
              <div className="absolute inset-0 bg-gradient-to-tr from-purple-950 via-slate-900 to-indigo-950 flex items-center justify-center">
                <div className="text-center">
                  <div className={`w-24 h-24 mx-auto rounded-full ring-4 ${isSpeaking ? 'ring-cyan-400 animate-pulse' : 'ring-purple-500/40'} p-1 bg-gradient-to-tr from-cyan-500 to-purple-600 shadow-2xl`}>
                    <img
                      src="/icon.svg"
                      alt="AI Agent"
                      className="w-full h-full rounded-full object-cover"
                    />
                  </div>
                  <span className={`inline-block mt-3 px-3 py-1 rounded-full text-xs font-bold border ${
                    isSpeaking
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400'
                      : 'bg-purple-500/20 text-purple-300 border-purple-400/30'
                  }`}>
                    {isSpeaking ? 'AI Agent sedang berbicara...' : 'AI Agent Standby'}
                  </span>
                </div>
              </div>

              {/* Top tag */}
              <div className="relative z-10 flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full bg-slate-900/80 text-white text-[11px] font-bold border border-purple-500/40 flex items-center gap-1.5">
                  <Bot className="w-3 h-3 text-cyan-400" />
                  {liveStateAvailable ? 'AI Agent terhubung' : 'Slot AI Agent'}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-600/30 text-purple-300 font-mono">
                  Neural Audio 48kHz
                </span>
              </div>

              {/* Bottom controls */}
              <div className="relative z-10 flex items-center justify-between pt-2">
                <div className="flex items-center gap-1.5">
                  <button
                    disabled={!liveStateAvailable}
                    onClick={() => setIsAiAgentMuted(!isAiAgentMuted)}
                    className={`p-2 rounded-xl transition ${
                      isAiAgentMuted ? 'bg-rose-600 text-white' : 'bg-slate-800/90 text-white hover:bg-slate-700'
                    }`}
                    title={isAiAgentMuted ? 'Nyalakan Audio AI' : 'Mute AI Agent'}
                  >
                    {isAiAgentMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                  <button
                    disabled={!liveStateAvailable}
                    onClick={() => alert('Takeover Mikrofon aktif: Human Owner mengambil alih suara')}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-800/90 text-cyan-300 hover:bg-slate-700 text-xs font-bold transition"
                  >
                    Takeover Mic
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  {audioFreqs.slice(6, 11).map((f, i) => (
                    <span
                      key={i}
                      className="w-1 bg-purple-400 rounded-full transition-all duration-150"
                      style={{ height: `${f * 0.28}px` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Shared Stage Presentation Screen (Document / Slide Viewer on Stage) */}
          <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 text-white shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Presentation className="w-4 h-4 text-cyan-400" />
                <span className="font-bold text-xs text-slate-200">
                  Layar Presentasi Stage 3D (Dokumen Interaktif)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  disabled={!liveStateAvailable}
                  onClick={() => setActiveSlideIndex((prev) => (prev > 0 ? prev - 1 : slides.length - 1))}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs font-mono text-cyan-300">
                  {activeSlideIndex + 1} / {slides.length}
                </span>
                <button
                  disabled={!liveStateAvailable}
                  onClick={() => setActiveSlideIndex((prev) => (prev < slides.length - 1 ? prev + 1 : 0))}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Slide Body */}
            {!liveStateAvailable ? <div role="status" className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 text-xs text-slate-300">Materi presentasi akan dimuat dari sesi Live kanonis. Belum ada dokumen atau slide yang terhubung.</div> :             <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 text-xs space-y-2.5">
              <span className="text-[10px] text-cyan-400 font-mono uppercase tracking-wider">
                {slides[activeSlideIndex].subtitle}
              </span>
              <h3 className="text-base font-black text-white">
                {slides[activeSlideIndex].title}
              </h3>
              <ul className="space-y-1.5 text-slate-300 pt-1">
                {slides[activeSlideIndex].bullets.map((b, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-cyan-400 font-bold">•</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
              <div className="p-3 rounded-xl bg-blue-950/40 border border-blue-500/20 text-cyan-200 font-mono text-[11px] mt-2">
                {slides[activeSlideIndex].diagram}
              </div>
            </div>}
          </div>
        </div>

        {/* Right Column: Live Chat & Audience Feedback */}
        <div className="flex flex-col h-[520px] rounded-3xl bg-white border border-slate-200 shadow-xl overflow-hidden">
          {/* Live Chat Header */}
          <div className="p-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs text-slate-900">Live Chat Pemirsa</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 font-bold">
                {liveStateAvailable ? 'Aktif' : 'Belum tersedia'}
              </span>
            </div>
            <button
              disabled={!liveStateAvailable}
              onClick={handleLike}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-rose-50 text-rose-600 border border-rose-200 text-xs font-bold hover:scale-105 transition"
            >
              <Heart className="w-3.5 h-3.5 fill-rose-500" />
              <span>{likesCount}</span>
            </button>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 bg-slate-50/40 text-xs">
            {!liveStateAvailable && <p role="status" className="rounded-xl border border-slate-200 bg-white p-3 text-slate-500">Belum ada sesi atau pesan Live yang dapat ditampilkan dari layanan kanonis.</p>}
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={`p-2.5 rounded-2xl ${
                  msg.isAi
                    ? 'bg-purple-50 border border-purple-200 text-purple-900'
                    : 'bg-white border border-slate-200 text-slate-800'
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-bold text-[11px]">
                    {msg.sender}
                    {msg.isAi && (
                      <span className="ml-1 text-[9px] px-1 py-0.2 rounded bg-purple-200 text-purple-800 font-semibold">
                        AI Agent
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] text-slate-400">{msg.handle}</span>
                </div>
                <p className="leading-relaxed text-[11px]">{msg.text}</p>
              </div>
            ))}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleSendChat} className="p-3 bg-white border-t border-slate-200 flex items-center gap-2">
            <input
              type="text"
              disabled={!liveStateAvailable}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Tulis pesan atau pertanyaan ke host..."
              className="flex-1 px-3 py-2 text-xs bg-slate-100 border border-slate-200 rounded-xl outline-none focus:bg-white focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={!liveStateAvailable || !chatInput.trim()}
              className="p-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white transition shadow"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
