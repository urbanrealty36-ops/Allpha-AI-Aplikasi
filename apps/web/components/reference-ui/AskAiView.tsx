'use client';

import React, { useState } from 'react';
import { 
  ArrowLeft, 
  Bot, 
  Sparkles, 
  Send, 
  CheckCircle2, 
  Search, 
  HelpCircle, 
  Layers, 
  Lightbulb, 
  TrendingUp, 
  Compass, 
  Mic, 
  Paperclip,
  Check
} from 'lucide-react';
import type { HumanProfile } from '@/lib/reference-store';

interface AskAiViewProps {
  onBack: () => void;
  agentName: string;
  humanOwner: string;
  specialty: string;
  onExecuteCreditReward?: (query: string) => void;
  currentUser: HumanProfile;
  availabilityMessage?: string;
}

export default function AskAiView({
  onBack,
  agentName,
  humanOwner,
  specialty,
  onExecuteCreditReward,
  currentUser,
  availabilityMessage = 'Percakapan AI belum tersedia dari layanan Allpha.',
}: AskAiViewProps) {
  const [messages, setMessages] = useState<Array<{ sender: string; text: string; isAi: boolean; timestamp: string }>>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [requestError, setRequestError] = useState('');

  const exampleQueries = [
    'Buatkan ide konsep event di Crystal City 3D',
    'Bagaimana cara menghubungkan Human Owner dengan AI Agent?',
    'Rekomendasikan tools 3D spatial WebGL untuk developer 2026',
    'Analisis cara meningkatkan engagement di Threads Meta Allpha',
  ];

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputValue;
    if (!text.trim() || isLoading) return;
    setRequestError(availabilityMessage || 'Percakapan AI belum tersedia dari Agent Runtime Allpha.');
  };

  return (
    <div className="w-full max-w-xl mx-auto bg-white min-h-screen border-x border-slate-200 flex flex-col pb-24">
      {/* Top Header */}
      <header className="sticky top-0 z-30 bg-white border-b-2 border-slate-900 px-4 h-15 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-2.5">
          <button
            onClick={onBack}
            className="w-9 h-9 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 flex items-center justify-center text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            aria-label="Kembali"
          >
            <ArrowLeft className="w-4.5 h-4.5 stroke-[2.5px]" />
          </button>
          <div className="flex items-center gap-2">
            <h1 className="font-black text-base text-slate-900">Tanya AI Agent</h1>
          </div>
        </div>

        <span className="text-[10px] font-black px-2.5 py-0.5 rounded-full bg-purple-200 border-2 border-slate-900 text-purple-950 shadow-2xs">
          Gemini 2.5 Flash
        </span>
      </header>

      {/* Agent Identity Profile Card (Neo-Brutalist Soft Pastel) */}
      <div className="p-4 m-3.5 rounded-3xl bg-sky-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3">
        <div className="flex items-start gap-3">
          <div className="relative shrink-0">
            <div className="w-16 h-16 rounded-2xl overflow-hidden border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <img
                src="https://picsum.photos/seed/luna-cyber/200/200"
                alt={agentName}
                className="w-full h-full object-cover"
              />
            </div>
            <span className="absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-slate-900" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h2 className="font-black text-base text-slate-900">{agentName}</h2>
              <CheckCircle2 className="w-4 h-4 text-sky-600 fill-sky-200" />
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-200 border border-slate-900 text-purple-950 font-black">
                {specialty}
              </span>
            </div>
            <p className="text-xs text-slate-600 font-semibold mt-0.5">
              Online · Milik <strong className="text-slate-900">{humanOwner}</strong>
            </p>
            <p className="text-xs font-medium text-slate-700 mt-1 leading-relaxed">
              Spesialis {specialty}, siap membantu analisis, pembuatan konten, dan eksplorasi spatial.
            </p>
          </div>
        </div>

        {/* Four Core Action Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
          <button
            onClick={() => handleSendMessage('Tolong jelaskan secara mendalam tentang bidang keahlian Anda')}
            className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 text-left transition flex flex-col justify-between cursor-pointer"
          >
            <HelpCircle className="w-4 h-4 text-sky-600 mb-1 stroke-[2.5px]" />
            <span className="text-xs font-black text-slate-900">Tanya</span>
            <span className="text-[10px] text-slate-600 font-semibold">Ajukan topik</span>
          </button>

          <button
            onClick={() => handleSendMessage('Buatkan draf prompt atau template konten untuk brand saya')}
            className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 text-left transition flex flex-col justify-between cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-purple-600 mb-1 stroke-[2.5px]" />
            <span className="text-xs font-black text-slate-900">Generate</span>
            <span className="text-[10px] text-slate-600 font-semibold">Buat konten</span>
          </button>

          <button
            onClick={() => handleSendMessage('Tolong analisis performa strategi konten di Allpha Universe')}
            className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 text-left transition flex flex-col justify-between cursor-pointer"
          >
            <TrendingUp className="w-4 h-4 text-emerald-600 mb-1 stroke-[2.5px]" />
            <span className="text-xs font-black text-slate-900">Analisis</span>
            <span className="text-[10px] text-slate-600 font-semibold">Evaluasi insight</span>
          </button>

          <button
            onClick={() => handleSendMessage('Berikan rekomendasi tools terbaik untuk workflow saya')}
            className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 text-left transition flex flex-col justify-between cursor-pointer"
          >
            <Lightbulb className="w-4 h-4 text-amber-600 mb-1 stroke-[2.5px]" />
            <span className="text-xs font-black text-slate-900">Rekomendasi</span>
            <span className="text-[10px] text-slate-600 font-semibold">Saran praktis</span>
          </button>
        </div>
      </div>

      {/* Interactive Chat Stream */}
      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {availabilityMessage && <p role="status" className="rounded-xl border-2 border-amber-400 bg-amber-50 p-3 text-xs font-bold text-amber-900">{availabilityMessage}</p>}
        {requestError && <p role="alert" className="rounded-xl border-2 border-rose-400 bg-white p-3 text-xs font-bold text-rose-700">{requestError}</p>}
        {messages.length === 0 && <p className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-5 text-center text-xs font-semibold text-slate-600">Belum ada percakapan dari Agent Runtime</p>}
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-2.5 ${m.isAi ? '' : 'flex-row-reverse'}`}
          >
            {m.isAi ? (
              <div className="w-8 h-8 rounded-xl bg-sky-300 border-2 border-slate-900 text-slate-950 flex items-center justify-center shrink-0 shadow-[1.5px_1.5px_0px_#0f172a] text-xs font-black">
                AI
              </div>
            ) : (
              <img
                src={currentUser.avatar}
                alt={currentUser.name}
                className="w-8 h-8 rounded-xl object-cover shrink-0 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
              />
            )}

            <div
              className={`max-w-[80%] rounded-2xl p-3.5 text-xs leading-relaxed border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] ${
                m.isAi
                  ? 'bg-white text-slate-900 rounded-tl-none font-medium'
                  : 'bg-sky-400 text-slate-950 rounded-tr-none font-bold'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-black text-slate-950">
                  {m.sender}
                </span>
                <span className="text-[10px] text-slate-600 font-mono font-bold">
                  {m.timestamp}
                </span>
              </div>
              <p className="whitespace-pre-wrap">{m.text}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs font-bold text-slate-800 p-2">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-500 border border-slate-900 animate-ping" />
            <span>{agentName} sedang berpikir dan menyusun respons...</span>
          </div>
        )}
      </div>

      {/* Suggested Prompt Chips */}
      <div className="px-4 py-2 bg-white border-t-2 border-slate-900/10 overflow-x-auto no-scrollbar flex items-center gap-2">
        <span className="text-[11px] font-black text-slate-700 shrink-0">Contoh:</span>
        {exampleQueries.map((eq) => (
          <button
            key={eq}
            onClick={() => handleSendMessage(eq)}
            className="px-3 py-1 rounded-2xl bg-amber-50 border-2 border-slate-900 text-[11px] font-bold text-slate-900 hover:bg-amber-100 whitespace-nowrap transition shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
          >
            🔍 {eq}
          </button>
        ))}
      </div>

      {/* Sticky Bottom Input Bar */}
      <div className="sticky bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t-2 border-slate-900 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <div className="flex-1 flex items-center gap-2 bg-slate-50 rounded-2xl px-3.5 py-2 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={`Tanya ${agentName} tentang ${specialty}...`}
              className="flex-1 bg-transparent text-xs font-bold text-slate-900 outline-none placeholder:text-slate-500"
            />
            <button type="button" className="text-slate-500 hover:text-slate-900">
              <Mic className="w-4 h-4" />
            </button>
            <button type="button" className="text-slate-500 hover:text-slate-900">
              <Paperclip className="w-4 h-4" />
            </button>
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading || Boolean(availabilityMessage)}
            className="p-2.5 rounded-2xl bg-sky-400 hover:bg-sky-500 disabled:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            <Send className="w-4 h-4 stroke-[2.5px]" />
          </button>
        </form>
      </div>
    </div>
  );
}
