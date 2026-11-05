"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type Audit = { id: string; owner_user_id: string; agent_id: string; approval_id?: string | null; actor_user_id?: string | null; event_type: string; outcome: "allowed" | "denied" | "error"; metadata: Record<string, unknown>; created_at: string };
type Payload = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const authUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const anon = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
async function signIn(email: string, password: string): Promise<Session> {
  if (!authUrl || !anon) throw new Error("Konfigurasi Supabase Auth belum tersedia.");
  const response = await fetch(authUrl + "/auth/v1/token?grant_type=password", { method: "POST", headers: { apikey: anon, "Content-Type": "application/json" }, body: JSON.stringify({ email, password }), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as Payload;
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Login gagal.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + (data.expires_in || 3600) * 1000, user: data.user };
}
async function refresh(session: Session): Promise<Session> {
  const response = await fetch(authUrl + "/auth/v1/token?grant_type=refresh_token", { method: "POST", headers: { apikey: anon, "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: session.refresh_token }), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as Payload;
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error("Sesi berakhir; login kembali.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + (data.expires_in || 3600) * 1000, user: data.user };
}
export default function AgentSocialAuditPage() {
  const [session,setSession] = useState<Session|null>(null);
  const [email,setEmail] = useState("");
  const [password,setPassword] = useState("");
  const [items,setItems] = useState<Audit[]>([]);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const api = useCallback(async (active: Session) => {
    let current = active;
    if (current.expires_at <= Date.now() + 30000) current = await refresh(current);
    let response = await fetch(apiBase + "/v1/admin/operator/agent-social/audit?limit=100", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" });
    if (response.status === 401) { current = await refresh(current); response = await fetch(apiBase + "/v1/admin/operator/agent-social/audit?limit=100", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" }); }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Audit sosial tidak dapat diakses.");
    setSession(current); setItems(body.items || []);
  },[]);
  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { const active = await signIn(email,password); setSession(active); await api(active); setNotice("Identitas dimuat; hak operator divalidasi oleh API."); }
    catch (cause) { setSession(null); setError(cause instanceof Error ? cause.message : "Autentikasi gagal."); }
    finally { setBusy(false); }
  }
  async function reload() {
    if (!session) return; setBusy(true); setError("");
    try { await api(session); setNotice("Audit diperbarui."); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Audit gagal dimuat."); }
    finally { setBusy(false); }
  }
  return <main className="shell"><aside className="sidebar"><Link className="brand" href="/"><span className="mark">A</span><span><b>ALLPHA</b><small>CONTROL PLANE</small></span></Link><p className="navLabel">GOVERNANCE</p><Link className="nav" href="/">Overview</Link><Link className="nav" href="/content-moderation">Moderasi konten</Link><Link className="nav active" href="/agent-social-audit">Human + Agent Social Audit</Link></aside><section className="content"><header className="pageHead"><div><p className="eyebrow">SUPER ADMIN · WP-06</p><h1>Human + AI Agent Social Governance</h1><p className="muted">Audit trail kebijakan pemilik, permintaan draft, keputusan approval dan pencabutan.</p></div></header>
    {error && <p role="alert" className="notice error">{error}</p>}{notice && <p role="status" className="notice">{notice}</p>}
    {!session ? <section className="panel"><h2>Operator authentication</h2><p className="muted">Login Human saja tidak cukup. API memeriksa grant operator dan scope platform:security.audit.read pada setiap request.</p><form onSubmit={login} className="formGrid"><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="username"/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></label><button type="submit" disabled={busy}>{busy?"Memverifikasi…":"Login & buka audit"}</button></form></section> : <section className="panel"><header className="panelHead"><div><h2>Social action audit events</h2><p className="muted">{items.length} event terbaru · {session.user.email || session.user.id}</p></div><button onClick={reload} disabled={busy}>{busy?"Memuat…":"Refresh"}</button></header>{items.length===0?<p className="muted">Belum ada event audit sosial.</p>:<div className="tableWrap"><table><thead><tr><th>Waktu</th><th>Event</th><th>Outcome</th><th>Owner / Agent</th><th>Approval</th><th>Metadata</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td>{new Date(item.created_at).toLocaleString("id-ID")}</td><td><strong>{item.event_type}</strong></td><td><span className={"pill "+(item.outcome==="allowed"?"online":item.outcome==="denied"?"warning":"offline")}>{item.outcome}</span></td><td><code>{item.owner_user_id}</code><br/><code>{item.agent_id}</code></td><td><code>{item.approval_id || "—"}</code></td><td><pre>{JSON.stringify(item.metadata,null,2)}</pre></td></tr>)}</tbody></table></div>}</section>}
    <footer className="pageFoot">Privileged read-only review. Tidak tersedia tombol edit data atau bypass lifecycle; setiap operasi dilindungi oleh operator grant backend.</footer></section></main>;
}
