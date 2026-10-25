'use client';

import React from 'react';
import {
  Home,
  Compass,
  Plus,
  Box,
  Film,
  UserRound,
} from 'lucide-react';

export type TabType =
  | 'FEED'
  | 'EXPLORE'
  | 'CREATE'
  | 'LIVESTAGE'
  | 'WORLD3D'
  | 'MESSAGES'
  | 'REELS'
  | 'SKILLS_CREDITS'
  | 'MARKETPLACE'
  | 'PROFILE'
  | 'POST_DETAIL'
  | 'TAKEOVER_CONTROL'
  | 'ASK_AI_VIEW'
  | 'FILM_AI';

interface BottomNavProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  onOpenCreateModal: () => void;
  unreadCount?: number;
}

export default function BottomNav({
  activeTab,
  setActiveTab,
  onOpenCreateModal,
}: BottomNavProps) {
  // Keep the source reference's detail-view navigation behavior.
  if (activeTab === 'POST_DETAIL' || activeTab === 'ASK_AI_VIEW') {
    return null;
  }

  const isReels = activeTab === 'REELS';

  return (
    <nav
      aria-label="Navigasi utama"
      className={`fixed bottom-0 left-0 right-0 z-40 transition-colors duration-200 ${
        isReels
          ? 'bg-black/90 backdrop-blur-lg border-t-2 border-slate-800'
          : 'bg-white border-t-2 border-slate-900 shadow-[0_-3px_15px_rgba(0,0,0,0.06)]'
      }`}
    >
      <div className="max-w-xl mx-auto px-3 h-17 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setActiveTab('FEED')}
          aria-current={activeTab === 'FEED' ? 'page' : undefined}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer ${
            activeTab === 'FEED' ? 'text-[#0284C7]' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Home className={`w-5.5 h-5.5 ${activeTab === 'FEED' ? 'fill-[#0284C7] stroke-[#0284C7]' : 'stroke-[2.2px]'}`} />
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'FEED' ? 'font-black' : 'font-semibold'}`}>Beranda</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('FILM_AI')}
          aria-current={activeTab === 'FILM_AI' ? 'page' : undefined}
          className={`flex flex-col items-center justify-center flex-1 py-1 relative transition cursor-pointer ${
            activeTab === 'FILM_AI' ? 'text-[#0284C7]' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <div className="relative">
            <Film className={`w-5.5 h-5.5 ${activeTab === 'FILM_AI' ? 'fill-blue-100 stroke-[#0284C7]' : 'stroke-[2.2px]'}`} />
            <span className="absolute -top-1.5 -right-3.5 px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[8px] font-black uppercase tracking-wider shadow-2xs">NEW</span>
          </div>
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'FILM_AI' ? 'font-black' : 'font-semibold'}`}>Film AI</span>
        </button>

        <div className="flex flex-col items-center justify-center flex-1 px-1">
          <button
            type="button"
            onClick={onOpenCreateModal}
            className="w-12 h-9 rounded-2xl bg-gradient-to-tr from-rose-500 via-pink-500 to-rose-500 hover:from-rose-600 hover:to-pink-600 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Buat Postingan, Generate AI, atau Live Stage"
            aria-label="Buat Konten"
          >
            <Plus className="w-5.5 h-5.5 stroke-[3px]" />
          </button>
          <span className="text-[10px] font-black text-slate-800 mt-0.5">Buat</span>
        </div>

        <button
          type="button"
          onClick={() => setActiveTab('WORLD3D')}
          aria-current={activeTab === 'WORLD3D' ? 'page' : undefined}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer ${
            activeTab === 'WORLD3D' ? 'text-[#0284C7]' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Box className={`w-5.5 h-5.5 ${activeTab === 'WORLD3D' ? 'fill-blue-100 stroke-[#0284C7]' : 'stroke-[2.2px]'}`} />
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'WORLD3D' ? 'font-black' : 'font-semibold'}`}>Dunia 3D</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('EXPLORE')}
          aria-current={activeTab === 'EXPLORE' ? 'page' : undefined}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer ${
            activeTab === 'EXPLORE' ? 'text-[#0284C7]' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Compass className={`w-5.5 h-5.5 ${activeTab === 'EXPLORE' ? 'stroke-[#0284C7] stroke-[2.6px]' : 'stroke-[2.2px]'}`} />
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'EXPLORE' ? 'font-black' : 'font-semibold'}`}>Allpha Hub</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('PROFILE')}
          aria-current={activeTab === 'PROFILE' ? 'page' : undefined}
          title="Profil Pengguna & AI Agent"
          className={`flex flex-col items-center justify-center flex-1 py-1 relative transition cursor-pointer ${
            activeTab === 'PROFILE' ? 'text-[#0284C7]' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <span className={`w-6 h-6 rounded-full overflow-hidden border-2 transition grid place-items-center bg-slate-50 ${
            activeTab === 'PROFILE' ? 'border-[#0284C7] ring-2 ring-sky-200' : 'border-slate-900'
          }`}>
            <UserRound className="h-4 w-4 text-slate-700" aria-hidden="true" />
          </span>
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'PROFILE' ? 'font-black' : 'font-semibold'}`}>Profil</span>
        </button>
      </div>
    </nav>
  );
}
