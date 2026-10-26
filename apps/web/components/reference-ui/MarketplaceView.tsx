'use client';

import React, { useState } from 'react';
import { 
  Search, 
  ShoppingBag, 
  Heart, 
  Coins, 
  Sparkles, 
  Box, 
  Bot, 
  CheckCircle2, 
  Filter 
} from 'lucide-react';

type MarketplaceItem = { id: string; title: string; category: 'AI_AGENT' | '3D_ASSET' | 'SERVICES'; categoryLabel: string; priceIdr: string; priceCredits: number; likes: number; avatar: string; description: string };

interface MarketplaceViewProps {
  onBuyItem: (title: string, priceCredits: number) => void;
  userCredits: number | null;
  catalogItems?: MarketplaceItem[];
  catalogState?: 'loading' | 'ready' | 'unavailable';
  productionMode?: boolean;
  purchaseAvailable?: boolean;
}

export default function MarketplaceView({ onBuyItem, userCredits, catalogItems, catalogState = 'ready', productionMode = false, purchaseAvailable = true }: MarketplaceViewProps) {
  const [filterTab, setFilterTab] = useState<'ALL' | 'AI_AGENT' | '3D_ASSET' | 'SERVICES'>('ALL');
  const [search, setSearch] = useState('');

  // Production and preview both render only catalog records supplied by the API adapter.
  const items = catalogItems ?? [];

  const filtered = items.filter((it) => {
    const matchesSearch = it.title.toLowerCase().includes(search.toLowerCase());
    if (filterTab === 'AI_AGENT') return matchesSearch && it.category === 'AI_AGENT';
    if (filterTab === '3D_ASSET') return matchesSearch && it.category === '3D_ASSET';
    return matchesSearch;
  });

  return (
    <div className="w-full max-w-xl mx-auto px-4 py-3 pb-24 font-sans space-y-4">
      {/* Neo-brutalist Header */}
      <div className="p-4 rounded-3xl bg-amber-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <h1 className="text-lg font-black text-slate-900 tracking-tight">Marketplace 3D & AI</h1>
            <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-rose-200 border-2 border-slate-900 text-rose-950 uppercase">
              STORE
            </span>
          </div>
          <p className="text-xs font-semibold text-slate-700 mt-0.5">AI Agent, Aset 3D Spatial, dan Digital Fashion</p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950 font-mono text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a]">
          <span>🪙</span>
          <span>{userCredits == null ? '—' : `${userCredits} Cr`}</span>
        </div>
      </div>

      {/* Neo-brutalist Search Bar */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari AI Agent, 3D asset, atau layanan..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border-2 border-slate-900 rounded-2xl text-xs font-bold text-slate-900 outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-sky-50 transition"
        />
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
        {[
          { id: 'ALL', label: 'Semua Item' },
          { id: 'AI_AGENT', label: '🤖 AI Agent' },
          { id: '3D_ASSET', label: '📦 3D Asset' },
          { id: 'SERVICES', label: '⚡ Layanan' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterTab(tab.id as 'ALL' | 'AI_AGENT' | '3D_ASSET' | 'SERVICES')}
            className={`px-3.5 py-1.5 rounded-2xl text-xs font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 whitespace-nowrap cursor-pointer ${
              filterTab === tab.id
                ? 'bg-sky-300 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Grid of Marketplace Items */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {filtered.length === 0 && <div role="status" className="col-span-full rounded-3xl border-2 border-dashed border-slate-300 bg-white p-6 text-center text-sm font-bold text-slate-600">{catalogState === 'loading' ? 'Memuat Marketplace…' : catalogState === 'unavailable' ? 'Katalog Marketplace belum tersedia dari layanan produksi.' : 'Belum ada item Marketplace yang dipublikasikan.'}</div>}
        {filtered.map((item, idx) => {
          const bgColors = ['bg-sky-50', 'bg-emerald-50', 'bg-amber-50', 'bg-purple-50', 'bg-rose-50', 'bg-blue-50'];
          const cardBg = bgColors[idx % bgColors.length];

          return (
            <div
              key={item.id}
              className={`rounded-3xl ${cardBg} border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] overflow-hidden flex flex-col justify-between transition hover:-translate-y-0.5`}
            >
              <div className="relative h-40 bg-slate-950 overflow-hidden border-b-2 border-slate-900">
                <img
                  src={item.avatar}
                  alt={item.title}
                  className="w-full h-full object-cover"
                />
                <span className="absolute top-2.5 left-2.5 px-2.5 py-1 rounded-full bg-white/95 border-2 border-slate-900 text-slate-950 text-[10px] font-black shadow-[1.5px_1.5px_0px_#0f172a]">
                  {item.categoryLabel}
                </span>
                <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full bg-slate-900/80 border border-slate-700 text-white text-[10px] font-bold flex items-center gap-1">
                  <Heart className="w-3 h-3 text-rose-400 fill-rose-400" />
                  <span>{item.likes}</span>
                </div>
              </div>

              <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
                <div>
                  <h3 className="font-black text-slate-900 text-xs sm:text-sm">{item.title}</h3>
                  <p className="text-[11px] font-medium text-slate-700 line-clamp-2 mt-0.5 leading-snug">{item.description}</p>
                </div>

                <div className="pt-2.5 border-t-2 border-slate-900/20 flex items-center justify-between gap-2">
                  <div>
                    <span className="font-black text-slate-900 text-xs block">{item.priceIdr}</span>
                    <span className="text-[10.5px] text-amber-900 font-mono font-black flex items-center gap-1">
                      🪙 {item.priceCredits} Cr
                    </span>
                  </div>
                  <button
                    onClick={() => onBuyItem(item.title, item.priceCredits)}
              disabled={!purchaseAvailable || (productionMode && userCredits == null)}
                    className="px-3.5 py-1.5 rounded-2xl bg-sky-400 hover:bg-sky-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                  >
                    Beli Item
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
