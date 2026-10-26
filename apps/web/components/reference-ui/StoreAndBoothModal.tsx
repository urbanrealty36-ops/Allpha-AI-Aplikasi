'use client';

import React, { useState } from 'react';
import { 
  ShoppingBag, 
  Box, 
  Sparkles, 
  X, 
  CheckCircle2, 
  Layers, 
  Store, 
  Palette, 
  MapPin, 
  Upload, 
  Coins, 
  Plus, 
  Truck, 
  QrCode, 
  ShieldCheck, 
  Eye, 
  Radio, 
  ExternalLink,
  DollarSign,
  ArrowRight,
  TrendingUp,
  Sliders,
  Bot,
  Zap,
  Image as ImageIcon
} from 'lucide-react';
import type { AIAgentProfile, HumanProfile } from '@/lib/reference-store';

export interface StoreProduct {
  id: string;
  name: string;
  type: 'DIGITAL' | 'PHYSICAL';
  category: 'AI_AGENT' | '3D_ASSET' | 'PHYSICAL_MERCH' | 'HARDWARE' | 'SERVICES';
  priceIdr: number;
  priceCredits: number;
  weightGram?: number;
  stock: number;
  image: string;
  description: string;
  inBoothShowcase: boolean;
}

export interface StoreConfig {
  brandName: string;
  tagline: string;
  category: string;
  description: string;
  logo: string;
  originCity: string;
  districtLocation: 'CRYSTAL_CITY' | 'NEO_TOKYO' | 'MARS_OASIS' | 'OCEANIC_WORLD';
  boothTheme: 'MENGGU_PASTEL' | 'CYBERPUNK_NEON' | 'QUARTZ_GLASS' | 'JAPANESE_ZEN';
  boothPrimaryColor: string;
  boothSecondaryColor: string;
  boothBanner: string;
  isBoothLiveIn3D: boolean;
  hasAiGreetingBot: boolean;
  hasHoloShowcase: boolean;
  warpCoordinates: string;
  bankAccount: {
    bankName: string;
    accountNumber: string;
    accountHolder: string;
  };
}

interface StoreAndBoothModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: HumanProfile;
  currentAgent: AIAgentProfile;
  onSaveStore?: (config: StoreConfig, products: StoreProduct[]) => Promise<void> | void;
  onWarpToBooth?: (boothName: string) => void;
}

const DEFAULT_STORE_CONFIG: StoreConfig = {
  brandName: '',
  tagline: '',
  category: '',
  description: '',
  logo: '',
  originCity: '',
  districtLocation: 'CRYSTAL_CITY',
  boothTheme: 'MENGGU_PASTEL',
  boothPrimaryColor: '#FEF08A',
  boothSecondaryColor: '#DDD6FE',
  boothBanner: '',
  isBoothLiveIn3D: false,
  hasAiGreetingBot: false,
  hasHoloShowcase: false,
  warpCoordinates: '',
  bankAccount: { bankName: '', accountNumber: '', accountHolder: '' },
};

const INITIAL_STORE_PRODUCTS: StoreProduct[] = [];

export default function StoreAndBoothModal({
  isOpen,
  onClose,
  currentUser,
  currentAgent,
  onSaveStore,
  onWarpToBooth,
}: StoreAndBoothModalProps) {
  const [activeTab, setActiveTab] = useState<'BRAND' | 'BOOTH_3D' | 'PRODUCTS' | 'EARNINGS'>('BRAND');
  const [config, setConfig] = useState<StoreConfig>(DEFAULT_STORE_CONFIG);
  const [products, setProducts] = useState<StoreProduct[]>(INITIAL_STORE_PRODUCTS);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Form New Product Modal
  const [isAddingProduct, setIsAddingProduct] = useState(false);
  const [newProdName, setNewProdName] = useState('');
  const [newProdType, setNewProdType] = useState<'DIGITAL' | 'PHYSICAL'>('DIGITAL');
  const [newProdCategory, setNewProdCategory] = useState<'AI_AGENT' | '3D_ASSET' | 'PHYSICAL_MERCH' | 'HARDWARE' | 'SERVICES'>('3D_ASSET');
  const [newProdPriceIdr, setNewProdPriceIdr] = useState(150000);
  const [newProdPriceCredits, setNewProdPriceCredits] = useState(100);
  const [newProdWeight, setNewProdWeight] = useState(250);
  const [newProdStock, setNewProdStock] = useState(50);
  const [newProdDesc, setNewProdDesc] = useState('');
  const [newProdShowcase, setNewProdShowcase] = useState(true);

  if (!isOpen) return null;

  const triggerToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleSaveAndApply = async () => {
    if (!onSaveStore) {
      triggerToast('Penyimpanan toko belum tersedia: API kanonis Store/Booth belum tersedia. Perubahan ini belum disimpan.');
      return;
    }
    try {
      await onSaveStore(config, products);
      triggerToast('Konfigurasi toko dikonfirmasi tersimpan oleh API.');
      setTimeout(() => onClose(), 1200);
    } catch (cause) {
      triggerToast(cause instanceof Error ? cause.message : 'Toko belum dapat disimpan. Perubahan belum diterapkan.');
    }
  };

  const handleCreateProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProdName.trim()) {
      triggerToast('Nama produk tidak boleh kosong!');
      return;
    }

    const created: StoreProduct = {
      id: `sp-${Date.now()}`,
      name: newProdName,
      type: newProdType,
      category: newProdCategory,
      priceIdr: Number(newProdPriceIdr),
      priceCredits: Number(newProdPriceCredits),
      weightGram: newProdType === 'PHYSICAL' ? Number(newProdWeight) : 0,
      stock: Number(newProdStock),
      image: '',
      description: newProdDesc,
      inBoothShowcase: newProdShowcase,
    };

    setProducts(prev => [created, ...prev]);
    setIsAddingProduct(false);
    setNewProdName('');
    setNewProdDesc('');
    triggerToast(`Produk "${created.name}" ditambahkan ke draft lokal. Belum tersimpan ke katalog produksi.`);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2.5 sm:p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200 font-sans">
      <div className="w-full max-w-2xl bg-white rounded-3xl border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col h-[92dvh] sm:h-auto sm:max-h-[88vh]">
        
        {/* Floating Toast Notification */}
        {toastMsg && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-60 px-4 py-2 rounded-full bg-slate-900 text-white text-xs font-bold shadow-2xl border border-slate-700 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>{toastMsg}</span>
          </div>
        )}

        {/* Modal Header (Neo-Brutalist Soft Pastel Menggu) */}
        <div className="shrink-0 p-3.5 sm:p-5 bg-[#FEF08A] border-b-2 border-slate-900 flex items-center justify-between">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center text-slate-900 shrink-0">
              <Store className="w-5 h-5 sm:w-6 sm:h-6 stroke-[2.5px]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-sm sm:text-lg font-black text-slate-950 tracking-tight leading-tight">
                  Buat Toko & Booth 3D Spatial
                </h2>
                <span className="text-[9px] sm:text-[10px] font-black px-2 py-0.5 rounded-full bg-emerald-200 border border-slate-900 text-emerald-950 uppercase shadow-2xs">
                  {config.isBoothLiveIn3D ? '🟢 BOOTH LIVE' : '⚪ DRAFT'}
                </span>
              </div>
              <p className="text-[11px] sm:text-xs font-semibold text-slate-800 line-clamp-1 sm:line-clamp-none mt-0.5">
                Atur nama brand, etalase produk digital/fisik, dan booth 3D Anda di Allpha Districts
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-white hover:bg-slate-100 border-2 border-slate-900 flex items-center justify-center text-slate-900 cursor-pointer transition shadow-[1.5px_1.5px_0px_#0f172a] shrink-0 ml-2"
          >
            <X className="w-4 h-4 stroke-[2.5px]" />
          </button>
        </div>

        {/* Navigation Tabs (Neo-Brutal Pill Tabs) */}
        <div className="shrink-0 z-10 flex border-b-2 border-slate-900 bg-slate-100 px-3 sm:px-4 py-2 gap-1.5 overflow-x-auto no-scrollbar">
          {[
            { id: 'BRAND', label: '🏬 Brand & Toko' },
            { id: 'BOOTH_3D', label: '🎪 Booth 3D Spatial' },
            { id: 'PRODUCTS', label: `📦 Produk (${products.length})` },
            { id: 'EARNINGS', label: '💰 Royalti & Payout (85%)' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-3 py-1.5 sm:px-3.5 sm:py-2 text-[11px] sm:text-xs font-black rounded-xl border-2 border-slate-900 transition-all cursor-pointer whitespace-nowrap active:translate-x-0.5 active:translate-y-0.5 ${
                  isActive
                    ? 'bg-white text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                    : 'bg-slate-200 hover:bg-slate-300 text-slate-700 shadow-none'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Modal Body / Tab Content */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-3.5 sm:p-5 space-y-4 pb-14 sm:pb-8">
          
          {/* ============================================================ */}
          {/* TAB 1: INFORMASI BRAND & TOKO                                */}
          {/* ============================================================ */}
          {activeTab === 'BRAND' && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <img
                    src={config.logo}
                    alt={config.brandName}
                    className="w-14 h-14 rounded-2xl object-cover border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]"
                  />
                  <div>
                    <h3 className="font-black text-sm text-slate-950">{config.brandName}</h3>
                    <p className="text-[11px] font-semibold text-slate-600">{config.tagline}</p>
                    <span className="text-[10px] font-bold text-sky-800 bg-sky-100 px-2 py-0.5 rounded-md border border-sky-300 inline-block mt-1">
                      {config.category}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => triggerToast('Unggah media belum tersambung ke endpoint Storage; file belum diunggah.')}
                  className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 border-2 border-slate-900 text-xs font-black shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer shrink-0"
                >
                  Ganti Logo
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-black text-slate-900 mb-1">Nama Brand / Toko</label>
                  <input
                    type="text"
                    value={config.brandName}
                    onChange={(e) => setConfig({ ...config, brandName: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold text-slate-900 bg-slate-50 focus:bg-white outline-none shadow-[2px_2px_0px_#0f172a]"
                    placeholder="Contoh: Aetheria Studio Lab"
                  />
                </div>

                <div>
                  <label className="block font-black text-slate-900 mb-1">Tagline / Slogan Toko</label>
                  <input
                    type="text"
                    value={config.tagline}
                    onChange={(e) => setConfig({ ...config, tagline: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold text-slate-900 bg-slate-50 focus:bg-white outline-none shadow-[2px_2px_0px_#0f172a]"
                    placeholder="Contoh: Official 3D Procedural Assets & Merchandise"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-black text-slate-900 mb-1">Kategori Toko Utama</label>
                    <select
                      value={config.category}
                      onChange={(e) => setConfig({ ...config, category: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold text-slate-900 bg-slate-50 focus:bg-white outline-none shadow-[2px_2px_0px_#0f172a]"
                    >
                      <option value="Aset 3D, AI Agent & Merchandise Fisik">Aset 3D, AI Agent & Merchandise Fisik</option>
                      <option value="Produk Digital & Smart Contracts">Produk Digital & Smart Contracts</option>
                      <option value="Fashion & Apparel Cyberpunk">Fashion & Apparel Cyberpunk</option>
                      <option value="Hardware IoT & Robotics Kit">Hardware IoT & Robotics Kit</option>
                      <option value="Creative Agency & Jasa 3D">Creative Agency & Jasa 3D</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-black text-slate-900 mb-1">Kota Asal Pengiriman (Ongkir Fisik)</label>
                    <select
                      value={config.originCity}
                      onChange={(e) => setConfig({ ...config, originCity: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold text-slate-900 bg-slate-50 focus:bg-white outline-none shadow-[2px_2px_0px_#0f172a]"
                    >
                      <option value="Jakarta Selatan">Jakarta Selatan</option>
                      <option value="Bandung">Bandung</option>
                      <option value="Surabaya">Surabaya</option>
                      <option value="Yogyakarta">Yogyakarta</option>
                      <option value="Denpasar (Bali)">Denpasar (Bali)</option>
                      <option value="Medan">Medan</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-black text-slate-900 mb-1">Deskripsi & Visi Toko</label>
                  <textarea
                    rows={3}
                    value={config.description}
                    onChange={(e) => setConfig({ ...config, description: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-semibold text-slate-900 bg-slate-50 focus:bg-white outline-none shadow-[2px_2px_0px_#0f172a]"
                    placeholder="Jelaskan jenis produk, spesifikasi, dan keunggulan toko Anda..."
                  />
                </div>
              </div>
            </div>
          )}

          {/* ============================================================ */}
          {/* TAB 2: KUSTOMISASI BOOTH 3D SPATIAL                          */}
          {/* ============================================================ */}
          {activeTab === 'BOOTH_3D' && (
            <div className="space-y-4">
              
              {/* Status Switcher Banner */}
              <div className="p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between">
                <div>
                  <h4 className="font-black text-xs text-slate-950">Status Tampil Booth 3D di Universe</h4>
                  <p className="text-[11px] font-semibold text-slate-600">
                    Jika aktif, booth Anda dapat dikunjungi di 3D Spatial Districts oleh ribuan penjelajah.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, isBoothLiveIn3D: !config.isBoothLiveIn3D })}
                  className={`px-4 py-2 rounded-xl font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition cursor-pointer ${
                    config.isBoothLiveIn3D ? 'bg-emerald-300 text-slate-950' : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {config.isBoothLiveIn3D ? 'AKTIF (LIVE) ✓' : 'NON-AKTIF (DRAFT)'}
                </button>
              </div>

              {/* District Choice */}
              <div>
                <label className="block font-black text-xs text-slate-900 mb-1.5">
                  Pilih Lokasi Distrik Spatial 3D
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { id: 'CRYSTAL_CITY', name: 'Crystal City', sub: 'Pusat Metropolis', color: 'bg-sky-100' },
                    { id: 'NEO_TOKYO', name: 'Neo Tokyo', sub: 'Cyber Neon Atrium', color: 'bg-purple-100' },
                    { id: 'MARS_OASIS', name: 'Mars Colony', sub: 'Sci-Fi Biosphere', color: 'bg-rose-100' },
                    { id: 'OCEANIC_WORLD', name: 'Oceanic World', sub: 'Bioluminescent', color: 'bg-teal-100' },
                  ].map((dist) => (
                    <button
                      key={dist.id}
                      type="button"
                      onClick={() => setConfig({ ...config, districtLocation: dist.id as any })}
                      className={`p-2.5 rounded-xl border-2 border-slate-900 text-left transition cursor-pointer ${
                        config.districtLocation === dist.id
                          ? `${dist.color} shadow-[3px_3px_0px_#0f172a] font-black`
                          : 'bg-white hover:bg-slate-50 shadow-[1px_1px_0px_#0f172a]'
                      }`}
                    >
                      <MapPin className="w-4 h-4 text-slate-900 mb-1 stroke-[2.5px]" />
                      <p className="text-xs font-black text-slate-950">{dist.name}</p>
                      <p className="text-[10px] text-slate-600 font-bold">{dist.sub}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Theme Choice */}
              <div>
                <label className="block font-black text-xs text-slate-900 mb-1.5">
                  Tema Arsitektur Booth 3D
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { id: 'MENGGU_PASTEL', label: 'Playful Menggu', bg: 'bg-[#FEF08A]' },
                    { id: 'CYBERPUNK_NEON', label: 'Cyberpunk Neon', bg: 'bg-indigo-300' },
                    { id: 'QUARTZ_GLASS', label: 'Minimalist Quartz', bg: 'bg-emerald-200' },
                    { id: 'JAPANESE_ZEN', label: 'Japanese Zen Spatial', bg: 'bg-amber-200' },
                  ].map((theme) => (
                    <button
                      key={theme.id}
                      type="button"
                      onClick={() => setConfig({ ...config, boothTheme: theme.id as any })}
                      className={`p-2.5 rounded-xl border-2 border-slate-900 text-center transition cursor-pointer ${
                        config.boothTheme === theme.id
                          ? `${theme.bg} shadow-[3px_3px_0px_#0f172a] font-black scale-102`
                          : 'bg-white hover:bg-slate-50 shadow-[1px_1px_0px_#0f172a]'
                      }`}
                    >
                      <Palette className="w-4 h-4 mx-auto text-slate-900 mb-1 stroke-[2.5px]" />
                      <span className="text-[11px] font-black text-slate-900">{theme.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Colors & Features */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                  <span className="font-black text-slate-900">Palet Warna Aksen Booth</span>
                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <label className="text-[10px] font-bold text-slate-600">Warna Pilar Utama</label>
                      <input
                        type="color"
                        value={config.boothPrimaryColor}
                        onChange={(e) => setConfig({ ...config, boothPrimaryColor: e.target.value })}
                        className="w-full h-8 rounded-lg border border-slate-900 cursor-pointer"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-[10px] font-bold text-slate-600">Warna Atap / Neon</label>
                      <input
                        type="color"
                        value={config.boothSecondaryColor}
                        onChange={(e) => setConfig({ ...config, boothSecondaryColor: e.target.value })}
                        className="w-full h-8 rounded-lg border border-slate-900 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                  <span className="font-black text-slate-900">Interaksi Cerdas Booth 3D</span>
                  <div className="space-y-1.5">
                    <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-800">
                      <input
                        type="checkbox"
                        checked={config.hasAiGreetingBot}
                        onChange={(e) => setConfig({ ...config, hasAiGreetingBot: e.target.checked })}
                        className="w-4 h-4 accent-slate-900"
                      />
                      <span>Pasang AI Greeting Bot penjaga booth</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-800">
                      <input
                        type="checkbox"
                        checked={config.hasHoloShowcase}
                        onChange={(e) => setConfig({ ...config, hasHoloShowcase: e.target.checked })}
                        className="w-4 h-4 accent-slate-900"
                      />
                      <span>Tampilkan Meja Hologram 3D Berputar</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Direct Warp Preview */}
              <div className="p-3.5 rounded-2xl bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-black text-purple-900 uppercase">Koordinat Warp Pad</span>
                  <p className="font-mono font-black text-xs text-slate-950">{config.warpCoordinates}</p>
                </div>
                {onWarpToBooth && (
                  <button
                    type="button"
                    onClick={() => onWarpToBooth(config.brandName)}
                    className="px-3 py-1.5 rounded-xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer flex items-center gap-1.5"
                  >
                    <Box className="w-3.5 h-3.5 text-slate-950 stroke-[2.5px]" />
                    <span>Lihat di 3D Universe</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* ============================================================ */}
          {/* TAB 3: KELOLA & TAMBAH PRODUK                                */}
          {/* ============================================================ */}
          {activeTab === 'PRODUCTS' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-black text-sm text-slate-950">Katalog Produk Toko & Booth</h3>
                  <p className="text-[11px] font-semibold text-slate-600">
                    Jual aset digital (download langsung) atau produk fisik (dikirim via ekspedisi).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsAddingProduct(true)}
                  className="px-3.5 py-2 rounded-xl bg-[#BBF7D0] hover:bg-emerald-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 stroke-[3px]" />
                  <span>Tambah Produk Baru</span>
                </button>
              </div>

              {/* Product List Cards */}
              <div className="space-y-2.5">
                {products.map((item) => (
                  <div
                    key={item.id}
                    className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2.5px_2.5px_0px_#0f172a] flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <img
                        src={item.image}
                        alt={item.name}
                        className="w-12 h-12 rounded-xl object-cover border-2 border-slate-900 shrink-0 shadow-2xs"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[9px] font-black px-1.5 py-0.2 rounded-md border border-slate-900 ${
                            item.type === 'DIGITAL' ? 'bg-sky-100 text-sky-950' : 'bg-amber-100 text-amber-950'
                          }`}>
                            {item.type}
                          </span>
                          {item.inBoothShowcase && (
                            <span className="text-[9px] font-black px-1.5 py-0.2 rounded-md border border-slate-900 bg-purple-100 text-purple-950">
                              🎪 Di Booth 3D
                            </span>
                          )}
                        </div>
                        <h4 className="font-black text-slate-950 truncate max-w-xs mt-0.5">{item.name}</h4>
                        <div className="flex items-center gap-2 text-[11px] font-bold text-slate-600">
                          <span className="text-emerald-700 font-mono font-black">
                            Rp {item.priceIdr.toLocaleString('id-ID')}
                          </span>
                          <span>•</span>
                          <span className="text-amber-800 font-mono font-black">
                            {item.priceCredits} Cr
                          </span>
                          <span>•</span>
                          <span>Stok: {item.stock}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => {
                          setProducts(prev => prev.map(p => p.id === item.id ? { ...p, inBoothShowcase: !p.inBoothShowcase } : p));
                          triggerToast(`Status showcase "${item.name}" berubah pada draft lokal saja; belum tersimpan.`);
                        }}
                        className="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 text-[10px] font-bold cursor-pointer"
                        title="Tampilkan di Hologram Booth 3D"
                      >
                        {item.inBoothShowcase ? 'Hapus dari Booth' : '+ Pajang di Booth'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setProducts(prev => prev.filter(p => p.id !== item.id));
                          triggerToast(`Produk "${item.name}" dihapus dari draft lokal; belum ada perubahan pada katalog produksi.`);
                        }}
                        className="w-7 h-7 rounded-xl bg-rose-100 hover:bg-rose-200 text-rose-900 border-2 border-slate-900 flex items-center justify-center cursor-pointer font-black"
                      >
                        <X className="w-3.5 h-3.5 stroke-[2.5px]" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ============================================================ */}
          {/* TAB 4: ROYALTI & PENARIKAN DANA (UNIT ECONOMICS 85%)        */}
          {/* ============================================================ */}
          {activeTab === 'EARNINGS' && (
            <div className="space-y-4 text-xs">
              
              {/* Unit Economics Banner */}
              <div className="p-4 rounded-2xl bg-[#BBF7D0] border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] font-black uppercase text-emerald-950 bg-white/80 px-2 py-0.5 rounded-md border border-slate-900">
                    Sistem Bagi Hasil Master PRD
                  </span>
                  <span className="font-black text-emerald-950">85% Penjual / 15% Platform</span>
                </div>
                <h3 className="font-black text-sm text-slate-950">
                  Hak Pendapatan Kreator Marketplace: 85% Bersih Masuk ke Dompet Anda!
                </h3>
                <p className="text-[11px] font-semibold text-slate-800 leading-relaxed">
                  Setiap transaksi produk digital atau fisik di toko Anda otomatis dipotong platform fee 15%, dan 85% langsung masuk ke saldo siap tarik. Khusus royalti penonton Film AI mendapat porsi 90%.
                </p>
              </div>

              {/* Balances Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                  <span className="text-[10px] font-bold text-slate-500">Saldo Penjualan Siap Tarik</span>
                  <p className="text-lg font-mono font-black text-slate-600 mt-0.5">Belum tersedia</p>
                  <span className="text-[9.5px] font-bold text-slate-500">Setara ~2.560 AI Credits</span>
                </div>

                <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                  <span className="text-[10px] font-bold text-slate-500">Total Produk Terjual</span>
                  <p className="text-lg font-mono font-black text-indigo-700 mt-0.5">38 Transaksi</p>
                  <span className="text-[9.5px] font-bold text-slate-500">Rating Toko: 4.9 ★ (120 Review)</span>
                </div>
              </div>

              {/* Bank Account Config */}
              <div className="p-3.5 rounded-2xl bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2.5">
                <h4 className="font-black text-slate-950 flex items-center gap-1.5">
                  <Coins className="w-4 h-4 text-amber-600 stroke-[2.5px]" />
                  <span>Rekening Bank Penarikan Royalti</span>
                </h4>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] font-bold text-slate-600">Bank / E-Wallet</label>
                    <input
                      type="text"
                      value={config.bankAccount.bankName}
                      onChange={(e) => setConfig({
                        ...config,
                        bankAccount: { ...config.bankAccount, bankName: e.target.value }
                      })}
                      className="w-full px-2.5 py-1.5 rounded-xl border border-slate-900 font-bold bg-white text-slate-950"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] font-bold text-slate-600">Nomor Rekening</label>
                    <input
                      type="text"
                      value={config.bankAccount.accountNumber}
                      onChange={(e) => setConfig({
                        ...config,
                        bankAccount: { ...config.bankAccount, accountNumber: e.target.value }
                      })}
                      className="w-full px-2.5 py-1.5 rounded-xl border border-slate-900 font-mono font-bold bg-white text-slate-950"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] font-bold text-slate-600">Atas Nama</label>
                    <input
                      type="text"
                      value={config.bankAccount.accountHolder}
                      onChange={(e) => setConfig({
                        ...config,
                        bankAccount: { ...config.bankAccount, accountHolder: e.target.value }
                      })}
                      className="w-full px-2.5 py-1.5 rounded-xl border border-slate-900 font-bold bg-white text-slate-950"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => triggerToast('Pencairan royalti belum tersedia: saldo dan endpoint payout belum terhubung. Tidak ada penarikan yang diproses.')}
                  className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  Ajukan Penarikan Dana (Withdraw Instant)
                </button>
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer Actions */}
        <div className="shrink-0 p-3.5 sm:p-4 border-t-2 border-slate-900 bg-slate-50 flex items-center justify-between gap-3 z-10">
          <div className="text-[11px] font-bold text-slate-600 hidden sm:block">
            Terhubung ke AI Agent: <strong className="text-slate-950">{currentAgent.name}</strong>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-slate-200 hover:bg-slate-300 font-black text-xs text-slate-900 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer"
            >
              Tutup
            </button>
            <button
              type="button"
              onClick={handleSaveAndApply}
              className="flex-1 sm:flex-none px-6 py-2.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2.5px_2.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-4 h-4 stroke-[2.5px] text-slate-950" />
              <span>Simpan & Tampilkan Booth</span>
            </button>
          </div>
        </div>
      </div>

      {/* ============================================================ */}
      {/* SUB-MODAL: TAMBAH PRODUK BARU                                */}
      {/* ============================================================ */}
      {isAddingProduct && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm animate-in fade-in zoom-in-95 duration-150">
          <div className="w-full max-w-md bg-white rounded-3xl border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-4 sm:p-5 space-y-3.5 text-xs max-h-[92dvh] flex flex-col">
            <div className="shrink-0 flex items-center justify-between pb-2 border-b-2 border-slate-100">
              <h3 className="font-black text-sm text-slate-950">Tambah Produk ke Toko & Booth</h3>
              <button
                onClick={() => setIsAddingProduct(false)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            <form onSubmit={handleCreateProduct} className="flex-1 min-h-0 overflow-y-auto space-y-3 pr-1 pb-4">
              <div>
                <label className="block font-black text-slate-900 mb-1">Nama Produk</label>
                <input
                  type="text"
                  required
                  value={newProdName}
                  onChange={(e) => setNewProdName(e.target.value)}
                  placeholder="Contoh: Shader Hologram Neon 3D"
                  className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-black text-slate-900 mb-1">Tipe Produk</label>
                  <select
                    value={newProdType}
                    onChange={(e) => setNewProdType(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 outline-none"
                  >
                    <option value="DIGITAL">Digital (Aset / Code)</option>
                    <option value="PHYSICAL">Fisik (Dikirim Kurir)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-black text-slate-900 mb-1">Kategori</label>
                  <select
                    value={newProdCategory}
                    onChange={(e) => setNewProdCategory(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 outline-none"
                  >
                    <option value="3D_ASSET">Aset 3D & Spatial</option>
                    <option value="AI_AGENT">AI Agent Companion</option>
                    <option value="PHYSICAL_MERCH">Merchandise Fisik</option>
                    <option value="HARDWARE">Hardware / IoT</option>
                    <option value="SERVICES">Jasa & Konsultasi</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-black text-slate-900 mb-1">Harga (Rupiah)</label>
                  <input
                    type="number"
                    min="10000"
                    step="5000"
                    value={newProdPriceIdr}
                    onChange={(e) => setNewProdPriceIdr(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-mono font-bold bg-slate-50 outline-none"
                  />
                </div>

                <div>
                  <label className="block font-black text-slate-900 mb-1">Harga (AI Credits)</label>
                  <input
                    type="number"
                    min="5"
                    step="5"
                    value={newProdPriceCredits}
                    onChange={(e) => setNewProdPriceCredits(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-mono font-bold bg-slate-50 outline-none"
                  />
                </div>
              </div>

              {newProdType === 'PHYSICAL' && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block font-black text-slate-900 mb-1">Berat Paket (gram)</label>
                    <input
                      type="number"
                      min="50"
                      value={newProdWeight}
                      onChange={(e) => setNewProdWeight(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-mono font-bold bg-slate-50 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-black text-slate-900 mb-1">Stok Barang</label>
                    <input
                      type="number"
                      min="1"
                      value={newProdStock}
                      onChange={(e) => setNewProdStock(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-mono font-bold bg-slate-50 outline-none"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block font-black text-slate-900 mb-1">Deskripsi Produk</label>
                <textarea
                  rows={2}
                  value={newProdDesc}
                  onChange={(e) => setNewProdDesc(e.target.value)}
                  placeholder="Spesifikasi, format file, dan garansi..."
                  className="w-full px-3 py-2 rounded-xl border-2 border-slate-900 font-semibold bg-slate-50 outline-none"
                />
              </div>

              <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-900 pt-1">
                <input
                  type="checkbox"
                  checked={newProdShowcase}
                  onChange={(e) => setNewProdShowcase(e.target.checked)}
                  className="w-4 h-4 accent-slate-900"
                />
                <span>Pajang langsung di Meja Hologram Booth 3D</span>
              </label>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddingProduct(false)}
                  className="flex-1 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] cursor-pointer"
                >
                  Simpan Produk
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
