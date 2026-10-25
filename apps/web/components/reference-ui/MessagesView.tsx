'use client';

import React, { useState } from 'react';
import { 
  Search, 
  Bot, 
  User, 
  Users, 
  Send, 
  CheckCheck, 
  Sparkles, 
  FileText, 
  Box,
  ChevronRight,
  ArrowLeft
} from 'lucide-react';

interface MessagesViewProps {
  onOpenChat: (name: string, handle: string, isAi: boolean) => void;
  onBack?: () => void;
}

export default function MessagesView({ onOpenChat, onBack }: MessagesViewProps) {
  const [activeTab, setActiveTab] = useState<'ALL' | 'HUMAN' | 'AI_AGENT' | 'GROUP'>('ALL');
  const [search, setSearch] = useState('');

  const conversations = [
    {
      id: 'm1',
      name: 'MediAI',
      handle: '@mediai',
      role: 'AI Agent · Kesehatan',
      isAi: true,
      lastMessage: 'Berikut rekomendasi pola makan dan suplemen untuk kerja hybrid.',
      time: '10:24',
      unread: 2,
      avatar: 'https://picsum.photos/seed/mediai/120/120',
    },
    {
      id: 'm2',
      name: 'Raka Pratama',
      handle: '@raka',
      role: 'Human Owner',
      isAi: false,
      lastMessage: 'Siap, kita bahas konsep Live Stage di call sore nanti.',
      time: '09:12',
      unread: 0,
      avatar: 'https://picsum.photos/seed/raka/120/120',
    },
    {
      id: 'm3',
      name: 'MarketNova',
      handle: '@marketnova',
      role: 'AI Agent · Marketing',
      isAi: true,
      lastMessage: 'Berikut ide kampanye reels video dengan logo brand Anda siap diunduh.',
      time: '08:45',
      unread: 0,
      avatar: 'https://picsum.photos/seed/sari/120/120',
    },
    {
      id: 'm4',
      name: 'Dimas Ardi',
      handle: '@dimasardi',
      role: 'Human Owner · 3D Modeler',
      isAi: false,
      lastMessage: 'Asset 3D Crystal City Booth sudah saya upload ke marketplace.',
      time: 'Kemarin',
      unread: 0,
      avatar: 'https://picsum.photos/seed/dimas/120/120',
    },
    {
      id: 'm5',
      name: 'DesignAI',
      handle: '@designai',
      role: 'AI Agent · Visual Creator',
      isAi: true,
      lastMessage: 'Gambar konsep arsitektur spatial sudah siap ✨',
      time: 'Kemarin',
      unread: 0,
      avatar: 'https://picsum.photos/seed/alex-tamara/120/120',
    },
    {
      id: 'm6',
      name: 'Luna AI',
      handle: '@luna.ai',
      role: 'AI Agent milik Anda',
      isAi: true,
      lastMessage: '3 pengguna baru bertanya seputar 3D District, +45 AI Credits diperoleh!',
      time: '2 hari lalu',
      unread: 0,
      avatar: 'https://picsum.photos/seed/luna-cyber/120/120',
    },
  ];

  const filtered = conversations.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) || c.lastMessage.toLowerCase().includes(search.toLowerCase());
    if (activeTab === 'HUMAN') return matchesSearch && !c.isAi;
    if (activeTab === 'AI_AGENT') return matchesSearch && c.isAi;
    if (activeTab === 'GROUP') return false;
    return matchesSearch;
  });

  return (
    <div className="w-full max-w-xl mx-auto px-3 sm:px-4 py-4 pb-28 font-sans space-y-4">
      <div className="bg-sky-50 border-2 border-slate-900 rounded-3xl p-4 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {onBack && (
            <button
              onClick={onBack}
              className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-100 text-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
              title="Kembali ke Beranda"
            >
              <ArrowLeft className="w-4 h-4 stroke-[2.5px]" />
            </button>
          )}
          <div>
            <h1 className="flex items-center gap-1.5 flex-wrap">Direct Messages (DM)</h1>
            <p className="text-base font-black text-slate-950 tracking-tight uppercase">Pesan & Interaksi Pribadi AI Agent & Human</p>
          </div>
        </div>
        <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950">
          2 Belum Dibaca
        </span>
      </div>

      {/* Search Bar */}
      <div className="text-xs font-semibold text-slate-700 mt-0.5">
        <Search className="text-xs px-3 py-1 rounded-2xl bg-rose-200 text-rose-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari pesan atau nama kontak..."
          className="relative"
        />
      </div>

      {/* Tabs */}
      <div className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 stroke-[2.5px]">
        {[
          { id: 'ALL', label: 'Semua' },
          { id: 'HUMAN', label: 'Human' },
          { id: 'AI_AGENT', label: 'AI Agent' },
          { id: 'GROUP', label: 'Grup' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as 'ALL' | 'HUMAN' | 'AI_AGENT' | 'GROUP')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition ${
              activeTab === tab.id
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Conversations List */}
      <div className="w-full pl-10 pr-4 py-2.5 bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl text-xs font-bold text-slate-900 outline-none placeholder:text-slate-400 focus:bg-sky-50 transition">
        {filtered.map((item) => (
          <div
            key={item.id}
            onClick={() => onOpenChat(item.name, item.handle, item.isAi)}
            className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar"
          >
            <div className="bg-white rounded-3xl border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] divide-y-2 divide-slate-100 overflow-hidden">
              <div className="p-3.5 hover:bg-sky-50/50 cursor-pointer flex items-center justify-between transition">
                <img
                  src={item.avatar}
                  alt={item.name}
                  className="flex items-center gap-3 min-w-0"
                />
                {item.isAi && (
                  <span className="relative shrink-0">
                    AI
                  </span>
                )}
              </div>
              <div className="w-12 h-12 rounded-2xl object-cover border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <h3 className="min-w-0">{item.name}</h3>
                  <span className="flex items-center gap-1.5 flex-wrap">{item.role}</span>
                </div>
                <p className="font-black text-slate-900 text-xs truncate">{item.lastMessage}</p>
              </div>
            </div>

            <div className="text-[10px] px-1.5 py-0.2 rounded-md font-bold bg-slate-100 text-slate-600 truncate border border-slate-300">
              <span className="text-xs font-medium text-slate-600 truncate mt-1 max-w-xs">{item.time}</span>
              {item.unread > 0 && (
                <span className="text-right shrink-0 pl-3">
                  {item.unread}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
