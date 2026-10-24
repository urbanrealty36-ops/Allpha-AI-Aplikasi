'use client';

import React from 'react';
import { 
  Home, 
  Compass, 
  PlusCircle, 
  Radio, 
  Box, 
  MessageSquare, 
  User, 
  Coins,
  Film
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
}

export default function BottomNav({
  activeTab,
  setActiveTab,
  onOpenCreateModal,
}: BottomNavProps) {
  // Hide global bottom nav in 3D world or dedicated input views
  if (activeTab === 'WORLD3D' || activeTab === 'POST_DETAIL' || activeTab === 'ASK_AI_VIEW') {
    return null;
  }

  interface NavItem {
    id: TabType;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    isAction?: boolean;
    highlight?: boolean;
    badge?: string;
  }

  const navItems: NavItem[] = [
    { id: 'FEED', label: 'Beranda', icon: Home },
    { id: 'FILM_AI', label: 'Film AI', icon: Film, badge: 'VIP' },
    { id: 'CREATE', label: 'Tambah', icon: PlusCircle, isAction: true },
    { id: 'WORLD3D', label: 'Dunia 3D', icon: Box, highlight: true },
    { id: 'EXPLORE', label: 'Allpha Hub', icon: Compass },
    { id: 'PROFILE', label: 'My Agent', icon: User },
  ];

  const isReels = activeTab === 'REELS';

  return (
    <nav className={`fixed bottom-0 left-0 right-0 z-40 transition-colors duration-300 ${
      isReels
        ? 'bg-black/80 backdrop-blur-lg border-t border-white/10'
        : 'bg-white/95 backdrop-blur border-t border-slate-200'
    }`}>
      <div className="max-w-xl mx-auto px-2 h-16 flex items-center justify-around">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          if (item.isAction) {
            return (
              <button
                key={item.id}
                onClick={onOpenCreateModal}
                className="flex flex-col items-center justify-center p-1 text-blue-600 hover:text-blue-700 transition"
              >
                <div className="w-10 h-10 rounded-full bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center shadow-md shadow-blue-500/25">
                  <Icon className="w-5 h-5" />
                </div>
              </button>
            );
          }

          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`relative flex flex-col items-center justify-center py-1 px-2 rounded-xl transition ${
                isActive
                  ? isReels ? 'text-cyan-400 font-bold' : 'text-blue-600 font-bold'
                  : isReels ? 'text-white/60 hover:text-white' : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <div className="relative">
                <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5px]' : 'stroke-[1.8px]'}`} />
                {item.badge && (
                  <span className="absolute -top-1.5 -right-3.5 px-1 py-0.2 rounded-full bg-rose-500 text-white text-[8px] font-bold uppercase tracking-tight animate-pulse">
                    {item.badge}
                  </span>
                )}
                {item.highlight && (
                  <span className="absolute -top-1.5 -right-2 px-1 py-0.2 rounded-full bg-cyan-600 text-white text-[8px] font-bold uppercase">
                    3D
                  </span>
                )}
              </div>
              <span className="text-[10px] mt-0.5 tracking-tight truncate max-w-[62px]">
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
