'use client';

import React, { useEffect, useState } from 'react';
import { Palette, Check, Sparkles, X, Sun, Moon, Eye } from 'lucide-react';

interface ThemeItem {
  id: string;
  name: string;
  subtitle: string;
  paletteColors: string[];
  borderStyle: string;
  description: string;
  badge: string;
}

interface ThemeCatalogModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentThemeId?: string;
  onSelectTheme: (themeId: string, themeName: string) => Promise<void> | void;
}

export default function ThemeCatalogModal({
  isOpen,
  onClose,
  currentThemeId = 'menggu-pastel',
  onSelectTheme,
}: ThemeCatalogModalProps) {
  const [selectedId, setSelectedId] = useState(currentThemeId);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  useEffect(() => { setSelectedId(currentThemeId); }, [currentThemeId, isOpen]);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const THEMES: ThemeItem[] = [
    {
      id: 'menggu-pastel',
      name: 'Soft Pastel Menggu (Default 2026)',
      subtitle: 'Playful, ramah, dan menenangkan dengan palet pastel lembut',
      paletteColors: ['#FEF08A', '#DDD6FE', '#BAE6FD', '#BBF7D0', '#FECDD3'],
      borderStyle: 'border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]',
      description: 'Perpaduan warna butter yellow, soft lavender, sky blue, dan blush pink dengan border tactile Neo-Brutalism.',
      badge: 'TERPOPULER'
    },
    {
      id: 'neo-brutal-slate',
      name: 'Playful Neo-Brutalist Spatial',
      subtitle: 'Kontras tinggi, border tebal 3px, dan bayangan taktil retro pop',
      paletteColors: ['#F43F5E', '#0EA5E9', '#FBBF24', '#10B981', '#0F172A'],
      borderStyle: 'border-3 border-slate-950 shadow-[4px_4px_0px_#000]',
      description: 'Estetika desain web modern dengan batas tegas, tipografi kuat, dan nuansa arcade futuristik.',
      badge: 'PRO'
    },
    {
      id: 'cyberpunk-tokyo',
      name: 'Neo Tokyo Cyberpunk',
      subtitle: 'Neon cyan, magenta, dan gelapnya distrik kota masa depan',
      paletteColors: ['#06B6D4', '#EC4899', '#A855F7', '#1E1B4B', '#09090B'],
      borderStyle: 'border-2 border-cyan-400 shadow-[3px_3px_0px_#ec4899]',
      description: 'Ideal untuk penjelajahan 3D Universe malam hari dan panggung konser live stage virtual.',
      badge: '3D SPATIAL'
    },
    {
      id: 'crystal-oasis',
      name: 'Crystal City Oasis',
      subtitle: 'Pantulan air jernih, biophilic design, dan emerald glass',
      paletteColors: ['#38BDF8', '#34D399', '#F0FDF4', '#047857', '#0F172A'],
      borderStyle: 'border-2 border-emerald-800 shadow-[3px_3px_0px_#047857]',
      description: 'Warna alam segar yang dipadukan dengan kaca PBR futuristik untuk suasana santai.',
      badge: 'BIO-TECH'
    },
  ];

  if (!isOpen) return null;

  const handleApply = (theme: ThemeItem) => {
    setSelectedId(theme.id);
    onSelectTheme(theme.id, theme.name);
    showToast(`Tema "${theme.name}" berhasil diterapkan ke Allpha Universe!`);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-4 border-b-2 border-slate-900 bg-[#FEF08A] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-slate-900">
              <Palette className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 tracking-tight">KATALOG TEMA & UI STYLES</h2>
              <p className="text-[10px] font-bold text-slate-700">Kustomisasi Nuansa Visual Web & Spatial Universe</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-700 hover:bg-slate-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Theme Cards List */}
        <div className="p-4 overflow-y-auto space-y-3.5 flex-1">
          {THEMES.map((th) => {
            const isSelected = selectedId === th.id;

            return (
              <div
                key={th.id}
                onClick={() => handleApply(th)}
                className={`p-4 rounded-3xl border-3 border-slate-900 transition cursor-pointer text-left space-y-2.5 ${
                  isSelected
                    ? 'bg-amber-50 shadow-[4px_4px_0px_#0f172a] ring-2 ring-amber-400'
                    : 'bg-white hover:bg-slate-50 shadow-[2px_2px_0px_#0f172a]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs sm:text-sm font-black text-slate-900">{th.name}</h3>
                    <span className="text-[9px] font-black px-2 py-0.5 rounded-md bg-purple-100 text-purple-900 border border-purple-300">
                      {th.badge}
                    </span>
                  </div>
                  {isSelected && (
                    <span className="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-black border border-slate-900">
                      ✓
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-slate-600 font-medium leading-snug">{th.description}</p>

                {/* Color Swatches */}
                <div className="flex items-center gap-1.5 pt-1">
                  <span className="text-[10px] font-bold text-slate-500 mr-1">Palet:</span>
                  {th.paletteColors.map((c, i) => (
                    <div
                      key={i}
                      className="w-5 h-5 rounded-lg border border-slate-900 shadow-2xs"
                      style={{ backgroundColor: c }}
                      title={c}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-3 border-t-2 border-slate-900 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-900 text-white font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
          >
            Selesai
          </button>
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
