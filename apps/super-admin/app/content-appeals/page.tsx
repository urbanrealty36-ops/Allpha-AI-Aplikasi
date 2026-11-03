"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type Operator = { id: string; email?: string; scopes: string[] };
type Appeal = { id: string; content_id: string; owner_id: string; submitted_version: number; reason: string; status: string; created_at: string; content?: { body: string; content_type: string; version: number; status: string; moderation_status: string } | null };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(supabaseUrl + "/auth/v1/token?grant_type=" + grant, { method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let active = session;
  if (active.expires_at <= Date.now() + 30000) active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}), Authorization: "Bearer " + token } });
  let response = await send(active.access_token);
  if (response.status === 401) { active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token"); response = await send(active.access_token); }
  return response;
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error?.message || data.detail?.message || "Permintaan gagal (HTTP " + response.status + ").");
  return data as T;
}

export default function ContentAppealsPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [items, setItems] = useState<Appeal[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadQueue = useCallback(async (active: Session) => {
    const result = await read<{ items: Appeal[] }>(await apiFetch("/v1/content/admin/appeal-queue?limit=100", active));
    setItems(Array.isArray(result.items) ? result.items : []);
  }, []);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const active = await authRequest({ email: email.trim(), password }, "password");
      const access = await read<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
      if (!access.operator.scopes.includes("platform:content.moderate")) throw new Error("Scope platform:content.moderate diperlukan.");
      setSession(active); setOperator(access.operator); setPassword(""); await loadQueue(active);
    } catch (cause) { setSession(null); setOperator(null); setError(cause instanceof Error ? cause.message : "Login operator gagal."); }
    finally { setBusy(false); }
  }

  async function decide(item: Appeal, decision: "approve" | "reject") {
    const reason = (reasons[item.id] || "").trim();
    if (reason.length < 8) { setError("Alasan keputusan minimal 8 karakter."); return; }
    if (!session) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await read<{ message?: string }>(await apiFetch("/v1/content/admin/appeals/" + item.id + "/review", session, { method: "POST", body: JSON.stringify({ decision, reason }) }));
      setNotice(result.message || "Keputusan banding tersimpan.");
      await loadQueue(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan banding gagal."); }
    finally { setBusy(false); }
  }

  return <main className="mx-auto min-h-screen w-full max-w-5xl px-5 py-8 text-slate-900 dark:text-slate-100">
    <nav className="mb-6 flex items-center justify-between"><Link href="/content-moderation" className="text-sm text-blue-600 hover:underline">← Moderasi konten</Link><span className="text-xs uppercase tracking-[0.18em] text-slate-500">ENG-P13 · Appeals</span></nav>
    <header className="mb-6"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700">Trust & Safety</p><h1 className="mt-2 text-3xl font-semibold">Banding moderasi konten</h1><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Banding diperiksa manusia. Persetujuan banding mengembalikan konten ke antrean moderasi, bukan langsung mempublikasikannya.</p></header>
    {error ? <p role="alert" className="mb-4 rounded-xl border border-red-300 p-3 text-sm text-red-700">{error}</p> : null}
    {notice ? <p role="status" className="mb-4 rounded-xl border border-emerald-300 p-3 text-sm text-emerald-800">{notice}</p> : null}
    {!session || !operator ? <form onSubmit={login} className="max-w-md space-y-4 rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><h2 className="font-semibold">Login operator</h2><label className="block text-sm">Email<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600" /></label><label className="block text-sm">Password<input type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600" /></label><button disabled={busy} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Memverifikasi…" : "Masuk & verifikasi scope"}</button></form> : <section>
      <div className="mb-4 flex items-center justify-between gap-3"><p className="text-xs text-slate-500">Operator: {operator.email || operator.id} · {items.length} banding menunggu</p><button disabled={busy} onClick={() => void loadQueue(session)} className="text-sm text-blue-600">Muat ulang</button></div>
      {items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">Tidak ada banding yang menunggu pemeriksaan.</div> : <div className="space-y-4">{items.map(item => <article key={item.id} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
        <div className="flex flex-wrap justify-between gap-3"><strong>{item.content?.content_type || "Konten"} · versi diajukan {item.submitted_version}</strong><span className="text-xs text-slate-500">{new Date(item.created_at).toLocaleString("id-ID")}</span></div>
        <p className="mt-3 whitespace-pre-wrap text-sm">{item.content?.body || "(Konten media tanpa teks)"}</p>
        <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800"><strong>Alasan banding</strong><p className="mt-1 whitespace-pre-wrap">{item.reason}</p></div>
        <p className="mt-2 text-xs text-slate-500">Konten {item.content_id} · Pemilik {item.owner_id} · {item.content?.status}/{item.content?.moderation_status}</p>
        <label className="mt-4 block text-sm">Alasan keputusan<textarea value={reasons[item.id] || ""} onChange={event => setReasons(prev => ({ ...prev, [item.id]: event.target.value }))} minLength={8} maxLength={500} required className="mt-1 min-h-20 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-600" /></label>
        <div className="mt-3 flex flex-wrap gap-2"><button disabled={busy} onClick={() => void decide(item, "approve")} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Terima banding · review ulang</button><button disabled={busy} onClick={() => void decide(item, "reject")} className="rounded-xl bg-red-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Tolak banding</button></div>
      </article>)}</div>}
    </section>}
  </main>;
}
