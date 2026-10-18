"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type AuthPayload = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
type Operator = { id: string; email?: string; scopes: string[] };
type Policy = { id: string; agent_id: string; policy_version: string; policy_digest: string; status: string; created_by?: string; approved_by?: string; approved_at?: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

function sessionFrom(data: AuthPayload): Session {
  if (!data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Supabase Auth tidak mengembalikan sesi.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=${grant}`, { method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as AuthPayload;
  if (!response.ok) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return sessionFrom(data);
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let active = session;
  if (active.expires_at <= Date.now() + 30000) active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: { Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}), Authorization: `Bearer ${token}` } });
  let response = await send(active.access_token);
  if (response.status === 401) { active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token"); response = await send(active.access_token); }
  return response;
}
async function body<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as { detail?: { message?: string; code?: string } | string; error?: { message?: string } };
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.detail?.message || data.detail?.code;
    throw new Error(detail || data.error?.message || `Permintaan gagal (HTTP ${response.status}).`);
  }
  return data as T;
}

const defaultAgent = "5c7185b5-ae9e-464d-9e81-792f0945ad7a";
const fieldStyle = { display: "block", width: "100%", boxSizing: "border-box" as const, padding: 10, marginTop: 5, border: "1px solid #d0d5dd", borderRadius: 8, background: "white", color: "#101828" };
const cardStyle = { border: "1px solid #eaecf0", borderRadius: 12, padding: 18, marginBottom: 16, background: "#fff" };

export default function RuntimePoliciesPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agentId, setAgentId] = useState(defaultAgent);
  const [version, setVersion] = useState("pdf-qa-test-v1");
  const [tools, setTools] = useState("pdf.extract_text");
  const [scopes, setScopes] = useState("");
  const [constraints, setConstraints] = useState('{"environment":"test-only","max_output_tokens":128,"max_cost_microunits":5000,"max_latency_ms":15000,"no_external_side_effects":true}');
  const [reason, setReason] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const active = await authRequest({ email: email.trim(), password }, "password");
      const result = await body<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
      setSession(active); setOperator(result.operator); setPassword("");
      setNotice("Login berhasil. Scope diperiksa dari API operator.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Login atau verifikasi operator gagal."); }
    finally { setBusy(false); }
  }
  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session || !operator) return;
    if (!operator.scopes.includes("platform:capabilities.review")) { setError("Scope platform:capabilities.review diperlukan untuk membuat draft."); return; }
    let risk: Record<string, unknown>;
    try { risk = JSON.parse(constraints) as Record<string, unknown>; if (!risk || Array.isArray(risk) || typeof risk !== "object") throw new Error(); }
    catch { setError("Risk constraints harus berupa objek JSON yang valid."); return; }
    const approvedToolKeys = tools.split(/[\n,]/).map(v => v.trim()).filter(Boolean);
    const requiredPermissionScopes = scopes.split(/[\n,]/).map(v => v.trim()).filter(Boolean);
    if (!approvedToolKeys.length) { setError("Masukkan minimal satu tool key yang benar-benar terdaftar."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await body<{ policy: Policy; runtime_authorized: boolean }>(await apiFetch("/v1/admin/operator/runtime-policies", session, { method: "POST", body: JSON.stringify({ agent_id: agentId.trim(), policy_version: version.trim(), approved_tool_keys: approvedToolKeys, required_permission_scopes: requiredPermissionScopes, risk_constraints: risk }) }));
      setPolicy(result.policy); setPolicyId(result.policy.id);
      setNotice("Draft policy tersimpan. Policy belum disetujui dan belum mengotorisasi runtime.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pembuatan draft policy gagal."); }
    finally { setBusy(false); }
  }
  async function approve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session || !operator) return;
    if (!operator.scopes.includes("platform:capabilities.review.high_risk")) { setError("Scope platform:capabilities.review.high_risk diperlukan untuk approval."); return; }
    if (reason.trim().length < 8) { setError("Alasan approval minimal 8 karakter."); return; }
    if (!window.confirm("Setujui policy runtime ini? Pastikan digest, agent, tools, dan batas test-only sudah ditinjau. Approval tidak otomatis mengaktifkan tarif atau runtime.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await body<{ policy: Policy; runtime_authorized?: boolean }>(await apiFetch("/v1/admin/operator/runtime-policies/" + encodeURIComponent(policyId.trim()) + "/approve", session, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) }));
      if (result.policy) setPolicy(result.policy);
      setNotice("API governance mengonfirmasi approval policy. Periksa status dan digest di bawah; tarif dan runtime tetap harus diverifikasi terpisah.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Approval policy gagal."); }
    finally { setBusy(false); }
  }
  const canDraft = !!operator?.scopes.includes("platform:capabilities.review");
  const canApprove = !!operator?.scopes.includes("platform:capabilities.review.high_risk");

  return <main style={{ maxWidth: 1080, margin: "0 auto", padding: "28px 18px", color: "#101828", fontFamily: "Arial, sans-serif" }}>
    <header style={{ marginBottom: 22 }}>
      <Link href="/" style={{ color: "#475467", textDecoration: "none" }}>← Super Admin</Link>
      <p style={{ color: "#667085", fontSize: 12, letterSpacing: 1.1, fontWeight: 700, marginBottom: 6 }}>GOVERNANCE / ENG-P12</p>
      <h1 style={{ fontSize: 30, margin: "0 0 8px" }}>Runtime Policy Approval</h1>
      <p style={{ color: "#475467", lineHeight: 1.6, maxWidth: 760 }}>Buat draft policy untuk Agent PDF QA dan lakukan persetujuan melalui endpoint governance resmi. Pembuatan dan approval adalah tindakan terpisah; halaman ini tidak memakai service-role key.</p>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12 }}><Link href="/costs">Model Cost & Tarif →</Link><a href="https://api.allpha.web.id/docs#/platform-operations" target="_blank" rel="noreferrer">API governance docs →</a></div>
    </header>
    <section style={{ ...cardStyle, background: "#fffaeb", borderColor: "#fedf89" }}>
      <strong>Kontrol keamanan</strong>
      <p style={{ marginBottom: 0, lineHeight: 1.6, color: "#7a2e0e" }}>Tool key harus dicocokkan dengan tool registry aktual. Jangan menyetujui policy hanya agar tes lewat. Persetujuan policy tidak memublikasikan Skill, tidak mengaktifkan tarif, dan tidak membuktikan provider berhasil dipanggil.</p>
    </section>
    {!session && <section style={cardStyle}><h2 style={{ marginTop: 0 }}>Login operator</h2><form onSubmit={login} style={{ display: "grid", gap: 12, maxWidth: 440 }}>
      <label>Email<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} style={fieldStyle}/></label>
      <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} style={fieldStyle}/></label>
      <button disabled={busy} style={{ padding: 12 }}>{busy ? "Memverifikasi…" : "Login & verifikasi scope"}</button>
    </form><p style={{ color: "#667085", fontSize: 13 }}>Sesi berada di memori halaman; token tidak disimpan ke localStorage/sessionStorage.</p></section>}
    {session && operator && <section style={cardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><div><h2 style={{ marginTop: 0 }}>Sesi operator terverifikasi</h2><p>{operator.email || operator.id}</p></div><button onClick={() => { setSession(null); setOperator(null); setPolicy(null); setPassword(""); }} style={{ padding: 9 }}>Keluar</button></div>
      <p style={{ fontSize: 13, color: "#475467" }}>Scope sesi: {operator.scopes.join(" · ") || "Tidak ada scope"}</p>
      {!canDraft && <p role="alert" style={{ color: "#b42318" }}>Akun tidak memiliki platform:capabilities.review. Draft tidak dapat dibuat.</p>}
      {!canApprove && <p role="alert" style={{ color: "#b42318" }}>Akun tidak memiliki platform:capabilities.review.high_risk. Approval tidak dapat dilakukan oleh sesi ini.</p>}
    </section>}
    {session && operator && <section style={cardStyle}><h2 style={{ marginTop: 0 }}>1. Buat draft policy</h2><form onSubmit={createDraft} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 14 }}>
      <label>Agent ID<input required value={agentId} onChange={e => setAgentId(e.target.value)} style={fieldStyle}/></label>
      <label>Policy version<input required value={version} onChange={e => setVersion(e.target.value)} style={fieldStyle}/></label>
      <label style={{ gridColumn: "1 / -1" }}>Approved tool keys — isi hanya key dari tool registry<textarea required rows={2} value={tools} onChange={e => setTools(e.target.value)} style={fieldStyle}/></label>
      <label style={{ gridColumn: "1 / -1" }}>Required permission scopes (opsional, pisahkan koma/baris baru)<textarea rows={2} value={scopes} onChange={e => setScopes(e.target.value)} style={fieldStyle}/></label>
      <label style={{ gridColumn: "1 / -1" }}>Risk constraints JSON<textarea required rows={5} value={constraints} onChange={e => setConstraints(e.target.value)} style={{ ...fieldStyle, fontFamily: "monospace" }}/></label>
      <div style={{ gridColumn: "1 / -1" }}><button type="submit" disabled={busy || !canDraft} style={{ padding: 12 }}>{busy ? "Memproses…" : "Buat draft melalui governance API"}</button></div>
    </form></section>}
    {session && operator && <section style={cardStyle}><h2 style={{ marginTop: 0 }}>2. Tinjau & setujui policy draft</h2><p style={{ color: "#475467", lineHeight: 1.6 }}>Pilih ID policy yang baru dibuat atau masukkan ID draft yang telah diverifikasi. API hanya menyetujui status draft dan mencatat aktor serta waktu approval.</p>
      <label>Policy ID<input value={policyId} onChange={e => setPolicyId(e.target.value)} required style={fieldStyle} placeholder="UUID policy draft"/></label>
      {policy && <div style={{ marginTop: 14, padding: 14, border: "1px solid #d0d5dd", borderRadius: 8, overflowWrap: "anywhere" }}><strong>Status dari respons API: {policy.status}</strong><p>Policy ID: {policy.id}</p><p>Agent: {policy.agent_id}</p><p>Versi: {policy.policy_version}</p><p>Digest SHA-256: <code>{policy.policy_digest}</code></p>{policy.approved_by && <p>Disetujui oleh: {policy.approved_by} · {policy.approved_at || ""}</p>}</div>}
      <label style={{ display: "block", marginTop: 14 }}>Alasan persetujuan (min. 8 karakter)<textarea required minLength={8} maxLength={500} rows={3} value={reason} onChange={e => setReason(e.target.value)} style={fieldStyle} placeholder="Contoh: disetujui untuk challenge PDF QA terisolasi sesuai batas biaya dan scope yang ditinjau."/></label>
      <form onSubmit={approve} style={{ marginTop: 12 }}><button type="submit" disabled={busy || !canApprove || !policyId.trim() || reason.trim().length < 8} style={{ padding: 12 }}>{busy ? "Memproses…" : "Setujui policy (high-risk scope)"}</button></form>
    </section>}
    {error && <section role="alert" style={{ ...cardStyle, background: "#fef3f2", color: "#b42318" }}>{error}</section>}
    {notice && <section role="status" style={{ ...cardStyle, background: "#ecfdf3", color: "#067647" }}>{notice}</section>}
    <footer style={{ color: "#667085", fontSize: 12, padding: "12px 0" }}>Allpha · Governance approval · Source of truth: FastAPI + Supabase · ENG-P12 remains in progress until runtime evidence and QA acceptance are verified.</footer>
  </main>;
}
