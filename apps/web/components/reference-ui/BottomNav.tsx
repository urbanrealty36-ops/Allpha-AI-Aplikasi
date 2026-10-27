'use client';

import React from 'react';
import { 
  Home, 
  Compass, 
  Plus, 
  Box, 
  Film,
  MessageSquare
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
  | 'FILM_AI'
  | 'ONBOARDING_PAGE';

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
  unreadCount,
}: BottomNavProps) {
  // Hide in detail sub-views or full-page onboarding
  if (activeTab === 'POST_DETAIL' || activeTab === 'ASK_AI_VIEW' || activeTab === 'ONBOARDING_PAGE') {
    return null;
  }

  const isReels = activeTab === 'REELS';

  return (
    <nav className={`fixed bottom-0 left-0 right-0 z-40 transition-colors duration-200 ${
      isReels
        ? 'bg-black/90 backdrop-blur-lg border-t-2 border-slate-800'
        : 'bg-white border-t-2 border-slate-900 shadow-[0_-3px_15px_rgba(0,0,0,0.06)]'
    }`}>
      <div className="max-w-xl mx-auto px-3 h-17 flex items-center justify-between">
        
        {/* 1. Beranda */}
        <button
          onClick={() => setActiveTab('FEED')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer ${
            activeTab === 'FEED'
              ? 'text-[#0284C7]'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Home className={`w-5.5 h-5.5 ${activeTab === 'FEED' ? 'fill-[#0284C7] stroke-[#0284C7]' : 'stroke-[2.2px]'}`} />
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'FEED' ? 'font-black' : 'font-semibold'}`}>
            Beranda
          </span>
        </button>

        {/* 2. Film AI with 'NEW' badge */}
        <button
          onClick={() => setActiveTab('FILM_AI')}
          className={`flex flex-col items-center justify-center flex-1 py-1 relative transition cursor-pointer ${
            activeTab === 'FILM_AI'
              ? 'text-[#0284C7]'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <div className="relative">
            <Film className={`w-5.5 h-5.5 ${activeTab === 'FILM_AI' ? 'fill-blue-100 stroke-[#0284C7]' : 'stroke-[2.2px]'}`} />
            {/* NEW Badge */}
            <span className="absolute -top-1.5 -right-3.5 px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[8px] font-black uppercase tracking-wider shadow-2xs">
              NEW
            </span>
          </div>
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'FILM_AI' ? 'font-black' : 'font-semibold'}`}>
            Film AI
          </span>
        </button>

        {/* 3. Center '+ Buat' Action Button */}
        <div className="flex flex-col items-center justify-center flex-1 px-1">
          <button
            onClick={onOpenCreateModal}
            className="w-12 h-9 rounded-2xl bg-gradient-to-tr from-rose-500 via-pink-500 to-rose-500 hover:from-rose-600 hover:to-pink-600 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            title="Buat Postingan, Generate AI, atau Live Stage"
            aria-label="Buat Konten"
          >
            <Plus className="w-5.5 h-5.5 stroke-[3px]" />
          </button>
          <span className="text-[10px] font-black text-slate-800 mt-0.5">
            Buat
          </span>
        </div>

        {/* 4. Dunia 3D */}
        <button
          onClick={() => setActiveTab('WORLD3D')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer ${
            activeTab === 'WORLD3D'
              ? 'text-[#0284C7]'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Box className={`w-5.5 h-5.5 ${activeTab === 'WORLD3D' ? 'fill-blue-100 stroke-[#0284C7]' : 'stroke-[2.2px]'}`} />
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'WORLD3D' ? 'font-black' : 'font-semibold'}`}>
            Dunia 3D
          </span>
        </button>

        {/* 5. Allpha Hub */}
        <button
          onClick={() => setActiveTab('EXPLORE')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer ${
            activeTab === 'EXPLORE'
              ? 'text-[#0284C7]'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Compass className={`w-5.5 h-5.5 ${activeTab === 'EXPLORE' ? 'stroke-[#0284C7] stroke-[2.6px]' : 'stroke-[2.2px]'}`} />
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'EXPLORE' ? 'font-black' : 'font-semibold'}`}>
            Allpha Hub
          </span>
        </button>

        {/* 6. Profil button with avatar and online indicator */}
        <button
          onClick={() => setActiveTab('PROFILE')}
          className={`flex flex-col items-center justify-center flex-1 py-1 relative transition cursor-pointer ${
            activeTab === 'PROFILE'
              ? 'text-[#0284C7]'
              : 'text-slate-600 hover:text-slate-900'
          }`}
          title="Profil Pengguna & AI Agent"
        >
          <div className="relative">
            <div className={`w-6 h-6 rounded-full overflow-hidden border-2 transition ${
              activeTab === 'PROFILE'
                ? 'border-[#0284C7] ring-2 ring-sky-200'
                : 'border-slate-900'
            }`}>
              <img
                src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80"
                alt="Profil"
                className="w-full h-full object-cover"
              />
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-500 border border-white absolute -bottom-0.5 -right-0.5" />
          </div>
          <span className={`text-[10.5px] mt-0.5 tracking-tight ${activeTab === 'PROFILE' ? 'font-black' : 'font-semibold'}`}>
            Profil
          </span>
        </button>

      </div>
    </nav>
  );
}
