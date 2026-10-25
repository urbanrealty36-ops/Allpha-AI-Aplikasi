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

export interface MarketplaceListing {
  id: string;
  title: string;
  category: 'AI_AGENT' | '3D_ASSET' | 'SERVICES';
  categoryLabel: string;
  priceIdr: string;
  priceCredits: number;
  likes: number;
  avatar: string;
  description: string;
}

interface MarketplaceViewProps {
  onBuyItem: (title: string, priceCredits: number) => void;
  userCredits: number | null;
  items?: MarketplaceListing[];
  catalogState?: 'ready' | 'unavailable';
}

export default function MarketplaceView({ onBuyItem, userCredits, items: propsItems = [], catalogState = 'unavailable' }: MarketplaceViewProps) {
  const [filterTab, setFilterTab] = useState<'ALL' | 'AI_AGENT' | '3D_ASSET' | 'SERVICES'>('ALL');
  const [search, setSearch] = useState('');

  // Production listings must come from the canonical Marketplace API.
  // An absent adapter intentionally renders an empty catalog, never demo commerce data.
  const items = propsItems;

  const filtered = items.filter((it) => {
    const matchesSearch = it.title.toLowerCase().includes(search.toLowerCase());
    if (filterTab === 'AI_AGENT') return matchesSearch && it.category === 'AI_AGENT';
    if (filterTab === '3D_ASSET') return matchesSearch && it.category === '3D_ASSET';
    return matchesSearch;
  });

  return (
    <div className="w-full max-w-xl mx-auto px-4 py-3 pb-24 font-sans space-y-4">
      <div className="p-4 rounded-3xl bg-amber-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-1.5">Marketplace</h1>
          <p className="text-lg font-black text-slate-900 tracking-tight">AI Agent, Aset 3D, dan Digital Fashion Crystal City</p>
        </div>
        <div className="text-[10px] font-black px-2 py-0.5 rounded-full bg-rose-200 border-2 border-slate-900 text-rose-950 uppercase">
          <Coins className="text-xs font-semibold text-slate-700 mt-0.5" />
          <span>{userCredits === null ? '—' : userCredits} Cr</span>
        </div>
      </div>

      {/* Search Input */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950 font-mono text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a]">
        <Search className="relative" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari AI Agent, 3D asset, atau layanan..."
          className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2"
        />
      </div>

      {/* Filter Tabs */}
      <div className="w-full pl-10 pr-4 py-2.5 bg-white border-2 border-slate-900 rounded-2xl text-xs font-bold text-slate-900 outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-sky-50 transition">
        {[
          { id: 'ALL', label: 'Semua' },
          { id: 'AI_AGENT', label: 'AI Agent' },
          { id: '3D_ASSET', label: '3D Asset' },
          { id: 'SERVICES', label: 'Layanan' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterTab(tab.id as 'ALL' | 'AI_AGENT' | '3D_ASSET' | 'SERVICES')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition ${
              filterTab === tab.id
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {catalogState === 'unavailable' && (
        <div role="status" className="rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600">
          Katalog Marketplace belum tersedia dari layanan kanonis. Listing dan harga akan ditampilkan setelah kontrak API Marketplace dan Booth/Tenant tersedia.
        </div>
      )}

      {/* Grid of Marketplace Items */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="grid grid-cols-1 sm:grid-cols-2 gap-3.5"
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
              <button
                onClick={() => alert(`Menyukai ${item.title}`)}
                className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full bg-slate-900/80 border border-slate-700 text-white text-[10px] font-bold flex items-center gap-1"
              >
                <Heart className="w-3 h-3 text-rose-400 fill-rose-400" />
              </button>
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
                    {item.priceCredits} AI Credits
                  </span>
                </div>
                <button
                  onClick={() => onBuyItem(item.title, item.priceCredits)}
                  className="px-3.5 py-1.5 rounded-2xl bg-sky-400 hover:bg-sky-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  Beli
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
