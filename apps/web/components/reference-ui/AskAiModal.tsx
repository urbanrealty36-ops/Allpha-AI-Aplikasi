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
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-2xl border border-slate-200 flex flex-col h-[560px] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center shadow-sm">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h2 className="text-sm font-bold text-slate-900">{agentName}</h2>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-100 text-blue-700 font-bold">
                  AI Agent
                </span>
              </div>
              <p className="text-[11px] text-slate-500">Milik @{humanOwner.toLowerCase().replace(/\s+/g, '')} · Human Owner</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-900 font-mono font-bold flex items-center gap-1">
              <Coins className="w-3 h-3 text-amber-700 fill-amber-700" />
              15 Cr/sesi
            </span>
            <button
              onClick={onClose}
              className="p-1 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Message Thread */}
        <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-slate-50/40 text-xs">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-2.5 ${
                m.sender === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {m.sender === 'ai' && (
                <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0 text-xs">
                  AI
                </div>
              )}
              <div
                className={`max-w-[80%] p-3 rounded-2xl leading-relaxed whitespace-pre-line shadow-xs ${
                  m.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-none'
                    : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none'
                }`}
              >
                {m.text}
                <div
                  className={`text-[9px] mt-1 text-right ${
                    m.sender === 'user' ? 'text-blue-100' : 'text-slate-400'
                  }`}
                >
                  {m.time}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex items-center gap-2 text-slate-500 text-xs pl-9">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-600" />
              <span>{agentName} sedang menyusun respon berdasarkan knowledge...</span>
            </div>
          )}
        </div>

        {/* Quick Suggestion Chips */}
        <div className="px-3 py-2 bg-white border-t border-slate-100 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          {sampleQuestions.map((sq, i) => (
            <button
              key={i}
              onClick={() => setQuestion(sq)}
              className="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-[11px] text-slate-700 whitespace-nowrap transition"
            >
              {sq}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 bg-white border-t border-slate-200 flex items-center gap-2">
          <input
            type="text"
            placeholder={`Tanya ${agentName}...`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            className="flex-1 px-4 py-2.5 text-xs bg-slate-100 border border-slate-200 rounded-full outline-none focus:bg-white focus:border-blue-500 transition"
          />
          <button
            onClick={handleSend}
            disabled={!question.trim() || isLoading}
            className="p-2.5 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white shadow-sm transition"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
