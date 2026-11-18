"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type Audit = { id: string; owner_user_id: string; agent_id: string; approval_id?: string | null; actor_user_id?: string | null; event_type: string; outcome: "allowed" | "denied" | "error"; metadata: Record<string, unknown>; created_at: string };
type SocialPolicy = { id: string; owner_user_id: string; agent_id: string; allowed_actions: string[]; approval_mode: string; disclosure_text: string; is_enabled: boolean; version: number; updated_at: string };
type SocialApproval = { id: string; owner_user_id: string; agent_id: string; action_type: string; status: string; content_id?: string | null; target_content_id?: string | null; target_comment_id?: string | null; requested_at: string; decided_at?: string | null; decided_by?: string | null; execution_result?: Record<string, unknown> | null };
type ControlEvent = { id: string; owner_user_id: string; agent_id: string; event_type: string; actor_user_id: string; metadata: Record<string, unknown>; created_at: string };
type AutomationGrant = { id: string; agent_id: string; granted_scopes: string[]; policy_version: number; status: string; expires_at?: string | null; granted_at: string; revoked_at?: string | null; revoke_reason?: string | null };
type AutomationRun = { id: string; agent_id: string; runtime_task_id: string; source_event_id: string; channel: string; status: string; created_at: string; updated_at: string };
type Governance = { policies: SocialPolicy[]; approvals: SocialApproval[]; automation_schema_active: boolean; control_events: ControlEvent[]; automation_grants: AutomationGrant[]; automation_runs: AutomationRun[] };
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
  const [governance,setGovernance] = useState<Governance|null>(null);
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
    let governanceResponse = await fetch(apiBase + "/v1/admin/operator/agent-social/governance?limit=100", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" });
    if (governanceResponse.status === 401) {
      current = await refresh(current);
      governanceResponse = await fetch(apiBase + "/v1/admin/operator/agent-social/governance?limit=100", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" });
    }
    const governanceBody = await governanceResponse.json().catch(() => ({}));
    if (!governanceResponse.ok) throw new Error(governanceBody?.error?.message || governanceBody?.detail?.message || "Snapshot governance sosial tidak dapat diakses.");
    setSession(current); setItems(body.items || []); setGovernance(governanceBody as Governance);
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
    {session && governance && <>
      <section className="panel"><header className="panelHead"><div><h2>Owner policies & Agent permissions</h2><p className="muted">{governance.policies.length} policy · read-only snapshot</p></div></header>
        {governance.policies.length===0?<p className="muted">Belum ada policy Agent Social.</p>:<div className="tableWrap"><table><thead><tr><th>Owner / Agent</th><th>Allowed actions</th><th>Approval</th><th>Status</th><th>Version</th><th>Updated</th></tr></thead><tbody>{governance.policies.map(item=><tr key={item.id}><td><code>{item.owner_user_id}</code><br/><code>{item.agent_id}</code></td><td>{item.allowed_actions.join(", ")}</td><td>{item.approval_mode}</td><td><span className={"pill "+(item.is_enabled?"online":"warning")}>{item.is_enabled?"enabled":"disabled"}</span></td><td>{item.version}</td><td>{new Date(item.updated_at).toLocaleString("id-ID")}</td></tr>)}</tbody></table></div>}
      </section>
      <section className="panel"><header className="panelHead"><div><h2>Approval inbox governance</h2><p className="muted">{governance.approvals.length} approval terbaru · konten draft privat tidak ditampilkan</p></div></header>
        {governance.approvals.length===0?<p className="muted">Belum ada approval.</p>:<div className="tableWrap"><table><thead><tr><th>Action</th><th>Status</th><th>Owner / Agent</th><th>Target</th><th>Requested / Decided</th></tr></thead><tbody>{governance.approvals.map(item=><tr key={item.id}><td><strong>{item.action_type}</strong><br/><code>{item.id}</code></td><td><span className={"pill "+(item.status==="approved"?"online":item.status==="pending"?"warning":"offline")}>{item.status}</span></td><td><code>{item.owner_user_id}</code><br/><code>{item.agent_id}</code></td><td><code>{item.target_content_id || item.content_id || "—"}</code>{item.target_comment_id && <><br/><code>{item.target_comment_id}</code></>}</td><td>{new Date(item.requested_at).toLocaleString("id-ID")}<br/>{item.decided_at?new Date(item.decided_at).toLocaleString("id-ID"):"Pending"}</td></tr>)}</tbody></table></div>}
      </section>
      <section className="panel"><header className="panelHead"><div><h2>Automation, grants & takeover</h2><p className="muted">Schema status: {governance.automation_schema_active?"active":"not applied"} · Auto Reply runtime remains fail-closed</p></div></header>
        {!governance.automation_schema_active?<p className="muted">Automation schema belum diterapkan pada database kanonis. Grant, run, dan control-event belum ditampilkan atau diaktifkan.</p>:<>
          <h3 className="subhead">Control events</h3>
          {governance.control_events.length===0?<p className="muted">Belum ada event kontrol.</p>:<div className="tableWrap"><table><thead><tr><th>Event</th><th>Owner / Agent</th><th>Actor</th><th>Time</th><th>Metadata</th></tr></thead><tbody>{governance.control_events.map(item=><tr key={item.id}><td>{item.event_type}</td><td><code>{item.owner_user_id}</code><br/><code>{item.agent_id}</code></td><td><code>{item.actor_user_id}</code></td><td>{new Date(item.created_at).toLocaleString("id-ID")}</td><td><code>{JSON.stringify(item.metadata)}</code></td></tr>)}</tbody></table></div>}
          <h3 className="subhead">Automation grants</h3>
          {governance.automation_grants.length===0?<p className="muted">Belum ada grant automation.</p>:<div className="tableWrap"><table><thead><tr><th>Grant</th><th>Agent</th><th>Scopes</th><th>Status</th><th>Policy</th><th>Expires</th></tr></thead><tbody>{governance.automation_grants.map(item=><tr key={item.id}><td><code>{item.id}</code></td><td><code>{item.agent_id}</code></td><td>{item.granted_scopes.join(", ")}</td><td>{item.status}</td><td>{item.policy_version}</td><td>{item.expires_at?new Date(item.expires_at).toLocaleString("id-ID"):"—"}</td></tr>)}</tbody></table></div>}
          <h3 className="subhead">Automation runs</h3>
          {governance.automation_runs.length===0?<p className="muted">Belum ada automation run.</p>:<div className="tableWrap"><table><thead><tr><th>Run</th><th>Agent</th><th>Channel</th><th>Status</th><th>Runtime task</th><th>Updated</th></tr></thead><tbody>{governance.automation_runs.map(item=><tr key={item.id}><td><code>{item.id}</code></td><td><code>{item.agent_id}</code></td><td>{item.channel}</td><td>{item.status}</td><td><code>{item.runtime_task_id}</code></td><td>{new Date(item.updated_at).toLocaleString("id-ID")}</td></tr>)}</tbody></table></div>}
        </>}
      </section>
    </>}
    <footer className="pageFoot">Privileged read-only review. Tidak tersedia tombol edit data atau bypass lifecycle; setiap operasi dilindungi oleh operator grant backend.</footer></section></main>;
}
