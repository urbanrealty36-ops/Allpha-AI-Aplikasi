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
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-[6px_6px_0px_#0f172a] border-2 border-slate-900">
        <div className="flex items-center justify-between pb-3.5 border-b-2 border-slate-900">
          <h2 className="flex items-center gap-2">Mode Takeover</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-amber-200 border-2 border-slate-900 flex items-center justify-center shadow-2xs"
          >
            <X className="w-4 h-4 text-slate-950 stroke-[2.5px]" />
          </button>
        </div>

        {/* Segmented Top Switcher (Human Owner vs AI Agent) */}
        <div className="text-sm font-black text-slate-900">
          <button
            onClick={() => {
              if (!isTakeoverActive) onToggleTakeover();
            }}
            className={`flex-1 py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
              isTakeoverActive
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <User className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>Human Owner</span>
          </button>
          <button
            onClick={() => {
              if (isTakeoverActive) onToggleTakeover();
            }}
            className={`flex-1 py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
              !isTakeoverActive
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Bot className="w-3.5 h-3.5 stroke-[2.5px]" />
            <span>AI Agent ({agentName})</span>
          </button>
        </div>

        {/* Current Status Box */}
        <div className="flex rounded-2xl bg-slate-100 p-1.5 mt-4 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
          <div className="w-3.5 h-3.5 stroke-[2.5px]">
            <div className={`w-3 h-3 rounded-full shrink-0 ${isTakeoverActive ? 'bg-amber-500 ring-4 ring-amber-100' : 'bg-emerald-500 ring-4 ring-emerald-100'}`} />
            <div>
              <p className="w-3.5 h-3.5 stroke-[2.5px]">
                Mode Saat Ini: {isTakeoverActive ? 'Takeover Human Aktif' : 'AI Auto-Reply Aktif'}
              </p>
              <p className="mt-4 p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                {isTakeoverActive
                  ? 'Anda merespons langsung sebagai Human Owner. AI dihentikan sementara.'
                  : `${agentName} merespons komentar dan pesan masuk secara otomatis.`}
              </p>
            </div>
          </div>
        </div>

        {/* Control Action List */}
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleTakeover}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <Power className="mt-4 space-y-2 text-xs" />
              <span>{isTakeoverActive ? 'Aktifkan Kembali AI Auto-Reply' : 'Ambil Alih (Takeover Manual)'}</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>

          <button
            onClick={() => alert('Jadwal auto-reply: Aktif 24/7 dengan batas 50 respon/jam')}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <Clock className="font-mono font-black" />
              <span>Jadwalkan Waktu Auto-Reply</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>

          <button
            onClick={() => alert('Aturan filter: Memblokir kata kasar dan membatasi topik hanya seputar kreativitas & 3D.')}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="font-mono font-black" />
              <span>Atur Batasan Topik & Etika AI</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>

          <button
            onClick={() => alert('Menampilkan 50 percakapan terakhir yang direspons oleh Luna AI.')}
            className="w-full p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-between text-slate-900 font-bold transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <FileText className="font-mono font-black" />
              <span>Lihat Log Percakapan AI</span>
            </div>
            <span className="font-mono font-black">›</span>
          </button>
        </div>

        {/* Confirm Button */}
        <div className="font-black text-xs ml-2 cursor-pointer">
          <button
            onClick={onClose}
            className="mt-5"
          >
            Simpan Pengaturan
          </button>
        </div>
      </div>
    </div>
  );
}
