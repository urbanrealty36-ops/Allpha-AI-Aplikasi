"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type AuthResponse = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
type Operator = { id: string; email?: string; scopes: string[] };
type Report = { id: string; content_id: string; reporter_user_id: string; reason: string; details?: string | null; status: string; created_at: string; content?: { id: string; owner_id: string; body: string; content_type: string; status: string; moderation_status: string; version: number; media?: { id: string; filename: string; media_type: string; preview_url?: string | null }[] } | null };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=${grant}`, { method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as AuthResponse;
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let current = session;
  if (current.expires_at <= Date.now() + 30000) current = await authRequest({ refresh_token: current.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}), Authorization: `Bearer ${token}` } });
  let response = await send(current.access_token);
  if (response.status === 401) { current = await authRequest({ refresh_token: current.refresh_token }, "refresh_token"); response = await send(current.access_token); }
  return response;
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as { error?: { message?: string } };
  if (!response.ok) throw new Error(data.error?.message || `Permintaan gagal (HTTP ${response.status}).`);
  return data as T;
}

export default function ContentReportsPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [items, setItems] = useState<Report[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");

  const loadQueue = useCallback(async (active: Session) => {
    const result = await read<{ items: Report[] }>(await apiFetch("/v1/admin/content-reports", active));
    setItems(Array.isArray(result.items) ? result.items : []);
  }, []);

  const verify = useCallback(async (active: Session) => {
    const result = await read<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
    setOperator(result.operator);
    if (!result.operator.scopes.includes("platform:content.moderate")) throw new Error("Scope platform:content.moderate diperlukan untuk mengelola laporan.");
    await loadQueue(active);
  }, [loadQueue]);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const active = await authRequest({ email: email.trim(), password }, "password"); setSession(active); setPassword(""); await verify(active); }
    catch (cause) { setSession(null); setOperator(null); setError(cause instanceof Error ? cause.message : "Login operator gagal."); }
    finally { setBusy(false); }
  }

  async function review(item: Report, decision: "dismiss" | "hide_content") {
    const reason = (reasons[item.id] || "").trim();
    if (reason.length < 8) { setError("Alasan peninjauan minimal 8 karakter."); return; }
    if (!session) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await read(await apiFetch(`/v1/admin/content-reports/${item.id}/review`, session, { method: "POST", body: JSON.stringify({ decision, reason }) }));
      setNotice(decision === "hide_content" ? "Konten disembunyikan dan laporan ditindaklanjuti." : "Laporan ditandai selesai tanpa menghapus konten.");
      await loadQueue(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Laporan gagal diproses."); }
    finally { setBusy(false); }
  }

  return <main className="mx-auto min-h-screen w-full max-w-5xl px-5 py-8 text-slate-900 dark:text-slate-100">
    <nav className="mb-8 flex items-center justify-between gap-3"><Link href="/content-moderation" className="text-sm text-blue-600 hover:underline">← Moderasi konten</Link><span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ENG-P14 · Reports</span></nav>
    <header className="mb-8"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">Trust & Safety</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Laporan konten</h1><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Antrean laporan memerlukan scope operator platform:content.moderate. Semua keputusan dicatat dalam audit.</p></header>
    {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-300 p-3 text-sm text-emerald-800">{notice}</p>}
    {!session || !operator ? <form className="max-w-md space-y-4 rounded-2xl border border-slate-200 p-5 dark:border-slate-700" onSubmit={login}>
      <h2 className="text-lg font-semibold">Login operator</h2><label className="block text-sm">Email<input className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></label>
      <label className="block text-sm">Kata sandi<input className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
      <button className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900" disabled={busy}>{busy ? "Memverifikasi…" : "Masuk & verifikasi scope"}</button>
    </form> : <>
      <div className="mb-5 flex items-center justify-between rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700"><span>Operator: {operator.email || operator.id}</span><button className="text-blue-600 hover:underline" onClick={() => void loadQueue(session)} disabled={busy}>Muat ulang antrean</button></div>
      {items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">Tidak ada laporan yang menunggu peninjauan.</div> : <div className="space-y-4">{items.map(item => <article key={item.id} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">Alasan: {item.reason}</p><p className="mt-1 text-xs text-slate-500">Laporan {item.id.slice(0, 8)} · konten {item.content_id.slice(0, 8)} · {new Date(item.created_at).toLocaleString()}</p></div><span className="rounded-full border border-amber-300 px-3 py-1 text-xs text-amber-800">{item.status}</span></div>
        <p className="mt-3 whitespace-pre-wrap text-sm">{item.content?.body || (item.content?.media?.length ? "[Konten berisi media]" : "[Konten tidak tersedia]")}</p>
        {item.content?.media?.map(media => media.preview_url && (media.media_type.startsWith("video/")
          ? <video key={media.id} src={media.preview_url} controls playsInline className="mt-3 max-h-[420px] w-full rounded-xl bg-black" />
          : media.media_type.startsWith("audio/") ? <audio key={media.id} src={media.preview_url} controls preload="metadata" className="mt-3 w-full" aria-label={media.filename} /> : <img key={media.id} src={media.preview_url} alt={media.filename} className="mt-3 max-h-[420px] w-full rounded-xl object-contain" />))}
        <p className="mt-2 text-xs text-slate-500">Reporter: {item.reporter_user_id} · Creator: {item.content?.owner_id || "tidak tersedia"}</p>
        {item.details && <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800">{item.details}</p>}
        <label className="mt-4 block text-sm">Alasan keputusan<textarea className="mt-1 min-h-20 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600" value={reasons[item.id] || ""} onChange={e => setReasons(current => ({ ...current, [item.id]: e.target.value }))} minLength={8} maxLength={500} required /></label>
        <div className="mt-3 flex flex-wrap gap-2"><button className="rounded-xl border border-slate-300 px-4 py-2 text-sm dark:border-slate-600" disabled={busy} onClick={() => void review(item, "dismiss")}>Tutup laporan</button><button className="rounded-xl bg-red-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} onClick={() => void review(item, "hide_content")}>Sembunyikan konten</button></div>
      </article>)}</div>}
    </>}
  </main>;
}
