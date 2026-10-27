'use client';

import React, { useState } from 'react';
import { Palette, Check, Sparkles, X, Sun, Moon, Eye } from 'lucide-react';

export interface ThemeItem {
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
  themes?: ThemeItem[];
  onSelectTheme: (themeId: string, themeName: string) => boolean | Promise<boolean>;
}

export default function ThemeCatalogModal({
  isOpen,
  onClose,
  currentThemeId = '',
  themes = [],
  onSelectTheme,
}: ThemeCatalogModalProps) {
  const [selectedId, setSelectedId] = useState(currentThemeId);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const THEMES: ThemeItem[] = themes;

  if (!isOpen) return null;

  const handleApply = async (theme: ThemeItem) => {
    const applied = await onSelectTheme(theme.id, theme.name);
    if (!applied) {
      showToast("Penerapan tema belum dikonfirmasi oleh layanan tema kanonis.");
      return;
    }
    setSelectedId(theme.id);
    showToast(`Tema "${theme.name}" diterapkan oleh layanan tema kanonis.`);
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
          {THEMES.length === 0 && (
            <div className="p-5 rounded-3xl border-2 border-dashed border-slate-400 bg-slate-50 text-center">
              <Palette className="w-7 h-7 mx-auto mb-2 text-slate-400" />
              <p className="text-xs font-black text-slate-800">Katalog tema kanonis belum tersedia.</p>
              <p className="mt-1 text-[10px] font-semibold text-slate-500">Tema tidak diisi dengan contoh statis. Daftar akan muncul setelah adapter tema tersambung.</p>
            </div>
          )}
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
