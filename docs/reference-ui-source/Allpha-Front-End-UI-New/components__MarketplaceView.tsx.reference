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

interface MarketplaceViewProps {
  onBuyItem: (title: string, priceCredits: number) => void;
  userCredits: number;
}

export default function MarketplaceView({ onBuyItem, userCredits }: MarketplaceViewProps) {
  const [filterTab, setFilterTab] = useState<'ALL' | 'AI_AGENT' | '3D_ASSET' | 'SERVICES'>('ALL');
  const [search, setSearch] = useState('');

  const items = [
    {
      id: 'it-1',
      title: 'Crystal City Pack',
      category: '3D_ASSET',
      categoryLabel: '3D Asset',
      priceIdr: 'Rp 250.000',
      priceCredits: 50,
      likes: 1240,
      avatar: 'https://picsum.photos/seed/crystal-pack/300/200',
      description: 'Paket modular bangunan pencakar langit, skywalk, dan neon billboards Three.js.',
    },
    {
      id: 'it-2',
      title: 'AI Character Pack',
      category: 'AI_AGENT',
      categoryLabel: 'AI Agent',
      priceIdr: 'Rp 350.000',
      priceCredits: 70,
      likes: 980,
      avatar: 'https://picsum.photos/seed/luna-cyber/300/200',
      description: 'Rig avatar 3D cybernetic lengkap dengan 12 animasi emote dan voice sync.',
    },
    {
      id: 'it-3',
      title: 'Futuristic Building V2',
      category: '3D_ASSET',
      categoryLabel: '3D Asset',
      priceIdr: 'Rp 150.000',
      priceCredits: 30,
      likes: 670,
      avatar: 'https://picsum.photos/seed/building-pack/300/200',
      description: 'Model gedung pencakar langit dengan material PBR kaca dan pantulan real-time.',
    },
    {
      id: 'it-4',
      title: 'Space Vehicle Speeder',
      category: '3D_ASSET',
      categoryLabel: '3D Asset',
      priceIdr: 'Rp 200.000',
      priceCredits: 40,
      likes: 856,
      avatar: 'https://picsum.photos/seed/vehicle-pack/300/200',
      description: 'Kendaraan masa depan melayang dengan lampu neon ground underglow.',
    },
    {
      id: 'it-5',
      title: 'Marketing AI Pro Agent',
      category: 'AI_AGENT',
      categoryLabel: 'AI Agent',
      priceIdr: 'Rp 300.000 / bln',
      priceCredits: 60,
      likes: 1540,
      avatar: 'https://picsum.photos/seed/marketing-ai/300/200',
      description: 'AI Agent otomatis untuk menyusun strategi reels dan campaign brand 2026.',
    },
    {
      id: 'it-6',
      title: 'Design AI Spatial Assistant',
      category: 'AI_AGENT',
      categoryLabel: 'AI Agent',
      priceIdr: 'Rp 250.000 / bln',
      priceCredits: 50,
      likes: 890,
      avatar: 'https://picsum.photos/seed/design-ai/300/200',
      description: 'AI Companion untuk 3D modeling, shader tuning, dan render stage lighting.',
    },
  ];

  const filtered = items.filter((it) => {
    const matchesSearch = it.title.toLowerCase().includes(search.toLowerCase());
    if (filterTab === 'AI_AGENT') return matchesSearch && it.category === 'AI_AGENT';
    if (filterTab === '3D_ASSET') return matchesSearch && it.category === '3D_ASSET';
    return matchesSearch;
  });

  return (
    <div className="w-full max-w-xl mx-auto px-4 py-4 pb-24 font-sans space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-black text-slate-900 tracking-tight">Marketplace</h1>
          <p className="text-xs text-slate-600">AI Agent, Aset 3D, dan Digital Fashion Crystal City</p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-900 font-mono text-xs font-bold">
          <Coins className="w-3.5 h-3.5 text-amber-700 fill-amber-700" />
          <span>{userCredits} Cr</span>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari AI Agent, 3D asset, atau layanan..."
          className="w-full pl-10 pr-4 py-2 bg-slate-100 border border-slate-200 rounded-full text-xs text-slate-900 outline-none focus:bg-white focus:border-blue-500"
        />
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
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

      {/* Grid of Marketplace Items */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="rounded-3xl bg-white border border-slate-200 shadow-sm overflow-hidden flex flex-col justify-between hover:border-blue-400 hover:shadow-md transition"
          >
            <div className="relative h-36 bg-slate-950 overflow-hidden">
              <img
                src={item.avatar}
                alt={item.title}
                className="w-full h-full object-cover"
              />
              <span className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full bg-slate-900/80 text-white text-[10px] font-bold">
                {item.categoryLabel}
              </span>
              <button
                onClick={() => alert(`Menyukai ${item.title}`)}
                className="absolute top-2.5 right-2.5 p-1.5 rounded-full bg-black/40 text-white hover:bg-black/60 transition"
              >
                <Heart className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="font-bold text-slate-900 text-xs">{item.title}</h3>
                <p className="text-[11px] text-slate-600 line-clamp-2 mt-0.5">{item.description}</p>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="font-bold text-blue-700 text-xs">{item.priceIdr}</span>
                  <span className="block text-[10px] text-amber-700 font-mono font-semibold">
                    {item.priceCredits} AI Credits
                  </span>
                </div>
                <button
                  onClick={() => onBuyItem(item.title, item.priceCredits)}
                  className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs transition shadow-xs"
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
