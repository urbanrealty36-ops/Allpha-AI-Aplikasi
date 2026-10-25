'use client';

import React, { useState } from 'react';
import {
  Bell,
  Search,
  Bot,
  X,
  MessageCircle,
  Download,
} from 'lucide-react';
import { usePWAInstall } from '@/hooks/usePWAInstall';

interface NavbarProps {
  userCredits: number | null;
  agentCredits: number | null;
  isTakeoverActive: boolean | null;
  onOpenTakeoverModal: () => void;
  onOpenCreditsHub: () => void;
  onOpenOnboarding?: () => void;
  onOpenMessages?: () => void;
  onOpenNotifications?: () => void;
  isMessagesActive?: boolean;
  unreadMessagesCount?: number;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearch?: (query: string) => void;
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
  isMessagesActive = false,
  unreadMessagesCount = 0,
  searchQuery,
  setSearchQuery,
  onSearch,
  isHidden = false,
}: NavbarProps) {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const { isInstallable, install } = usePWAInstall();

  if (isHidden) return null;

  const submitSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchQuery.trim();
    if (query) onSearch?.(query);
  };

  return (
    <header className="sticky top-0 z-40 bg-white border-b-2 border-slate-900 shadow-xs">
      <div className="max-w-xl mx-auto px-4 h-16 flex items-center justify-between gap-2.5">
        <div className="flex items-center gap-2 cursor-pointer select-none shrink-0">
          <div className="flex flex-col">
            <div className="flex items-center tracking-tighter text-2xl font-black leading-none">
              <span className="text-[#0284C7]">ALL</span>
              <span className="text-[#0F172A]">PHA</span>
            </div>
            <span className="text-[9px] font-extrabold tracking-[0.25em] text-[#0F172A] uppercase leading-tight mt-0.5">UNIVERSE</span>
          </div>
        </div>

        {isSearchOpen && (
          <form className="flex-1 min-w-0 mx-1 relative animate-in fade-in duration-200" role="search" onSubmit={submitSearch}>
            <input
              type="search"
              autoFocus
              aria-label="Cari konten, AI Agent, atau District 3D"
              placeholder="Cari konten, agent, district 3D..."
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              className="w-full min-w-0 pl-8 pr-7 py-1.5 text-xs font-semibold bg-slate-50 border-2 border-slate-900 rounded-full outline-none shadow-[1.5px_1.5px_0px_#0f172a] focus:bg-white"
            />
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <button
              type="button"
              onClick={() => { setSearchQuery(''); setIsSearchOpen(false); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-800"
              aria-label="Tutup pencarian"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </form>
        )}

        <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
          {userCredits !== null && agentCredits !== null && (
            <button
              type="button"
              onClick={onOpenCreditsHub}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 hover:bg-amber-200 border-2 border-slate-900 text-slate-900 font-extrabold text-xs shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              title="Saldo AI Credits & Rewards Hub"
            >
              <span className="w-4 h-4 rounded-full bg-amber-400 border border-amber-600 flex items-center justify-center text-[10px] text-amber-950 font-black shadow-2xs" aria-hidden="true">🪙</span>
              <span className="font-mono tracking-tight font-black text-xs text-amber-950">{userCredits + agentCredits}</span>
            </button>
          )}

          <button
            type="button"
            onClick={onOpenTakeoverModal}
            className={`w-9 h-9 rounded-2xl border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
              isTakeoverActive ? 'bg-emerald-100 text-emerald-700' : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-600'
            }`}
            title="Kelola AI Agent & Mode Takeover"
            aria-label="AI Agent Controller"
          >
            <Bot className="w-4.5 h-4.5 stroke-[2.4px]" />
          </button>

          <button
            type="button"
            onClick={() => setIsSearchOpen(open => !open)}
            className={`w-9 h-9 rounded-2xl border-2 border-slate-900 flex items-center justify-center text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
              isSearchOpen ? 'bg-sky-100 text-sky-800' : 'bg-white hover:bg-slate-50'
            }`}
            title="Pencarian"
            aria-label="Buka pencarian"
            aria-expanded={isSearchOpen}
          >
            <Search className="w-4.5 h-4.5 stroke-[2.2px]" />
          </button>

          {isInstallable && (
            <button
              type="button"
              onClick={install}
              className="w-9 h-9 rounded-2xl bg-sky-50 hover:bg-sky-100 border-2 border-slate-900 text-sky-700 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              title="Install Allpha PWA"
              aria-label="Install PWA"
            >
              <Download className="w-4.5 h-4.5" />
            </button>
          )}

          <button
            type="button"
            onClick={onOpenNotifications}
            className="w-9 h-9 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 text-slate-900 flex items-center justify-center relative shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Notifikasi"
            aria-label="Notifikasi"
          >
            <Bell className="w-4.5 h-4.5 stroke-[2.2px]" />
          </button>

          <button
            type="button"
            onClick={onOpenMessages}
            className={`w-9 h-9 rounded-2xl border-2 border-slate-900 flex items-center justify-center relative shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer ${
              isMessagesActive ? 'bg-sky-100 text-sky-800' : 'bg-white hover:bg-slate-50 text-slate-900'
            }`}
            title="Pesan Langsung & AI Agent Chat"
            aria-label="Pesan"
          >
            <MessageCircle className="w-4.5 h-4.5 stroke-[2.2px]" />
            {unreadMessagesCount > 0 && (
              <span className="absolute -top-1 -right-1 px-1.5 py-0.2 min-w-4.5 h-4.5 rounded-full bg-rose-500 border border-white text-white text-[9px] font-black flex items-center justify-center shadow-2xs">
                {unreadMessagesCount}
              </span>
            )}
          </button>

          {onOpenOnboarding && (
            <button
              type="button"
              onClick={onOpenOnboarding}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-900 hover:bg-slate-800 border-2 border-slate-900 text-white text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition"
              title="Buka Splash Onboarding & Pengaturan Identitas"
            >
              <span>Onboarding</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
