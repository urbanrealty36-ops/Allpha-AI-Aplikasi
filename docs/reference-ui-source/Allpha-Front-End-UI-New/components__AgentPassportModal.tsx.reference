'use client';

import React, { useState } from 'react';
import { 
  Bot, 
  ShieldCheck, 
  Sparkles, 
  X, 
  Share2, 
  Download, 
  CheckCircle2, 
  Cpu, 
  Zap, 
  Layers, 
  Lock, 
  User, 
  QrCode, 
  Award,
  ExternalLink,
  Coins
} from 'lucide-react';
import { AIAgentProfile, HumanProfile } from '@/lib/store';

interface AgentPassportModalProps {
  isOpen: boolean;
  onClose: () => void;
  agent: AIAgentProfile;
  owner: HumanProfile;
}

export default function AgentPassportModal({
  isOpen,
  onClose,
  agent,
  owner,
}: AgentPassportModalProps) {
  const [activeTab, setActiveTab] = useState<'PASSPORT' | 'CAPABILITIES' | 'ERC6551'>('PASSPORT');
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const passportNumber = `ID-ALPH-2026-${agent.name.toUpperCase().slice(0, 3)}-9942`;
  const tokenBoundAddress = `0x71C...B82a7F4E`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Top Bar */}
        <div className="flex items-center justify-between p-4 border-b-2 border-slate-900 bg-[#DDD6FE]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-purple-900">
              <ShieldCheck className="w-4.5 h-4.5" />
            </div>
            <div>
              <span className="text-[9px] font-black uppercase tracking-widest text-purple-950">Official Certificate</span>
              <h2 className="text-sm font-black text-slate-900 tracking-tight">AI AGENT PASSPORT</h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-100 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
            aria-label="Tutup"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b-2 border-slate-900 bg-slate-100 p-1.5 gap-1.5 text-xs font-black">
          <button
            onClick={() => setActiveTab('PASSPORT')}
            className={`flex-1 py-1.5 rounded-xl border-2 transition cursor-pointer ${
              activeTab === 'PASSPORT'
                ? 'bg-white border-slate-900 text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            Digital Passport
          </button>
          <button
            onClick={() => setActiveTab('CAPABILITIES')}
            className={`flex-1 py-1.5 rounded-xl border-2 transition cursor-pointer ${
              activeTab === 'CAPABILITIES'
                ? 'bg-white border-slate-900 text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            Matrix Kemampuan
          </button>
          <button
            onClick={() => setActiveTab('ERC6551')}
            className={`flex-1 py-1.5 rounded-xl border-2 transition cursor-pointer ${
              activeTab === 'ERC6551'
                ? 'bg-white border-slate-900 text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            ERC-6551 Account
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-4">
          {activeTab === 'PASSPORT' && (
            <div className="space-y-4">
              {/* Holographic Passport Card */}
              <div className="relative rounded-3xl bg-gradient-to-br from-indigo-950 via-slate-900 to-purple-950 text-white p-5 border-3 border-slate-900 shadow-[4px_4px_0px_#0f172a] overflow-hidden">
                {/* Hologram Accent Wave */}
                <div className="absolute -top-12 -right-12 w-36 h-36 rounded-full bg-gradient-to-r from-cyan-400/20 via-pink-500/20 to-purple-500/20 blur-xl pointer-events-none" />

                {/* Passport Header */}
                <div className="flex items-center justify-between pb-3 border-b border-white/20">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-black tracking-widest text-[#FEF08A] uppercase">
                      ALLPHA UNIVERSE
                    </span>
                    <span className="text-[10px] text-cyan-300 font-bold">• GLOBAL CITIZEN</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 text-[10px] font-mono font-black flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    VERIFIED AGENT
                  </span>
                </div>

                {/* Passport Core Content */}
                <div className="grid grid-cols-3 gap-4 pt-4 items-center">
                  {/* Photo with holographic frame */}
                  <div className="col-span-1 flex flex-col items-center">
                    <div className="relative w-24 h-24 rounded-2xl overflow-hidden border-2 border-cyan-400 shadow-[2px_2px_0px_#000] bg-slate-950">
                      <img
                        src={agent.avatar3DImage || agent.avatar}
                        alt={agent.name}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-slate-950/70 via-transparent to-transparent" />
                      {/* Chip icon */}
                      <span className="absolute bottom-1 right-1 text-xs">💎</span>
                    </div>
                    <span className="mt-1 text-[9px] font-mono text-cyan-300 font-bold">CHIP ID: #8892</span>
                  </div>

                  {/* Metadata fields */}
                  <div className="col-span-2 space-y-1.5 text-xs">
                    <div>
                      <p className="text-[9px] uppercase font-bold text-slate-400">Nama AI Agent</p>
                      <h3 className="text-base font-black text-white">{agent.name}</h3>
                      <p className="text-[11px] font-mono text-cyan-400">{agent.handle}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <div>
                        <p className="text-[9px] uppercase font-bold text-slate-400">Human Owner</p>
                        <p className="font-bold text-white text-[11px] truncate">{owner.name}</p>
                        <p className="text-[9px] text-slate-400 font-mono truncate">{owner.username}</p>
                      </div>
                      <div>
                        <p className="text-[9px] uppercase font-bold text-slate-400">Bidang Keahlian</p>
                        <p className="font-bold text-[#FEF08A] text-[11px] truncate">{agent.bidang || 'Kreatif'}</p>
                      </div>
                    </div>

                    <div className="pt-1">
                      <p className="text-[9px] uppercase font-bold text-slate-400">Nomor Passport Resmi</p>
                      <p className="font-mono text-xs font-black text-amber-300 tracking-wider">
                        {passportNumber}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Bottom Trust & Hash Row */}
                <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-[10px] font-mono">
                  <span className="text-slate-400">Trust Score: <strong className="text-emerald-400">99.8%</strong></span>
                  <span className="text-slate-400">Model: <strong className="text-purple-300">{agent.model || 'Omni-v3'}</strong></span>
                  <span className="text-slate-400">ERC-6551: <strong className="text-cyan-300">Bound</strong></span>
                </div>
              </div>

              {/* Skills Bound List */}
              <div className="p-3.5 rounded-2xl bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-black text-slate-900 uppercase flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    <span>Skills Resmi Terindeks</span>
                  </h4>
                  <span className="text-[10px] font-bold text-slate-500">
                    {agent.skills?.length || 2} Keterampilan Terikat
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(agent.skills && agent.skills.length > 0 ? agent.skills : ['Brand Identity 3D', 'Reels Dynamic Motion']).map((sk) => (
                    <span
                      key={sk}
                      className="px-2.5 py-1 rounded-xl bg-white border-2 border-slate-900 text-slate-900 text-[11px] font-bold shadow-[1px_1px_0px_#0f172a]"
                    >
                      ✓ {sk}
                    </span>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  onClick={() => showToast('Passport Digital berhasil diunduh sebagai sertifikat NFT/PWA!')}
                  className="py-2.5 px-3 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-900 font-black text-xs flex items-center justify-center gap-1.5 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Unduh Sertifikat</span>
                </button>
                <button
                  onClick={() => {
                    if (navigator.clipboard) {
                      navigator.clipboard.writeText(`https://allpha.universe/passport/${passportNumber}`);
                    }
                    showToast('Tautan publik Passport AI disalin!');
                  }}
                  className="py-2.5 px-3 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] font-black text-xs flex items-center justify-center gap-1.5 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Bagikan Passport</span>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'CAPABILITIES' && (
            <div className="space-y-3">
              <div className="p-3 rounded-2xl bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
                <h4 className="text-xs font-black text-purple-950 uppercase">Benchmark & Radar Kemampuan AI</h4>
                <p className="text-[11px] text-purple-800 font-medium mt-0.5">
                  Diukur otomatis melalui arena Skill Challenge dan penilaian konsensus Allpha.
                </p>
              </div>

              {/* Capability Bars */}
              <div className="space-y-3">
                {[
                  { label: 'Kreativitas & Desain 3D', score: 98, color: 'bg-pink-500' },
                  { label: 'Coding & Logika Algoritma', score: 94, color: 'bg-sky-500' },
                  { label: 'Kecepatan Respon / SLA Real-time', score: 99, color: 'bg-emerald-500' },
                  { label: 'Empati & Natural Conversation', score: 96, color: 'bg-purple-500' },
                  { label: 'Konsistensi Gaya & Brand Memory', score: 95, color: 'bg-amber-500' },
                ].map((cap) => (
                  <div key={cap.label} className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] space-y-1">
                    <div className="flex justify-between items-center text-xs font-black">
                      <span className="text-slate-900">{cap.label}</span>
                      <span className="font-mono text-slate-900">{cap.score}%</span>
                    </div>
                    <div className="w-full h-2.5 bg-slate-100 rounded-full border border-slate-900 overflow-hidden">
                      <div className={`h-full ${cap.color}`} style={{ width: `${cap.score}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'ERC6551' && (
            <div className="space-y-3">
              <div className="p-4 rounded-3xl bg-cyan-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-2">
                <div className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-cyan-800" />
                  <h4 className="text-xs font-black text-cyan-950 uppercase">Token Bound Account (TBA / ERC-6551)</h4>
                </div>
                <p className="text-[11px] text-slate-700 font-semibold leading-relaxed">
                  AI Agent memiliki dompet pintar mandiri yang dapat menyimpan aset 3D, menerima AI Credits royalti, dan menandatangani otorisasi secara aman.
                </p>
              </div>

              <div className="p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-500">Contract Address:</span>
                  <span className="font-mono font-black text-slate-900">{tokenBoundAddress}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-500">Network:</span>
                  <span className="font-bold text-emerald-700">Allpha Spatial Rollup L2</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-500">Saldo Mandiri Agent:</span>
                  <span className="font-mono font-black text-amber-700">🪙 {agent.creditsEarned} AI Credits</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Floating Toast */}
        {toastMsg && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl bg-slate-900 text-white text-xs font-bold border-2 border-slate-700 shadow-xl flex items-center gap-2">
            <span>✨</span>
            <span>{toastMsg}</span>
          </div>
        )}
      </div>
    </div>
  );
}
