'use client';

import React, { useEffect, useRef, useState } from 'react';
import { 
  Bell, 
  X, 
  CheckCheck, 
  Sparkles
} from 'lucide-react';

interface NotificationItem {
  id: string;
  category: 'ALL' | 'AI_AGENT' | 'SOCIAL' | 'CREDITS' | 'SYSTEM';
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  avatar?: string;
  badge?: string;
  badgeColor?: string;
}

interface NotificationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: NotificationItem[];
  loading?: boolean;
  error?: string;
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  onNavigateToTab?: (tab: string) => void;
  onOpenCreditsHub?: () => void;
  onOpenMessages?: () => void;
  onOpenLiveStage?: () => void;
}

export default function NotificationsModal({
  isOpen,
  onClose,
  notifications,
  loading = false,
  error = "",
  onMarkRead,
  onMarkAllRead,
}: NotificationsModalProps) {
  const [activeTab, setActiveTab] = useState<'ALL' | 'AI_AGENT' | 'SOCIAL' | 'CREDITS' | 'SYSTEM'>('ALL');
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const previousActiveElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable?.length) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousActiveElement?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filtered = notifications.filter((n) => {
    if (activeTab === 'ALL') return true;
    return n.category === activeTab;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="notifications-modal-title" tabIndex={-1} className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-4 border-b-2 border-slate-900 bg-[#BAE6FD] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-slate-900">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h2 id="notifications-modal-title" className="text-sm font-black text-slate-900 tracking-tight">NOTIFIKASI AKTIVITAS</h2>
              <p className="text-[10px] font-bold text-slate-700">Pemberitahuan Sosial, AI Agent, & Credits</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onMarkAllRead}
              className="text-[10px] font-black text-slate-800 bg-white hover:bg-slate-50 px-2 py-1 rounded-lg border border-slate-900 shadow-[1px_1px_0px_#0f172a] flex items-center gap-1 cursor-pointer"
            >
              <CheckCheck className="w-3 h-3 text-emerald-700" />
              <span>Tandai Semua Dibaca</span>
            </button>
            <button
              ref={closeButtonRef}
              type="button"
              aria-label="Tutup notifikasi"
              onClick={onClose}
              className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-700 hover:bg-slate-100"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Categories Tab Bar */}
        <div className="flex border-b-2 border-slate-900 bg-slate-100 p-1.5 gap-1 overflow-x-auto no-scrollbar text-xs font-black">
          {[
            { id: 'ALL', label: 'Semua' },
            { id: 'AI_AGENT', label: '🤖 AI Agent' },
            { id: 'SOCIAL', label: '💬 Sosial' },
            { id: 'CREDITS', label: '🪙 Finansial' },
            { id: 'SYSTEM', label: '🛡️ Sistem' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3 py-1.5 rounded-xl border-2 transition whitespace-nowrap cursor-pointer ${
                activeTab === tab.id
                  ? 'bg-white border-slate-900 text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Notifications List */}
        <div className="p-3 sm:p-4 overflow-y-auto space-y-2.5 flex-1">
          {loading ? (
            <div role="status" className="py-12 text-center text-slate-500 space-y-1"><Bell className="w-8 h-8 mx-auto text-slate-300 stroke-[1.5]" /><p className="text-xs font-bold">Memuat notifikasi…</p></div>
          ) : error ? (
            <div role="alert" className="py-8 text-center text-rose-700 text-xs font-bold">{error}</div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-slate-500 space-y-1">
              <Bell className="w-8 h-8 mx-auto text-slate-300 stroke-[1.5]" />
              <p className="text-xs font-bold">Tidak ada notifikasi di kategori ini</p>
            </div>
          ) : (
            filtered.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => { if (!item.isRead) onMarkRead(item.id); }}
                aria-label={item.isRead ? item.title : item.title + " — tandai dibaca"}
                className={`w-full text-left p-3 rounded-2xl border-2 border-slate-900 transition flex items-start gap-3 ${
                  item.isRead ? 'bg-white shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-[#FEF08A]/30 shadow-[2.5px_2.5px_0px_#0f172a]'
                }`}
              >
                {/* Avatar / Icon */}
                <div className="relative shrink-0">
                  {item.avatar ? (
                    <img src={item.avatar} alt="Avatar" className="w-9 h-9 rounded-xl border-2 border-slate-900 object-cover" />
                  ) : (
                    <div className="w-9 h-9 rounded-xl bg-purple-100 border-2 border-slate-900 flex items-center justify-center text-purple-700">
                      <Sparkles className="w-4 h-4" />
                    </div>
                  )}
                  {!item.isRead && (
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 border border-white absolute -top-1 -right-1" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 space-y-0.5">
                  <div className="flex items-center justify-between gap-1">
                    <h4 className="text-xs font-black text-slate-900">{item.title}</h4>
                    <span className="text-[9.5px] text-slate-400 font-bold shrink-0">{item.timestamp}</span>
                  </div>
                  <p className="text-[11px] text-slate-600 font-medium leading-relaxed">{item.message}</p>
                  
                  {item.badge && (
                    <span className={`inline-block mt-1 px-2 py-0.5 rounded-md border text-[9px] font-black ${item.badgeColor}`}>
                      {item.badge}
                    </span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t-2 border-slate-900 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-900 text-white font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}
