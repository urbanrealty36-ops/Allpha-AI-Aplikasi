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
import { KnowledgeDocument, CreditTransaction, AIAgentProfile } from '@/lib/store';

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
    <div className="w-full max-w-4xl mx-auto px-3 sm:px-4 py-4 pb-28 font-sans">
      {/* Header Banner (Playful Neo-Brutalist Soft Pastel) */}
      <div className="p-5 sm:p-6 rounded-3xl bg-amber-50 text-slate-950 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] mb-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full bg-amber-300 text-slate-950 text-[10px] font-black uppercase tracking-wider border-2 border-slate-900 shadow-2xs">
                ALLPHA HUB OFFICIAL
              </span>
              <h1 className="text-lg sm:text-xl font-black tracking-tight text-slate-950 uppercase">
                Skills Challenge & AI Credits
              </h1>
            </div>
            <p className="text-xs text-slate-700 max-w-xl leading-relaxed font-semibold">
              Tingkatkan kemampuan AI Agent Anda lewat Ebook atau Plugin. Raih reward AI Credits saat pengguna lain berkonsultasi atau membuat reels ber-brand!
            </p>
          </div>

          {/* Credits Summary Badge */}
          <div className="flex items-center gap-3 bg-white text-slate-950 p-3 rounded-2xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] shrink-0">
            <div className="w-10 h-10 rounded-xl bg-amber-300 border-2 border-slate-900 flex items-center justify-center text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]">
              <Coins className="w-5 h-5 stroke-[2.5px]" />
            </div>
            <div>
              <p className="text-[10px] uppercase font-black text-slate-700">Total Reward Agent</p>
              <p className="text-lg font-black text-slate-950 font-mono">
                +{agentCredits} <span className="text-xs font-bold text-slate-700">Cr</span>
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Tabs within Hub */}
        <div className="flex items-center gap-2 mt-5 pt-4 border-t-2 border-slate-900/15 text-xs font-black overflow-x-auto pb-1">
          <button
            onClick={() => setActiveTab('SIMULATOR')}
            className={`px-3.5 py-2 rounded-2xl transition flex items-center gap-1.5 border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
              activeTab === 'SIMULATOR'
                ? 'bg-amber-300 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-700 stroke-[2.5px]" />
            <span>Simulasi Challenge & Transfer</span>
          </button>

          <button
            onClick={() => setActiveTab('UPGRADE')}
            className={`px-3.5 py-2 rounded-2xl transition flex items-center gap-1.5 border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
              activeTab === 'UPGRADE'
                ? 'bg-sky-300 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
            }`}
          >
            <Upload className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>Upgrade Knowledge & Plugin ({knowledgeDocs.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('LEDGER')}
            className={`px-3.5 py-2 rounded-2xl transition flex items-center gap-1.5 border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
              activeTab === 'LEDGER'
                ? 'bg-emerald-300 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
            }`}
          >
            <Coins className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>Audit Buku Besar ({transactions.length})</span>
          </button>
        </div>
      </div>

      {/* TAB 1: SIMULATOR CHALLENGE & CREDIT TRANSFER */}
      {activeTab === 'SIMULATOR' && (
        <div className="space-y-5">
          <div className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-5 h-5 text-[#0284C7]" />
              <h2 className="text-sm font-black text-slate-900 uppercase">
                Simulasi Interaksi Nyata: Human Lain Bertanya ke AI Agent Anda
              </h2>
            </div>
            <p className="text-xs text-slate-600 mb-4 leading-relaxed font-semibold">
              Uji skenario: Ketika pengguna lain memesan reels ber-brand kustom, AI Agent Anda merespons, mengirim file ke Direct Message, dan sistem memotong kredit penanya (-15 Cr) lalu menambahkannya ke saldo AI Agent Anda (+15 Cr).
            </p>

            {/* Scenario Picker */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              <button
                type="button"
                onClick={() => setSimScenario('REELS_BRAND')}
                className={`p-3.5 rounded-2xl border-2 border-slate-900 text-left transition active:translate-x-0.5 active:translate-y-0.5 ${
                  simScenario === 'REELS_BRAND'
                    ? 'bg-sky-100 shadow-[3px_3px_0px_#0f172a]'
                    : 'bg-slate-50 hover:bg-slate-100 shadow-[1px_1px_0px_#0f172a]'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-black text-slate-900">1: Reels Kustom Brand Sendiri</span>
                  <span className="text-[10px] font-black px-2 py-0.5 rounded-lg bg-sky-200 text-sky-900 border border-slate-900">
                    +15 Cr
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 font-medium">
                  Pengguna lain: &ldquo;Buat reels seperti ini dengan logo & produk saya.&rdquo;
                </p>
              </button>

              <button
                type="button"
                onClick={() => setSimScenario('HEALTH_ASK')}
                className={`p-3.5 rounded-2xl border-2 border-slate-900 text-left transition active:translate-x-0.5 active:translate-y-0.5 ${
                  simScenario === 'HEALTH_ASK'
                    ? 'bg-emerald-100 shadow-[3px_3px_0px_#0f172a]'
                    : 'bg-slate-50 hover:bg-slate-100 shadow-[1px_1px_0px_#0f172a]'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-black text-slate-900">2: Tanya Kesehatan & Nutrisi</span>
                  <span className="text-[10px] font-black px-2 py-0.5 rounded-lg bg-emerald-200 text-emerald-900 border border-slate-900">
                    +15 Cr
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 font-medium">
                  Pengguna lain berkonsultasi rekomendasi nutrisi kerja hybrid ke AI Agent Anda.
                </p>
              </button>
            </div>

            {/* Scenario Parameters */}
            {simScenario === 'REELS_BRAND' && (
              <div className="p-4 rounded-2xl bg-[#F4F7FB] border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-3 mb-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block text-slate-800 font-black mb-1">Nama Brand / Logo Pemohon:</label>
                    <input
                      type="text"
                      value={simBrandName}
                      onChange={(e) => setSimBrandName(e.target.value)}
                      className="w-full px-3 py-2 bg-white border-2 border-slate-900 rounded-xl outline-none font-bold text-slate-900"
                      placeholder="Contoh: Kopi Nusantara / NeoFashion"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-800 font-black mb-1">Detail Produk / Aset 3D:</label>
                    <input
                      type="text"
                      value={simProductDetails}
                      onChange={(e) => setSimProductDetails(e.target.value)}
                      className="w-full px-3 py-2 bg-white border-2 border-slate-900 rounded-xl outline-none font-bold text-slate-900"
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
              className="w-full py-3.5 rounded-2xl bg-sky-300 hover:bg-sky-400 disabled:bg-slate-200 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-2 cursor-pointer"
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin stroke-[2.5px]" />
                  <span>AI Agent Menganalisis Knowledge & Mengenerate Konten...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-700 stroke-[2.5px]" />
                  <span>Jalankan AI Agent, Kirim File ke DM & Transfer +15 AI Credits</span>
                </>
              )}
            </button>
          </div>

          {/* Results Box */}
          {lastSimResult && (
            <div className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-4">
              <div className="flex items-center justify-between pb-3 border-b-2 border-slate-100 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <span className="font-black text-sm text-slate-900">
                    Challenge Berhasil & Kredit Terdistribusi!
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2.5 py-1 rounded-xl bg-rose-100 text-rose-800 font-mono font-black border-2 border-slate-900">
                    Penanya: -{lastSimResult.creditsDeducted} Cr
                  </span>
                  <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-100 text-emerald-800 font-mono font-black border-2 border-slate-900">
                    AI Agent Anda: +{lastSimResult.creditsRewarded} Cr
                  </span>
                </div>
              </div>

              {/* Direct Message Dispatch Notice */}
              <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-3">
                <Inbox className="w-5 h-5 text-[#0284C7] shrink-0 mt-0.5" />
                <div className="text-xs font-medium">
                  <p className="font-black text-slate-900">Notifikasi Pengiriman Direct Message:</p>
                  <p className="text-slate-700 mt-0.5">{lastSimResult.fileDmNotice}</p>
                </div>
              </div>

              {/* Generated Content Body */}
              <div className="p-4 rounded-2xl bg-slate-50 border-2 border-slate-900 text-xs text-slate-900 whitespace-pre-line leading-relaxed font-semibold">
                {lastSimResult.text}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: UPGRADE KNOWLEDGE & PLUGINS */}
      {activeTab === 'UPGRADE' && (
        <div className="space-y-5">
          <div className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
            <h3 className="text-sm font-black text-slate-900 mb-1 uppercase">
              Dokumen Ebook & Plugin Siap Pasang
            </h3>
            <p className="text-xs text-slate-600 mb-4 font-medium">
              Klik salah satu dokumen/plugin di bawah untuk langsung menambah kemampuan baru pada {agentProfile.name}:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-sky-700 mb-1">
                    <FileText className="w-4 h-4" />
                    <span className="text-[10px] font-black uppercase">Ebook PDF</span>
                  </div>
                  <h4 className="text-xs font-black text-slate-900">Pedoman Nutrisi Klinis 2026.pdf</h4>
                  <p className="text-[11px] text-slate-600 mt-1 font-medium">
                    Diagnosis preventif, nutrisi kerja hybrid, kalkulasi kalori.
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
                  className="mt-3 py-2 px-3 rounded-2xl bg-sky-300 hover:bg-sky-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  + Install Dokumen
                </button>
              </div>

              <div className="p-3.5 rounded-2xl bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-purple-900 mb-1">
                    <Cpu className="w-4 h-4 stroke-[2.5px]" />
                    <span className="text-[10px] font-black uppercase">Plugin JSON</span>
                  </div>
                  <h4 className="text-xs font-black text-slate-900">Brand Logo Reels Generator v2.5</h4>
                  <p className="text-[11px] text-slate-600 mt-1 font-medium">
                    Rendering logo otomatis pada adegan 3D & dispatch file DM.
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
                  className="mt-3 py-2 px-3 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  + Install Plugin
                </button>
              </div>

              <div className="p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-amber-900 mb-1">
                    <FileCode className="w-4 h-4 stroke-[2.5px]" />
                    <span className="text-[10px] font-black uppercase">3D Spatial Plugin</span>
                  </div>
                  <h4 className="text-xs font-black text-slate-900">Three.js WebGL Shader Pack</h4>
                  <p className="text-[11px] text-slate-600 mt-1 font-medium">
                    Procedural neon shaders, emissive glow, spatial district.
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
                  className="mt-3 py-2 px-3 rounded-2xl bg-amber-300 hover:bg-amber-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  + Install Spatial
                </button>
              </div>
            </div>
          </div>

          {/* Active Knowledge List */}
          <div className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
            <h3 className="text-sm font-black text-slate-900 mb-3 flex items-center gap-2 uppercase">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Knowledge & Plugin Aktif Milik {agentProfile.name}</span>
            </h3>

            <div className="divide-y-2 divide-slate-100">
              {knowledgeDocs.map((doc) => (
                <div key={doc.id} className="py-3.5 flex items-start justify-between gap-3 text-xs">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-xl bg-slate-100 border-2 border-slate-900 flex items-center justify-center text-slate-800 shrink-0">
                      {doc.type === 'EBOOK_PDF' ? <FileText className="w-4 h-4" /> : <Cpu className="w-4 h-4" />}
                    </div>
                    <div>
                      <p className="font-black text-slate-900">{doc.title}</p>
                      <div className="flex items-center gap-2 text-slate-500 text-[11px] font-bold mt-0.5">
                        <span>{doc.size}</span>
                        <span>•</span>
                        <span>Ditambahkan {doc.dateAdded}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {doc.skillsGranted.map((sk) => (
                          <span
                            key={sk}
                            className="text-[10px] px-2 py-0.5 rounded-lg bg-sky-100 text-sky-800 font-black border border-sky-300"
                          >
                            +{sk}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <span className="px-2.5 py-1 rounded-xl bg-emerald-100 text-emerald-800 text-[10px] font-black border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a] shrink-0">
                    Aktif
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: AUDIT BUKU BESAR TRANSAKSI */}
      {activeTab === 'LEDGER' && (
        <div className="p-5 rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-black text-slate-900 uppercase">Buku Besar Transaksi AI Credits</h3>
              <p className="text-xs text-slate-500 font-semibold">
                Pencatatan transparan transfer kredit dari penanya ke AI Agent pemilik
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 font-bold">Akumulasi Reward:</span>
              <p className="text-base font-black text-amber-600 font-mono">+{agentCredits} AI Credits</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-2 border-slate-900 rounded-2xl overflow-hidden">
              <thead className="bg-[#F4F7FB] text-slate-900 font-black border-b-2 border-slate-900">
                <tr>
                  <th className="p-3">Waktu</th>
                  <th className="p-3">Penanya</th>
                  <th className="p-3">Penerima</th>
                  <th className="p-3">Keterangan</th>
                  <th className="p-3 text-right">Kredit</th>
                  <th className="p-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y-2 divide-slate-100 text-slate-700 font-medium">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-sky-50/50 transition">
                    <td className="p-3 font-mono text-[11px] font-bold text-slate-500">{tx.timestamp}</td>
                    <td className="p-3 font-black text-slate-900">{tx.fromUser}</td>
                    <td className="p-3 text-[#0284C7] font-black">{tx.toAgent}</td>
                    <td className="p-3 max-w-[200px] truncate" title={tx.querySummary}>
                      {tx.querySummary}
                    </td>
                    <td className="p-3 text-right font-mono font-black text-emerald-600">
                      +{tx.amount} Cr
                    </td>
                    <td className="p-3 text-center">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-black border border-emerald-300">
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
