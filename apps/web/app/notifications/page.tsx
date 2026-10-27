"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type NotificationItem = {
  id: string;
  category: string;
  event_key: string;
  title: string;
  body: string;
  payload: Record<string, unknown>;
  delivery_state: "queued" | "delivered" | "failed" | "suppressed";
  read_at: string | null;
  delivered_at: string | null;
  created_at: string;
  expires_at: string | null;
};
type InboxResponse = { items: NotificationItem[]; unread_count: number; limit: number };
type NotificationPreferences = { social_activity: boolean; community: boolean; workspace: boolean; product_updates: boolean; security_alerts: boolean; push_enabled: boolean };
type ApiError = { detail?: { message?: string }; error?: { message?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

export default function NotificationsPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [preferencesBusy, setPreferencesBusy] = useState(false);
  const requestSequence = useRef(0);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) setSession(data.session); });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; requestSequence.current += 1; data.subscription.unsubscribe(); };
  }, [supabase]);

  const api = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!session) throw new Error("Masuk terlebih dahulu untuk melihat notifikasi.");
    const response = await fetch(apiBase + path, {
      ...init,
      headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", ...(init.headers || {}) },
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({})) as T & ApiError;
    if (!response.ok) throw new Error(data.detail?.message || data.error?.message || "Permintaan notifikasi gagal (" + response.status + ").");
    return data as T;
  }, [session]);

  const load = useCallback(async () => {
    if (!session) { setItems([]); setUnreadCount(0); setLoading(false); return; }
    const sequence = ++requestSequence.current;
    setLoading(true); setError("");
    try {
      const query = unreadOnly ? "?unread_only=true&limit=100" : "?limit=100";
      const result = await api<InboxResponse>("/v1/notifications" + query);
      if (sequence !== requestSequence.current) return;
      setItems(result.items || []);
      setUnreadCount(result.unread_count || 0);
    } catch (cause) {
      if (sequence === requestSequence.current) setError(cause instanceof Error ? cause.message : "Notifikasi tidak dapat dimuat.");
    } finally { if (sequence === requestSequence.current) setLoading(false); }
  }, [api, session, unreadOnly]);

  useEffect(() => { void load(); }, [load]);

  const loadPreferences = useCallback(async () => {
    if (!session) { setPreferences(null); return; }
    try {
      const result = await api<{ preferences: NotificationPreferences }>("/v1/notifications/preferences");
      setPreferences(result.preferences);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preferensi notifikasi tidak dapat dimuat.");
    }
  }, [api, session]);

  useEffect(() => { void loadPreferences(); }, [loadPreferences]);

  async function updatePreference(key: keyof NotificationPreferences, value: boolean) {
    setPreferencesBusy(true); setError("");
    try {
      const result = await api<{ preferences: NotificationPreferences }>("/v1/notifications/preferences", {
        method: "PATCH", body: JSON.stringify({ [key]: value }),
      });
      setPreferences(result.preferences);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preferensi notifikasi tidak dapat disimpan.");
    } finally { setPreferencesBusy(false); }
  }

  async function markRead(item: NotificationItem) {
    if (item.read_at) return;
    setBusyId(item.id); setError(""); setNotice("");
    try {
      await api("/v1/notifications/" + encodeURIComponent(item.id) + "/read", { method: "PATCH", body: "{}" });
      setItems(current => current.map(row => row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row));
      setUnreadCount(count => Math.max(0, count - 1));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Status baca tidak dapat disimpan."); }
    finally { setBusyId(null); }
  }

  async function markAllRead() {
    setBusyId("all"); setError(""); setNotice("");
    try {
      const result = await api<{ updated_count: number }>("/v1/notifications/read-all", { method: "POST", body: "{}" });
      setItems(current => current.map(row => row.read_at ? row : { ...row, read_at: new Date().toISOString() }));
      setUnreadCount(0);
      setNotice(result.updated_count + " notifikasi ditandai sudah dibaca.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Notifikasi tidak dapat ditandai sudah dibaca."); }
    finally { setBusyId(null); }
  }

  if (!session) return <><main className="allpha-page allpha-notifications-page mx-auto max-w-3xl p-6 text-slate-100"><h1 className="text-2xl font-semibold">Notifikasi</h1><p className="mt-3 text-slate-300">Masuk melalui halaman utama Allpha untuk melihat kotak notifikasi.</p><a className="mt-4 inline-block underline" href="/">Kembali ke Allpha</a></main></>;

  return <><main className="allpha-page allpha-notifications-page mx-auto max-w-3xl space-y-5 p-4 text-slate-100 sm:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-300">Allpha Universe</p><h1 className="mt-1 text-2xl font-semibold">Notifikasi</h1><p className="mt-1 text-sm text-slate-400">{unreadCount} belum dibaca</p></div>
      <div className="flex flex-wrap gap-2"><a className="rounded-xl border border-slate-700 px-3 py-2 text-sm" href="/">Beranda</a><button className="rounded-xl border border-slate-700 px-3 py-2 text-sm disabled:opacity-50" onClick={() => void load()} disabled={loading}>Muat ulang</button><button className="rounded-xl bg-indigo-500 px-3 py-2 text-sm font-medium disabled:opacity-50" onClick={() => void markAllRead()} disabled={loading || busyId !== null || unreadCount === 0}>Baca semua</button></div>
    </header>
    <section className="rounded-2xl border border-slate-800 p-4">
      <h2 className="font-semibold">Preferensi notifikasi</h2>
      <p className="mt-1 text-sm text-slate-400">Atur kategori inbox dan izin push perangkat.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {([
          ["social_activity", "Aktivitas sosial"],
          ["community", "Komunitas"],
          ["workspace", "Workspace"],
          ["product_updates", "Pembaruan produk"],
          ["security_alerts", "Peringatan keamanan"],
          ["push_enabled", "Push ke perangkat"],
        ] as const).map(([key, label]) => (
          <label key={key} className="flex items-center gap-3 rounded-xl border border-slate-800 p-3 text-sm">
            <input type="checkbox" checked={preferences?.[key] ?? true} disabled={!preferences || preferencesBusy}
              onChange={event => void updatePreference(key, event.target.checked)}
              className="h-4 w-4 accent-indigo-400" />
            <span>{label}</span>
          </label>
        ))}
      </div>
    </section>
    <div className="flex gap-2" role="group" aria-label="Filter notifikasi"><button className={"rounded-full px-4 py-2 text-sm " + (!unreadOnly ? "bg-slate-100 text-slate-900" : "border border-slate-700")} onClick={() => setUnreadOnly(false)}>Semua</button><button className={"rounded-full px-4 py-2 text-sm " + (unreadOnly ? "bg-slate-100 text-slate-900" : "border border-slate-700")} onClick={() => setUnreadOnly(true)}>Belum dibaca</button></div>
    {error ? <div role="alert" className="rounded-xl border border-rose-400/40 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</div> : null}
    {notice ? <p role="status" className="text-sm text-emerald-300">{notice}</p> : null}
    {loading ? <div className="rounded-2xl border border-slate-800 p-8 text-center text-slate-400">Memuat notifikasi…</div> :
      items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-700 p-8 text-center"><h2 className="font-medium">Belum ada notifikasi</h2><p className="mt-2 text-sm text-slate-400">Notifikasi baru akan muncul di sini setelah dibuat oleh layanan Allpha.</p></div> :
      <ul className="space-y-3">{items.map(item => <li key={item.id} className={"rounded-2xl border p-4 " + (item.read_at ? "border-slate-800 bg-slate-950/30" : "border-indigo-400/40 bg-indigo-950/20")}>
        <div className="flex items-start gap-3"><span aria-hidden="true" className={"mt-1 h-2.5 w-2.5 shrink-0 rounded-full " + (item.read_at ? "bg-slate-600" : "bg-indigo-400")} /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-start justify-between gap-2"><h2 className="font-semibold">{item.title}</h2><time className="text-xs text-slate-500" dateTime={item.created_at}>{new Date(item.created_at).toLocaleString("id-ID")}</time></div>{item.body ? <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{item.body}</p> : null}<p className="mt-2 text-xs text-slate-500">{item.category.replaceAll("_", " ")} · {item.delivery_state === "delivered" ? "Terkirim ke inbox" : item.delivery_state === "queued" ? "Menunggu pengiriman" : item.delivery_state === "suppressed" ? "Pengiriman ditahan" : "Pengiriman gagal"}</p>{!item.read_at ? <button className="mt-3 rounded-lg border border-slate-700 px-3 py-1.5 text-sm disabled:opacity-50" disabled={busyId !== null} onClick={() => void markRead(item)}>{busyId === item.id ? "Menyimpan…" : "Tandai dibaca"}</button> : <p className="mt-3 text-xs text-slate-500">Sudah dibaca</p>}</div></div>
      </li>)}</ul>}
  </main></>;
}
