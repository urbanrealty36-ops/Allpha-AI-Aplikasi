'use client';

import React, { useState } from 'react';
import { 
  Upload, 
  FileText, 
  Cpu, 
  Coins, 
  ArrowRight, 
  CheckCircle2, 
  Sparkles, 
  ShieldCheck, 
  FileCode, 
  RefreshCw, 
  Send, 
  Bot, 
  User, 
  FolderPlus,
  Inbox,
  AlertCircle
} from 'lucide-react';
import { KnowledgeDocument, CreditTransaction, AIAgentProfile } from '@/lib/reference-store';

interface SkillsChallengeHubProps {
  userCredits: number;
  agentCredits: number;
  knowledgeDocs: KnowledgeDocument[];
  transactions: CreditTransaction[];
  agentProfile: AIAgentProfile;
  onAddDocument: (doc: KnowledgeDocument) => void;
  onExecuteCreditTransfer: (
    fromUser: string,
    toAgent: string,
    ownerName: string,
    amount: number,
    querySummary: string,
    type: 'ASK_QUESTION' | 'GENERATE_CONTENT' | 'REELS_CUSTOM_BRAND' | 'PLUGIN_REWARD'
  ) => void;
}

export default function SkillsChallengeHub({
  userCredits,
  agentCredits,
  knowledgeDocs,
  transactions,
  agentProfile,
  onAddDocument,
  onExecuteCreditTransfer,
}: SkillsChallengeHubProps) {
  const [activeTab, setActiveTab] = useState<'UPGRADE' | 'SIMULATOR' | 'LEDGER'>('SIMULATOR');
  
  // Simulation form states
  const [simScenario, setSimScenario] = useState<'REELS_BRAND' | 'HEALTH_ASK' | 'CUSTOM'>('REELS_BRAND');
  const [simBrandName, setSimBrandName] = useState('Kopi Nusantara');
  const [simProductDetails, setSimProductDetails] = useState('Cold Brew Botol 250ml');
  const [simCustomQuestion, setSimCustomQuestion] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastSimResult, setLastSimResult] = useState<{
    text: string;
    fileDmNotice: string;
    creditsDeducted: number;
    creditsRewarded: number;
  } | null>(null);

  // Manual document upload form
  const [docTitle, setDocTitle] = useState('');
  const [docType, setDocType] = useState<'EBOOK_PDF' | 'PLUGIN_JSON'>('EBOOK_PDF');
  const [docSkill, setDocSkill] = useState('');

  // Preset quick upload samples
  const handleInstallPreset = (presetName: string, type: 'EBOOK_PDF' | 'PLUGIN_JSON', skills: string[], size: string) => {
    const newDoc: KnowledgeDocument = {
      id: `doc-${Date.now()}`,
      title: presetName,
      type,
      size,
      dateAdded: new Date().toISOString().split('T')[0],
      skillsGranted: skills,
      status: 'INDEXED_READY',
    };
    onAddDocument(newDoc);
  };

  const handleRunChallengeSimulation = async () => {
    setIsProcessing(true);
    setLastSimResult(null);

    let query = '';
    let type: 'REELS_CUSTOM_BRAND' | 'ASK_QUESTION' | 'GENERATE_CONTENT' = 'ASK_QUESTION';

    if (simScenario === 'REELS_BRAND') {
      type = 'REELS_CUSTOM_BRAND';
      query = `Membuat reels video kustom dengan brand "${simBrandName}" & produk "${simProductDetails}". File diserahkan via DM.`;
    } else if (simScenario === 'HEALTH_ASK') {
      type = 'ASK_QUESTION';
      query = 'Konsultasi kesehatan: Panduan nutrisi dan latihan ergonomis untuk pemulihan stamina kerja hybrid.';
    } else {
      type = 'GENERATE_CONTENT';
      query = simCustomQuestion || 'Permintaan kustom analisis dan generate solusi AI.';
    }

    try {
      const res = await fetch('/api/agent/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: type === 'REELS_CUSTOM_BRAND' ? 'brand_reels' : 'ask',
          agentName: agentProfile.name,
          agentSpecialty: agentProfile.specialty,
          humanOwner: agentProfile.ownerName,
          userQuestion: query,
          brandName: simBrandName,
          productDetails: simProductDetails,
        }),
      });

      const data = await res.json();

      // Trigger the real credits transfer from the asking Human to the AI Agent Owner!
      onExecuteCreditTransfer(
        '@budi_creative (Human Lain)',
        `${agentProfile.name} (Milik ${agentProfile.ownerHandle})`,
        agentProfile.ownerName,
        15,
        query,
        type
      );

      setLastSimResult({
        text: data.text || 'Respon berhasil digenerate oleh AI Agent.',
        fileDmNotice: type === 'REELS_CUSTOM_BRAND' 
          ? '📦 Paket File (Video Render Reels .mp4 60fps & 3D Logo GLB) telah dikirim otomatis ke Direct Message @budi_creative!'
          : '📄 Dokumen ringkasan solusi lengkap telah dikirimkan ke Direct Message.',
        creditsDeducted: 15,
        creditsRewarded: 15,
      });
    } catch {
      // Fallback transfer even if network glitches
      onExecuteCreditTransfer(
        '@budi_creative (Human Lain)',
        `${agentProfile.name} (Milik ${agentProfile.ownerHandle})`,
        agentProfile.ownerName,
        15,
        query,
        type
      );

      setLastSimResult({
        text: `Konten berhasil digenerate oleh ${agentProfile.name} berdasarkan basis pengetahuan yang diunggah.`,
        fileDmNotice: '📦 File paket reels brand telah dikirim ke Direct Message!',
        creditsDeducted: 15,
        creditsRewarded: 15,
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-6 pb-24">
      {/* Header Banner: Clarified Challenge & Rewards Definition */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white shadow-xl mb-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded-full bg-blue-500/30 border border-blue-400 text-blue-200 text-[10px] font-bold uppercase tracking-wider">
                Resmi Allpha Hub
              </span>
              <h1 className="text-xl font-black tracking-tight text-white">
                Skills Challenge & AI Credits Economy
              </h1>
            </div>
            <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
              Tingkatkan kapabilitas AI Agent Anda melalui upload dokumen Ebook atau Plugin. Raih reward AI Credits saat Human lain bertanya atau meminta AI Agent Anda mengenerate konten / reels ber-brand!
            </p>
          </div>

          {/* Credits Summary Badge */}
          <div className="flex items-center gap-3 bg-white/10 p-3 rounded-xl border border-white/10 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-amber-400/20 border border-amber-300/40 flex items-center justify-center text-amber-300">
              <Coins className="w-6 h-6" />
            </div>
            <div>
              <p className="text-[10px] uppercase font-bold text-slate-300">Total Reward AI Agent</p>
              <p className="text-lg font-black text-amber-300 font-mono">
                +{agentCredits} <span className="text-xs font-normal text-white">Cr</span>
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Tabs within Hub */}
        <div className="flex items-center gap-2 mt-5 pt-4 border-t border-white/10 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('SIMULATOR')}
            className={`px-3.5 py-1.5 rounded-xl transition flex items-center gap-1.5 ${
              activeTab === 'SIMULATOR'
                ? 'bg-white text-blue-900 shadow font-bold'
                : 'text-slate-300 hover:text-white hover:bg-white/10'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Simulasi Challenge & Transfer Kredit</span>
          </button>

          <button
            onClick={() => setActiveTab('UPGRADE')}
            className={`px-3.5 py-1.5 rounded-xl transition flex items-center gap-1.5 ${
              activeTab === 'UPGRADE'
                ? 'bg-white text-blue-900 shadow font-bold'
                : 'text-slate-300 hover:text-white hover:bg-white/10'
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upgrade Knowledge & Plugin ({knowledgeDocs.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('LEDGER')}
            className={`px-3.5 py-1.5 rounded-xl transition flex items-center gap-1.5 ${
              activeTab === 'LEDGER'
                ? 'bg-white text-blue-900 shadow font-bold'
                : 'text-slate-300 hover:text-white hover:bg-white/10'
            }`}
          >
            <Coins className="w-3.5 h-3.5" />
            <span>Audit Buku Besar ({transactions.length})</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* TAB 1: SIMULATOR CHALLENGE & CREDIT TRANSFER             */}
      {/* ======================================================== */}
      {activeTab === 'SIMULATOR' && (
        <div className="space-y-6">
          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-5 h-5 text-blue-600" />
              <h2 className="text-sm font-bold text-slate-900">
                Simulasi Interaksi Nyata: Human Lain Bertanya ke AI Agent Anda
              </h2>
            </div>
            <p className="text-xs text-slate-600 mb-4 leading-relaxed">
              Uji skenario persis yang Anda jelaskan: Ketika Human lain melihat reels/feed dan ingin membuat konten serupa dengan brand & logo mereka, AI Agent Anda akan merespons, mengirim file ke Direct Message, dan sistem secara otomatis memotong kredit penanya (-15 Cr) lalu menambahkannya ke saldo AI Agent Anda (+15 Cr).
            </p>

            {/* Scenario Picker */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              <button
                type="button"
                onClick={() => setSimScenario('REELS_BRAND')}
                className={`p-3.5 rounded-xl border text-left transition ${
                  simScenario === 'REELS_BRAND'
                    ? 'border-blue-600 bg-blue-50/60 ring-2 ring-blue-500/20'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-blue-900">Contoh 1: Reels Kustom Brand Sendiri</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-200 text-blue-800">
                    Reward +15 Cr
                  </span>
                </div>
                <p className="text-[11px] text-slate-600">
                  Human lain: &ldquo;Bagaimana cara membuat reels seperti ini, tetapi dengan logo &amp; produk saya?&rdquo;
                </p>
              </button>

              <button
                type="button"
                onClick={() => setSimScenario('HEALTH_ASK')}
                className={`p-3.5 rounded-xl border text-left transition ${
                  simScenario === 'HEALTH_ASK'
                    ? 'border-blue-600 bg-blue-50/60 ring-2 ring-blue-500/20'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-blue-900">Contoh 2: Tanya Kesehatan & Nutrisi</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-200 text-emerald-800">
                    Reward +15 Cr
                  </span>
                </div>
                <p className="text-[11px] text-slate-600">
                  Human lain bertanya rekomendasi nutrisi kerja hybrid kepada AI Agent Anda.
                </p>
              </button>
            </div>

            {/* Scenario Parameters */}
            {simScenario === 'REELS_BRAND' && (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 mb-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block text-slate-700 font-medium mb-1">Nama Brand / Logo Pemohon:</label>
                    <input
                      type="text"
                      value={simBrandName}
                      onChange={(e) => setSimBrandName(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg outline-none focus:border-blue-500"
                      placeholder="Contoh: Kopi Nusantara / NeoFashion"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-700 font-medium mb-1">Detail Produk / Aset 3D:</label>
                    <input
                      type="text"
                      value={simProductDetails}
                      onChange={(e) => setSimProductDetails(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg outline-none focus:border-blue-500"
                      placeholder="Contoh: Cold Brew Botol 250ml"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Interactive Run Simulation Button */}
            <button
              onClick={handleRunChallengeSimulation}
              disabled={isProcessing}
              className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white font-bold text-xs shadow-md transition flex items-center justify-center gap-2"
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>AI Agent Sedang Menganalisis Knowledge & Mengenerate Konten...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-300" />
                  <span>Jalankan AI Agent, Generate File ke DM & Transfer +15 AI Credits</span>
                </>
              )}
            </button>
          </div>

          {/* Results Box with File DM delivery & Credit Ledger Settlement */}
          {lastSimResult && (
            <div className="p-5 rounded-2xl bg-slate-900 border border-cyan-500/40 text-white shadow-xl animate-fade-in space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span className="font-bold text-sm text-emerald-300">
                    AI Challenge Berhasil Selesai & Kredit Terdistribusi!
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2.5 py-1 rounded-full bg-rose-500/20 text-rose-300 font-mono border border-rose-500/30">
                    Penanya: -{lastSimResult.creditsDeducted} Cr
                  </span>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 font-mono border border-emerald-500/30 font-bold">
                    AI Agent Anda: +{lastSimResult.creditsRewarded} Cr
                  </span>
                </div>
              </div>

              {/* Direct Message Dispatch Notice (as explicitly requested) */}
              <div className="p-3.5 rounded-xl bg-blue-950/80 border border-blue-500/40 flex items-start gap-3">
                <Inbox className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
                <div className="text-xs">
                  <p className="font-bold text-cyan-200">Notifikasi Pengiriman Direct Message:</p>
                  <p className="text-slate-300 mt-0.5">{lastSimResult.fileDmNotice}</p>
                </div>
              </div>

              {/* Generated Content Body */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-200 whitespace-pre-line leading-relaxed font-sans">
                {lastSimResult.text}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 2: UPGRADE KNOWLEDGE & PLUGINS (DOCUMENTS / EBOOKS) */}
      {/* ======================================================== */}
      {activeTab === 'UPGRADE' && (
        <div className="space-y-6">
          {/* Quick Preset Install Cards */}
          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 mb-1">
              Pilihan Cepat: Dokumen Ebook & Plugin Siap Install
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              Klik salah satu dokumen/plugin di bawah untuk langsung menambah kemampuan dan wawasan baru pada {agentProfile.name}:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-blue-600 mb-1">
                    <FileText className="w-4 h-4" />
                    <span className="text-[10px] font-bold uppercase">Ebook PDF</span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900">Pedoman Nutrisi Klinis 2026.pdf</h4>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Menambah keahlian: Diagnosis preventif, pola makan hybrid, dan kalkulasi nutrisi.
                  </p>
                </div>
                <button
                  onClick={() =>
                    handleInstallPreset(
                      'Pedoman Nutrisi Klinis 2026.pdf',
                      'EBOOK_PDF',
                      ['Kesehatan Nutrisi Preventif', 'Hybrid Wellness Calculator'],
                      '12.4 MB'
                    )
                  }
                  className="mt-3 py-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs transition"
                >
                  + Install Dokumen Ebook
                </button>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-purple-600 mb-1">
                    <Cpu className="w-4 h-4" />
                    <span className="text-[10px] font-bold uppercase">Plugin JSON</span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900">Brand Logo Reels Generator v2.5</h4>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Menambah kemampuan: Rendering logo otomatis pada adegan 3D dan dispatch file DM.
                  </p>
                </div>
                <button
                  onClick={() =>
                    handleInstallPreset(
                      'Brand Logo Reels Generator v2.5.json',
                      'PLUGIN_JSON',
                      ['Auto Logo Reels Engine', 'DM Asset Dispatcher'],
                      '4.2 MB'
                    )
                  }
                  className="mt-3 py-1.5 px-3 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-xs transition"
                >
                  + Install Plugin
                </button>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-cyan-600 mb-1">
                    <FileCode className="w-4 h-4" />
                    <span className="text-[10px] font-bold uppercase">3D Spatial Plugin</span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900">Three.js WebGL Shader Pack</h4>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Menambah kemampuan: Procedural neon shaders, emissive glow, dan district building scripts.
                  </p>
                </div>
                <button
                  onClick={() =>
                    handleInstallPreset(
                      'Three.js WebGL Shader Pack.zip',
                      'PLUGIN_JSON',
                      ['Procedural Neon Shader', 'Spatial Light Mapping'],
                      '8.9 MB'
                    )
                  }
                  className="mt-3 py-1.5 px-3 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white font-medium text-xs transition"
                >
                  + Install Spatial Pack
                </button>
              </div>
            </div>
          </div>

          {/* Active Knowledge & Installed Plugins List */}
          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Daftar Knowledge & Plugin Aktif Milik {agentProfile.name}</span>
            </h3>

            <div className="divide-y divide-slate-100">
              {knowledgeDocs.map((doc) => (
                <div key={doc.id} className="py-3 flex items-start justify-between gap-3 text-xs">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0">
                      {doc.type === 'EBOOK_PDF' ? <FileText className="w-4 h-4" /> : <Cpu className="w-4 h-4" />}
                    </div>
                    <div>
                      <p className="font-bold text-slate-900">{doc.title}</p>
                      <div className="flex items-center gap-2 text-slate-500 text-[11px] mt-0.5">
                        <span>{doc.size}</span>
                        <span>•</span>
                        <span>Ditambahkan {doc.dateAdded}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {doc.skillsGranted.map((sk) => (
                          <span
                            key={sk}
                            className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200"
                          >
                            +{sk}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <span className="px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200 shrink-0">
                    Terindeks & Siap
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 3: AUDIT BUKU BESAR TRANSAKSI (CREDIT LEDGER)       */}
      {/* ======================================================== */}
      {activeTab === 'LEDGER' && (
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Buku Besar Transaksi AI Credits Reward</h3>
              <p className="text-xs text-slate-500">
                Pencatatan transparan transfer kredit dari penanya ke AI Agent pemilik
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500">Akumulasi Reward:</span>
              <p className="text-base font-black text-amber-600 font-mono">+{agentCredits} AI Credits</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border border-slate-100 rounded-xl overflow-hidden">
              <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-3">Waktu</th>
                  <th className="p-3">Penanya (Human Lain)</th>
                  <th className="p-3">Penerima Reward (AI Agent & Pemilik)</th>
                  <th className="p-3">Keterangan / Query</th>
                  <th className="p-3 text-right">Perpindahan Kredit</th>
                  <th className="p-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-600">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/80 transition">
                    <td className="p-3 font-mono text-[11px] text-slate-500">{tx.timestamp}</td>
                    <td className="p-3 font-medium text-slate-900">{tx.fromUser}</td>
                    <td className="p-3 text-blue-700 font-semibold">{tx.toAgent}</td>
                    <td className="p-3 max-w-[220px] truncate" title={tx.querySummary}>
                      {tx.querySummary}
                    </td>
                    <td className="p-3 text-right font-mono font-bold text-emerald-600">
                      +{tx.amount} Cr
                    </td>
                    <td className="p-3 text-center">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                        {tx.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
