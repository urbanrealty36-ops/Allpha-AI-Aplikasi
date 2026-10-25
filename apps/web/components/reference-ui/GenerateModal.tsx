'use client';

import React, { useState, useRef } from 'react';
import { 
  Wand2, 
  Sparkles, 
  X, 
  Film, 
  Image as ImageIcon, 
  CheckCircle2, 
  FileText,
  Upload,
  Video,
  Copy,
  Check,
  Download,
  Send,
  Layers,
  Palette,
  Eye,
  Trash2
} from 'lucide-react';
import { PostItem } from '@/lib/store';

interface GenerateModalProps {
  isOpen: boolean;
  onClose: () => void;
  contextPost: PostItem | null;
  onRewardTriggered: (brandName: string, query: string) => void;
}

type ContentType = 'REELS_BRAND' | 'FEED_POST' | 'DOCUMENT_PROPOSAL' | 'CAMPAIGN_SUITE';

interface BrandPreset {
  name: string;
  product: string;
  logoUrl: string;
  productUrl: string;
  color: string;
}

const PRESET_BRANDS: BrandPreset[] = [
  {
    name: 'Kopi Nusantara Artisan',
    product: 'Cold Brew Kemasan Ramah Lingkungan 250ml',
    logoUrl: 'https://picsum.photos/seed/kopi-logo/150/150',
    productUrl: 'https://picsum.photos/seed/kopi-product/300/300',
    color: '#D97706',
  },
  {
    name: 'GlowWear Cybertech',
    product: 'Jaket Armor Cyberpunk dengan Neon Glow 3D',
    logoUrl: 'https://picsum.photos/seed/glow-logo/150/150',
    productUrl: 'https://picsum.photos/seed/glow-jacket/300/300',
    color: '#06B6D4',
  },
  {
    name: 'Spatial Studio 3D',
    product: 'Asset Pack Modeling Virtual Worlds & District',
    logoUrl: 'https://picsum.photos/seed/spatial-logo/150/150',
    productUrl: 'https://picsum.photos/seed/spatial-city/300/300',
    color: '#9333EA',
  },
];

export default function GenerateModal({
  isOpen,
  onClose,
  contextPost,
  onRewardTriggered,
}: GenerateModalProps) {
  const [contentType, setContentType] = useState<ContentType>('REELS_BRAND');
  const [brandName, setBrandName] = useState('Brand Studio Saya');
  const [productDetails, setProductDetails] = useState('Solusi Kreatif Digital');
  const [customBrief, setCustomBrief] = useState('');
  
  // Media Assets State
  const [logoMedia, setLogoMedia] = useState<{ url: string; name: string; type: 'image' | 'video' } | null>({
    url: 'https://picsum.photos/seed/default-brand-logo/150/150',
    name: 'logo_brand_vector.png',
    type: 'image',
  });
  const [productMedia, setProductMedia] = useState<{ url: string; name: string; type: 'image' | 'video' } | null>({
    url: 'https://picsum.photos/seed/product-asset-demo/300/300',
    name: 'product_showcase.jpg',
    type: 'image',
  });

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  const logoInputRef = useRef<HTMLInputElement>(null);
  const productInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  // Handle Logo Upload from Local Device
  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const isVideo = file.type.startsWith('video');
      const reader = new FileReader();
      reader.onload = (event) => {
        setLogoMedia({
          url: event.target?.result as string,
          name: file.name,
          type: isVideo ? 'video' : 'image',
        });
      };
      reader.readAsDataURL(file);
    }
  };

  // Handle Product Upload from Local Device
  const handleProductUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const isVideo = file.type.startsWith('video');
      const reader = new FileReader();
      reader.onload = (event) => {
        setProductMedia({
          url: event.target?.result as string,
          name: file.name,
          type: isVideo ? 'video' : 'image',
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleApplyPreset = (preset: BrandPreset) => {
    setBrandName(preset.name);
    setProductDetails(preset.product);
    setLogoMedia({
      url: preset.logoUrl,
      name: `${preset.name.toLowerCase().replace(/\s+/g, '_')}_logo.png`,
      type: 'image',
    });
    setProductMedia({
      url: preset.productUrl,
      name: `${preset.name.toLowerCase().replace(/\s+/g, '_')}_product.jpg`,
      type: 'image',
    });
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    setResult(null);

    const query = customBrief || `Generate konten ${contentType} dengan branding ${brandName} dan produk ${productDetails}.`;

    try {
      const res = await fetch('/api/agent/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'brand_reels',
          contentType,
          agentName: contextPost?.aiAgent.name || 'Luna AI',
          agentSpecialty: contextPost?.aiAgent.specialty || 'Kreativitas & Desain 3D',
          humanOwner: contextPost?.humanOwner.name || 'Alex Tamara',
          userQuestion: query,
          brandName,
          productDetails,
          logoName: logoMedia?.name || '',
          hasLogo: !!logoMedia,
          hasProductMedia: !!productMedia,
          context: contextPost?.content,
        }),
      });

      const data = await res.json();
      setResult(data.text);
      onRewardTriggered(brandName, query);
    } catch {
      setResult(`✨ Konten berhasil digenerate oleh AI Agent dengan branding ${brandName}. File siap dikirimkan ke Direct Message.`);
      onRewardTriggered(brandName, query);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyResult = () => {
    if (result) {
      navigator.clipboard.writeText(result);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2500);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-[6px_6px_0px_#0f172a] border-2 border-slate-900 p-5 max-h-[92vh] overflow-y-auto space-y-4">
        {/* Modal Top Header */}
        <div className="flex items-center justify-between pb-3.5 border-b-2 border-slate-900">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-purple-300 border-2 border-slate-900 text-slate-950 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
              <Wand2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 tracking-tight">
                AI Content & Reels Studio
              </h2>
              <p className="text-[11px] font-semibold text-slate-600">
                Didukung oleh {contextPost?.aiAgent.name || 'Luna AI'} (Milik @{contextPost?.humanOwner.handle || 'alextamara'})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 text-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Target Content Type Segmented Tabs */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-black text-slate-800 uppercase tracking-wider">Pilih Jenis Konten yang Ingin Digenerate:</label>
          <div className="grid grid-cols-2 gap-2 p-1.5 rounded-2xl bg-slate-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-black">
            <button
              onClick={() => setContentType('REELS_BRAND')}
              className={`py-2 px-2 rounded-xl transition flex items-center justify-center gap-1.5 text-center ${
                contentType === 'REELS_BRAND'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Film className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Reels Dengan Brand</span>
            </button>
            <button
              onClick={() => setContentType('FEED_POST')}
              className={`py-2 px-2 rounded-xl transition flex items-center justify-center gap-1.5 text-center ${
                contentType === 'FEED_POST'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Draf Feed & 3D</span>
            </button>
            <button
              onClick={() => setContentType('DOCUMENT_PROPOSAL')}
              className={`py-2 px-2 rounded-xl transition flex items-center justify-center gap-1.5 text-center ${
                contentType === 'DOCUMENT_PROPOSAL'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileText className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Dokumen & Proposal</span>
            </button>
            <button
              onClick={() => setContentType('CAMPAIGN_SUITE')}
              className={`py-2 px-2 rounded-xl transition flex items-center justify-center gap-1.5 text-center ${
                contentType === 'CAMPAIGN_SUITE'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Layers className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Campaign Suite</span>
            </button>
          </div>
        </div>

        {/* Challenge & AI Credit Notice */}
        <div className="p-3.5 rounded-2xl bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-900 text-xs leading-relaxed space-y-1">
          <p className="font-black flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-purple-700 stroke-[2.5px]" />
            <span>Mekanisme Challenge & Transfer Kredit:</span>
          </p>
          <p className="text-[11px] font-medium text-slate-700">
            AI Agent akan mempelajari Nama Brand, Logo, dan Aset Produk yang Anda unggah, lalu menghasilkan skrip video reels, draf postingan, atau proposal yang selaras dengan identitas brand Anda. Sesi ini memotong 15 AI Credits Anda dan mentransfernya ke pemilik AI Agent.
          </p>
        </div>

        {/* Quick Brand Preset Shortcuts */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-black text-slate-900">Contoh Cepat (Klik untuk Pasang):</span>
            <span className="text-slate-500 font-bold">Preset Brand</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
            {PRESET_BRANDS.map((b) => (
              <button
                key={b.name}
                type="button"
                onClick={() => handleApplyPreset(b)}
                className="shrink-0 px-3 py-1.5 rounded-2xl border-2 border-slate-900 bg-amber-50 hover:bg-amber-100 text-xs font-black text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-2 cursor-pointer"
              >
                <img src={b.logoUrl} alt={b.name} className="w-5 h-5 rounded-full object-cover border border-slate-900" />
                <span className="truncate max-w-[130px]">{b.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Form Inputs */}
        <div className="space-y-3.5 text-xs">
          <div>
            <label className="block text-slate-900 font-black mb-1">
              Nama Brand / Bisnis Anda:
            </label>
            <input
              type="text"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Contoh: Kopi Nusantara / GlowWear"
              className="w-full px-3.5 py-2.5 bg-slate-50 border-2 border-slate-900 rounded-2xl outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-white transition font-bold text-slate-950"
            />
          </div>

          <div>
            <label className="block text-slate-900 font-black mb-1">
              Detail Produk / Aset Jasa yang Dipromosikan:
            </label>
            <input
              type="text"
              value={productDetails}
              onChange={(e) => setProductDetails(e.target.value)}
              placeholder="Contoh: Cold Brew Artisan / Jaket Cybernetic 3D"
              className="w-full px-3.5 py-2.5 bg-slate-50 border-2 border-slate-900 rounded-2xl outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-white transition font-bold text-slate-950"
            />
          </div>

          {/* ======================================================== */}
          {/* UPLOAD LOGO & PRODUCT ASSET (IMAGE OR VIDEO)            */}
          {/* ======================================================== */}
          <div className="p-4 rounded-3xl bg-purple-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3">
            <h3 className="font-black text-xs text-slate-950 flex items-center gap-1.5">
              <Upload className="w-4 h-4 text-purple-700 stroke-[2.5px]" />
              <span>Unggah Aset Visual Logo & Produk (Image / Video)</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* 1. LOGO ASSET PICKER */}
              <div className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-black text-[11px] text-slate-950">1. Logo Brand:</span>
                  {logoMedia && (
                    <button
                      onClick={() => setLogoMedia(null)}
                      className="text-slate-500 hover:text-rose-600 transition cursor-pointer"
                      title="Hapus Logo"
                    >
                      <Trash2 className="w-3.5 h-3.5 stroke-[2.5px]" />
                    </button>
                  )}
                </div>

                {logoMedia ? (
                  <div className="flex items-center gap-2.5 p-1.5 rounded-lg bg-slate-50 border border-slate-100">
                    <img
                      src={logoMedia.url}
                      alt="Logo Brand"
                      className="w-10 h-10 rounded-xl object-cover border border-slate-900 shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-black text-slate-950 truncate">
                        {logoMedia.name}
                      </p>
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-200 border border-slate-900 text-purple-950 font-black">
                        {logoMedia.type === 'video' ? 'Video Logo' : 'Logo Terverifikasi'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-3 text-slate-400">
                    <ImageIcon className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p className="text-[10px] font-bold">Belum ada logo dipilih</p>
                  </div>
                )}

                <input
                  ref={logoInputRef}
                  type="file"
                  accept="image/*,video/*"
                  onChange={handleLogoUpload}
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={() => logoInputRef.current?.click()}
                  className="w-full py-2 rounded-xl border-2 border-slate-900 bg-purple-100 hover:bg-purple-200 text-purple-950 text-[10px] font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Upload className="w-3 h-3" />
                  <span>Pilih File Logo (JPG/PNG/MP4)</span>
                </button>
              </div>

              {/* 2. PRODUCT ASSET PICKER */}
              <div className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-black text-[11px] text-slate-950">2. Aset Produk:</span>
                  {productMedia && (
                    <button
                      onClick={() => setProductMedia(null)}
                      className="text-slate-500 hover:text-rose-600 transition cursor-pointer"
                      title="Hapus Aset Produk"
                    >
                      <Trash2 className="w-3.5 h-3.5 stroke-[2.5px]" />
                    </button>
                  )}
                </div>

                {productMedia ? (
                  <div className="flex items-center gap-2.5 p-1.5 rounded-lg bg-slate-50 border border-slate-100">
                    <img
                      src={productMedia.url}
                      alt="Produk"
                      className="w-10 h-10 rounded-xl object-cover border border-slate-900 shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-black text-slate-950 truncate">
                        {productMedia.name}
                      </p>
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-cyan-200 border border-slate-900 text-cyan-950 font-black">
                        {productMedia.type === 'video' ? 'Video Produk' : 'Foto Produk Siap'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-3 text-slate-400">
                    <Video className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p className="text-[10px] font-bold">Belum ada produk dipilih</p>
                  </div>
                )}

                <input
                  ref={productInputRef}
                  type="file"
                  accept="image/*,video/*"
                  onChange={handleProductUpload}
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={() => productInputRef.current?.click()}
                  className="w-full py-2 rounded-xl border-2 border-slate-900 bg-cyan-100 hover:bg-cyan-200 text-cyan-950 text-[10px] font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Upload className="w-3 h-3" />
                  <span>Pilih File Produk (Foto/Video)</span>
                </button>
              </div>
            </div>

            {/* AI Vision Badge */}
            <div className="flex items-center gap-2 p-2.5 rounded-2xl bg-purple-100 border-2 border-slate-900 text-purple-950 text-[11px] shadow-2xs font-semibold">
              <Sparkles className="w-4 h-4 text-purple-800 shrink-0 stroke-[2.5px]" />
              <span>
                <strong>AI Vision Engine:</strong> AI Agent membaca logo, nama brand, dan aset produk untuk disematkan otomatis ke naskah dan draf konten.
              </span>
            </div>
          </div>

          <div>
            <label className="block text-slate-900 font-black mb-1">
              Catatan / Brief Khusus (Opsional):
            </label>
            <textarea
              rows={2}
              value={customBrief}
              onChange={(e) => setCustomBrief(e.target.value)}
              placeholder="Contoh: Berikan nuansa futuristik dengan pencahayaan neon cyan dan sertakan ajakan mengunjungi booth 3D."
              className="w-full px-3.5 py-2.5 bg-slate-50 border-2 border-slate-900 rounded-2xl outline-none shadow-[2px_2px_0px_#0f172a] focus:bg-white transition resize-none font-bold text-slate-950"
            />
          </div>

          {/* Action Button */}
          <button
            onClick={handleGenerate}
            disabled={isLoading || !brandName}
            className="w-full py-3 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? (
              <>
                <Sparkles className="w-4 h-4 animate-spin stroke-[2.5px]" />
                <span>AI Agent Sedang Menganalisis Logo & Menulis Konten...</span>
              </>
            ) : (
              <>
                <Wand2 className="w-4 h-4" />
                <span>Generate & Kirim File ke DM (-15 Cr)</span>
              </>
            )}
          </button>
        </div>

        {/* Generated Result Output */}
        {result && (
          <div className="pt-3 border-t-2 border-slate-900 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-black text-slate-900 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 stroke-[2.5px]" />
                <span>Hasil Generate Konten & Branding Selesai</span>
              </h4>
              <button
                onClick={handleCopyResult}
                className="px-3 py-1.5 rounded-xl bg-amber-100 hover:bg-amber-200 text-slate-950 border-2 border-slate-900 text-[11px] font-black shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
              >
                {isCopied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-700 stroke-[3px]" />
                    <span>Tersalin!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Salin Teks</span>
                  </>
                )}
              </button>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950 text-cyan-200 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
              {result}
            </div>

            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="flex-1 py-2.5 rounded-2xl bg-emerald-300 hover:bg-emerald-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>Buka di Direct Message</span>
              </button>
              <button
                onClick={() => {
                  setResult(null);
                  handleGenerate();
                }}
                className="px-4 py-2.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Generate Ulang
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
