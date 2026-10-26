'use client';

import React, { useState } from 'react';
import { 
  Bell, 
  Bot, 
  Heart, 
  MessageCircle, 
  Coins, 
  ShieldCheck, 
  X, 
  CheckCheck, 
  Sparkles,
  ArrowRight
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
  onNavigateToTab?: (tab: string) => void;
  onOpenCreditsHub?: () => void;
  onOpenMessages?: () => void;
  onOpenLiveStage?: () => void;
}

export default function NotificationsModal({
  isOpen,
  onClose,
  onNavigateToTab,
  onOpenCreditsHub,
  onOpenMessages,
  onOpenLiveStage,
}: NotificationsModalProps) {
  const [activeTab, setActiveTab] = useState<'ALL' | 'AI_AGENT' | 'SOCIAL' | 'CREDITS' | 'SYSTEM'>('ALL');
  const [notifications, setNotifications] = useState<NotificationItem[]>([
    {
      id: 'notif-1',
      category: 'AI_AGENT',
      title: 'Luna AI Membalas Konsultasi',
      message: 'Luna AI telah menjawab 3 pertanyaan seputar Desain 3D dan menghasilkan +45 AI Credits untuk Anda.',
      timestamp: '5 menit lalu',
      isRead: false,
      avatar: 'https://picsum.photos/seed/luna-cyber/80/80',
      badge: '+45 Credits',
      badgeColor: 'bg-amber-100 text-amber-900 border-amber-300'
    },
    {
      id: 'notif-2',
      category: 'CREDITS',
      title: 'Settlement Royalti Konten',
      message: 'Royalti 85% dari unduhan paket Crystal City Pack sebesar Rp 212.500 telah masuk ke saldo pendapatan Anda.',
      timestamp: '25 menit lalu',
      isRead: false,
      avatar: 'https://picsum.photos/seed/coin/80/80',
      badge: 'Rp 212.500',
      badgeColor: 'bg-emerald-100 text-emerald-900 border-emerald-300'
    },
    {
      id: 'notif-3',
      category: 'SOCIAL',
      title: 'Raka Pratama Menyukai Postingan Anda',
      message: 'Postingan Anda tentang "Peta Arsitektur Crystal City" disukai oleh 24 orang baru.',
      timestamp: '1 jam lalu',
      isRead: true,
      avatar: 'https://picsum.photos/seed/raka/80/80',
    },
    {
      id: 'notif-4',
      category: 'AI_AGENT',
      title: 'Nova AI Menyelesaikan Quest 3D',
      message: 'Nova AI menyelesaikan eksplorasi 3 district di Crystal City dan membuka bonus reputasi.',
      timestamp: '2 jam lalu',
      isRead: true,
      avatar: 'https://picsum.photos/seed/technova/80/80',
    },
    {
      id: 'notif-5',
      category: 'SYSTEM',
      title: 'Pembaruan ERC-6551 TBA Berhasil',
      message: 'Kontrak Token-Bound Account agen Anda telah diperbarui ke Allpha Spatial Rollup L2.',
      timestamp: '5 jam lalu',
      isRead: true,
      badge: 'Keamanan',
      badgeColor: 'bg-blue-100 text-blue-900 border-blue-300'
    },
  ]);

  if (!isOpen) return null;

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
  };

  const filtered = notifications.filter((n) => {
    if (activeTab === 'ALL') return true;
    return n.category === activeTab;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-4 border-b-2 border-slate-900 bg-[#BAE6FD] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-slate-900">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 tracking-tight">NOTIFIKASI AKTIVITAS</h2>
              <p className="text-[10px] font-bold text-slate-700">Pemberitahuan Sosial, AI Agent, & Credits</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleMarkAllRead}
              className="text-[10px] font-black text-slate-800 bg-white hover:bg-slate-50 px-2 py-1 rounded-lg border border-slate-900 shadow-[1px_1px_0px_#0f172a] flex items-center gap-1 cursor-pointer"
            >
              <CheckCheck className="w-3 h-3 text-emerald-700" />
              <span>Tandai Semua Dibaca</span>
            </button>
            <button
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
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-slate-500 space-y-1">
              <Bell className="w-8 h-8 mx-auto text-slate-300 stroke-[1.5]" />
              <p className="text-xs font-bold">Tidak ada notifikasi di kategori ini</p>
            </div>
          ) : (
            filtered.map((item) => (
              <div
                key={item.id}
                className={`p-3 rounded-2xl border-2 border-slate-900 transition flex items-start gap-3 ${
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
              </div>
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
