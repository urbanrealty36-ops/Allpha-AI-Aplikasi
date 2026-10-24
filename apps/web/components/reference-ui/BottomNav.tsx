"use client";

import { Compass, Home, MessageCircle, PlusCircle, UserRound } from "lucide-react";

export type TabType =
  | "FEED" | "EXPLORE" | "CREATE" | "LIVESTAGE" | "WORLD3D" | "MESSAGES"
  | "REELS" | "SKILLS_CREDITS" | "MARKETPLACE" | "PROFILE" | "POST_DETAIL"
  | "TAKEOVER_CONTROL" | "ASK_AI_VIEW" | "FILM_AI";

interface BottomNavProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  onOpenCreateModal: () => void;
}

const items = [
  { id: "FEED", label: "Beranda", icon: Home },
  { id: "EXPLORE", label: "Explore", icon: Compass },
  { id: "CREATE", label: "Buat", icon: PlusCircle, action: true },
  { id: "MESSAGES", label: "Pesan", icon: MessageCircle },
  { id: "PROFILE", label: "My Agent", icon: UserRound },
] as const;

export default function BottomNav({ activeTab, setActiveTab, onOpenCreateModal }: BottomNavProps) {
  if (activeTab === "WORLD3D" || activeTab === "POST_DETAIL" || activeTab === "ASK_AI_VIEW") return null;
  const activeId = activeTab === "REELS" ? "FEED" : activeTab === "FILM_AI" || activeTab === "LIVESTAGE" || activeTab === "MARKETPLACE" || activeTab === "SKILLS_CREDITS" ? "EXPLORE" : activeTab;

  return (
    <nav aria-label="Navigasi utama" className={`fixed inset-x-0 bottom-0 z-40 border-t backdrop-blur-xl ${activeTab === "REELS" ? "border-white/10 bg-slate-950/95 text-white" : "border-slate-200 bg-white/95 text-slate-700"}`}>
      <div className="mx-auto grid h-16 max-w-xl grid-cols-5 items-center px-2 pb-[env(safe-area-inset-bottom)]">
        {items.map(item => {
          const Icon = item.icon;
          const selected = activeId === item.id;
          if ("action" in item && item.action) return (
            <button key={item.id} type="button" aria-label="Buat konten" onClick={onOpenCreateModal} className="mx-auto flex min-h-12 min-w-12 items-center justify-center rounded-2xl bg-blue-700 text-white shadow-sm transition hover:bg-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500">
              <Icon size={23} strokeWidth={2.4}/>
            </button>
          );
          return (
            <button key={item.id} type="button" aria-label={item.label} aria-current={selected ? "page" : undefined} onClick={() => setActiveTab(item.id)} className={`flex min-h-12 min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-1 py-1 text-[9px] font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-500 ${selected ? (activeTab === "REELS" ? "text-cyan-300" : "text-blue-700") : (activeTab === "REELS" ? "text-white/65 hover:text-white" : "text-slate-500 hover:text-slate-900")}`}>
              <Icon size={20} strokeWidth={selected ? 2.5 : 1.8}/>
              <span className="whitespace-nowrap">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
