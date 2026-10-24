'use client';

import React, { useState } from 'react';
import { 
  ArrowLeft, 
  Bot, 
  User, 
  CheckCircle2, 
  Clock, 
  SlidersHorizontal, 
  MessageSquare, 
  ShieldAlert, 
  Sparkles, 
  ChevronRight, 
  HelpCircle, 
  RotateCcw,
  Check
} from 'lucide-react';
import { AIAgentProfile, HumanProfile } from '@/lib/store';

interface TakeoverControlViewProps {
  onBack: () => void;
  isTakeoverActive: boolean;
  onToggleTakeover: () => void;
  humanUser: HumanProfile;
  agentProfile: AIAgentProfile;
  onSaveNotification?: (msg: string) => void;
}

export default function TakeoverControlView({
  onBack,
  isTakeoverActive,
  onToggleTakeover,
  humanUser,
  agentProfile,
  onSaveNotification,
}: TakeoverControlViewProps) {
  const [activeTab, setActiveTab] = useState<'HUMAN' | 'AI_AGENT'>('AI_AGENT');
  const [autoReplyEnabled, setAutoReplyEnabled] = useState(!isTakeoverActive);
  const [selectedTopicScope, setSelectedTopicScope] = useState<'ALL' | 'MODERATED' | 'WHITELIST'>('MODERATED');
  const [activeMenuModal, setActiveMenuModal] = useState<string | null>(null);

  const handleSave = () => {
    if (autoReplyEnabled === isTakeoverActive) {
      onToggleTakeover();
    }
    if (onSaveNotification) {
      onSaveNotification('Pengaturan Mode Takeover & Auto-Reply berhasil disimpan!');
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto bg-white min-h-screen border-x border-slate-200 pb-24">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-100 px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 -ml-1 rounded-full text-slate-700 hover:bg-slate-100 transition"
            aria-label="Kembali"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-bold text-base text-slate-900">Mode Takeover</h1>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => alert('Mode Takeover memungkinkan Human Owner mengambil alih percakapan secara langsung kapan saja saat AI dinonaktifkan.')}
            className="p-1.5 rounded-full text-slate-500 hover:bg-slate-100"
          >
            <HelpCircle className="w-5 h-5" />
          </button>
        </div>
      </header>

      <div className="p-4 space-y-5">
        {/* Top Segmented Tab (Screen 5 Reference) */}
        <div className="flex rounded-2xl bg-slate-100 p-1">
          <button
            onClick={() => setActiveTab('HUMAN')}
            className={`flex-1 py-2 rounded-xl text-xs font-bold transition ${
              activeTab === 'HUMAN'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Human Owner
          </button>
          <button
            onClick={() => setActiveTab('AI_AGENT')}
            className={`flex-1 py-2 rounded-xl text-xs font-bold transition ${
              activeTab === 'AI_AGENT'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            AI Agent
          </button>
        </div>

        {/* Profile Card Summary */}
        <div className="p-4 rounded-3xl bg-slate-50 border border-slate-200/80 space-y-3">
          {/* Human Owner Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src={humanUser.avatar}
                alt={humanUser.name}
                className="w-12 h-12 rounded-full object-cover ring-2 ring-white shadow-sm"
              />
              <div>
                <h3 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                  <span>{humanUser.name}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                    Human Owner
                  </span>
                </h3>
                <span className="text-xs text-emerald-600 font-semibold flex items-center gap-1 mt-0.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Online
                </span>
              </div>
            </div>
          </div>

          <div className="border-t border-slate-200/80 pt-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src={agentProfile.avatar}
                alt={agentProfile.name}
                className="w-12 h-12 rounded-full object-cover ring-2 ring-purple-200 shadow-sm"
              />
              <div>
                <h3 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                  <span>{agentProfile.name}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-purple-50 text-purple-700 font-semibold border border-purple-200">
                    AI Agent · {agentProfile.specialty}
                  </span>
                </h3>
                <span className="text-xs text-blue-600 font-semibold flex items-center gap-1 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                  {autoReplyEnabled ? 'Auto-Reply Aktif' : 'Ambil Alih Human (Takeover)'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Mode Switch Cards (Screen 5 & 7 Reference) */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setAutoReplyEnabled(true)}
            className={`p-4 rounded-3xl border text-left transition flex flex-col justify-between ${
              autoReplyEnabled
                ? 'bg-blue-50/80 border-blue-500 text-blue-900 shadow-sm ring-1 ring-blue-500'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs">
                AI
              </div>
              {autoReplyEnabled && (
                <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">
                  ✓
                </span>
              )}
            </div>
            <div>
              <h4 className="font-extrabold text-xs">AI Auto</h4>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Agent merespons komentar dan pesan secara otomatis.
              </p>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setAutoReplyEnabled(false)}
            className={`p-4 rounded-3xl border text-left transition flex flex-col justify-between ${
              !autoReplyEnabled
                ? 'bg-purple-50/80 border-purple-500 text-purple-900 shadow-sm ring-1 ring-purple-500'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-8 h-8 rounded-xl bg-purple-600 text-white flex items-center justify-center font-bold text-xs">
                <User className="w-4 h-4" />
              </div>
              {!autoReplyEnabled && (
                <span className="w-5 h-5 rounded-full bg-purple-600 text-white flex items-center justify-center text-[10px]">
                  ✓
                </span>
              )}
            </div>
            <div>
              <h4 className="font-extrabold text-xs">Takeover Human</h4>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Anda yang merespons langsung sebagai Human Owner.
              </p>
            </div>
          </button>
        </div>

        {/* Current Status Pill Banner */}
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0 animate-pulse" />
          <p className="text-xs text-emerald-900 font-semibold">
            {autoReplyEnabled
              ? `Saat ini ${agentProfile.name} merespons komentar dan pesan secara otomatis.`
              : 'Mode Takeover Aktif: Anda memegang kendali penuh respons pesan.'}
          </p>
        </div>

        {/* Configuration Options Menu (Exact Match with Screen 5 & 7) */}
        <div className="rounded-3xl border border-slate-200 divide-y divide-slate-100 overflow-hidden bg-white">
          <button
            type="button"
            onClick={() => setAutoReplyEnabled(!autoReplyEnabled)}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
                <ShieldAlert className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  {autoReplyEnabled ? 'Matikan Auto-Reply' : 'Nyalakan Auto-Reply'}
                </h4>
                <p className="text-[11px] text-slate-500">
                  {autoReplyEnabled ? 'Hentikan respons otomatis AI' : 'Aktifkan respons otomatis AI'}
                </p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </button>

          <button
            type="button"
            onClick={() => {
              setAutoReplyEnabled(false);
              alert('Mode Takeover langsung diaktifkan!');
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                <User className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Ambil Alih (Takeover)</h4>
                <p className="text-[11px] text-slate-500">Jawab pesan masuk langsung atas nama Human</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </button>

          <button
            type="button"
            onClick={() => alert('Jadwal Auto-Reply: Aktif 24/7. Anda dapat mengatur rentang waktu operasional AI.')}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                <Clock className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Jadwalkan Auto-Reply</h4>
                <p className="text-[11px] text-slate-500">Atur jam operasional aktif AI Agent</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </button>

          <button
            type="button"
            onClick={() => alert('Batasan Topik: AI dibatasi hanya menjawab seputar Kesehatan, 3D, dan Marketing.')}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                <SlidersHorizontal className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Atur Batasan Topik</h4>
                <p className="text-[11px] text-slate-500">Tentukan topik yang boleh dijawab AI</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </button>

          <button
            type="button"
            onClick={() => alert('Panduan Gaya Komunikasi: Ramah, Ringkas, menggunakan Bahasa Indonesia santun.')}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Panduan Gaya Komunikasi</h4>
                <p className="text-[11px] text-slate-500">Sesuaikan nada bicara dan etiket respons AI</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </button>

          <button
            type="button"
            onClick={() => alert('Riwayat Percakapan: 142 sesi interaksi berhasil dijawab AI bulan ini.')}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center">
                <MessageSquare className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Lihat Log Percakapan</h4>
                <p className="text-[11px] text-slate-500">Audit pesan yang telah dijawab otomatis</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {/* CTA Save Button */}
        <div className="pt-2">
          <button
            type="button"
            onClick={handleSave}
            className="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white font-bold text-xs shadow-lg shadow-blue-500/25 transition flex items-center justify-center gap-2"
          >
            <span>Simpan Pengaturan</span>
            <Check className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
