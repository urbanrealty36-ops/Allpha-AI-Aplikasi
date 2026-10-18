"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type AuthResponse = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
type Operator = { id: string; email?: string; scopes: string[] };
type ContentItem = { id: string; owner_id: string; body: string; content_type: string; visibility: string; status: string; moderation_status: string; version: number; created_at: string };
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

export default function ContentModerationPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [items, setItems] = useState<ContentItem[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");

  const loadQueue = useCallback(async (active: Session) => {
    const result = await read<{ items: ContentItem[] }>(await apiFetch("/v1/content/admin/review-queue?limit=100", active));
    setItems(Array.isArray(result.items) ? result.items : []);
  }, []);

  const verify = useCallback(async (active: Session) => {
    const result = await read<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
    setOperator(result.operator);
    if (!result.operator.scopes.includes("platform:content.moderate")) throw new Error("Scope platform:content.moderate diperlukan untuk meninjau konten.");
    await loadQueue(active);
  }, [loadQueue]);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const active = await authRequest({ email: email.trim(), password }, "password"); setSession(active); setPassword(""); await verify(active); }
    catch (cause) { setSession(null); setOperator(null); setError(cause instanceof Error ? cause.message : "Login operator gagal."); }
    finally { setBusy(false); }
  }

  async function review(item: ContentItem, decision: "approve" | "reject") {
    const reason = (reasons[item.id] || "").trim();
    if (reason.length < 8) { setError("Alasan moderasi minimal 8 karakter."); return; }
    if (!session) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await read(await apiFetch(`/v1/content/admin/${item.id}/review`, session, { method: "POST", body: JSON.stringify({ decision, expected_version: item.version, reason }) }));
      setNotice(decision === "approve" ? "Konten disetujui dan dipublikasikan." : "Konten ditolak dan dikembalikan ke pemilik sebagai gagal.");
      await loadQueue(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan moderasi gagal."); }
    finally { setBusy(false); }
  }

  const canModerate = Boolean(operator?.scopes.includes("platform:content.moderate"));
  return <main style={{ maxWidth: 1000, margin: "0 auto", padding: 24, color: "#101828" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
      <div><Link href="/" style={{ color: "#175cd3", fontSize: 13 }}>← Super Admin</Link><h1 style={{ fontSize: 28, margin: "10px 0 4px" }}>Moderasi konten</h1><p style={{ margin: 0, color: "#667085" }}>Antrean review konten kreator. Keputusan dicatat dengan alasan, versi, dan audit operator.</p></div>
      {session ? <button onClick={() => { setSession(null); setOperator(null); setItems([]); setNotice(""); }} style={{ padding: "9px 13px" }}>Keluar</button> : null}
    </header>
    {error ? <p role="alert" style={{ padding: 12, background: "#fef3f2", color: "#b42318", borderRadius: 8 }}>{error}</p> : null}
    {notice ? <p role="status" style={{ padding: 12, background: "#ecfdf3", color: "#027a48", borderRadius: 8 }}>{notice}</p> : null}
    {!session ? <section style={{ border: "1px solid #eaecf0", borderRadius: 12, padding: 20, maxWidth: 480 }}><h2 style={{ marginTop: 0 }}>Login operator</h2><form onSubmit={login} style={{ display: "grid", gap: 12 }}><label>Email<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label><button type="submit" disabled={busy} style={{ padding: 12 }}>{busy ? "Memverifikasi…" : "Login & verifikasi scope"}</button></form></section> : null}
    {session && canModerate ? <section><div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}><p style={{ color: "#667085" }}>{items.length} konten menunggu review · {operator?.email || operator?.id}</p><button onClick={() => void loadQueue(session).catch(cause => setError(cause instanceof Error ? cause.message : "Antrean gagal dimuat."))} disabled={busy} style={{ padding: "8px 12px" }}>Muat ulang antrean</button></div>
      {items.length === 0 ? <div style={{ border: "1px dashed #d0d5dd", borderRadius: 12, padding: 28, color: "#667085" }}>Antrean moderasi kosong.</div> : <div style={{ display: "grid", gap: 14 }}>{items.map(item => <article key={item.id} style={{ border: "1px solid #eaecf0", borderRadius: 12, padding: 18 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{item.content_type} · v{item.version}</strong><span style={{ color: "#667085", fontSize: 12 }}>{item.visibility} · {new Date(item.created_at).toLocaleString("id-ID")}</span></div><p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.body || "(Konten media tanpa teks)"}</p><p style={{ color: "#667085", fontSize: 12 }}>ID: {item.id} · status: {item.status}/{item.moderation_status}</p><label style={{ display: "block", fontSize: 13 }}>Alasan / catatan review<input value={reasons[item.id] || ""} onChange={e => setReasons(prev => ({ ...prev, [item.id]: e.target.value }))} minLength={8} maxLength={500} placeholder="Jelaskan alasan keputusan (min. 8 karakter)" style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label><div style={{ display: "flex", gap: 8, marginTop: 12 }}><button disabled={busy} onClick={() => void review(item, "approve")} style={{ padding: "9px 14px", background: "#067647", color: "white", border: 0, borderRadius: 8 }}>Setujui & publikasikan</button><button disabled={busy} onClick={() => void review(item, "reject")} style={{ padding: "9px 14px", background: "#b42318", color: "white", border: 0, borderRadius: 8 }}>Tolak</button></div></article>)}</div>}
    </section> : null}
  </main>;
}
