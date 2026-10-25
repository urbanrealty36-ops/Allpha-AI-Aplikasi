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

export interface ReferenceConversation {
  id: string; name: string; handle: string; role: string; isAi: boolean;
  lastMessage: string; time: string; unread?: number; avatar?: string;
}

interface MessagesViewProps {
  onOpenChat: (name: string, handle: string, isAi: boolean) => void;
  onBack?: () => void;
  conversations?: ReferenceConversation[];
  loading?: boolean;
}

export default function MessagesView({ onOpenChat, onBack, conversations: suppliedConversations, loading = false }: MessagesViewProps) {
  const [activeTab, setActiveTab] = useState<'ALL' | 'HUMAN' | 'AI_AGENT' | 'GROUP'>('ALL');
  const [search, setSearch] = useState('');

  // Production routes provide conversations from the authenticated messaging API.
  const conversations = suppliedConversations ?? [];

  const filtered = conversations.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) || c.lastMessage.toLowerCase().includes(search.toLowerCase());
    if (activeTab === 'HUMAN') return matchesSearch && !c.isAi;
    if (activeTab === 'AI_AGENT') return matchesSearch && c.isAi;
    if (activeTab === 'GROUP') return false;
    return matchesSearch;
  });

  return (
    <div className="w-full max-w-xl mx-auto px-3 sm:px-4 py-4 pb-28 font-sans space-y-4">
      {/* Header */}
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
            <div className="flex items-center gap-1.5">
              <h1 className="text-base font-black text-slate-950 tracking-tight uppercase">Pesan Langsung (DM)</h1>
              <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950">
                INBOX
              </span>
            </div>
            <p className="text-xs font-semibold text-slate-700 mt-0.5">Percakapan Manusia & AI Agent</p>
          </div>
        </div>
        <span className="text-xs px-3 py-1 rounded-2xl bg-rose-200 text-rose-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
          {conversations.some(item => typeof item.unread === 'number') ? conversations.reduce((sum, item) => sum + (item.unread ?? 0), 0) + ' Baru' : 'INBOX'}
        </span>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 stroke-[2.5px]" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari percakapan atau nama agent..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] rounded-2xl text-xs font-bold text-slate-900 outline-none placeholder:text-slate-400 focus:bg-sky-50 transition"
        />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
        {[
          { id: 'ALL', label: 'Semua' },
          { id: 'HUMAN', label: '👤 Human' },
          { id: 'AI_AGENT', label: '🤖 AI Agent' },
          { id: 'GROUP', label: '👥 Grup' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as 'ALL' | 'HUMAN' | 'AI_AGENT' | 'GROUP')}
            className={`px-3.5 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 whitespace-nowrap cursor-pointer ${
              activeTab === tab.id
                ? 'bg-sky-300 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Conversations List */}
      <div className="bg-white rounded-3xl border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] divide-y-2 divide-slate-100 overflow-hidden">
        {loading && <p className="p-5 text-center text-xs font-bold text-slate-500">Memuat percakapan…</p>}
        {!loading && filtered.length === 0 && <p className="p-5 text-center text-xs font-bold text-slate-500">Belum ada percakapan yang cocok.</p>}
        {filtered.map((item) => (
          <div
            key={item.id}
            onClick={() => onOpenChat(item.name, item.handle, item.isAi)}
            className="p-3.5 hover:bg-sky-50/50 cursor-pointer flex items-center justify-between transition"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="relative shrink-0">
                {item.avatar ? <img src={item.avatar} alt={item.name} className="w-12 h-12 rounded-2xl object-cover border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]" /> : <div aria-label={item.name} className="w-12 h-12 rounded-2xl bg-sky-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center text-slate-900"><User className="w-5 h-5" /></div>}
                {item.isAi && (
                  <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-md bg-[#0284C7] text-white flex items-center justify-center text-[9px] font-black border border-slate-900">
                    AI
                  </span>
                )}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <h3 className="font-black text-slate-900 text-xs truncate">{item.name}</h3>
                  <span className="text-[10px] px-1.5 py-0.2 rounded-md font-bold bg-slate-100 text-slate-600 truncate border border-slate-300">
                    {item.role}
                  </span>
                </div>
                <p className="text-xs font-medium text-slate-600 truncate mt-1 max-w-xs">{item.lastMessage}</p>
              </div>
            </div>

            <div className="text-right shrink-0 pl-3">
              <span className="text-[10px] font-bold text-slate-400 block">{item.time}</span>
              {item.unread > 0 && (
                <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-rose-500 text-white font-black text-[9px] border border-slate-900 shadow-[1px_1px_0px_#0f172a]">
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
