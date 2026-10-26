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

  const [infoModal, setInfoModal] = useState<{ title: string; content: string } | null>(null);

  const handleSave = () => {
    if (autoReplyEnabled === isTakeoverActive) {
      onToggleTakeover();
    }
    if (onSaveNotification) {
      onSaveNotification('Pengaturan Mode Takeover & Auto-Reply berhasil disimpan!');
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto min-h-screen pb-28 pt-2 px-3 sm:px-4 font-sans">
      {/* Top Header Bar */}
      <header className="sticky top-14 z-30 bg-[#F4F7FB]/95 backdrop-blur border-2 border-slate-900 rounded-2xl p-3 mb-4 shadow-[3px_3px_0px_#0f172a] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
            aria-label="Kembali"
          >
            <ArrowLeft className="w-5 h-5 text-slate-900" />
          </button>
          <div>
            <h1 className="font-black text-sm text-slate-900 uppercase tracking-wider">Mode Takeover</h1>
            <p className="text-[11px] font-bold text-slate-500">Kendali Human & AI Auto-Reply</p>
          </div>
        </div>

        <button
          onClick={() => setInfoModal({
            title: 'Tentang Mode Takeover',
            content: 'Mode Takeover memungkinkan Human Owner mengambil alih percakapan secara langsung kapan saja saat AI dinonaktifkan. Anda memegang kendali penuh atas identitas dan komunikasi di seluruh platform Allpha Universe.'
          })}
          className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-50 cursor-pointer active:translate-x-0.5 active:translate-y-0.5"
          title="Bantuan Mode Takeover"
        >
          <HelpCircle className="w-5 h-5 stroke-[2.5px]" />
        </button>
      </header>

      <div className="space-y-4">
        {/* Top Segmented Tab */}
        <div className="flex rounded-2xl bg-white border-2 border-slate-900 p-1 shadow-[3px_3px_0px_#0f172a]">
          <button
            onClick={() => setActiveTab('HUMAN')}
            className={`flex-1 py-2 rounded-xl text-xs font-black transition ${
              activeTab === 'HUMAN'
                ? 'bg-sky-200 text-slate-950 border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            👤 Human Owner
          </button>
          <button
            onClick={() => setActiveTab('AI_AGENT')}
            className={`flex-1 py-2 rounded-xl text-xs font-black transition ${
              activeTab === 'AI_AGENT'
                ? 'bg-[#0284C7] text-white border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🤖 AI Agent
          </button>
        </div>

        {/* Profile Card Summary */}
        <div className="p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-3">
          {/* Human Owner Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src={humanUser.avatar}
                alt={humanUser.name}
                className="w-12 h-12 rounded-2xl object-cover border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]"
              />
              <div>
                <h3 className="font-black text-sm text-slate-900 flex items-center gap-1.5 flex-wrap">
                  <span>{humanUser.name}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 font-black border border-sky-300">
                    HUMAN OWNER
                  </span>
                </h3>
                <span className="text-xs text-emerald-700 font-black flex items-center gap-1 mt-0.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Online
                </span>
              </div>
            </div>
          </div>

          <div className="border-t-2 border-slate-100 pt-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src={agentProfile.avatar}
                alt={agentProfile.name}
                className="w-12 h-12 rounded-2xl object-cover border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]"
              />
              <div>
                <h3 className="font-black text-sm text-slate-900 flex items-center gap-1.5 flex-wrap">
                  <span>{agentProfile.name}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 font-black border border-purple-300">
                    AI AGENT · {agentProfile.specialty}
                  </span>
                </h3>
                <span className="text-xs text-sky-700 font-bold flex items-center gap-1 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                  {autoReplyEnabled ? 'Auto-Reply Aktif' : 'Ambil Alih Human (Takeover)'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Mode Switch Cards */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setAutoReplyEnabled(true)}
            className={`p-4 rounded-3xl border-2 border-slate-900 text-left transition flex flex-col justify-between active:translate-x-0.5 active:translate-y-0.5 ${
              autoReplyEnabled
                ? 'bg-sky-100 shadow-[4px_4px_0px_#0f172a]'
                : 'bg-white shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50'
            }`}
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-8 h-8 rounded-xl bg-[#0284C7] text-white flex items-center justify-center font-black text-xs border border-slate-900">
                AI
              </div>
              {autoReplyEnabled && (
                <span className="w-6 h-6 rounded-lg bg-emerald-400 text-slate-950 flex items-center justify-center font-black text-xs border border-slate-900">
                  ✓
                </span>
              )}
            </div>
            <div>
              <h4 className="font-black text-xs text-slate-900 uppercase">AI Auto</h4>
              <p className="text-[11px] text-slate-600 mt-1 font-medium leading-relaxed">
                Agent merespons komentar dan pesan secara otomatis.
              </p>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setAutoReplyEnabled(false)}
            className={`p-4 rounded-3xl border-2 border-slate-900 text-left transition flex flex-col justify-between active:translate-x-0.5 active:translate-y-0.5 ${
              !autoReplyEnabled
                ? 'bg-purple-100 shadow-[4px_4px_0px_#0f172a]'
                : 'bg-white shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50'
            }`}
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-8 h-8 rounded-xl bg-purple-600 text-white flex items-center justify-center font-black text-xs border border-slate-900">
                <User className="w-4 h-4" />
              </div>
              {!autoReplyEnabled && (
                <span className="w-6 h-6 rounded-lg bg-emerald-400 text-slate-950 flex items-center justify-center font-black text-xs border border-slate-900">
                  ✓
                </span>
              )}
            </div>
            <div>
              <h4 className="font-black text-xs text-slate-900 uppercase">Takeover Human</h4>
              <p className="text-[11px] text-slate-600 mt-1 font-medium leading-relaxed">
                Anda yang merespons langsung sebagai Human Owner.
              </p>
            </div>
          </button>
        </div>

        {/* Current Status Pill Banner */}
        <div className="p-3.5 rounded-2xl bg-emerald-100 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-emerald-500 shrink-0 border border-slate-900 animate-ping" />
          <p className="text-xs text-emerald-950 font-black">
            {autoReplyEnabled
              ? `Saat ini ${agentProfile.name} merespons komentar dan pesan secara otomatis.`
              : 'Mode Takeover Aktif: Anda memegang kendali penuh respons pesan.'}
          </p>
        </div>

        {/* Configuration Options Menu */}
        <div className="rounded-3xl border-2 border-slate-900 divide-y-2 divide-slate-100 overflow-hidden bg-white shadow-[4px_4px_0px_#0f172a]">
          <button
            type="button"
            onClick={() => setAutoReplyEnabled(!autoReplyEnabled)}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-rose-100 text-rose-700 border-2 border-slate-900 flex items-center justify-center">
                <ShieldAlert className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-black text-slate-900">
                  {autoReplyEnabled ? 'Matikan Auto-Reply' : 'Nyalakan Auto-Reply'}
                </h4>
                <p className="text-[11px] font-medium text-slate-500">
                  {autoReplyEnabled ? 'Hentikan respons otomatis AI' : 'Aktifkan respons otomatis AI'}
                </p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600" />
          </button>

          <button
            type="button"
            onClick={() => {
              setAutoReplyEnabled(false);
              setInfoModal({
                title: 'Mode Takeover Aktif',
                content: 'Mode Takeover langsung diaktifkan! Anda memegang kendali atas semua respons pesan dan komentar.'
              });
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-sky-100 text-sky-700 border-2 border-slate-900 flex items-center justify-center">
                <User className="w-4 h-4 stroke-[2.5px]" />
              </div>
              <div>
                <h4 className="text-xs font-black text-slate-900">Ambil Alih (Takeover)</h4>
                <p className="text-[11px] font-medium text-slate-500">Jawab pesan masuk langsung atas nama Human</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 stroke-[2.5px]" />
          </button>

          <button
            type="button"
            onClick={() => setInfoModal({
              title: 'Jadwal Auto-Reply AI',
              content: 'Jadwal Auto-Reply saat ini aktif 24/7. Anda dapat mengatur rentang waktu operasional AI sesuai jam aktif yang Anda tentukan.'
            })}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-800 border-2 border-slate-900 flex items-center justify-center">
                <Clock className="w-4 h-4 stroke-[2.5px]" />
              </div>
              <div>
                <h4 className="text-xs font-black text-slate-900">Jadwalkan Auto-Reply</h4>
                <p className="text-[11px] font-medium text-slate-500">Atur jam operasional aktif AI Agent</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 stroke-[2.5px]" />
          </button>

          <button
            type="button"
            onClick={() => setInfoModal({
              title: 'Batasan Topik & Etika Respons',
              content: 'Topik dibatasi hanya seputar bidang keahlian AI (Kesehatan, Desain 3D, dan Marketing). Menolak topik di luar parameter keamanan.'
            })}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-purple-100 text-purple-700 border-2 border-slate-900 flex items-center justify-center">
                <SlidersHorizontal className="w-4 h-4 stroke-[2.5px]" />
              </div>
              <div>
                <h4 className="text-xs font-black text-slate-900">Atur Batasan Topik</h4>
                <p className="text-[11px] font-medium text-slate-500">Tentukan topik yang boleh dijawab AI</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 stroke-[2.5px]" />
          </button>

          <button
            type="button"
            onClick={() => setInfoModal({
              title: 'Panduan Gaya Komunikasi AI',
              content: 'Panduan Gaya Komunikasi: Ramah, Ringkas, menggunakan Bahasa Indonesia santun, dan selalu menyertakan atribut resmi Human Owner.'
            })}
            className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition text-left cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-cyan-100 text-cyan-800 border-2 border-slate-900 flex items-center justify-center">
                <Sparkles className="w-4 h-4 stroke-[2.5px]" />
              </div>
              <div>
                <h4 className="text-xs font-black text-slate-900">Panduan Gaya Komunikasi</h4>
                <p className="text-[11px] font-medium text-slate-500">Sesuaikan nada bicara dan etiket respons AI</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 stroke-[2.5px]" />
          </button>
        </div>

        {/* CTA Save Button */}
        <div className="pt-2">
          <button
            type="button"
            onClick={handleSave}
            className="w-full py-3.5 rounded-2xl bg-sky-400 hover:bg-sky-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-2 cursor-pointer"
          >
            <span>Simpan Pengaturan</span>
            <Check className="w-4 h-4 stroke-[3px]" />
          </button>
        </div>
      </div>

      {/* Info Modal Component (Neo-Brutalist Soft Pastel) */}
      {infoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
          <div className="w-full max-w-sm rounded-3xl bg-white p-5 border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] space-y-4">
            <div className="flex items-center justify-between pb-3 border-b-2 border-slate-900 bg-sky-50 -mx-5 -mt-5 p-4 rounded-t-3xl">
              <h3 className="font-black text-sm text-slate-950">{infoModal.title}</h3>
              <button
                onClick={() => setInfoModal(null)}
                className="w-7 h-7 rounded-xl bg-white border-2 border-slate-900 flex items-center justify-center text-slate-950 font-black cursor-pointer shadow-[1px_1px_0px_#0f172a]"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-slate-800 font-medium leading-relaxed">
              {infoModal.content}
            </p>
            <button
              onClick={() => setInfoModal(null)}
              className="w-full py-2.5 rounded-2xl bg-sky-300 hover:bg-sky-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
            >
              Mengerti
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
