"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type Operator = { id: string; email?: string; scopes: string[] };
type CinemaTitle = {
  id: string; owner_id: string; title: string; genre: string; status: string;
  moderation_status: string; rights_status: string; version: number; updated_at: string;
};
type Queue = { items: CinemaTitle[] };
type AuthPayload = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(supabaseUrl + "/auth/v1/token?grant_type=" + grant, {
    method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" },
    body: JSON.stringify(body), cache: "no-store",
  });
  const data = await response.json().catch(() => ({})) as AuthPayload;
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let active = session;
  if (active.expires_at <= Date.now() + 30000) active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: {
    Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}),
    ...(init.headers || {}), Authorization: "Bearer " + token,
  }});
  let response = await send(active.access_token);
  if (response.status === 401) { active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token"); response = await send(active.access_token); }
  return response;
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as { detail?: { message?: string }; error?: { message?: string }; message?: string };
  if (!response.ok) throw new Error(data.detail?.message || data.error?.message || data.message || "Permintaan gagal (HTTP " + response.status + ").");
  return data as T;
}

export default function CinemaGovernancePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [moderation, setModeration] = useState<CinemaTitle[]>([]);
  const [rights, setRights] = useState<CinemaTitle[]>([]);
  const [lifecycle, setLifecycle] = useState<CinemaTitle[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadQueues = useCallback(async (active: Session) => {
    const [m, r, l] = await Promise.all([
      read<Queue>(await apiFetch("/v1/cinema/admin/moderation-queue?limit=100", active)),
      read<Queue>(await apiFetch("/v1/cinema/admin/rights-queue?limit=100", active)),
      read<Queue>(await apiFetch("/v1/cinema/admin/lifecycle-queue?limit=100", active)),
    ]);
    setModeration(m.items || []); setRights(r.items || []); setLifecycle(l.items || []);
  }, []);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const active = await authRequest({ email: email.trim(), password }, "password");
      const result = await read<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
      if (!result.operator.scopes.includes("platform:content.moderate")) throw new Error("Scope platform:content.moderate diperlukan untuk moderasi, rights review dan lifecycle.");
      setSession(active); setOperator(result.operator); setPassword(""); await loadQueues(active);
    } catch (cause) {
      setSession(null); setOperator(null);
      setError(cause instanceof Error ? cause.message : "Login operator gagal.");
    } finally { setBusy(false); }
  }

  async function refresh() {
    if (!session) return;
    setBusy(true); setError("");
    try { await loadQueues(session); } catch (cause) { setError(cause instanceof Error ? cause.message : "Antrean gagal dimuat."); }
    finally { setBusy(false); }
  }

  async function reviewRights(item: CinemaTitle, decision: "clear" | "reject") {
    const reason = (reasons[item.id] || "").trim();
    const evidenceReference = (evidence[item.id] || "").trim();
    if (reason.length < 8 || evidenceReference.length < 8 || !session) { setError("Alasan dan referensi bukti hak cipta wajib diisi (minimal 8 karakter)."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await read(await apiFetch("/v1/cinema/admin/titles/" + item.id + "/rights-review", session, {
        method: "POST", body: JSON.stringify({ decision, expected_version: item.version, evidence_reference: evidenceReference, reason }),
      }));
      setNotice("Keputusan hak cipta tercatat. Status moderasi dan publikasi tetap mengikuti gate terpisah.");
      await loadQueues(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Review hak cipta gagal."); }
    finally { setBusy(false); }
  }

  async function reviewModeration(item: CinemaTitle, decision: "approve" | "reject") {
    const reason = (reasons[item.id] || "").trim();
    if (reason.length < 8 || !session) { setError("Alasan moderasi minimal 8 karakter."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await read(await apiFetch("/v1/cinema/admin/titles/" + item.id + "/moderation", session, {
        method: "POST", body: JSON.stringify({ decision, expected_version: item.version, reason }),
      }));
      setNotice(decision === "approve" ? "Moderasi disetujui; publikasi hanya terjadi jika rights dan media readiness lolos." : "Judul ditolak pada tahap moderasi.");
      await loadQueues(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Moderasi gagal."); }
    finally { setBusy(false); }
  }

  async function lifecycleAction(item: CinemaTitle, action: "archive" | "block" | "restore_to_draft") {
    const reason = (reasons[item.id] || "").trim();
    if (reason.length < 8 || !session) { setError("Alasan lifecycle minimal 8 karakter."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await read(await apiFetch("/v1/cinema/admin/titles/" + item.id + "/lifecycle", session, {
        method: "POST", body: JSON.stringify({ action, expected_version: item.version, reason }),
      }));
      setNotice("Perubahan lifecycle tersimpan melalui endpoint operator-scoped.");
      await loadQueues(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Perubahan lifecycle gagal."); }
    finally { setBusy(false); }
  }

  const inputClass = "mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-600";
  const cardClass = "rounded-2xl border border-slate-200 p-4 dark:border-slate-700";
  return <main className="mx-auto min-h-screen w-full max-w-6xl px-5 py-8 text-slate-900 dark:text-slate-100">
    <nav className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div className="flex gap-4 text-sm"><Link href="/" className="text-blue-600 hover:underline">← Dashboard</Link><Link href="/content-moderation" className="text-blue-600 hover:underline">Moderasi konten</Link><Link href="/content-lifecycle" className="text-blue-600 hover:underline">Lifecycle konten</Link></div>
      <span className="text-xs uppercase tracking-[.18em] text-slate-500">ENG-P13 · AI Cinema Governance</span>
    </nav>
    <header className="mb-6"><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-700">Trust, Copyright & Lifecycle</p><h1 className="mt-2 text-3xl font-semibold">AI Cinema Governance</h1><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Moderasi, bukti hak cipta, dan lifecycle film/episode melalui FastAPI dengan scope operator dan audit. Hak cipta tidak dianggap cleared tanpa referensi bukti.</p></header>
    {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-300 p-3 text-sm text-emerald-800">{notice}</p>}
    {!session || !operator ? <form onSubmit={login} className="max-w-md space-y-4 rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
      <h2 className="font-semibold">Login operator</h2>
      <label className="block text-sm">Email<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} className={inputClass}/></label>
      <label className="block text-sm">Password<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} className={inputClass}/></label>
      <button disabled={busy} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Memverifikasi…" : "Masuk & verifikasi scope"}</button>
    </form> : <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
        <span>Operator: {operator.email || operator.id} · platform:content.moderate</span>
        <button disabled={busy} onClick={() => void refresh()} className="text-blue-600 hover:underline">Muat ulang antrean</button>
      </div>
      <section className="mb-8 space-y-3">
        <div><h2 className="text-xl font-semibold">Hak cipta / rights review</h2><p className="text-sm text-slate-500">Setiap keputusan wajib menyertakan referensi bukti dan alasan; clearance tidak otomatis menerbitkan film.</p></div>
        {rights.length === 0 ? <p className={cardClass + " text-sm text-slate-500"}>Tidak ada judul yang menunggu pemeriksaan hak.</p> : rights.map(item => <article key={item.id} className={cardClass}>
          <div className="flex flex-wrap justify-between gap-2"><strong>{item.title}</strong><span className="text-xs text-amber-700">{item.rights_status} · v{item.version}</span></div>
          <p className="mt-1 text-xs text-slate-500">{item.genre} · {item.status} · {item.id}</p>
          <label className="mt-3 block text-sm">Referensi bukti hak cipta<input value={evidence[item.id] || ""} onChange={e => setEvidence(v => ({...v,[item.id]:e.target.value}))} className={inputClass} placeholder="ID dokumen / URL arsip / nomor lisensi"/></label>
          <label className="mt-3 block text-sm">Alasan / catatan review<textarea value={reasons[item.id] || ""} onChange={e => setReasons(v => ({...v,[item.id]:e.target.value}))} className={inputClass} minLength={8} maxLength={500}/></label>
          <div className="mt-3 flex gap-2"><button disabled={busy} onClick={() => void reviewRights(item,"clear")} className="rounded-xl bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Clear rights</button><button disabled={busy} onClick={() => void reviewRights(item,"reject")} className="rounded-xl bg-red-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Reject rights</button></div>
        </article>)}
      </section>
      <section className="mb-8 space-y-3">
        <div><h2 className="text-xl font-semibold">Moderasi film</h2><p className="text-sm text-slate-500">Approve hanya dapat dilakukan jika rights cleared dan minimal satu episode memiliki media ready + scan clean.</p></div>
        {moderation.length === 0 ? <p className={cardClass + " text-sm text-slate-500"}>Tidak ada judul dalam antrean moderasi.</p> : moderation.map(item => <article key={item.id} className={cardClass}>
          <div className="flex flex-wrap justify-between gap-2"><strong>{item.title}</strong><span className="text-xs text-amber-700">{item.moderation_status} · rights {item.rights_status} · v{item.version}</span></div>
          <p className="mt-1 text-xs text-slate-500">{item.genre} · {item.status} · {item.id}</p>
          <label className="mt-3 block text-sm">Alasan moderasi<textarea value={reasons[item.id] || ""} onChange={e => setReasons(v => ({...v,[item.id]:e.target.value}))} className={inputClass} minLength={8} maxLength={500}/></label>
          <div className="mt-3 flex gap-2"><button disabled={busy} onClick={() => void reviewModeration(item,"approve")} className="rounded-xl bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Approve</button><button disabled={busy} onClick={() => void reviewModeration(item,"reject")} className="rounded-xl bg-red-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Reject</button></div>
        </article>)}
      </section>
      <section className="space-y-3">
        <div><h2 className="text-xl font-semibold">Lifecycle film</h2><p className="text-sm text-slate-500">Archive/block dan restore selalu kembali ke draft; tidak ada restore langsung ke publik.</p></div>
        {lifecycle.length === 0 ? <p className={cardClass + " text-sm text-slate-500"}>Belum ada judul AI Cinema.</p> : lifecycle.map(item => <article key={item.id} className={cardClass}>
          <div className="flex flex-wrap justify-between gap-2"><strong>{item.title}</strong><span className="text-xs text-slate-500">{item.status} · rights {item.rights_status} · v{item.version}</span></div>
          <label className="mt-3 block text-sm">Alasan lifecycle<textarea value={reasons[item.id] || ""} onChange={e => setReasons(v => ({...v,[item.id]:e.target.value}))} className={inputClass} minLength={8} maxLength={500}/></label>
          <div className="mt-3 flex flex-wrap gap-2">
            {["draft","rejected","published"].includes(item.status) && <button disabled={busy} onClick={() => void lifecycleAction(item,"archive")} className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-600">Archive</button>}
            {!["archived","blocked"].includes(item.status) && <button disabled={busy} onClick={() => void lifecycleAction(item,"block")} className="rounded-xl bg-red-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Block</button>}
            {["archived","blocked"].includes(item.status) && <button disabled={busy} onClick={() => void lifecycleAction(item,"restore_to_draft")} className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Restore to draft</button>}
          </div>
        </article>)}
      </section>
    </>}
  </main>;
}
