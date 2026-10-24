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
      <div className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <h2 className="text-sm font-black text-slate-900">Mode Takeover</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Segmented Top Switcher (Human Owner vs AI Agent) */}
        <div className="flex rounded-2xl bg-slate-100 p-1 mt-4">
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
            <User className="w-3.5 h-3.5" />
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
            <Bot className="w-3.5 h-3.5" />
            <span>AI Agent ({agentName})</span>
          </button>
        </div>

        {/* Current Status Box */}
        <div className="mt-4 p-3.5 rounded-2xl bg-slate-50 border border-slate-200">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full shrink-0 ${isTakeoverActive ? 'bg-amber-500 ring-4 ring-amber-100' : 'bg-emerald-500 ring-4 ring-emerald-100'}`} />
            <div>
              <p className="text-xs font-bold text-slate-900">
                Mode Saat Ini: {isTakeoverActive ? 'Takeover Human Aktif' : 'AI Auto-Reply Aktif'}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {isTakeoverActive
                  ? 'Anda merespons langsung sebagai Human Owner. AI dihentikan sementara.'
                  : `${agentName} merespons komentar dan pesan masuk secara otomatis.`}
              </p>
            </div>
          </div>
        </div>

        {/* Control Action List */}
        <div className="mt-4 space-y-1.5 text-xs">
          <button
            onClick={onToggleTakeover}
            className="w-full p-2.5 rounded-xl hover:bg-slate-50 border border-slate-100 flex items-center justify-between text-slate-800 transition"
          >
            <div className="flex items-center gap-2.5">
              <Power className="w-4 h-4 text-rose-500" />
              <span>{isTakeoverActive ? 'Aktifkan Kembali AI Auto-Reply' : 'Ambil Alih (Takeover Manual)'}</span>
            </div>
            <span className="text-slate-400">›</span>
          </button>

          <button
            onClick={() => alert('Jadwal auto-reply: Aktif 24/7 dengan batas 50 respon/jam')}
            className="w-full p-2.5 rounded-xl hover:bg-slate-50 border border-slate-100 flex items-center justify-between text-slate-800 transition"
          >
            <div className="flex items-center gap-2.5">
              <Clock className="w-4 h-4 text-blue-500" />
              <span>Jadwalkan Waktu Auto-Reply</span>
            </div>
            <span className="text-slate-400">›</span>
          </button>

          <button
            onClick={() => alert('Aturan filter: Memblokir kata kasar dan membatasi topik hanya seputar kreativitas & 3D.')}
            className="w-full p-2.5 rounded-xl hover:bg-slate-50 border border-slate-100 flex items-center justify-between text-slate-800 transition"
          >
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-500" />
              <span>Atur Batasan Topik & Etika AI</span>
            </div>
            <span className="text-slate-400">›</span>
          </button>

          <button
            onClick={() => alert('Menampilkan 50 percakapan terakhir yang direspons oleh Luna AI.')}
            className="w-full p-2.5 rounded-xl hover:bg-slate-50 border border-slate-100 flex items-center justify-between text-slate-800 transition"
          >
            <div className="flex items-center gap-2.5">
              <FileText className="w-4 h-4 text-purple-500" />
              <span>Lihat Log Percakapan AI</span>
            </div>
            <span className="text-slate-400">›</span>
          </button>
        </div>

        {/* Confirm Button */}
        <div className="mt-5">
          <button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs transition"
          >
            Simpan Pengaturan
          </button>
        </div>
      </div>
    </div>
  );
}
