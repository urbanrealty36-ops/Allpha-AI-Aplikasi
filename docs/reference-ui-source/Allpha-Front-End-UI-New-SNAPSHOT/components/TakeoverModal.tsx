'use client';

import React from 'react';
import { 
  User, 
  Bot, 
  Power, 
  Clock, 
  ShieldAlert, 
  FileText, 
  Check, 
  X,
  AlertCircle
} from 'lucide-react';

interface TakeoverModalProps {
  isOpen: boolean;
  onClose: () => void;
  isTakeoverActive: boolean;
  onToggleTakeover: () => void;
  agentName: string;
}

export default function TakeoverModal({
  isOpen,
  onClose,
  isTakeoverActive,
  onToggleTakeover,
  agentName,
}: TakeoverModalProps) {
  const [activeNotice, setActiveNotice] = React.useState<string | null>(null);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-[6px_6px_0px_#0f172a] border-2 border-slate-900">
        <div className="flex items-center justify-between pb-3.5 border-b-2 border-slate-900">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-amber-200 border-2 border-slate-900 flex items-center justify-center shadow-2xs">
              <Bot className="w-4 h-4 text-slate-950 stroke-[2.5px]" />
            </div>
            <h2 className="text-sm font-black text-slate-900">Mode Takeover Human</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 text-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            <X className="w-4 h-4 stroke-[2.5px]" />
          </button>
        </div>

        {/* Segmented Top Switcher (Human Owner vs AI Agent) */}
        <div className="flex rounded-2xl bg-slate-100 p-1.5 mt-4 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
          <button
            onClick={() => {
              if (!isTakeoverActive) onToggleTakeover();
            }}
            className={`flex-1 py-2 rounded-xl text-xs font-black transition flex items-center justify-center gap-1.5 cursor-pointer ${
              isTakeoverActive
                ? 'bg-amber-300 text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                : 'text-slate-700 hover:text-slate-950'
            }`}
          >
            <User className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>Human Owner</span>
          </button>
          <button
            onClick={() => {
              if (isTakeoverActive) onToggleTakeover();
            }}
            className={`flex-1 py-2 rounded-xl text-xs font-black transition flex items-center justify-center gap-1.5 cursor-pointer ${
              !isTakeoverActive
                ? 'bg-emerald-300 text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                : 'text-slate-700 hover:text-slate-950'
            }`}
          >
            <Bot className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>AI Auto-Reply</span>
          </button>
        </div>

        {/* Current Status Box */}
        <div className="mt-4 p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
          <div className="flex items-center gap-3">
            <div className={`w-3.5 h-3.5 rounded-full border border-slate-900 shrink-0 ${isTakeoverActive ? 'bg-amber-400' : 'bg-emerald-500 animate-pulse'}`} />
            <div>
              <p className="text-xs font-black text-slate-900">
                Mode: {isTakeoverActive ? 'Takeover Human Aktif' : 'AI Auto-Reply Aktif'}
              </p>
              <p className="text-[11px] font-semibold text-slate-700 mt-0.5 leading-snug">
                {isTakeoverActive
                  ? 'Anda merespons langsung sebagai Human Owner. AI dihentikan sementara.'
                  : `${agentName} merespons komentar dan pesan masuk secara otomatis.`}
              </p>
            </div>
          </div>
        </div>

        {/* Control Action List */}
        <div className="mt-4 space-y-2 text-xs">
          <button
            onClick={onToggleTakeover}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <Power className="w-4 h-4 text-rose-600 stroke-[2.5px]" />
              <span>{isTakeoverActive ? 'Aktifkan Kembali AI Auto-Reply' : 'Ambil Alih (Takeover Manual)'}</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>

          <button
            onClick={() => setActiveNotice('Jadwal auto-reply: Aktif 24/7 dengan batas 50 respon/jam')}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <Clock className="w-4 h-4 text-sky-600 stroke-[2.5px]" />
              <span>Jadwalkan Waktu Auto-Reply</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>

          <button
            onClick={() => setActiveNotice('Aturan filter: Memblokir kata tidak pantas & fokus pada kreativitas, 3D, dan kolaborasi.')}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-600 stroke-[2.5px]" />
              <span>Atur Batasan Topik & Etika AI</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>
        </div>

        {/* Notice Info Box */}
        {activeNotice && (
          <div className="mt-3 p-2.5 rounded-xl bg-sky-100 border-2 border-slate-900 text-[11px] font-bold text-slate-950 flex items-center justify-between shadow-2xs">
            <span>ℹ️ {activeNotice}</span>
            <button onClick={() => setActiveNotice(null)} className="font-black text-xs ml-2 cursor-pointer">✕</button>
          </div>
        )}

        {/* Confirm Button */}
        <div className="mt-5">
          <button
            onClick={onClose}
            className="w-full py-2.5 rounded-2xl bg-sky-400 hover:bg-sky-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            Simpan Pengaturan
          </button>
        </div>
      </div>
    </div>
  );
}
