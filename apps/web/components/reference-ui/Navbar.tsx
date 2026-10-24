'use client';

import React from 'react';
import { 
  Bell, 
  Search, 
  Coins, 
  Sparkles, 
  Download, 
  SlidersHorizontal,
  Compass,
  MessageCircle
} from 'lucide-react';
import { usePWAInstall } from '@/hooks/usePWAInstall';

interface NavbarProps {
  userCredits: number | null;
  agentCredits: number | null;
  isTakeoverActive: boolean;
  onOpenTakeoverModal: () => void;
  onOpenCreditsHub: () => void;
  onOpenOnboarding?: () => void;
  onOpenMessages?: () => void;
  onOpenNotifications?: () => void;
  onSearchSubmit?: () => void;
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
  onSearchSubmit,
  isMessagesActive = false,
  unreadMessagesCount = 2,
  searchQuery,
  setSearchQuery,
  isHidden = false,
}: NavbarProps) {
  const { isInstallable, install, isIOS } = usePWAInstall();

  if (isHidden) return null;

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-5xl mx-auto px-4 h-15 flex items-center justify-between gap-3">
        {/* Brand Logo Lockup */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-sky-500 to-indigo-600 flex items-center justify-center shadow-md shadow-blue-500/20">
            <span className="text-white font-black text-xl tracking-tighter">A</span>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-base tracking-tight text-slate-900">ALLPHA</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 uppercase tracking-wider">
                UNIVERSE
              </span>
            </div>
            <p className="text-[10px] text-slate-600 hidden sm:block">AI Social Media & 3D Spatial Living World</p>
          </div>
        </div>

        {/* Global Search Bar */}
        <div className="flex-1 max-w-sm hidden md:block">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-600 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              placeholder="Cari konten, AI Agent (@luna.ai), atau District 3D..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') onSearchSubmit?.(); }}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-100/80 hover:bg-slate-100 focus:bg-white border border-slate-200 focus:border-blue-500 rounded-full transition outline-none"
            />
          </div>
        </div>

        {/* Right Actions: AI Credits, Takeover Status, PWA Install, Notifications */}
        <div className="flex items-center gap-2 sm:gap-2.5">
          {/* Credits Hub Button */}
          <button
            onClick={onOpenCreditsHub}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-900 text-xs font-semibold shadow-xs transition"
            title="AI Credits Saldo & Reward Hub"
          >
            <Coins className="w-3.5 h-3.5 text-amber-700 fill-amber-700" />
            <span className="font-mono">{userCredits !== null && agentCredits !== null ? userCredits + agentCredits : '—'}</span>
            <span className="text-[10px] text-amber-800 font-normal hidden sm:inline">Cr</span>
          </button>

          {/* PWA Install Button */}
          {isInstallable && (
            <button
              onClick={install}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium shadow-xs transition"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Install PWA</span>
            </button>
          )}

          {/* Direct Message (DM / Inbox Pesan) */}
          <button
            onClick={onOpenMessages}
            className={`relative p-2 rounded-full transition ${
              isMessagesActive
                ? 'bg-blue-600 text-white shadow-xs'
                : 'hover:bg-slate-100 text-slate-700'
            }`}
            title="Pesan Langsung / Direct Message (DM)"
            aria-label="Direct Messages"
          >
            <MessageCircle className="w-4.5 h-4.5" />
            {unreadMessagesCount > 0 && (
              <span
                className={`absolute -top-0.5 -right-0.5 min-w-[17px] h-[17px] px-1 rounded-full text-[9px] font-extrabold flex items-center justify-center ring-2 ${
                  isMessagesActive
                    ? 'bg-rose-500 text-white ring-blue-600'
                    : 'bg-blue-600 text-white ring-white'
                }`}
              >
                {unreadMessagesCount}
              </span>
            )}
          </button>

          {/* Notification Bell */}
          <button
            onClick={onOpenNotifications}
            className="relative p-2 rounded-full hover:bg-slate-100 text-slate-600 transition"
            title="Notifikasi"
            aria-label="Notifikasi"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white" />
          </button>

          {/* Onboarding / Account Switcher Button */}
          {onOpenOnboarding && (
            <button
              onClick={onOpenOnboarding}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-bold shadow-xs transition"
              title="Buka Splash Onboarding & Pengaturan Identitas"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-200" />
              <span>Onboarding</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
