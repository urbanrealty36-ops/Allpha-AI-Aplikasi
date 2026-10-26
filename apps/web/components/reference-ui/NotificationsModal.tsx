'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, Bot, X, CheckCheck, Sparkles, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import { getBrowserSupabase } from '@/lib/supabase';

type Category = 'ALL' | 'AI_AGENT' | 'SOCIAL' | 'CREDITS' | 'SYSTEM';
type ApiNotification = {
  id: string;
  category: string;
  event_key: string;
  title: string;
  body: string;
  payload?: Record<string, unknown>;
  delivery_state: 'queued' | 'delivered' | 'failed' | 'suppressed';
  read_at: string | null;
  created_at: string;
};
type InboxResponse = { items: ApiNotification[]; unread_count: number };
type NotificationItem = {
  id: string;
  category: Exclude<Category, 'ALL'>;
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  badge?: string;
};

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === 'production' ? 'https://api.allpha.web.id' : 'http://localhost:8000')).replace(/\/$/, '');

function categoryFor(item: ApiNotification): Exclude<Category, 'ALL'> {
  const key = (item.event_key + ' ' + item.category).toLowerCase();
  if (/credit|billing|payment|royalt|settlement|wallet|finance/.test(key)) return 'CREDITS';
  if (/agent|runtime|goal|task|skill|passport/.test(key)) return 'AI_AGENT';
  if (/social|follow|like|comment|message|story|post/.test(key)) return 'SOCIAL';
  return 'SYSTEM';
}

function displayTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' });
}

export default function NotificationsModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [activeTab, setActiveTab] = useState<Category>('ALL');
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error('Masuk terlebih dahulu untuk melihat notifikasi.');
    const response = await fetch(apiBase + path, {
      ...init,
      headers: { Authorization: 'Bearer ' + session.access_token, Accept: 'application/json', 'Content-Type': 'application/json', ...(init.headers || {}) },
      cache: 'no-store',
    });
    const body = await response.json().catch(() => ({})) as { detail?: { message?: string }; error?: { message?: string } } & Partial<InboxResponse>;
    if (!response.ok) throw new Error(body.detail?.message || body.error?.message || 'Permintaan notifikasi gagal (' + response.status + ').');
    return body;
  }, [session]);

  const load = useCallback(async () => {
    if (!isOpen) return;
    if (!session) {
      setNotifications([]);
      setUnreadCount(0);
      setError('Masuk terlebih dahulu untuk melihat notifikasi akun Anda.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const body = await request('/v1/notifications?limit=100');
      const rows = Array.isArray(body.items) ? body.items as ApiNotification[] : [];
      setNotifications(rows.map(item => ({
        id: item.id,
        category: categoryFor(item),
        title: item.title,
        message: item.body || '',
        timestamp: displayTime(item.created_at),
        isRead: Boolean(item.read_at),
        badge: typeof item.payload?.display_badge === 'string' ? item.payload.display_badge : undefined,
      })));
      setUnreadCount(typeof body.unread_count === 'number' ? body.unread_count : rows.filter(item => !item.read_at).length);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Notifikasi tidak dapat dimuat.');
    } finally {
      setLoading(false);
    }
  }, [isOpen, request, session]);

  useEffect(() => { void load(); }, [load]);

  const markAllRead = async () => {
    if (!session || busy || unreadCount === 0) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await request('/v1/notifications/read-all', { method: 'POST', body: '{}' });
      setNotifications(current => current.map(item => ({ ...item, isRead: true })));
      setUnreadCount(0);
      setNotice('Semua notifikasi berhasil ditandai dibaca.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Status baca tidak dapat diperbarui.');
    } finally { setBusy(false); }
  };

  const markRead = async (item: NotificationItem) => {
    if (!session || item.isRead || busy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await request('/v1/notifications/' + encodeURIComponent(item.id) + '/read', { method: 'PATCH', body: '{}' });
      setNotifications(current => current.map(row => row.id === item.id ? { ...row, isRead: true } : row));
      setUnreadCount(count => Math.max(0, count - 1));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Notifikasi belum dapat ditandai dibaca.');
    } finally { setBusy(false); }
  };

  if (!isOpen) return null;
  const filtered = notifications.filter(item => activeTab === 'ALL' || item.category === activeTab);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-200" role="dialog" aria-modal="true" aria-label="Notifikasi aktivitas">
      <div className="relative w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col max-h-[90dvh]">
        <div className="p-4 border-b-2 border-slate-900 bg-[#BAE6FD] flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 shrink-0 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-slate-900"><Bell className="w-4 h-4" /></div>
            <div className="min-w-0"><h2 className="text-sm font-black text-slate-900 tracking-tight">NOTIFIKASI AKTIVITAS</h2><p className="text-[10px] font-bold text-slate-700">{unreadCount} belum dibaca · data akun Anda</p></div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={() => void markAllRead()} disabled={busy || loading || unreadCount === 0} className="text-[10px] font-black text-slate-800 bg-white hover:bg-slate-50 disabled:opacity-50 px-2 py-1 rounded-lg border border-slate-900 shadow-[1px_1px_0px_#0f172a] flex items-center gap-1"><CheckCheck className="w-3 h-3 text-emerald-700" /><span className="hidden sm:inline">Tandai Semua Dibaca</span><span className="sm:hidden">Baca Semua</span></button>
            <button onClick={onClose} className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-700 hover:bg-slate-100" aria-label="Tutup notifikasi"><X className="w-4 h-4" /></button>
          </div>
        </div>
        <div className="flex border-b-2 border-slate-900 bg-slate-100 p-1.5 gap-1 overflow-x-auto no-scrollbar text-xs font-black">
          {([{ id: 'ALL', label: 'Semua' }, { id: 'AI_AGENT', label: '🤖 AI Agent' }, { id: 'SOCIAL', label: '💬 Sosial' }, { id: 'CREDITS', label: '💳 Finansial & Credits' }, { id: 'SYSTEM', label: '⚙️ Sistem' }] as { id: Category; label: string }[]).map(tab => <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={'px-3 py-1.5 rounded-xl border-2 transition whitespace-nowrap ' + (activeTab === tab.id ? 'bg-white border-slate-900 text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]' : 'border-transparent text-slate-600 hover:text-slate-900')}>{tab.label}</button>)}
        </div>
        <div className="p-3 sm:p-4 overflow-y-auto space-y-2.5 flex-1 overscroll-contain">
          {error && <div className="rounded-xl border-2 border-rose-300 bg-rose-50 p-3 text-xs font-semibold text-rose-800 flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" /><span>{error}</span><button onClick={() => void load()} className="ml-auto underline">Coba lagi</button></div>}
          {notice && <div className="rounded-xl border-2 border-emerald-300 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800 flex gap-2"><CheckCircle2 className="w-4 h-4 shrink-0" /><span>{notice}</span></div>}
          {loading ? <div className="py-12 text-center text-slate-500"><RefreshCw className="w-6 h-6 mx-auto animate-spin" /><p className="mt-2 text-xs font-bold">Memuat notifikasi akun…</p></div> : filtered.length === 0 ? <div className="py-12 text-center text-slate-500 space-y-1"><Bell className="w-8 h-8 mx-auto text-slate-300 stroke-[1.5]" /><p className="text-xs font-bold">Tidak ada notifikasi di kategori ini</p></div> : filtered.map(item => (
            <button type="button" key={item.id} onClick={() => void markRead(item)} disabled={busy || item.isRead} className={'w-full text-left p-3 rounded-2xl border-2 border-slate-900 transition flex items-start gap-3 disabled:cursor-default ' + (item.isRead ? 'bg-white shadow-[1.5px_1.5px_0px_#0f172a]' : 'bg-[#FEF08A]/30 shadow-[2.5px_2.5px_0px_#0f172a]')}>
              <div className="relative shrink-0"><div className="w-9 h-9 rounded-xl bg-purple-100 border-2 border-slate-900 flex items-center justify-center text-purple-700">{item.category === 'AI_AGENT' ? <Bot className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}</div>{!item.isRead && <span className="w-2.5 h-2.5 rounded-full bg-rose-500 border border-white absolute -top-1 -right-1" />}</div>
              <div className="flex-1 min-w-0 space-y-0.5"><div className="flex items-start justify-between gap-2"><h4 className="text-xs font-black text-slate-900">{item.title}</h4><span className="text-[9.5px] text-slate-400 font-bold shrink-0">{item.timestamp}</span></div><p className="text-[11px] text-slate-600 font-medium leading-relaxed">{item.message}</p>{item.badge && <span className="inline-block mt-1 px-2 py-0.5 rounded-md border border-emerald-300 bg-emerald-100 text-emerald-900 text-[9px] font-black">{item.badge}</span>}</div>
            </button>
          ))}
        </div>
        <div className="p-3 border-t-2 border-slate-900 bg-slate-50 flex justify-between items-center gap-2"><button onClick={() => void load()} disabled={loading} className="px-3 py-2 rounded-xl bg-white text-slate-900 font-black text-xs border-2 border-slate-900 disabled:opacity-50"><RefreshCw className="inline w-3 h-3 mr-1" />Muat ulang</button><button onClick={onClose} className="px-5 py-2 rounded-xl bg-slate-900 text-white font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">Tutup</button></div>
      </div>
    </div>
  );
}
