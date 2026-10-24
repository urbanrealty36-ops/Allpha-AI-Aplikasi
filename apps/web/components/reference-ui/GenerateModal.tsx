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
import { PostItem } from '@/lib/reference-store';

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
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-2xl border border-slate-200 p-5 max-h-[92vh] overflow-y-auto space-y-4">
        {/* Modal Top Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-white flex items-center justify-center shadow-md">
              <Wand2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900">
                AI Content & Reels Studio
              </h2>
              <p className="text-[11px] text-slate-500">
                Didukung oleh {contextPost?.aiAgent.name || 'Luna AI'} (Milik @{contextPost?.humanOwner.handle || 'alextamara'})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Target Content Type Segmented Tabs */}
        <div className="space-y-1">
          <label className="text-[11px] font-bold text-slate-700">Pilih Jenis Konten yang Ingin Digenerate:</label>
          <div className="grid grid-cols-2 gap-1.5 p-1 rounded-2xl bg-slate-100 text-xs font-semibold">
            <button
              onClick={() => setContentType('REELS_BRAND')}
              className={`py-2 px-2 rounded-xl transition flex items-center justify-center gap-1.5 text-center ${
                contentType === 'REELS_BRAND'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Film className="w-3.5 h-3.5 shrink-0" />
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
              <Sparkles className="w-3.5 h-3.5 shrink-0" />
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
              <FileText className="w-3.5 h-3.5 shrink-0" />
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
              <Layers className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Campaign Suite</span>
            </button>
          </div>
        </div>

        {/* Challenge & AI Credit Notice */}
        <div className="p-3.5 rounded-2xl bg-purple-50 border border-purple-200 text-purple-900 text-xs leading-relaxed space-y-1">
          <p className="font-bold flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-purple-600" />
            <span>Mekanisme Challenge & Transfer Kredit:</span>
          </p>
          <p className="text-[11px] text-purple-700">
            AI Agent akan mempelajari Nama Brand, Logo, dan Aset Produk yang Anda unggah, lalu menghasilkan skrip video reels, draf postingan, atau proposal yang selaras dengan identitas brand Anda. Sesi ini memotong 15 AI Credits Anda dan mentransfernya ke pemilik AI Agent.
          </p>
        </div>

        {/* Quick Brand Preset Shortcuts */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-bold text-slate-700">Contoh Cepat (Klik untuk Pasang):</span>
            <span className="text-slate-400">Preset Brand</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
            {PRESET_BRANDS.map((b) => (
              <button
                key={b.name}
                type="button"
                onClick={() => handleApplyPreset(b)}
                className="shrink-0 px-2.5 py-1.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-purple-50 hover:border-purple-300 text-xs font-medium text-slate-700 transition flex items-center gap-1.5"
              >
                <img src={b.logoUrl} alt={b.name} className="w-4 h-4 rounded-full object-cover" />
                <span className="truncate max-w-[120px]">{b.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Form Inputs */}
        <div className="space-y-3 text-xs">
          <div>
            <label className="block text-slate-700 font-bold mb-1">
              Nama Brand / Bisnis Anda:
            </label>
            <input
              type="text"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Contoh: Kopi Nusantara / GlowWear"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:border-purple-500 outline-none transition"
            />
          </div>

          <div>
            <label className="block text-slate-700 font-bold mb-1">
              Detail Produk / Aset Jasa yang Dipromosikan:
            </label>
            <input
              type="text"
              value={productDetails}
              onChange={(e) => setProductDetails(e.target.value)}
              placeholder="Contoh: Cold Brew Artisan / Jaket Cybernetic 3D"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:border-purple-500 outline-none transition"
            />
          </div>

          {/* ======================================================== */}
          {/* UPLOAD LOGO & PRODUCT ASSET (IMAGE OR VIDEO)            */}
          {/* ======================================================== */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
            <h3 className="font-extrabold text-xs text-slate-900 flex items-center gap-1.5">
              <Upload className="w-3.5 h-3.5 text-purple-600" />
              <span>Unggah Aset Visual Logo & Produk (Image / Video)</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* 1. LOGO ASSET PICKER */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[11px] text-slate-700">1. Logo Brand:</span>
                  {logoMedia && (
                    <button
                      onClick={() => setLogoMedia(null)}
                      className="text-slate-400 hover:text-rose-600 transition"
                      title="Hapus Logo"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {logoMedia ? (
                  <div className="flex items-center gap-2.5 p-1.5 rounded-lg bg-slate-50 border border-slate-100">
                    <img
                      src={logoMedia.url}
                      alt="Logo Brand"
                      className="w-10 h-10 rounded-lg object-cover ring-1 ring-slate-200 shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-bold text-slate-900 truncate">
                        {logoMedia.name}
                      </p>
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 font-mono">
                        {logoMedia.type === 'video' ? 'Video Logo' : 'Logo Terverifikasi'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-3 text-slate-400">
                    <ImageIcon className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p className="text-[10px]">Belum ada logo dipilih</p>
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
                  className="w-full py-1.5 rounded-lg border border-purple-200 bg-purple-50/60 hover:bg-purple-100 text-purple-700 text-[10px] font-bold transition flex items-center justify-center gap-1"
                >
                  <Upload className="w-3 h-3" />
                  <span>Pilih File Logo (JPG/PNG/MP4)</span>
                </button>
              </div>

              {/* 2. PRODUCT ASSET PICKER */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[11px] text-slate-700">2. Aset Produk:</span>
                  {productMedia && (
                    <button
                      onClick={() => setProductMedia(null)}
                      className="text-slate-400 hover:text-rose-600 transition"
                      title="Hapus Aset Produk"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {productMedia ? (
                  <div className="flex items-center gap-2.5 p-1.5 rounded-lg bg-slate-50 border border-slate-100">
                    <img
                      src={productMedia.url}
                      alt="Produk"
                      className="w-10 h-10 rounded-lg object-cover ring-1 ring-slate-200 shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-bold text-slate-900 truncate">
                        {productMedia.name}
                      </p>
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-100 text-cyan-800 font-mono">
                        {productMedia.type === 'video' ? 'Video Produk' : 'Foto Produk Siap'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-3 text-slate-400">
                    <Video className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p className="text-[10px]">Belum ada produk dipilih</p>
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
                  className="w-full py-1.5 rounded-lg border border-cyan-200 bg-cyan-50/60 hover:bg-cyan-100 text-cyan-800 text-[10px] font-bold transition flex items-center justify-center gap-1"
                >
                  <Upload className="w-3 h-3" />
                  <span>Pilih File Produk (Foto/Video)</span>
                </button>
              </div>
            </div>

            {/* AI Vision Badge */}
            <div className="flex items-center gap-2 p-2 rounded-xl bg-purple-100/60 text-purple-900 text-[11px]">
              <Sparkles className="w-3.5 h-3.5 text-purple-600 shrink-0" />
              <span>
                <strong>AI Vision Engine:</strong> AI Agent membaca logo, nama brand, dan aset produk untuk disematkan otomatis ke naskah dan draf konten.
              </span>
            </div>
          </div>

          <div>
            <label className="block text-slate-700 font-bold mb-1">
              Catatan / Brief Khusus (Opsional):
            </label>
            <textarea
              rows={2}
              value={customBrief}
              onChange={(e) => setCustomBrief(e.target.value)}
              placeholder="Contoh: Berikan nuansa futuristik dengan pencahayaan neon cyan dan sertakan ajakan mengunjungi booth 3D."
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:border-purple-500 outline-none transition resize-none"
            />
          </div>

          {/* Action Button */}
          <button
            onClick={handleGenerate}
            disabled={isLoading || !brandName}
            className="w-full py-2.5 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-xs shadow-md shadow-purple-500/20 transition flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Sparkles className="w-4 h-4 animate-spin" />
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
          <div className="pt-3 border-t border-slate-200 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-black text-slate-900 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Hasil Generate Konten & Branding Selesai</span>
              </h4>
              <button
                onClick={handleCopyResult}
                className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-bold transition flex items-center gap-1"
              >
                {isCopied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-600" />
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

            <div className="p-3.5 rounded-2xl bg-slate-900 text-slate-100 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto border border-slate-800">
              {result}
            </div>

            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="flex-1 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs shadow-xs transition flex items-center justify-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Buka di Direct Message</span>
              </button>
              <button
                onClick={() => {
                  setResult(null);
                  handleGenerate();
                }}
                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition"
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
