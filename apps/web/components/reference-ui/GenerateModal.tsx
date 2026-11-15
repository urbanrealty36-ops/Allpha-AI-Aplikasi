'use client';

import React, { useState } from 'react';
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
export type GenerateContentType = 'REELS_BRAND' | 'FEED_POST' | 'DOCUMENT_PROPOSAL' | 'CAMPAIGN_SUITE';

export interface GenerateRequest {
  contentType: GenerateContentType;
  brandName: string;
  productDetails: string;
  brief: string;
}

const BRIEF_PRESETS: Array<{ id: string; label: string; contentType: GenerateContentType; brief: string }> = [
  {
    id: "food-beverage",
    label: "F&B / Kuliner",
    contentType: "REELS_BRAND",
    brief: "Buat konsep konten yang menonjolkan keunggulan produk, bahan atau proses utama, pengalaman pelanggan, dan ajakan bertindak yang jelas. Jangan mengarang klaim kualitas, sertifikasi, harga, atau testimoni.",
  },
  {
    id: "fashion-lifestyle",
    label: "Fashion / Lifestyle",
    contentType: "CAMPAIGN_SUITE",
    brief: "Susun konsep kampanye yang menampilkan desain, material, detail penggunaan, manfaat yang dapat dibuktikan, variasi konten, dan ajakan bertindak. Gunakan hanya informasi produk yang saya berikan.",
  },
  {
    id: "digital-spatial",
    label: "Digital / 3D",
    contentType: "FEED_POST",
    brief: "Buat konsep konten digital atau 3D yang menjelaskan use-case, fitur utama, konteks penggunaan, manfaat, dan arahan visual. Hindari klaim performa atau kompatibilitas yang belum saya berikan.",
  },
];

interface GenerateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (request: GenerateRequest) => Promise<string | null>;
  canCancelGeneration: boolean;
  onCancelGeneration: () => Promise<{ status?: string }>;
  directMessageAvailable: boolean;
  onOpenDirectMessage: () => void;
  artifactDeleteAvailable: boolean;
  artifactDeleting: boolean;
  onDeleteArtifact: () => Promise<{ status?: string }>;
}

export default function GenerateModal({ isOpen, onClose, onGenerate, canCancelGeneration, onCancelGeneration, directMessageAvailable, onOpenDirectMessage, artifactDeleteAvailable, artifactDeleting, onDeleteArtifact }: GenerateModalProps) {
  const [contentType, setContentType] = useState<GenerateContentType>('REELS_BRAND');
  const [brandName, setBrandName] = useState('');
  const [productDetails, setProductDetails] = useState('');
  const [customBrief, setCustomBrief] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (isLoading || !brandName.trim() || !productDetails.trim() || !customBrief.trim()) return;
    setIsLoading(true);
    setResult(null);
    setError('');
    setNotice('');
    try {
      const output = await onGenerate({
        contentType,
        brandName: brandName.trim(),
        productDetails: productDetails.trim(),
        brief: customBrief.trim(),
      });
      if (output) {
        setResult(output);
        setNotice('Job selesai. Artefak privat dan pengiriman DM mengikuti konfirmasi backend.');
      } else {
        setNotice('Job belum menghasilkan artefak yang dapat ditampilkan. Periksa status Generation Job; permintaan tidak dikirim ulang otomatis.');
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Generation tidak dapat diselesaikan.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelGeneration = async () => {
    if (!isLoading || !canCancelGeneration || isCancelling) return;
    setIsCancelling(true);
    setError('');
    try {
      const cancellation = await onCancelGeneration();
      setNotice(cancellation.status === 'cancelled'
        ? 'Antrean berhasil dibatalkan sebelum worker memanggil provider. Reservasi dilepas sesuai policy aktif.'
        : 'Permintaan pembatalan tercatat, tetapi policy belum mengizinkan pelepasan reservasi. Saldo menunggu rekonsiliasi.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Pembatalan antrean tidak dapat dikonfirmasi.');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleCopyResult = () => {
    if (result) {
      navigator.clipboard.writeText(result);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2500);
    }
  };

  const handleDeleteArtifact = async () => {
    if (!artifactDeleteAvailable || artifactDeleting || isLoading) return;
    if (!window.confirm('Hapus artefak privat ini? URL baru akan diblokir; URL sementara yang sudah diterbitkan dapat berlaku sampai 60 detik atau sampai objek Storage dihapus.')) return;
    setError('');
    try {
      const deletion = await onDeleteArtifact();
      setResult(null);
      setNotice(deletion.status === 'dead'
        ? 'Job penghapusan membutuhkan pemulihan operator. Artefak tetap privat; hubungi dukungan Allpha.'
        : deletion.status === 'succeeded'
          ? 'Artefak privat sudah dihapus.'
          : 'Permintaan penghapusan diterima. URL baru diblokir; URL lama berakhir maksimal 60 detik atau saat objek Storage dihapus.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Penghapusan artefak belum dapat dikonfirmasi.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-[6px_6px_0px_#0f172a] border-2 border-slate-900 p-5 max-h-[92vh] overflow-y-auto space-y-4">
        {/* Modal Top Header */}
        <div className="flex items-center justify-between pb-3.5 border-b-2 border-slate-900">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-purple-300 border-2 border-slate-900 text-slate-950 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
              <Wand2 className="w-5 h-5 stroke-[2.5px]" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 tracking-tight">
                AI Content & Reels Studio
              </h2>
              <p className="text-[11px] font-semibold text-slate-600">
                Generation memakai Agent, Skill, Knowledge, dan Model Router yang dipilih pada halaman sebelumnya.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 text-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            <X className="w-4 h-4 stroke-[2.5px]" />
          </button>
        </div>

        {/* Target Content Type Segmented Tabs */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-black text-slate-800 uppercase tracking-wider">Pilih Jenis Konten yang Ingin Digenerate:</label>
          <div className="grid grid-cols-2 gap-2 p-1.5 rounded-2xl bg-slate-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-black">
            <button
              onClick={() => setContentType('REELS_BRAND')}
              className={`py-2 px-2.5 rounded-xl transition flex items-center justify-center gap-1.5 text-center cursor-pointer ${
                contentType === 'REELS_BRAND'
                  ? 'bg-purple-300 text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'text-slate-700 hover:text-slate-950'
              }`}
            >
              <Film className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Reels Dengan Brand</span>
            </button>
            <button
              onClick={() => setContentType('FEED_POST')}
              className={`py-2 px-2.5 rounded-xl transition flex items-center justify-center gap-1.5 text-center cursor-pointer ${
                contentType === 'FEED_POST'
                  ? 'bg-purple-300 text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'text-slate-700 hover:text-slate-950'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Draf Feed & 3D</span>
            </button>
            <button
              onClick={() => setContentType('DOCUMENT_PROPOSAL')}
              className={`py-2 px-2.5 rounded-xl transition flex items-center justify-center gap-1.5 text-center cursor-pointer ${
                contentType === 'DOCUMENT_PROPOSAL'
                  ? 'bg-purple-300 text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'text-slate-700 hover:text-slate-950'
              }`}
            >
              <FileText className="w-3.5 h-3.5 shrink-0 stroke-[2.5px]" />
              <span className="truncate">Dokumen & Proposal</span>
            </button>
            <button
              onClick={() => setContentType('CAMPAIGN_SUITE')}
              className={`py-2 px-2.5 rounded-xl transition flex items-center justify-center gap-1.5 text-center cursor-pointer ${
                contentType === 'CAMPAIGN_SUITE'
                  ? 'bg-purple-300 text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'text-slate-700 hover:text-slate-950'
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
            Generation memakai Agent, Skill, Knowledge, tarif dan Model Router yang disetujui. AI Credits baru direservasi setelah quote backend dikonfirmasi; reward pemilik Agent hanya berlaku jika policy reward disetujui.
          </p>
        </div>

        {/* Reference quick-preset composition adapted as reusable prompt templates, not seeded business identities. */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-black text-slate-900">Template Brief Kreatif:</span>
            <span className="text-slate-500 font-bold">1-Klik Isi Brief</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
            {BRIEF_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                title="Mengisi template brief; tidak membuat atau menyimpan data bisnis."
                aria-pressed={customBrief === preset.brief}
                onClick={() => {
                  setContentType(preset.contentType);
                  setCustomBrief(preset.brief);
                }}
                className="shrink-0 px-3 py-1.5 rounded-2xl border-2 border-slate-900 bg-amber-50 hover:bg-amber-100 text-xs font-black text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-2 cursor-pointer"
              >
                <Palette className="w-4 h-4" />
                <span className="truncate max-w-[130px]">{preset.label}</span>
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

          {/* Reference GenerateModal media-picker composition; controls stay disabled until
              a quarantined, scanned and capability-matched generation input contract exists. */}
          <div className="p-4 rounded-3xl bg-purple-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-3">
            <h3 className="font-black text-xs text-slate-950 flex items-center gap-1.5">
              <Upload className="w-4 h-4 text-purple-700 stroke-[2.5px]" />
              <span>Unggah Aset Visual Logo & Produk (Image / Video)</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                <span className="font-black text-[11px] text-slate-950">1. Logo Brand:</span>
                <div className="text-center py-3 text-slate-400">
                  <ImageIcon className="w-6 h-6 mx-auto mb-1 opacity-50" />
                  <p className="text-[10px] font-bold">Belum ada logo dipilih</p>
                </div>
                <input type="file" accept="image/*" disabled className="hidden" aria-label="Pilih logo brand" />
                <button type="button" disabled title="Upload belum tersedia pada Generation Input API" className="w-full py-2 rounded-xl border-2 border-slate-900 bg-purple-100 text-purple-950 text-[10px] font-black shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center gap-1.5 cursor-not-allowed opacity-60">
                  <Upload className="w-3.5 h-3.5 stroke-[2.5px]" />
                  <span>Pilih File Logo (JPG/PNG)</span>
                </button>
              </div>

              <div className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                <span className="font-black text-[11px] text-slate-950">2. Aset Produk:</span>
                <div className="text-center py-3 text-slate-400">
                  <Video className="w-6 h-6 mx-auto mb-1 opacity-50" />
                  <p className="text-[10px] font-bold">Belum ada produk dipilih</p>
                </div>
                <input type="file" accept="image/*,video/*" disabled className="hidden" aria-label="Pilih aset produk" />
                <button type="button" disabled title="Upload belum tersedia pada Generation Input API" className="w-full py-2 rounded-xl border-2 border-slate-900 bg-cyan-100 text-cyan-950 text-[10px] font-black shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center gap-1.5 cursor-not-allowed opacity-60">
                  <Upload className="w-3.5 h-3.5 stroke-[2.5px]" />
                  <span>Pilih File Produk (Foto/Video)</span>
                </button>
              </div>
            </div>

            <div className="flex items-start gap-2 p-2.5 rounded-2xl bg-purple-100 border-2 border-slate-900 text-purple-950 text-[11px] shadow-2xs font-semibold">
              <Sparkles className="w-4 h-4 text-purple-800 shrink-0 stroke-[2.5px]" />
              <span><strong>AI Vision Engine belum aktif:</strong> media hanya dapat diaktifkan setelah tersedia input snapshot privat, scanning/quarantine, izin penggunaan dan Model Router dengan capability image/video yang disetujui. File lokal tidak akan dianggap tersimpan atau dibaca AI.</span>
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

          {error && <p role="alert" className="rounded-xl border-2 border-rose-500 bg-rose-50 p-3 text-[11px] font-bold text-rose-800">{error}</p>}
        {notice && <p role="status" className="rounded-xl border-2 border-emerald-500 bg-emerald-50 p-3 text-[11px] font-bold text-emerald-900">{notice}</p>}

        {/* Action Button */}
          <button
            onClick={handleGenerate}
            disabled={isLoading || !brandName.trim() || !productDetails.trim() || !customBrief.trim()}
            className="w-full py-3 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? (
              <>
                <Sparkles className="w-4 h-4 animate-spin stroke-[2.5px]" />
                <span>AI Agent sedang memproses Generation Job...</span>
              </>
            ) : (
              <>
                <Wand2 className="w-4 h-4 stroke-[2.5px]" />
                <span>Minta Quote & Generate</span>
              </>
            )}
          </button>
          {isLoading && canCancelGeneration && <button type="button" onClick={() => void handleCancelGeneration()} disabled={isCancelling} className="w-full py-2.5 rounded-2xl bg-rose-100 hover:bg-rose-200 text-rose-900 font-black text-xs border-2 border-rose-700 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{isCancelling ? 'Membatalkan antrean…' : 'Batalkan antrean sebelum diproses'}</button>}
        </div>

        {/* Generated Result Output */}
        {result && (
          <div className="pt-3 border-t-2 border-slate-900 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-black text-slate-900 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 stroke-[2.5px]" />
                <span>Draft Teks Generation Selesai</span>
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
                    <Copy className="w-3 h-3 stroke-[2.5px]" />
                    <span>Salin Teks</span>
                  </>
                )}
              </button>
            </div>

            <p className="rounded-xl border border-sky-300 bg-sky-50 px-3 py-2 text-[11px] font-semibold text-sky-900">Output jalur ini adalah draft teks yang dihasilkan melalui Model Router. File gambar/video final belum dibuat oleh Generation Job ini.</p>
            <div className="p-4 rounded-2xl bg-slate-950 text-cyan-200 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
              {result}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={onOpenDirectMessage}
                disabled={!directMessageAvailable}
                className="min-w-0 flex-1 py-2.5 rounded-2xl bg-emerald-300 hover:bg-emerald-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>{directMessageAvailable ? 'Buka Direct Message' : 'DM belum dikonfirmasi'}</span>
              </button>
              <button
                onClick={() => { setResult(null); handleGenerate(); }}
                disabled={isLoading || artifactDeleting}
                className="px-4 py-2.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer disabled:opacity-50"
              >
                Generate Ulang
              </button>
              {artifactDeleteAvailable && <button
                type="button"
                onClick={() => void handleDeleteArtifact()}
                disabled={artifactDeleting || isLoading}
                className="w-full py-2.5 rounded-2xl bg-rose-100 hover:bg-rose-200 text-rose-900 font-black text-xs border-2 border-rose-700 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50"
              >
                <span className="inline-flex items-center justify-center gap-1.5"><Trash2 className="h-3.5 w-3.5"/>{artifactDeleting ? 'Menghapus…' : 'Hapus artefak privat'}</span>
              </button>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
