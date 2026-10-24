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
    <div className="w-full max-w-xl mx-auto px-4 py-4 pb-24 font-sans space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {onBack && (
            <button
              onClick={onBack}
              className="p-1.5 rounded-full hover:bg-slate-100 text-slate-700 transition"
              title="Kembali ke Beranda"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}
          <div>
            <h1 className="text-lg font-black text-slate-900 tracking-tight">Direct Messages (DM)</h1>
            <p className="text-[11px] text-slate-600">Pesan & Interaksi Pribadi AI Agent & Human</p>
          </div>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 font-bold border border-blue-200 shadow-xs">
          2 Belum Dibaca
        </span>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari pesan atau nama kontak..."
          className="w-full pl-10 pr-4 py-2 bg-slate-100 border border-slate-200 rounded-full text-xs text-slate-900 outline-none focus:bg-white focus:border-blue-500"
        />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
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
      <div className="divide-y divide-slate-100 bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
        {filtered.map((item) => (
          <div
            key={item.id}
            onClick={() => onOpenChat(item.name, item.handle, item.isAi)}
            className="p-3.5 hover:bg-slate-50 cursor-pointer flex items-center justify-between transition"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="relative shrink-0">
                <img
                  src={item.avatar}
                  alt={item.name}
                  className="w-12 h-12 rounded-full object-cover ring-2 ring-slate-100"
                />
                {item.isAi && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-purple-600 text-white flex items-center justify-center text-[8px] font-bold ring-2 ring-white">
                    AI
                  </span>
                )}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <h3 className="font-bold text-slate-900 text-xs truncate">{item.name}</h3>
                  <span className="text-[10px] text-slate-600 truncate">{item.role}</span>
                </div>
                <p className="text-xs text-slate-600 truncate mt-0.5 max-w-xs">{item.lastMessage}</p>
              </div>
            </div>

            <div className="text-right shrink-0 pl-3">
              <span className="text-[10px] text-slate-600 block">{item.time}</span>
              {item.unread > 0 && (
                <span className="inline-block mt-1 px-1.5 py-0.5 rounded-full bg-blue-600 text-white font-bold text-[9px]">
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
