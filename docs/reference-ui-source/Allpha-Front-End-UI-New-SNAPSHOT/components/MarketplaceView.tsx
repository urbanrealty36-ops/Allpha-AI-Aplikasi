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
  Filter,
  Truck,
  MessageCircle,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  CreditCard,
  QrCode,
  X,
  Package,
  Layers,
  MapPin,
  Clock,
  ArrowRight
} from 'lucide-react';

export interface ProductItem {
  id: string;
  title: string;
  type: 'DIGITAL' | 'PHYSICAL';
  category: 'AI_AGENT' | '3D_ASSET' | 'PHYSICAL_MERCH' | 'HARDWARE' | 'SERVICES';
  categoryLabel: string;
  priceIdr: number;
  priceCredits: number;
  likes: number;
  image: string;
  description: string;
  sellerName: string;
  sellerHandle: string;
  sellerAvatar: string;
  booth3DName: string;
  weightGram?: number;
  rating: number;
  soldCount: number;
  stock: number;
}

interface MarketplaceViewProps {
  onBuyItem: (title: string, priceCredits: number) => void;
  userCredits: number;
  onWarpToBooth?: (boothName: string) => void;
  onOpenSellerChat?: (sellerName: string, sellerHandle: string) => void;
}

export default function MarketplaceView({ 
  onBuyItem, 
  userCredits,
  onWarpToBooth,
  onOpenSellerChat
}: MarketplaceViewProps) {
  const [filterTab, setFilterTab] = useState<'ALL' | 'PHYSICAL' | 'DIGITAL' | 'AI_AGENT' | '3D_ASSET'>('ALL');
  const [search, setSearch] = useState('');
  
  // Modals
  const [selectedProduct, setSelectedProduct] = useState<ProductItem | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [checkoutProduct, setCheckoutProduct] = useState<ProductItem | null>(null);

  // Ongkir Shipping Calculator State
  const [destinationCity, setDestinationCity] = useState<'Jakarta' | 'Bandung' | 'Surabaya' | 'Medan' | 'Bali' | 'Yogyakarta'>('Jakarta');
  const [selectedCourier, setSelectedCourier] = useState<'JNE_REG' | 'JNE_YES' | 'SICEPAT_BEST' | 'JNT_EZ'>('JNE_REG');

  // Midtrans Payment Simulator State
  const [paymentMethod, setPaymentMethod] = useState<'QRIS' | 'GOPAY' | 'BCA_VA' | 'MANDIRI_VA' | 'CREDIT_CARD' | 'AI_CREDITS'>('QRIS');
  const [isPaymentProcessing, setIsPaymentProcessing] = useState(false);
  const [paymentSuccessData, setPaymentSuccessData] = useState<{
    orderId: string;
    totalAmount: string;
    productTitle: string;
    courierName?: string;
  } | null>(null);

  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const PRODUCTS: ProductItem[] = [
    // Physical Goods
    {
      id: 'prod-p1',
      title: 'Allpha Holographic Cyber Hoodie',
      type: 'PHYSICAL',
      category: 'PHYSICAL_MERCH',
      categoryLabel: 'Produk Fisik',
      priceIdr: 450000,
      priceCredits: 90,
      likes: 1840,
      image: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=600&q=80',
      description: 'Hoodie katun fleece premium 330gsm dengan sablon reflektif hologram Allpha Universe dan NFC chip terintegrasi untuk klaim digital wearable avatar 3D.',
      sellerName: 'Allpha Official Store',
      sellerHandle: '@allpha.gear',
      sellerAvatar: 'https://picsum.photos/seed/allpha-official/100/100',
      booth3DName: 'Central Fashion Booth #01',
      weightGram: 650,
      rating: 4.9,
      soldCount: 312,
      stock: 45,
    },
    {
      id: 'prod-p2',
      title: 'Neural AI Edge Node Box v2',
      type: 'PHYSICAL',
      category: 'HARDWARE',
      categoryLabel: 'Hardware Fisik',
      priceIdr: 1850000,
      priceCredits: 370,
      likes: 920,
      image: 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=80',
      description: 'Perangkat keras mini PC Linux untuk menjalankan AI Agent Allpha secara lokal, sinkronisasi otomatis ke spatial district tanpa latensi cloud.',
      sellerName: 'TechNova Hardware',
      sellerHandle: '@technova.hw',
      sellerAvatar: 'https://picsum.photos/seed/technova/100/100',
      booth3DName: 'TechNova AI Hardware Plaza',
      weightGram: 820,
      rating: 4.8,
      soldCount: 88,
      stock: 12,
    },
    {
      id: 'prod-p3',
      title: 'Cyberpunk Valkyrie 3D Resin Statue',
      type: 'PHYSICAL',
      category: 'PHYSICAL_MERCH',
      categoryLabel: 'Produk Fisik',
      priceIdr: 650000,
      priceCredits: 130,
      likes: 1105,
      image: 'https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=600&q=80',
      description: 'Patung pajangan meja presisi tinggi 18cm dicetak dengan SLA resin photopolymer, hand-painted dengan aksen cat neon UV glow in the dark.',
      sellerName: 'Luna Studio Art',
      sellerHandle: '@luna.art',
      sellerAvatar: 'https://picsum.photos/seed/luna-cyber/100/100',
      booth3DName: 'Luna 3D Sculpt Gallery',
      weightGram: 500,
      rating: 5.0,
      soldCount: 64,
      stock: 8,
    },

    // Digital Goods
    {
      id: 'prod-d1',
      title: 'Crystal City 3D Cyber Pack (Three.js)',
      type: 'DIGITAL',
      category: '3D_ASSET',
      categoryLabel: 'Aset 3D Digital',
      priceIdr: 250000,
      priceCredits: 50,
      likes: 1240,
      image: 'https://images.unsplash.com/photo-1508739773434-c26b3d09e071?auto=format&fit=crop&w=600&q=80',
      description: 'Paket modular bangunan pencakar langit, skywalk, neon billboards Three.js lengkap dengan file GLB dan shader pantulan real-time PBR.',
      sellerName: 'Alex Tamara',
      sellerHandle: '@alextamara',
      sellerAvatar: 'https://picsum.photos/seed/alex-tamara/100/100',
      booth3DName: 'Alex Architecture Booth',
      rating: 4.9,
      soldCount: 420,
      stock: 999,
    },
    {
      id: 'prod-d2',
      title: 'Luna Cybernetic AI Avatar Rig',
      type: 'DIGITAL',
      category: 'AI_AGENT',
      categoryLabel: 'AI Agent Rig',
      priceIdr: 350000,
      priceCredits: 70,
      likes: 980,
      image: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80',
      description: 'Rig avatar 3D cybernetic siap pakai lengkap dengan 12 animasi gerak emote, sinkronisasi suara real-time, dan konektor kepribadian AI Agent.',
      sellerName: 'Luna AI',
      sellerHandle: '@luna.ai',
      sellerAvatar: 'https://picsum.photos/seed/luna-cyber/100/100',
      booth3DName: 'Luna AI Experience Center',
      rating: 4.9,
      soldCount: 290,
      stock: 999,
    },
    {
      id: 'prod-d3',
      title: 'Marketing AI Pro Strategy Agent',
      type: 'DIGITAL',
      category: 'AI_AGENT',
      categoryLabel: 'AI Agent',
      priceIdr: 300000,
      priceCredits: 60,
      likes: 1540,
      image: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=600&q=80',
      description: 'Lisensi sebulan untuk AI Agent yang otomatis merancang copywriting, naskah reels, analitik kampanye, dan tren engagement 2026.',
      sellerName: 'Budi Kreatif',
      sellerHandle: '@budi_creative',
      sellerAvatar: 'https://picsum.photos/seed/budi/100/100',
      booth3DName: 'Budi Agency Virtual Office',
      rating: 4.8,
      soldCount: 512,
      stock: 999,
    },
  ];

  // Courier Rates calculation based on destination
  const COURIER_OPTIONS = {
    JNE_REG: { name: 'JNE Reguler', days: '2-3 Hari', baseRate: 15000 },
    JNE_YES: { name: 'JNE YES (Yakin Esok Sampai)', days: '1 Hari', baseRate: 28000 },
    SICEPAT_BEST: { name: 'SiCepat BEST', days: '1-2 Hari', baseRate: 18000 },
    JNT_EZ: { name: 'J&T Express EZ', days: '2-3 Hari', baseRate: 16000 },
  };

  const getCityMultiplier = (city: string) => {
    switch (city) {
      case 'Jakarta': return 1.0;
      case 'Bandung': return 1.1;
      case 'Surabaya': return 1.4;
      case 'Yogyakarta': return 1.3;
      case 'Bali': return 1.8;
      case 'Medan': return 2.2;
      default: return 1.0;
    }
  };

  const calculateOngkir = (courierKey: keyof typeof COURIER_OPTIONS, city: string) => {
    const courier = COURIER_OPTIONS[courierKey];
    const multiplier = getCityMultiplier(city);
    return Math.round(courier.baseRate * multiplier);
  };

  const filtered = PRODUCTS.filter((it) => {
    const matchesSearch = it.title.toLowerCase().includes(search.toLowerCase()) || 
                          it.description.toLowerCase().includes(search.toLowerCase());
    if (filterTab === 'PHYSICAL') return matchesSearch && it.type === 'PHYSICAL';
    if (filterTab === 'DIGITAL') return matchesSearch && it.type === 'DIGITAL';
    if (filterTab === 'AI_AGENT') return matchesSearch && it.category === 'AI_AGENT';
    if (filterTab === '3D_ASSET') return matchesSearch && it.category === '3D_ASSET';
    return matchesSearch;
  });

  const handleStartCheckout = (prod: ProductItem) => {
    setSelectedProduct(null);
    setCheckoutProduct(prod);
    setIsCheckoutOpen(true);
  };

  const handleProcessPayment = () => {
    if (!checkoutProduct) return;

    if (paymentMethod === 'AI_CREDITS') {
      if (userCredits < checkoutProduct.priceCredits) {
        showToast(`AI Credits tidak mencukupi (${userCredits} < ${checkoutProduct.priceCredits})`);
        return;
      }
      onBuyItem(checkoutProduct.title, checkoutProduct.priceCredits);
    }

    setIsPaymentProcessing(true);
    setTimeout(() => {
      setIsPaymentProcessing(false);
      const ongkir = checkoutProduct.type === 'PHYSICAL' ? calculateOngkir(selectedCourier, destinationCity) : 0;
      const totalNum = paymentMethod === 'AI_CREDITS' 
        ? `${checkoutProduct.priceCredits} AI Credits` 
        : `Rp ${(checkoutProduct.priceIdr + ongkir + 2000).toLocaleString('id-ID')}`;

      setPaymentSuccessData({
        orderId: `MID-ALPH-2026-${Math.floor(100000 + Math.random() * 900000)}`,
        totalAmount: totalNum,
        productTitle: checkoutProduct.title,
        courierName: checkoutProduct.type === 'PHYSICAL' ? COURIER_OPTIONS[selectedCourier].name : undefined,
      });
    }, 1200);
  };

  return (
    <div className="w-full max-w-xl mx-auto px-3.5 sm:px-4 py-3 pb-28 font-sans space-y-3.5">
      
      {/* Header Banner */}
      <div className="p-4 rounded-3xl bg-[#FEF08A] border-3 border-slate-900 shadow-[4px_4px_0px_#0f172a] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <h1 className="text-base sm:text-lg font-black text-slate-900 tracking-tight">Marketplace & Toko Online</h1>
            <span className="text-[9px] font-black px-2 py-0.5 rounded-full bg-white border-2 border-slate-900 text-slate-950 uppercase">
              ALLPHA STORE
            </span>
          </div>
          <p className="text-xs font-bold text-slate-800 mt-0.5">Produk Fisik (Hoodie, Node, Patung) & Aset Digital 3D</p>
        </div>
        <div className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white border-2 border-slate-900 text-slate-950 font-mono text-xs font-black shadow-[2px_2px_0px_#0f172a]">
          <span>🪙</span>
          <span>{userCredits} Cr</span>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari produk fisik, AI Agent, 3D asset, aksesoris..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border-2 border-slate-900 rounded-2xl text-xs font-bold text-slate-900 outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-sky-50 transition"
        />
      </div>

      {/* Filter Segmented Buttons */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
        {[
          { id: 'ALL', label: 'Semua Produk' },
          { id: 'PHYSICAL', label: '📦 Produk Fisik' },
          { id: 'DIGITAL', label: '⚡ Aset Digital' },
          { id: 'AI_AGENT', label: '🤖 AI Agent' },
          { id: '3D_ASSET', label: '💎 3D Assets' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterTab(tab.id as any)}
            className={`px-3 py-1.5 rounded-xl text-xs font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 whitespace-nowrap cursor-pointer ${
              filterTab === tab.id
                ? 'bg-[#BAE6FD] text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-800 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Grid of Online Store Product Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {filtered.map((item) => {
          const isPhysical = item.type === 'PHYSICAL';

          return (
            <div
              key={item.id}
              onClick={() => setSelectedProduct(item)}
              className="rounded-3xl bg-white border-3 border-slate-900 shadow-[3px_3px_0px_#0f172a] overflow-hidden flex flex-col justify-between transition hover:-translate-y-0.5 cursor-pointer text-left"
            >
              {/* Product Image + Badges */}
              <div className="relative h-44 bg-slate-900 overflow-hidden border-b-2 border-slate-900">
                <img
                  src={item.image}
                  alt={item.title}
                  className="w-full h-full object-cover transition duration-300 hover:scale-105"
                />
                <span className={`absolute top-2.5 left-2.5 px-2.5 py-0.5 rounded-full border-2 border-slate-900 text-[9.5px] font-black shadow-[1.5px_1.5px_0px_#0f172a] ${
                  isPhysical ? 'bg-[#BBF7D0] text-emerald-950' : 'bg-[#DDD6FE] text-purple-950'
                }`}>
                  {isPhysical ? '📦 Fisik + Ongkir' : '⚡ Digital Instan'}
                </span>

                <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full bg-slate-900/80 border border-slate-700 text-white text-[10px] font-bold flex items-center gap-1">
                  <Heart className="w-3 h-3 text-rose-400 fill-rose-400" />
                  <span>{item.likes}</span>
                </div>

                <div className="absolute bottom-2 left-2.5 px-2 py-0.5 rounded-md bg-slate-950/80 backdrop-blur-xs text-white text-[9px] font-mono font-bold flex items-center gap-1">
                  <span>⭐ {item.rating}</span>
                  <span>•</span>
                  <span>{item.soldCount} Terjual</span>
                </div>
              </div>

              {/* Product Info */}
              <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 mb-0.5">
                    <span>Oleh: {item.sellerName}</span>
                  </div>
                  <h3 className="font-black text-slate-900 text-xs sm:text-sm line-clamp-1">{item.title}</h3>
                  <p className="text-[11px] font-medium text-slate-600 line-clamp-2 mt-1 leading-snug">{item.description}</p>
                </div>

                {/* Price and CTA */}
                <div className="pt-2 border-t-2 border-slate-100 flex items-center justify-between gap-2">
                  <div>
                    <span className="font-black text-slate-900 text-xs sm:text-sm block">
                      Rp {item.priceIdr.toLocaleString('id-ID')}
                    </span>
                    <span className="text-[10px] text-amber-900 font-mono font-black flex items-center gap-1">
                      🪙 {item.priceCredits} Credits
                    </span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleStartCheckout(item);
                    }}
                    className="px-3.5 py-1.5 rounded-xl bg-[#BAE6FD] hover:bg-sky-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                  >
                    Beli Sekarang
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ======================================================== */}
      {/* PRODUCT DETAIL MODAL                                     */}
      {/* ======================================================== */}
      {selectedProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[92vh]">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between p-3.5 border-b-2 border-slate-900 bg-slate-50">
              <span className="text-xs font-black uppercase text-slate-700 tracking-wider flex items-center gap-1.5">
                <ShoppingBag className="w-4 h-4 text-slate-900" />
                <span>Detail Produk & Toko</span>
              </span>
              <button
                onClick={() => setSelectedProduct(null)}
                className="p-1 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-700 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-4 sm:p-5 overflow-y-auto space-y-4">
              {/* Product Hero Image */}
              <div className="relative h-52 rounded-2xl overflow-hidden border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] bg-slate-950">
                <img
                  src={selectedProduct.image}
                  alt={selectedProduct.title}
                  className="w-full h-full object-cover"
                />
                <span className={`absolute top-2.5 left-2.5 px-2.5 py-0.5 rounded-full border-2 border-slate-900 text-[10px] font-black shadow-[1.5px_1.5px_0px_#0f172a] ${
                  selectedProduct.type === 'PHYSICAL' ? 'bg-[#BBF7D0] text-emerald-950' : 'bg-[#DDD6FE] text-purple-950'
                }`}>
                  {selectedProduct.type === 'PHYSICAL' ? '📦 Produk Fisik' : '⚡ Digital'}
                </span>
              </div>

              {/* Title & Price */}
              <div>
                <h2 className="text-base sm:text-lg font-black text-slate-900">{selectedProduct.title}</h2>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-base font-black text-slate-900">
                    Rp {selectedProduct.priceIdr.toLocaleString('id-ID')}
                  </span>
                  <span className="text-xs font-mono font-black text-amber-800 bg-[#FEF08A] px-2 py-0.5 rounded-lg border border-slate-900">
                    🪙 {selectedProduct.priceCredits} Credits
                  </span>
                  <span className="text-xs text-slate-500 font-bold">Stok: {selectedProduct.stock} unit</span>
                </div>
              </div>

              {/* Description */}
              <div className="p-3.5 rounded-2xl bg-slate-50 border-2 border-slate-900 text-xs text-slate-700 leading-relaxed font-medium">
                <h4 className="font-black text-slate-900 uppercase text-[11px] mb-1">Deskripsi Produk:</h4>
                <p>{selectedProduct.description}</p>
              </div>

              {/* Seller & Direct 3D Booth Warp Box */}
              <div className="p-3.5 rounded-2xl bg-[#BAE6FD]/40 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col gap-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <img
                      src={selectedProduct.sellerAvatar}
                      alt={selectedProduct.sellerName}
                      className="w-8 h-8 rounded-xl border border-slate-900 object-cover"
                    />
                    <div>
                      <p className="text-xs font-black text-slate-900">{selectedProduct.sellerName}</p>
                      <p className="text-[10px] font-bold text-slate-600">{selectedProduct.sellerHandle}</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-black text-sky-900 bg-sky-200 px-2 py-0.5 rounded-md border border-sky-400">
                    VERIFIED SELLER
                  </span>
                </div>

                {/* Direct Action Buttons: Warp to 3D Booth & Direct Message */}
                <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-300">
                  <button
                    onClick={() => {
                      if (onWarpToBooth) onWarpToBooth(selectedProduct.booth3DName);
                      showToast(`Teleporting ke ${selectedProduct.booth3DName} di Dunia 3D!`);
                      setSelectedProduct(null);
                    }}
                    className="py-2 px-2.5 rounded-xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-900 font-black text-[11px] flex items-center justify-center gap-1.5 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                  >
                    <Box className="w-3.5 h-3.5 text-purple-700" />
                    <span>Warp ke Booth 3D</span>
                  </button>

                  <button
                    onClick={() => {
                      if (onOpenSellerChat) onOpenSellerChat(selectedProduct.sellerName, selectedProduct.sellerHandle);
                      showToast(`Membuka percakapan langsung dengan ${selectedProduct.sellerName}`);
                      setSelectedProduct(null);
                    }}
                    className="py-2 px-2.5 rounded-xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-900 font-black text-[11px] flex items-center justify-center gap-1.5 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                  >
                    <MessageCircle className="w-3.5 h-3.5 text-blue-600" />
                    <span>Chat Penjual</span>
                  </button>
                </div>
              </div>

              {/* Ongkir Calculator Preview for Physical */}
              {selectedProduct.type === 'PHYSICAL' && (
                <div className="p-3.5 rounded-2xl bg-[#BBF7D0]/40 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase">
                      <Truck className="w-3.5 h-3.5 text-emerald-800" />
                      <span>Estimasi Ongkir ({destinationCity})</span>
                    </span>
                    <span className="text-xs font-black text-slate-900 font-mono">
                      Rp {calculateOngkir(selectedCourier, destinationCity).toLocaleString('id-ID')}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-600 font-bold">
                    Kurir: {COURIER_OPTIONS[selectedCourier].name} ({COURIER_OPTIONS[selectedCourier].days})
                  </p>
                </div>
              )}
            </div>

            {/* Modal Bottom CTA */}
            <div className="p-3.5 border-t-2 border-slate-900 bg-white flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase font-bold text-slate-500">Total Harga</p>
                <p className="text-sm font-black text-slate-900">
                  Rp {selectedProduct.priceIdr.toLocaleString('id-ID')}
                </p>
              </div>
              <button
                onClick={() => handleStartCheckout(selectedProduct)}
                className="py-2.5 px-6 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
              >
                <span>Lanjut ke Checkout</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MIDTRANS CHECKOUT & ONGKIR MODAL                         */}
      {/* ======================================================== */}
      {isCheckoutOpen && checkoutProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[92vh]">
            
            {/* Header */}
            <div className="flex items-center justify-between p-3.5 border-b-2 border-slate-900 bg-[#DDD6FE]">
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-purple-950" />
                <h3 className="text-xs font-black uppercase text-purple-950 tracking-wider">
                  Midtrans Payment & Checkout Gateway
                </h3>
              </div>
              <button
                onClick={() => {
                  setIsCheckoutOpen(false);
                  setPaymentSuccessData(null);
                }}
                className="p-1 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-700 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 sm:p-5 overflow-y-auto space-y-4">
              {paymentSuccessData ? (
                /* Payment Success Receipt */
                <div className="py-6 flex flex-col items-center text-center space-y-3">
                  <div className="w-16 h-16 rounded-2xl bg-emerald-200 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-emerald-800 flex items-center justify-center animate-bounce">
                    <CheckCircle2 className="w-8 h-8 stroke-[2.5]" />
                  </div>
                  <h4 className="text-base font-black text-slate-900">Pembayaran Berhasil Diverifikasi!</h4>
                  <p className="text-xs text-slate-600 font-semibold">
                    Pesanan Anda telah dicatat oleh payment gateway Midtrans dan diteruskan ke penjual.
                  </p>

                  <div className="w-full p-4 rounded-2xl bg-slate-50 border-2 border-slate-900 text-xs space-y-1.5 text-left font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Order ID:</span>
                      <span className="font-bold text-slate-900">{paymentSuccessData.orderId}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Produk:</span>
                      <span className="font-bold text-slate-900 truncate max-w-[200px]">{paymentSuccessData.productTitle}</span>
                    </div>
                    {paymentSuccessData.courierName && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">Ekspedisi:</span>
                        <span className="font-bold text-emerald-700">{paymentSuccessData.courierName}</span>
                      </div>
                    )}
                    <div className="flex justify-between border-t border-slate-300 pt-1.5">
                      <span className="text-slate-900 font-black">Total Terbayar:</span>
                      <span className="font-black text-emerald-700">{paymentSuccessData.totalAmount}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setIsCheckoutOpen(false);
                      setPaymentSuccessData(null);
                    }}
                    className="w-full py-2.5 rounded-xl bg-slate-900 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5"
                  >
                    Kembali ke Marketplace
                  </button>
                </div>
              ) : (
                <>
                  {/* Item Summary */}
                  <div className="p-3 rounded-2xl bg-slate-50 border-2 border-slate-900 flex items-center gap-3">
                    <img
                      src={checkoutProduct.image}
                      alt={checkoutProduct.title}
                      className="w-14 h-14 rounded-xl border border-slate-900 object-cover"
                    />
                    <div className="flex-1">
                      <h4 className="text-xs font-black text-slate-900 line-clamp-1">{checkoutProduct.title}</h4>
                      <p className="text-[10.5px] text-slate-500 font-bold">{checkoutProduct.categoryLabel}</p>
                      <p className="text-xs font-black text-slate-900 mt-0.5">
                        Rp {checkoutProduct.priceIdr.toLocaleString('id-ID')}
                      </p>
                    </div>
                  </div>

                  {/* Shipping Calculator for Physical Goods */}
                  {checkoutProduct.type === 'PHYSICAL' && (
                    <div className="p-3.5 rounded-2xl bg-amber-50/70 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-slate-900 flex items-center gap-1 uppercase">
                          <MapPin className="w-3.5 h-3.5 text-amber-800" />
                          <span>Pilih Kota Tujuan Pengiriman</span>
                        </span>
                      </div>
                      
                      {/* Destination Picker */}
                      <select
                        value={destinationCity}
                        onChange={(e) => setDestinationCity(e.target.value as any)}
                        className="w-full px-3 py-2 bg-white rounded-xl border-2 border-slate-900 text-xs font-bold text-slate-900 outline-none shadow-[1.5px_1.5px_0px_#0f172a]"
                      >
                        <option value="Jakarta">DKI Jakarta (Jabodetabek)</option>
                        <option value="Bandung">Bandung, Jawa Barat</option>
                        <option value="Surabaya">Surabaya, Jawa Timur</option>
                        <option value="Yogyakarta">DI Yogyakarta</option>
                        <option value="Bali">Denpasar, Bali</option>
                        <option value="Medan">Medan, Sumatera Utara</option>
                      </select>

                      {/* Courier Selector */}
                      <div className="space-y-1.5">
                        <span className="text-[10.5px] font-black uppercase text-slate-700">Pilih Opsi Kurir Ekspedisi:</span>
                        <div className="grid grid-cols-2 gap-2">
                          {(Object.keys(COURIER_OPTIONS) as Array<keyof typeof COURIER_OPTIONS>).map((ck) => {
                            const c = COURIER_OPTIONS[ck];
                            const rate = calculateOngkir(ck, destinationCity);
                            const isSelected = selectedCourier === ck;
                            return (
                              <button
                                key={ck}
                                type="button"
                                onClick={() => setSelectedCourier(ck)}
                                className={`p-2 rounded-xl text-left border-2 border-slate-900 transition text-xs ${
                                  isSelected
                                    ? 'bg-[#FEF08A] shadow-[2px_2px_0px_#0f172a] scale-102 font-black'
                                    : 'bg-white hover:bg-slate-50 font-bold text-slate-700'
                                }`}
                              >
                                <p className="text-[11px] font-black text-slate-900">{c.name}</p>
                                <div className="flex justify-between items-center text-[10px] mt-0.5 text-slate-600">
                                  <span>{c.days}</span>
                                  <span className="font-mono font-black text-slate-900">Rp {rate.toLocaleString('id-ID')}</span>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Midtrans Payment Method Selector */}
                  <div className="space-y-2">
                    <span className="text-xs font-black uppercase text-slate-900 flex items-center gap-1.5">
                      <CreditCard className="w-3.5 h-3.5 text-purple-700" />
                      <span>Metode Pembayaran (Midtrans Gateway)</span>
                    </span>

                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: 'QRIS', label: 'QRIS Real-Time', icon: '📱' },
                        { id: 'GOPAY', label: 'GoPay / e-Wallet', icon: '🟢' },
                        { id: 'BCA_VA', label: 'BCA Virtual Acc', icon: '🏦' },
                        { id: 'MANDIRI_VA', label: 'Mandiri VA', icon: '🏛️' },
                        { id: 'CREDIT_CARD', label: 'Kartu Kredit', icon: '💳' },
                        { id: 'AI_CREDITS', label: `AI Credits (${userCredits})`, icon: '🪙' },
                      ].map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => setPaymentMethod(m.id as any)}
                          className={`p-2 rounded-xl border-2 border-slate-900 text-left transition ${
                            paymentMethod === m.id
                              ? 'bg-[#BAE6FD] shadow-[2px_2px_0px_#0f172a] font-black'
                              : 'bg-white hover:bg-slate-50 font-bold text-slate-700'
                          }`}
                        >
                          <span className="text-xs block">{m.icon}</span>
                          <span className="text-[10px] leading-tight block mt-0.5">{m.label}</span>
                        </button>
                      ))}
                    </div>

                    {/* QRIS Interactive Display */}
                    {paymentMethod === 'QRIS' && (
                      <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 flex flex-col items-center text-center space-y-2">
                        <div className="p-2 bg-slate-900 rounded-xl">
                          {/* Stylized QRIS QR Matrix */}
                          <div className="w-32 h-32 bg-white p-2 rounded-lg flex flex-col items-center justify-center border border-slate-300">
                            <QrCode className="w-24 h-24 text-slate-900" />
                          </div>
                        </div>
                        <p className="text-[10px] font-bold text-slate-600">
                          Scan dengan BCA, GoPay, OVO, ShopeePay, Dana, atau Livin&apos;
                        </p>
                      </div>
                    )}

                    {paymentMethod === 'BCA_VA' && (
                      <div className="p-3 rounded-xl bg-slate-50 border-2 border-slate-900 text-xs flex justify-between items-center">
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold">Nomor BCA Virtual Account:</p>
                          <p className="font-mono font-black text-sm text-slate-900">88012 0891 2938 12</p>
                        </div>
                        <button
                          onClick={() => {
                            if (navigator.clipboard) navigator.clipboard.writeText('880120891293812');
                            showToast('Nomor VA BCA disalin!');
                          }}
                          className="px-2.5 py-1 rounded-lg bg-white border border-slate-900 font-black text-[10px]"
                        >
                          Salin VA
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Payment Breakdown calculation */}
                  <div className="p-3 rounded-2xl bg-slate-100 border-2 border-slate-900 text-xs space-y-1">
                    <div className="flex justify-between text-slate-600 font-semibold">
                      <span>Harga Produk:</span>
                      <span className="font-mono">Rp {checkoutProduct.priceIdr.toLocaleString('id-ID')}</span>
                    </div>
                    {checkoutProduct.type === 'PHYSICAL' && (
                      <div className="flex justify-between text-slate-600 font-semibold">
                        <span>Ongkos Kirim ({destinationCity}):</span>
                        <span className="font-mono">
                          Rp {calculateOngkir(selectedCourier, destinationCity).toLocaleString('id-ID')}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between text-slate-600 font-semibold">
                      <span>Biaya Layanan Midtrans:</span>
                      <span className="font-mono">Rp 2.000</span>
                    </div>
                    <div className="flex justify-between text-slate-900 font-black text-sm border-t border-slate-300 pt-1.5 mt-1">
                      <span>Total Tagihan:</span>
                      <span className="font-mono text-emerald-800">
                        {paymentMethod === 'AI_CREDITS' 
                          ? `${checkoutProduct.priceCredits} AI Credits` 
                          : `Rp ${(checkoutProduct.priceIdr + (checkoutProduct.type === 'PHYSICAL' ? calculateOngkir(selectedCourier, destinationCity) : 0) + 2000).toLocaleString('id-ID')}`
                        }
                      </span>
                    </div>
                  </div>

                  {/* Midtrans Pay Button */}
                  <button
                    onClick={handleProcessPayment}
                    disabled={isPaymentProcessing}
                    className="w-full py-3 px-4 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <span>{isPaymentProcessing ? 'Memverifikasi Pembayaran Midtrans...' : 'Bayar Sekarang (Simulasi Midtrans)'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Floating Marketplace Toast */}
      {toastMsg && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl bg-slate-900 text-white text-xs font-bold border-2 border-slate-700 shadow-xl flex items-center gap-2">
          <span>✨</span>
          <span>{toastMsg}</span>
        </div>
      )}

    </div>
  );
}
