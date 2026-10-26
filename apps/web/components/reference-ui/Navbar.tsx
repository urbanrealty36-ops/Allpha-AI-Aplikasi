'use client';

import React, { useState } from 'react';
import { 
  Bell, 
  Search, 
  Coins, 
  Bot,
  X,
  MessageCircle,
  Store
} from 'lucide-react';

interface NavbarProps {
  userCredits: number | null;
  agentCredits: number | null;
  isTakeoverActive: boolean | null;
  onOpenTakeoverModal: () => void;
  onOpenCreditsHub: () => void;
  onOpenOnboarding?: () => void;
  onOpenMessages?: () => void;
  onOpenNotifications?: () => void;
  onOpenStore?: () => void;
  onSearch?: (query: string) => void;
  isMessagesActive?: boolean;
  unreadMessagesCount?: number;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  isHidden?: boolean;
}

export default function Navbar({
  userCredits,
  agentCredits,
  isTakeoverActive,
  onOpenTakeoverModal,
  onOpenCreditsHub,
  onOpenOnboarding,
  onOpenMessages,
  onOpenNotifications,
  onOpenStore,
  onSearch,
  isMessagesActive = false,
  unreadMessagesCount,
  searchQuery,
  setSearchQuery,
  isHidden = false,
}: NavbarProps) {
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  if (isHidden) return null;

  return (
    <header className="sticky top-0 z-40 bg-white border-b-2 border-slate-900 shadow-xs">
      <div className="max-w-xl mx-auto px-4 h-16 flex items-center justify-between gap-2.5">
        
        {/* Brand Logo Lockup matching the reference design */}
        <a href="/login" aria-label="ALLPHA UNIVERSE — buka halaman onboarding, login, dan register" className="flex items-center gap-2 cursor-pointer select-none no-underline">
          <div className="flex flex-col">
            <div className="flex items-center tracking-tighter text-2xl font-black leading-none">
              <span className="text-[#0284C7]">ALL</span>
              <span className="text-[#0F172A]">PHA</span>
            </div>
            <span className="text-[9px] font-extrabold tracking-[0.25em] text-[#0F172A] uppercase leading-tight mt-0.5">
              UNIVERSE
            </span>
          </div>
        </a>

        {/* Expandable Search Input (if active) */}
        {isSearchOpen && (
          <div className="flex-1 mx-1 relative animate-in fade-in duration-200">
            <input
              type="text"
              autoFocus
              placeholder="Cari konten, agent, district 3D..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") onSearch?.(searchQuery.trim()); }}
              className="w-full pl-8 pr-7 py-1.5 text-xs font-semibold bg-slate-50 border-2 border-slate-900 rounded-full outline-none shadow-[1.5px_1.5px_0px_#0f172a] focus:bg-white"
            />
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <button
              onClick={() => {
                setSearchQuery('');
                setIsSearchOpen(false);
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-800"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Right Action Icons matching reference image */}
        <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
          
          {/* 1. Coin Pill Badge: (🪙 730) */}
          <button
            onClick={onOpenCreditsHub}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 hover:bg-amber-200 border-2 border-slate-900 text-slate-900 font-extrabold text-xs shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Saldo AI Credits & Rewards Hub"
          >
            <div className="w-4 h-4 rounded-full bg-amber-400 border border-amber-600 flex items-center justify-center text-[10px] text-amber-950 font-black shadow-2xs">
              🪙
            </div>
            <span className="font-mono tracking-tight font-black text-xs text-amber-950">
              {typeof userCredits === 'number' && typeof agentCredits === 'number' ? userCredits + agentCredits : '—'}
            </span>
          </button>

          {/* 2. Robot / AI Agent Icon Button */}
          <button
            onClick={onOpenTakeoverModal}
            className="w-9 h-9 rounded-2xl bg-emerald-50 hover:bg-emerald-100 border-2 border-slate-900 text-emerald-600 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Kelola AI Agent & Mode Takeover"
            aria-label="AI Agent Controller"
          >
            <Bot className="w-4.5 h-4.5 stroke-[2.4px]" />
          </button>

          {/* Reference shortcut: Marketplace & 3D Booths */}
          <button
            onClick={onOpenStore}
            className="w-9 h-9 rounded-2xl bg-emerald-50 hover:bg-emerald-100 border-2 border-slate-900 text-emerald-800 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Marketplace & Booth 3D"
            aria-label="Marketplace dan Booth 3D"
          >
            <Store className="w-4.5 h-4.5 stroke-[2.4px]" />
          </button>

          {/* 3. Search Icon Button */}
          <button
            onClick={() => setIsSearchOpen(!isSearchOpen)}
            className={`w-9 h-9 rounded-2xl border-2 border-slate-900 flex items-center justify-center text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
              isSearchOpen ? 'bg-sky-100 text-sky-800' : 'bg-white hover:bg-slate-50'
            }`}
            title="Pencarian"
            aria-label="Search"
          >
            <Search className="w-4.5 h-4.5 stroke-[2.2px]" />
          </button>

          {/* 4. Notification Bell with red dot */}
          <button
            onClick={() => {
              onOpenNotifications?.();
            }}
            className="w-9 h-9 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 text-slate-900 flex items-center justify-center relative shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Notifikasi & Pesan"
            aria-label="Notifications"
          >
            <Bell className="w-4.5 h-4.5 stroke-[2.2px]" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-rose-500 border border-white" />
          </button>

          {/* 5. Pesan / Messages Icon Button (Replaced from Bottom Nav to Top Header) */}
          <button
            onClick={onOpenMessages}
            className={`w-9 h-9 rounded-2xl border-2 border-slate-900 flex items-center justify-center relative shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
              isMessagesActive ? 'bg-sky-100 text-sky-800' : 'bg-white hover:bg-slate-50 text-slate-900'
            }`}
            title="Pesan Langsung & AI Agent Chat"
            aria-label="Pesan"
          >
            <MessageCircle className="w-4.5 h-4.5 stroke-[2.2px]" />
            {typeof unreadMessagesCount === "number" && unreadMessagesCount > 0 && (
              <span className="absolute -top-1 -right-1 px-1.5 py-0.2 min-w-4.5 h-4.5 rounded-full bg-rose-500 border border-white text-white text-[9px] font-black flex items-center justify-center shadow-2xs">
                {unreadMessagesCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
