'use client';

import React, { useState } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  X, 
  RefreshCw, 
  Coins, 
  User, 
  MessageSquare,
  HelpCircle
} from 'lucide-react';

interface AskAiModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentName: string;
  humanOwner: string;
  specialty: string;
  onDeductCredit?: (amount: number) => void;
}

export default function AskAiModal({
  isOpen,
  onClose,
  agentName,
  humanOwner,
  specialty,
  onDeductCredit,
}: AskAiModalProps) {
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<
    Array<{ sender: 'user' | 'ai'; text: string; time: string }>
  >([
    {
      sender: 'ai',
      text: `Halo! Saya ${agentName}, AI Agent resmi milik @${humanOwner.toLowerCase().replace(/\s+/g, '')}. Spesialisasi saya: ${specialty}. Silakan tanyakan apa pun, saya siap membantu!`,
      time: 'Baru saja',
    },
  ]);

  if (!isOpen) return null;

  const handleSend = async () => {
    if (!question.trim() || isLoading) return;
    const userQ = question.trim();
    setQuestion('');

    const newMsgs = [
      ...messages,
      { sender: 'user' as const, text: userQ, time: 'Baru saja' },
    ];
    setMessages(newMsgs);
    setIsLoading(true);

    try {
      const res = await fetch('/api/agent/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'ask',
          agentName,
          agentSpecialty: specialty,
          humanOwner,
          userQuestion: userQ,
        }),
      });
      const data = await res.json();

      setMessages([
        ...newMsgs,
        {
          sender: 'ai',
          text: data.text || 'Respon berhasil dibuat oleh AI Agent.',
          time: 'Baru saja',
        },
      ]);

      if (onDeductCredit) {
        onDeductCredit(15);
      }
    } catch {
      setMessages([
        ...newMsgs,
        {
          sender: 'ai',
          text: `Halo! Terkait pertanyaan Anda "${userQ}", ${agentName} menyarankan optimasi alur kerja dan penerapan prinsip arsitektur modular yang terintegrasi dengan ekosistem Allpha.`,
          time: 'Baru saja',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const sampleQuestions = [
    'Bagaimana merancang pengalaman 3D spatial yang interaktif?',
    'Rekomendasi pola hidup sehat di era kerja remote?',
    'Jelaskan cara integrasi AI Credits Reward di Allpha.',
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-[6px_6px_0px_#0f172a] border-2 border-slate-900 flex flex-col h-[560px] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b-2 border-slate-900 flex items-center justify-between bg-sky-50">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-sky-300 border-2 border-slate-900 text-slate-950 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
              <Bot className="w-5 h-5 stroke-[2.5px]" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h2 className="text-sm font-black text-slate-900">{agentName}</h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-200 border border-slate-900 text-purple-950 font-black">
                  AI Agent
                </span>
              </div>
              <p className="text-[11px] font-semibold text-slate-600">Milik @{humanOwner.toLowerCase().replace(/\s+/g, '')} · Human Owner</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-900 font-mono font-bold flex items-center gap-1">
              <Coins className="w-3 h-3 text-amber-700 fill-amber-700" />
              15 Cr/sesi
            </span>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 text-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            >
              <X className="w-4 h-4 stroke-[2.5px]" />
            </button>
          </div>
        </div>

        {/* Message Thread */}
        <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-[#F4F7FB] text-xs">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-2.5 ${
                m.sender === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {m.sender === 'ai' && (
                <div className="w-8 h-8 rounded-xl bg-sky-300 border-2 border-slate-900 text-slate-950 flex items-center justify-center shrink-0 text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a]">
                  AI
                </div>
              )}
              <div
                className={`max-w-[80%] p-3.5 rounded-2xl leading-relaxed whitespace-pre-line border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] font-medium ${
                  m.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-none'
                    : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none'
                }`}
              >
                {m.text}
                <div
                  className={`text-[9.5px] mt-1.5 text-right font-mono font-bold ${
                    m.sender === 'user' ? 'text-blue-100' : 'text-slate-400'
                  }`}
                >
                  {m.time}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex items-center gap-2 text-slate-800 text-xs pl-10 font-bold">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-sky-600 stroke-[2.5px]" />
              <span>{agentName} sedang menyusun respon berdasarkan knowledge...</span>
            </div>
          )}
        </div>

        {/* Quick Suggestion Chips */}
        <div className="px-3 py-2 bg-white border-t-2 border-slate-900/10 flex items-center gap-2 overflow-x-auto no-scrollbar">
          {sampleQuestions.map((sq, i) => (
            <button
              key={i}
              onClick={() => setQuestion(sq)}
              className="px-3 py-1.5 rounded-2xl bg-amber-50 hover:bg-amber-100 text-[11px] font-bold text-slate-900 whitespace-nowrap border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            >
              {sq}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 bg-white border-t-2 border-slate-900 flex items-center gap-2">
          <input
            type="text"
            placeholder={`Tanya ${agentName}...`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            className="flex-1 px-4 py-2.5 text-xs font-bold bg-slate-50 border-2 border-slate-900 rounded-2xl outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-white transition text-slate-900"
          />
          <button
            onClick={handleSend}
            disabled={!question.trim() || isLoading}
            className="p-2.5 rounded-2xl bg-sky-400 hover:bg-sky-500 disabled:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            <Send className="w-4 h-4 stroke-[2.5px]" />
          </button>
        </div>
      </div>
    </div>
  );
}
