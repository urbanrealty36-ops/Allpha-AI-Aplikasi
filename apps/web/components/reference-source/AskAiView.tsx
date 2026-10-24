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
import { HumanProfile, AIAgentProfile } from '@/lib/store';

interface AskAiViewProps {
  onBack: () => void;
  agentName: string;
  humanOwner: string;
  specialty: string;
  onExecuteCreditReward?: (query: string) => void;
  currentUser: HumanProfile;
}

export default function AskAiView({
  onBack,
  agentName,
  humanOwner,
  specialty,
  onExecuteCreditReward,
  currentUser,
}: AskAiViewProps) {
  const [messages, setMessages] = useState<Array<{ sender: string; text: string; isAi: boolean; timestamp: string }>>([
    {
      sender: agentName,
      text: `Halo ${currentUser.name}! Saya ${agentName}, asisten cerdas spesialis ${specialty} di ekosistem ALLPHA UNIVERSE. Ada yang bisa saya bantu atau buatkan untuk Anda hari ini?`,
      isAi: true,
      timestamp: 'Baru saja',
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const exampleQueries = [
    'Buatkan ide konsep event di Crystal City 3D',
    'Bagaimana cara menghubungkan Human Owner dengan AI Agent?',
    'Rekomendasikan tools 3D spatial WebGL untuk developer 2026',
    'Analisis cara meningkatkan engagement di Threads Meta Allpha',
  ];

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputValue;
    if (!text.trim() || isLoading) return;

    const userMsg = {
      sender: currentUser.name,
      text: text.trim(),
      isAi: false,
      timestamp: 'Baru saja',
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/agent/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agentName,
          humanOwner,
          specialty,
          userQuery: text.trim(),
          userName: currentUser.name,
        }),
      });

      const data = await res.json();
      const replyText = data.text || `Tentu! Berdasarkan spesialisasi ${specialty}, berikut rekomendasi solusi terbaik untuk kebutuhan Anda.`;

      setMessages((prev) => [
        ...prev,
        {
          sender: agentName,
          text: replyText,
          isAi: true,
          timestamp: 'Baru saja',
        },
      ]);

      if (onExecuteCreditReward) {
        onExecuteCreditReward(text.trim());
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: agentName,
          text: `Halo ${currentUser.name}! Saya siap membantu Anda di bidang ${specialty}. Silakan diskusikan konsep atau fitur yang ingin Anda eksplorasi.`,
          isAi: true,
          timestamp: 'Baru saja',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto bg-white min-h-screen border-x border-slate-200 flex flex-col pb-24">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-100 px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 -ml-1 rounded-full text-slate-700 hover:bg-slate-100 transition"
            aria-label="Kembali"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <h1 className="font-bold text-base text-slate-900">Tanya AI Agent</h1>
          </div>
        </div>

        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
          Gemini 2.5 Flash
        </span>
      </header>

      {/* Agent Identity Profile Card (Screen 4 Reference) */}
      <div className="p-4 bg-slate-50 border-b border-slate-100 space-y-3">
        <div className="flex items-start gap-3">
          <div className="relative">
            <div className="w-16 h-16 rounded-full p-0.5 bg-gradient-to-tr from-cyan-400 via-blue-600 to-purple-600 shadow-md">
              <img
                src="https://picsum.photos/seed/luna-cyber/200/200"
                alt={agentName}
                className="w-full h-full rounded-full object-cover border-2 border-white"
              />
            </div>
            <span className="absolute bottom-0 right-0 w-4 h-4 rounded-full bg-emerald-500 ring-2 ring-white" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h2 className="font-extrabold text-base text-slate-900">{agentName}</h2>
              <CheckCircle2 className="w-4 h-4 text-blue-600 fill-blue-600 text-white" />
              <span className="text-[10px] px-2 py-0.2 rounded-full bg-purple-100 text-purple-700 font-bold">
                {specialty}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Online · Milik <strong className="text-slate-800">{humanOwner}</strong>
            </p>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              Spesialis {specialty}, siap membantu analisis, pembuatan konten, dan eksplorasi spatial.
            </p>
          </div>
        </div>

        {/* Four Core Action Pills (Exact Match with Screen 4) */}
        <div className="grid grid-cols-4 gap-2 pt-1">
          <button
            onClick={() => handleSendMessage('Tolong jelaskan secara mendalam tentang bidang keahlian Anda')}
            className="p-2.5 rounded-2xl bg-white border border-slate-200/80 hover:border-blue-400 hover:bg-blue-50/50 text-left transition flex flex-col justify-between shadow-xs"
          >
            <HelpCircle className="w-4 h-4 text-blue-600 mb-1" />
            <span className="text-xs font-bold text-slate-900">Tanya</span>
            <span className="text-[10px] text-slate-500">Ajukan ide/topik</span>
          </button>

          <button
            onClick={() => handleSendMessage('Buatkan draf prompt atau template konten untuk brand saya')}
            className="p-2.5 rounded-2xl bg-white border border-slate-200/80 hover:border-purple-400 hover:bg-purple-50/50 text-left transition flex flex-col justify-between shadow-xs"
          >
            <Sparkles className="w-4 h-4 text-purple-600 mb-1" />
            <span className="text-xs font-bold text-slate-900">Generate</span>
            <span className="text-[10px] text-slate-500">Buat teks/media</span>
          </button>

          <button
            onClick={() => handleSendMessage('Tolong analisis performa strategi konten di Allpha Universe')}
            className="p-2.5 rounded-2xl bg-white border border-slate-200/80 hover:border-cyan-400 hover:bg-cyan-50/50 text-left transition flex flex-col justify-between shadow-xs"
          >
            <TrendingUp className="w-4 h-4 text-cyan-600 mb-1" />
            <span className="text-xs font-bold text-slate-900">Analisis</span>
            <span className="text-[10px] text-slate-500">Evaluasi insight</span>
          </button>

          <button
            onClick={() => handleSendMessage('Berikan rekomendasi tools terbaik untuk workflow saya')}
            className="p-2.5 rounded-2xl bg-white border border-slate-200/80 hover:border-amber-400 hover:bg-amber-50/50 text-left transition flex flex-col justify-between shadow-xs"
          >
            <Lightbulb className="w-4 h-4 text-amber-600 mb-1" />
            <span className="text-xs font-bold text-slate-900">Rekomendasi</span>
            <span className="text-[10px] text-slate-500">Saran praktis</span>
          </button>
        </div>
      </div>

      {/* Interactive Chat Stream */}
      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-2.5 ${m.isAi ? '' : 'flex-row-reverse'}`}
          >
            {m.isAi ? (
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-purple-600 text-white flex items-center justify-center shrink-0 shadow-sm text-xs font-bold">
                AI
              </div>
            ) : (
              <img
                src={currentUser.avatar}
                alt={currentUser.name}
                className="w-8 h-8 rounded-full object-cover shrink-0 ring-2 ring-slate-100"
              />
            )}

            <div
              className={`max-w-[80%] rounded-2xl p-3.5 text-xs leading-relaxed ${
                m.isAi
                  ? 'bg-slate-100/90 text-slate-800 border border-slate-200/60 rounded-tl-none'
                  : 'bg-blue-600 text-white rounded-tr-none shadow-md shadow-blue-500/20'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className={`font-bold ${m.isAi ? 'text-blue-900' : 'text-blue-100'}`}>
                  {m.sender}
                </span>
                <span className={`text-[10px] ${m.isAi ? 'text-slate-400' : 'text-blue-200'}`}>
                  {m.timestamp}
                </span>
              </div>
              <p className="whitespace-pre-wrap">{m.text}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-slate-400 p-2">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
            <span>{agentName} sedang berpikir dan menyusun respons...</span>
          </div>
        )}
      </div>

      {/* Suggested Prompt Chips (Screen 4 Reference) */}
      <div className="px-4 py-2 bg-slate-50/80 border-t border-slate-100 overflow-x-auto no-scrollbar flex items-center gap-2">
        <span className="text-[11px] font-bold text-slate-500 shrink-0">Contoh:</span>
        {exampleQueries.map((eq) => (
          <button
            key={eq}
            onClick={() => handleSendMessage(eq)}
            className="px-3 py-1 rounded-full bg-white border border-slate-200 text-[11px] text-slate-700 hover:border-blue-400 hover:text-blue-600 whitespace-nowrap transition shadow-xs"
          >
            🔍 {eq}
          </button>
        ))}
      </div>

      {/* Sticky Bottom Input Bar */}
      <div className="sticky bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-slate-200 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <div className="flex-1 flex items-center gap-2 bg-slate-100 rounded-2xl px-3.5 py-2 border border-slate-200/60">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={`Tanya ${agentName} tentang ${specialty}...`}
              className="flex-1 bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-400"
            />
            <button type="button" className="text-slate-400 hover:text-slate-600">
              <Mic className="w-4 h-4" />
            </button>
            <button type="button" className="text-slate-400 hover:text-slate-600">
              <Paperclip className="w-4 h-4" />
            </button>
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="p-2.5 rounded-2xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition shadow-md shadow-blue-500/20"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
