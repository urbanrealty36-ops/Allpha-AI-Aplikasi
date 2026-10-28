'use client';

import React, { useState } from 'react';
import { 
  Bot, 
  Sparkles, 
  X, 
  Image as ImageIcon, 
  Film, 
  FileText, 
  Code2, 
  MessageSquare, 
  Clapperboard, 
  Upload, 
  CheckCircle2, 
  ArrowRight, 
  Zap, 
  Sliders, 
  Play, 
  Coins, 
  Copy,
  Layers,
  Wand2
} from 'lucide-react';
import { AIAgentProfile, HumanProfile } from '@/lib/reference-store';

interface CreatorStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  agent: AIAgentProfile;
  user: HumanProfile;
  userCredits: number;
  onDeductCredits: (amount: number, reason: string) => void;
  onOpenFilmAi?: () => void;
}

type StudioTool = 'IMAGE' | 'CONTENT' | 'VIDEO' | 'DOCS' | 'CODING' | 'AGENT_CHAT' | 'AI_CINEMA';

export default function CreatorStudioModal({
  isOpen,
  onClose,
  agent,
  user,
  userCredits,
  onDeductCredits,
  onOpenFilmAi,
}: CreatorStudioModalProps) {
  const [activeTool, setActiveTool] = useState<StudioTool>('IMAGE');
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedResult, setGeneratedResult] = useState<string | null>(null);
  const [selectedStyle, setSelectedStyle] = useState('Cyberpunk 3D');
  const [selectedAspectRatio, setSelectedAspectRatio] = useState<'1:1' | '16:9' | '9:16'>('1:1');
  const [codeLanguage, setCodeLanguage] = useState<'typescript' | 'python' | 'solidity'>('typescript');

  // Agent Chat Simulation State
  const [chatMessages, setChatMessages] = useState<Array<{ sender: string; text: string; isAi: boolean }>>([]);
  const [chatInput, setChatInput] = useState('');

  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  if (!isOpen) return null;

  const handleGenerate = () => {
    if (!prompt.trim()) {
      showToast('Masukkan prompt atau instruksi kreasi terlebih dahulu.');
      return;
    }
    // No canonical generation-job, media, or credit-ledger contract is currently
    // wired to this reference modal. Never simulate output or deduct local credits.
    setGeneratedResult(null);
    showToast('Fitur ini belum tersedia: layanan generasi dan ledger kredit belum terhubung.');
  };

  const handleSendChatMessage = () => {
    if (!chatInput.trim()) return;
    showToast('Chat Agent dari Creator Studio belum terhubung ke endpoint generasi kanonis.');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Studio Header */}
        <div className="p-4 border-b-2 border-slate-900 bg-[#FEF08A] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-slate-900">
              <Wand2 className="w-5 h-5 text-purple-700" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-black text-slate-900 tracking-tight">ALLPHA CREATOR STUDIO</h2>
                <span className="text-[9px] font-black px-2 py-0.5 rounded-full bg-white border border-slate-900 text-slate-900 uppercase">
                  MULTI-MODAL AI
                </span>
              </div>
              <p className="text-[11px] font-bold text-slate-800">
                Didukung AI Agent: <strong>{agent.name}</strong> ({agent.bidang || 'Kreatif'})
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-black text-slate-900 bg-white px-2.5 py-1 rounded-xl border border-slate-900 shadow-[1px_1px_0px_#0f172a]">
              🪙 {userCredits} Cr
            </span>
            <button
              onClick={onClose}
              className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-700 hover:bg-slate-100 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Studio Tool Selection Tabs */}
        <div className="flex border-b-2 border-slate-900 bg-slate-100 p-2 gap-1.5 overflow-x-auto no-scrollbar">
          {[
            { id: 'IMAGE', label: '🎨 Image 3D', cost: '10 Cr' },
            { id: 'CONTENT', label: '✍️ Text / Content', cost: '10 Cr' },
            { id: 'VIDEO', label: '🎥 Video AI', cost: '25 Cr' },
            { id: 'DOCS', label: '📄 Dokumen & RAG', cost: '10 Cr' },
            { id: 'CODING', label: '💻 Coding / Code', cost: '10 Cr' },
            { id: 'AGENT_CHAT', label: '💬 Tanya Agent', cost: 'Gratis' },
            { id: 'AI_CINEMA', label: '🎬 Film AI', cost: '40 Cr' },
          ].map((tool) => (
            <button
              key={tool.id}
              onClick={() => {
                setActiveTool(tool.id as StudioTool);
                setGeneratedResult(null);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-black border-2 border-slate-900 whitespace-nowrap transition cursor-pointer ${
                activeTool === tool.id
                  ? 'bg-white text-slate-900 shadow-[2px_2px_0px_#0f172a]'
                  : 'bg-slate-200/60 hover:bg-white text-slate-600'
              }`}
            >
              <span>{tool.label}</span>
              <span className="text-[9.5px] font-mono text-amber-700 block mt-0.2">{tool.cost}</span>
            </button>
          ))}
        </div>

        {/* Tool Workspace Area */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-4 flex-1">
          
          {/* AI CINEMA SHORTCUT */}
          {activeTool === 'AI_CINEMA' && (
            <div className="p-4 rounded-3xl bg-[#DDD6FE]/40 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3">
              <div className="flex items-center gap-2">
                <Clapperboard className="w-5 h-5 text-purple-700" />
                <h3 className="text-sm font-black text-slate-900 uppercase">Studio Produksi Film AI Allpha</h3>
              </div>
              <p className="text-xs text-slate-700 font-medium leading-relaxed">
                Buat serial drama pendek vertikal AI, susun naskah per episode, rancang storyboard, dan generate trailer premiere langsung ke tab Film AI Allpha Universe!
              </p>
              <button
                onClick={() => {
                  onClose();
                  if (onOpenFilmAi) onOpenFilmAi();
                }}
                className="w-full py-2.5 px-4 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center gap-2"
              >
                <span>Buka Allpha Cinema & AI Director Studio</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* AGENT CHAT COMMUNICATION SIMULATOR */}
          {activeTool === 'AGENT_CHAT' && (
            <div className="flex flex-col h-[380px] rounded-2xl border-2 border-slate-900 bg-slate-50 overflow-hidden">
              <div className="p-3 border-b-2 border-slate-900 bg-white flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <img src={agent.avatar3DImage || agent.avatar} alt={agent.name} className="w-7 h-7 rounded-lg border border-slate-900 object-cover" />
                  <div>
                    <span className="text-xs font-black text-slate-900">{agent.name}</span>
                    <span className="text-[10px] text-emerald-600 font-bold block leading-none">● Online & Auto-Reply Aktif</span>
                  </div>
                </div>
                <span className="text-[10px] font-black bg-purple-100 text-purple-800 px-2 py-0.5 rounded-md border border-purple-300">
                  {agent.bidang || 'Kreatif'}
                </span>
              </div>

              {/* Chat Feed */}
              <div className="flex-1 p-3 overflow-y-auto space-y-2.5 text-xs">
                {chatMessages.map((m, i) => (
                  <div key={i} className={`flex ${m.isAi ? 'justify-start' : 'justify-end'}`}>
                    <div className={`max-w-[80%] p-2.5 rounded-2xl border-2 border-slate-900 font-medium ${
                      m.isAi ? 'bg-white shadow-[1.5px_1.5px_0px_#0f172a] text-slate-900' : 'bg-[#BAE6FD] text-slate-950 font-bold'
                    }`}>
                      <p className="text-[9px] font-bold text-slate-500 mb-0.5">{m.sender}</p>
                      <p>{m.text}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Chat Input */}
              <div className="p-2.5 border-t-2 border-slate-900 bg-white flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendChatMessage()}
                  placeholder={`Ketik pesan atau instruksi ke ${agent.name}...`}
                  className="flex-1 px-3 py-2 bg-slate-50 border-2 border-slate-900 rounded-xl text-xs font-medium outline-none"
                />
                <button
                  onClick={handleSendChatMessage}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-black text-xs rounded-xl shadow-[1.5px_1.5px_0px_#0f172a]"
                >
                  Kirim
                </button>
              </div>
            </div>
          )}

          {/* GENERATION CONTROLS (IMAGE, CONTENT, VIDEO, DOCS, CODING) */}
          {activeTool !== 'AI_CINEMA' && activeTool !== 'AGENT_CHAT' && (
            <div className="space-y-3.5">
              
              {/* Option Selectors based on tool */}
              {activeTool === 'IMAGE' && (
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="font-black text-slate-900 text-[11px] block mb-1">Gaya Visual:</label>
                    <select
                      value={selectedStyle}
                      onChange={(e) => setSelectedStyle(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl border-2 border-slate-900 bg-white font-bold"
                    >
                      <option value="Cyberpunk 3D">Cyberpunk 3D Spatial</option>
                      <option value="Anime Menggu Pastel">Soft Pastel Menggu</option>
                      <option value="Hyper-Realistic PBR">Hyper-Realistic PBR Three.js</option>
                      <option value="Neo-Brutalism Poster">Neo-Brutalism Graphic Art</option>
                    </select>
                  </div>
                  <div>
                    <label className="font-black text-slate-900 text-[11px] block mb-1">Aspect Ratio:</label>
                    <div className="flex gap-1.5">
                      {(['1:1', '16:9', '9:16'] as const).map((r) => (
                        <button
                          key={r}
                          onClick={() => setSelectedAspectRatio(r)}
                          className={`flex-1 py-1.5 rounded-xl border-2 border-slate-900 font-black text-xs ${
                            selectedAspectRatio === r ? 'bg-[#FEF08A] shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-white'
                          }`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTool === 'CODING' && (
                <div>
                  <label className="font-black text-slate-900 text-[11px] block mb-1">Bahasa Pemrograman / Stack:</label>
                  <div className="flex gap-2">
                    {[
                      { id: 'typescript', label: 'TypeScript / React' },
                      { id: 'python', label: 'Python AI Agent' },
                      { id: 'solidity', label: 'Solidity ERC-6551 TBA' },
                    ].map((lang) => (
                      <button
                        key={lang.id}
                        onClick={() => setCodeLanguage(lang.id as any)}
                        className={`px-3 py-1.5 rounded-xl border-2 border-slate-900 font-bold text-xs ${
                          codeLanguage === lang.id ? 'bg-[#BBF7D0] shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-white'
                        }`}
                      >
                        {lang.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Prompt Input Box */}
              <div>
                <label className="font-black text-slate-900 text-xs block mb-1 uppercase">
                  {activeTool === 'IMAGE' && 'Deskripsikan Aset Gambar / Visual 3D yang ingin di-generate:'}
                  {activeTool === 'CONTENT' && 'Topik Postingan / Naskah Konten yang diinginkan:'}
                  {activeTool === 'VIDEO' && 'Prompt Video Reels AI (Adegan, Gerak Kamera, Suasana):'}
                  {activeTool === 'DOCS' && 'Upload atau tempel referensi dokumen untuk RAG Knowledge Agent:'}
                  {activeTool === 'CODING' && 'Spesifikasi fitur atau logika kode yang ingin dibuat:'}
                </label>
                <textarea
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={`Contoh: Buatkan ${activeTool.toLowerCase()} futuristik bertema Allpha Universe 2026...`}
                  className="w-full p-3 rounded-2xl border-2 border-slate-900 bg-slate-50 text-xs font-semibold text-slate-900 outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-white"
                />
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="w-full py-3 px-4 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                <span>{isGenerating ? 'AI Sedang Memproses Kreasi...' : `Generate dengan ${agent.name}`}</span>
              </button>

              {/* Generated Result Container */}
              {generatedResult && (
                <div className="p-4 rounded-3xl bg-slate-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-2.5 animate-in fade-in duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-slate-900 uppercase flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>Hasil Kreasi Berhasil Dibuat</span>
                    </span>
                    <button
                      onClick={() => {
                        if (navigator.clipboard) navigator.clipboard.writeText(generatedResult);
                        showToast('Hasil disalin ke clipboard!');
                      }}
                      className="px-2.5 py-1 rounded-xl bg-white border border-slate-900 font-bold text-[10px] flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>Salin</span>
                    </button>
                  </div>

                  {activeTool === 'IMAGE' ? (
                    <div className="rounded-2xl overflow-hidden border-2 border-slate-900 bg-slate-950 max-h-60">
                      <img src={generatedResult} alt="Hasil AI" className="w-full h-full object-cover" />
                    </div>
                  ) : activeTool === 'CODING' ? (
                    <pre className="p-3 bg-slate-900 text-emerald-400 rounded-xl text-[11px] font-mono overflow-x-auto border border-slate-800">
                      <code>{generatedResult}</code>
                    </pre>
                  ) : (
                    <div className="p-3 bg-white rounded-xl border border-slate-200 text-xs font-medium text-slate-800 whitespace-pre-line leading-relaxed">
                      {generatedResult}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Floating Toast */}
        {toastMsg && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl bg-slate-900 text-white text-xs font-bold border-2 border-slate-700 shadow-xl flex items-center gap-2">
            <span>✨</span>
            <span>{toastMsg}</span>
          </div>
        )}
      </div>
    </div>
  );
}
