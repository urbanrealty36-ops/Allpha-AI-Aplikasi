"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type OperatorScope =
  | "platform:operations.read"
  | "platform:security.audit.read"
  | "platform:capabilities.review"
  | "platform:capabilities.review.high_risk"
  | "platform:operators.manage";
type AuthSession = {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: { id: string; email?: string };
};
type AuthPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  user?: { id: string; email?: string };
  error_description?: string;
  msg?: string;
};
type Operator = { id: string; email?: string; scopes: OperatorScope[] };
type AuditEvent = {
  id: string;
  actor_user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  outcome: "allowed" | "denied" | "error";
  request_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
};
type CapabilityRequest = {
  id: string;
  agent_id: string;
  created_by: string;
  capability_key: string;
  description: string;
  required_permission_scopes: string[];
  risk_level: "low" | "medium" | "high" | "critical";
  status: "requested" | "approved" | "denied" | "revoked";
  created_at: string;
};
type OfficialBot = { id: string; skill_key: string; display_name: string; category_key: string; category_label: string; skill_description: string; character_archetype_key: string; character_asset_key?: string | null; asset_validation_status: "unverified" | "verified" | "rejected"; agent_id?: string | null; runtime_policy_id?: string | null; status: "draft" | "pending_approval" | "approved" | "active" | "stopped" | "isolated" | "blocked"; autonomy_mode: "disabled" | "supervised" | "bounded"; isolation_reason?: string | null };
type Grant = {
  id: string;
  user_id: string;
  scopes: OperatorScope[];
  status: "active" | "revoked";
  reason: string;
  granted_by: string;
  expires_at?: string | null;
  created_at: string;
  revoked_at?: string | null;
  revoked_by?: string | null;
  revocation_reason?: string | null;
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const allScopes: OperatorScope[] = [
  "platform:operations.read",
  "platform:security.audit.read",
  "platform:capabilities.review",
  "platform:capabilities.review.high_risk",
  "platform:operators.manage",
];

function sessionFrom(payload: AuthPayload): AuthSession {
  if (!payload.access_token || !payload.refresh_token || !payload.user?.id) {
    throw new Error(payload.error_description || payload.msg || "Supabase Auth tidak mengembalikan sesi yang valid.");
  }
  return {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    expires_at: Date.now() + Math.max(60, payload.expires_in || 3600) * 1000,
    user: payload.user,
  };
}
async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<AuthSession> {
  if (!supabaseUrl || !publishableKey) {
    throw new Error("Konfigurasi NEXT_PUBLIC_SUPABASE_URL dan NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY belum tersedia.");
  }
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=${grant}`, {
    method: "POST",
    headers: { apikey: publishableKey, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = (await response.json().catch(() => ({}))) as AuthPayload;
  if (!response.ok) throw new Error(payload.error_description || payload.msg || "Autentikasi Supabase gagal.");
  return sessionFrom(payload);
}
async function refreshAuth(session: AuthSession): Promise<AuthSession> {
  return authRequest({ refresh_token: session.refresh_token }, "refresh_token");
}
async function adminFetch(
  path: string,
  session: AuthSession,
  setSession: (value: AuthSession | null) => void,
  init: RequestInit = {},
): Promise<Response> {
  let current = session;
  if (current.expires_at <= Date.now() + 30_000) {
    try {
      current = await refreshAuth(current);
      setSession(current);
    } catch {
      setSession(null);
      throw new Error("Sesi berakhir. Silakan login kembali.");
    }
  }
  const send = (token: string) => fetch(apiBase + path, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(init.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  });
  let response = await send(current.access_token);
  if (response.status === 401) {
    try {
      current = await refreshAuth(current);
      setSession(current);
      response = await send(current.access_token);
    } catch {
      setSession(null);
      throw new Error("Sesi tidak valid atau telah berakhir. Silakan login kembali.");
    }
  }
  return response;
}
async function responseBody<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({})) as { error?: { message?: string; code?: string } };
  if (!response.ok) throw new Error(body.error?.message || `Permintaan gagal (HTTP ${response.status}).`);
  return body as T;
}

export default function OperationsPage() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [operator, setOperator] = useState<Operator | null>(null);
  const [probes, setProbes] = useState<{ label: string; path: string; status: "checking" | "online" | "warning" | "offline"; detail: string }[]>(
    ["/healthz", "/readyz", "/v1/system/status"].map((path, i) => ({
      label: ["API liveness", "Dependency readiness", "System diagnostics"][i],
      path, status: "checking", detail: "Menunggu pemeriksaan",
    })),
  );
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilityRequest[]>([]);
  const [officialBots, setOfficialBots] = useState<OfficialBot[]>([]);
  const [officialBotsTotal, setOfficialBotsTotal] = useState(0);
  const [officialBotsBusy, setOfficialBotsBusy] = useState(false);
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>({});
  const [targetUser, setTargetUser] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<OperatorScope[]>([]);
  const [grantReason, setGrantReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkedAt, setCheckedAt] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const online = probes.filter((probe) => probe.status === "online").length;
  const canReadAudit = Boolean(operator?.scopes.includes("platform:security.audit.read"));
  const canManage = Boolean(operator?.scopes.includes("platform:operators.manage"));
  const canReview = Boolean(operator?.scopes.includes("platform:capabilities.review"));
  const canControlBots = Boolean(operator?.scopes.includes("platform:capabilities.review.high_risk"));
  const availableGrantScopes = useMemo(
    () => allScopes.filter((scope) => operator?.scopes.includes(scope)),
    [operator],
  );

  const refreshProbes = async () => {
    setBusy(true);
    const paths = ["/healthz", "/readyz", "/v1/system/status"];
    const labels = ["API liveness", "Dependency readiness", "System diagnostics"];
    const results = await Promise.all(paths.map(async (path, i) => {
      try {
        const response = await fetch(apiBase + path, { cache: "no-store", headers: { Accept: "application/json" } });
        const body = await response.json() as { status?: string; service?: string; version?: string; environment?: string; dependencies?: Record<string, string>; capabilities?: Record<string, boolean> };
        if (!response.ok) return { label: labels[i], path, status: "offline" as const, detail: "HTTP " + response.status };
        if (path === "/healthz") return { label: labels[i], path, status: body.status === "ok" ? "online" as const : "warning" as const, detail: body.service || "Respons diterima" };
        if (path === "/readyz") {
          const missing = ["database", "authentication"].filter((key) => body.dependencies?.[key] !== "reachable");
          return { label: labels[i], path, status: body.status === "ready" && !missing.length ? "online" as const : "warning" as const, detail: missing.length ? "Dependensi inti belum terjangkau: " + missing.join(", ") : "Auth dan database terjangkau" };
        }
        const missing = Object.entries(body.capabilities || {}).filter(([, value]) => value === false).map(([key]) => key);
        return { label: labels[i], path, status: missing.length ? "warning" as const : "online" as const, detail: "Versi " + (body.version || "—") + " · " + (body.environment || "environment tidak dilaporkan") + (missing.length ? " · belum tersedia: " + missing.join(", ") : "") };
      } catch {
        return { label: labels[i], path, status: "offline" as const, detail: "Tidak dapat terhubung ke " + apiBase };
      }
    }));
    setProbes(results);
    setCheckedAt(new Date().toLocaleString("id-ID"));
    setBusy(false);
  };

  const loadOperatorData = async (activeSession: AuthSession) => {
    setError("");
    setNotice("");
    const accessResponse = await adminFetch("/v1/admin/operator/access", activeSession, setSession);
    const access = await responseBody<{ operator: Operator }>(accessResponse);
    setOperator(access.operator);
    if (access.operator.scopes.includes("platform:security.audit.read")) {
      const auditResponse = await adminFetch("/v1/admin/operator/audit?limit=50", activeSession, setSession);
      const auditBody = await responseBody<{ items: AuditEvent[] }>(auditResponse);
      setAudit(auditBody.items);
    } else {
      setAudit([]);
    }
    if (access.operator.scopes.includes("platform:operators.manage")) {
      const grantsResponse = await adminFetch("/v1/admin/operator/grants?limit=100", activeSession, setSession);
      const grantBody = await responseBody<{ items: Grant[] }>(grantsResponse);
      setGrants(grantBody.items);
    } else {
      setGrants([]);
    }
    if (access.operator.scopes.includes("platform:capabilities.review")) {
      const capabilityResponse = await adminFetch("/v1/admin/operator/capabilities?limit=50", activeSession, setSession);
      const capabilityBody = await responseBody<{ items: CapabilityRequest[] }>(capabilityResponse);
      setCapabilities(capabilityBody.items);
    } else {
      setCapabilities([]);
    }
    if (access.operator.scopes.includes("platform:operations.read")) {
      const botResponse = await adminFetch("/v1/admin/official-bots?limit=50&offset=0", activeSession, setSession);
      const botBody = await responseBody<{ items: OfficialBot[] }>(botResponse);
      setOfficialBots(botBody.items ?? []); setOfficialBotsTotal(botBody.items?.length ?? 0);
    } else { setOfficialBots([]); setOfficialBotsTotal(0); }
  };

  useEffect(() => { void refreshProbes(); }, []);
  useEffect(() => {
    if (!session) {
      setOperator(null);
      setAudit([]);
      setGrants([]);
      setCapabilities([]);
      return;
    }
    let cancelled = false;
    void loadOperatorData(session).catch((cause: unknown) => {
      if (!cancelled) {
        setOperator(null);
        setError(cause instanceof Error ? cause.message : "Akses operator tidak dapat diverifikasi.");
      }
    });
    return () => { cancelled = true; };
  }, [session?.access_token]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const activeSession = await authRequest({ email: email.trim(), password }, "password");
      setSession(activeSession);
      setPassword("");
      setNotice("Login berhasil. Backend sedang memverifikasi grant operator.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Login gagal.");
    } finally {
      setBusy(false);
    }
  }

  async function refreshOfficialBots(activeSession = session) {
    if (!activeSession) return;
    setOfficialBotsBusy(true); setError("");
    try {
      const response = await adminFetch("/v1/admin/official-bots?limit=50&offset=0", activeSession, setSession);
      const body = await responseBody<{ items: OfficialBot[] }>(response);
      setOfficialBots(body.items ?? []); setOfficialBotsTotal(body.items?.length ?? 0);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Roster Official Bot tidak dapat dimuat."); }
    finally { setOfficialBotsBusy(false); }
  }

  async function provisionOfficialBots() {
    if (!session || !canReview) return;
    if (!window.confirm("Siapkan hingga 500 kandidat Official Bot dari katalog Skill? Ini membuat roster draft saja; tidak mengaktifkan runtime.")) return;
    setOfficialBotsBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/official-bots/provision", session, setSession, { method: "POST", body: JSON.stringify({ limit: 500 }) });
      const body = await responseBody<{ roster_count_observed: number; catalog_count: number; message: string }>(response);
      setNotice(body.message + " Katalog: " + body.catalog_count + "; roster teramati: " + body.roster_count_observed + ".");
      await refreshOfficialBots();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Provision roster gagal."); }
    finally { setOfficialBotsBusy(false); }
  }

  async function officialBotAction(bot: OfficialBot, action: "approve" | "activate" | "stop" | "isolate" | "resume_to_draft") {
    if (!session || !canControlBots) return;
    const reason = window.prompt("Alasan wajib untuk aksi " + action + " pada " + bot.display_name + " (minimal 8 karakter):", action === "stop" ? "Stop operasional oleh Super Admin" : action === "isolate" ? "Isolasi untuk pemeriksaan keamanan" : "Perubahan lifecycle ditinjau operator");
    if (!reason || reason.trim().length < 8) return;
    if (action === "activate" && !window.confirm("Aktivasi hanya berhasil jika Agent identity, runtime policy approved, dan asset GLB sudah diverifikasi backend. Lanjutkan permintaan?")) return;
    setOfficialBotsBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/official-bots/" + encodeURIComponent(bot.id) + "/action", session, setSession, { method: "POST", body: JSON.stringify({ action, reason: reason.trim(), autonomy_mode: "supervised" }) });
      const body = await responseBody<{ bot: OfficialBot; runtime_action_dispatched?: boolean }>(response);
      setNotice("Status roster: " + body.bot.status + ". Runtime action dispatched: " + String(Boolean(body.runtime_action_dispatched)) + ".");
      await refreshOfficialBots();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Aksi Official Bot ditolak."); }
    finally { setOfficialBotsBusy(false); }
  }

  async function createGrant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !targetUser.trim() || !selectedScopes.length) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/operator/grants", session, setSession, {
        method: "POST",
        body: JSON.stringify({ user_id: targetUser.trim(), scopes: selectedScopes, reason: grantReason }),
      });
      await responseBody<{ grant: Grant }>(response);
      setTargetUser(""); setSelectedScopes([]); setGrantReason("");
      setNotice("Grant operator berhasil dibuat dan dicatat dalam audit.");
      const current = await adminFetch("/v1/admin/operator/grants?limit=100", session, setSession);
      setGrants((await responseBody<{ items: Grant[] }>(current)).items);
      if (operator?.scopes.includes("platform:security.audit.read")) {
        const auditResponse = await adminFetch("/v1/admin/operator/audit?limit=50", session, setSession);
        setAudit((await responseBody<{ items: AuditEvent[] }>(auditResponse)).items);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Grant operator gagal dibuat.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeGrant(grant: Grant) {
    if (!session || !window.confirm("Cabut akses operator " + grant.user_id + "?")) return;
    const reason = window.prompt("Alasan pencabutan akses (minimal 8 karakter):", "Akses operasional berakhir");
    if (!reason || reason.trim().length < 8) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/operator/grants/" + grant.id + "/revoke", session, setSession, {
        method: "POST",
        body: JSON.stringify({ reason: reason.trim() }),
      });
      await responseBody<{ grant: Grant; revoked: boolean }>(response);
      setNotice("Grant dicabut. Pemeriksaan grant berikutnya akan menolak aksesnya.");
      const current = await adminFetch("/v1/admin/operator/grants?limit=100", session, setSession);
      setGrants((await responseBody<{ items: Grant[] }>(current)).items);
      const auditResponse = await adminFetch("/v1/admin/operator/audit?limit=50", session, setSession);
      setAudit((await responseBody<{ items: AuditEvent[] }>(auditResponse)).items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Grant operator gagal dicabut.");
    } finally {
      setBusy(false);
    }
  }

  async function reviewCapability(capability: CapabilityRequest, decision: "approved" | "denied") {
    if (!session) return;
    const reason = reviewReasons[capability.id]?.trim() || "";
    if (reason.length < 8) {
      setError("Alasan review minimal 8 karakter.");
      return;
    }
    const highRisk = capability.risk_level === "high" || capability.risk_level === "critical";
    if (highRisk && !operator?.scopes.includes("platform:capabilities.review.high_risk")) {
      setError("Capability berisiko tinggi memerlukan scope review tambahan.");
      return;
    }
    if (highRisk && !window.confirm("Konfirmasi keputusan " + decision + " untuk capability " + capability.capability_key + " dengan risiko " + capability.risk_level + "?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/operator/capabilities/" + capability.id + "/review", session, setSession, {
        method: "POST",
        body: JSON.stringify({ decision, reason }),
      });
      await responseBody<{ capability: CapabilityRequest; runtime_authorized: boolean }>(response);
      setNotice("Keputusan capability tersimpan. Status approved tidak dengan sendirinya memberikan izin runtime.");
      const refreshed = await adminFetch("/v1/admin/operator/capabilities?limit=50", session, setSession);
      setCapabilities((await responseBody<{ items: CapabilityRequest[] }>(refreshed)).items);
      if (canReadAudit) {
        const auditResponse = await adminFetch("/v1/admin/operator/audit?limit=50", session, setSession);
        setAudit((await responseBody<{ items: AuditEvent[] }>(auditResponse)).items);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Review capability gagal.");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setSession(null); setOperator(null); setAudit([]); setGrants([]); setCapabilities([]); setError(""); setNotice("");
  }

  return <main className="shell">
    <aside className="sidebar">
      <a className="brand" href="/"><span className="mark">A</span><span><b>ALLPHA</b><small>CONTROL PLANE</small></span></a>
      <p className="navLabel">OPERATIONS</p>
      <a className="nav active" href="#overview">◈ &nbsp; Overview</a>
      <a className="nav" href="#operator-access">◎ &nbsp; Operator access</a>
      {canManage && <a className="nav" href="#operator-grants">◇ &nbsp; Operator grants</a>}
      {canReview && <a className="nav" href="#capability-review">◇ &nbsp; Capability review</a>}
      {canReadAudit && <a className="nav" href="#operator-audit">≋ &nbsp; Audit events</a>}
      <div className="sidebarFoot">● &nbsp; ENG-P06 <small>Least privilege</small></div>
    </aside>
    <section className="main" id="overview">
      <header className="top">
        <div><p className="eyebrow">PLATFORM OPERATIONS / GOVERNANCE</p><h1>Operator security</h1><p className="sub">Login Supabase, grant server-side, permission scope eksak, audit durable.</p></div>
        {session && <button onClick={logout} disabled={busy}>Logout</button>}
      </header>
      <section className="summary">
        <article><label>API endpoint</label><strong className="endpoint">{apiBase}</strong><small>Canonical FastAPI</small></article>
        <article><label>Probe sehat</label><strong>{online}<span> / {probes.length}</span></strong><small>{checkedAt || "Memeriksa layanan…"}</small></article>
        <article><label>Privileged operations</label><strong className={operator ? "authorized" : "restricted"}>{operator ? "Scope verified" : "Restricted"}</strong><small>{operator ? operator.scopes.length + " scope terverifikasi" : "Setiap tindakan istimewa diperiksa backend"}</small></article>
      </section>
      {!session && <section className="panel authPanel">
        <header className="panelHead"><div><h2>Login operator</h2><p>Gunakan akun Supabase yang telah menerima grant operator secara terpisah.</p></div><span className="pill warning">GRANT REQUIRED</span></header>
        <form className="authForm" onSubmit={login}>
          <label>Email<input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <button type="submit" disabled={busy}>{busy ? "Memverifikasi…" : "Login & verifikasi operator"}</button>
        </form>
        <p className="muted">Sesi hanya disimpan di memori halaman ini; token tidak disimpan ke localStorage/sessionStorage. Refresh halaman akan meminta login ulang.</p>
      </section>}
      {session && <section className="panel" id="operator-access">
        <header className="panelHead"><div><h2>Operator identity & scopes</h2><p>Otorisasi dikonfirmasi oleh backend, bukan oleh status login saja.</p></div><span className="pill online">AUTHENTICATED</span></header>
        {operator ? <><p className="operatorIdentity">{operator.email || operator.id}</p><code>{operator.id}</code><div className="scopeList">{operator.scopes.map((scope) => <span className="scopeChip" key={scope}>{scope}</span>)}</div></> : <p className="muted">Backend belum memverifikasi grant operator.</p>}
        <button onClick={() => session && void loadOperatorData(session)} disabled={busy}>Refresh akses & audit</button>
      </section>}
      {session && canManage && <section className="panel" id="operator-grants">
        <header className="panelHead"><div><h2>Operator grants</h2><p>Grant dan pencabutan memakai endpoint backend dan dicatat oleh trigger audit database.</p></div><span className="pill online">MANAGE SCOPE</span></header>
        <form className="grantForm" onSubmit={createGrant}>
          <label>Supabase User ID<input value={targetUser} onChange={(event) => setTargetUser(event.target.value)} placeholder="UUID pengguna target" required pattern="[0-9a-fA-F-]{36}" /></label>
          <label>Alasan pemberian grant<input value={grantReason} onChange={(event) => setGrantReason(event.target.value)} minLength={8} maxLength={500} required placeholder="Alasan operasional (min. 8 karakter)" /></label>
          <fieldset><legend>Scopes yang boleh didelegasikan</legend>{availableGrantScopes.map((scope) => <label className="checkRow" key={scope}><input type="checkbox" checked={selectedScopes.includes(scope)} onChange={(event) => setSelectedScopes((current) => event.target.checked ? [...current, scope] : current.filter((item) => item !== scope))} />{scope}</label>)}</fieldset>
          <button type="submit" disabled={busy || !selectedScopes.length || !targetUser.trim()}>Buat grant</button>
        </form>
        <div className="tableWrap"><table><thead><tr><th>Pengguna</th><th>Scopes</th><th>Status</th><th>Alasan</th><th>Aksi</th></tr></thead><tbody>
          {grants.map((grant) => <tr key={grant.id}><td><code>{grant.user_id}</code></td><td>{grant.scopes.join(", ")}</td><td><span className={"pill " + (grant.status === "active" ? "online" : "warning")}>{grant.status}</span></td><td>{grant.status === "revoked" ? grant.revocation_reason || grant.reason : grant.reason}</td><td>{grant.status === "active" && <button className="secondaryButton" disabled={busy || grant.user_id === operator?.id} onClick={() => void revokeGrant(grant)}>Cabut</button>}</td></tr>)}
          {!grants.length && <tr><td colSpan={5} className="emptyCell">Belum ada grant yang dapat ditampilkan.</td></tr>}
        </tbody></table></div>
      </section>}
      {session && canReview && <section className="panel" id="capability-review">
        <header className="panelHead"><div><h2>Capability review</h2><p>Hanya permintaan berstatus requested yang dapat diputuskan; keputusan dicatat oleh trigger database.</p></div><span className="pill warning">REVIEW SCOPE</span></header>
        <div className="capabilityList">
          {capabilities.map((capability) => {
            const highRisk = capability.risk_level === "high" || capability.risk_level === "critical";
            const highRiskAllowed = operator?.scopes.includes("platform:capabilities.review.high_risk");
            return <article className="capabilityCard" key={capability.id}>
              <div className="capabilityHead"><div><strong>{capability.capability_key}</strong><p>{capability.description || "Tidak ada deskripsi."}</p></div><span className={"pill " + (highRisk ? "warning" : "online")}>{capability.risk_level.toUpperCase()}</span></div>
              <p className="muted">Agent: <code>{capability.agent_id}</code> · Pemohon: <code>{capability.created_by}</code></p>
              <p className="muted">Permission scopes: {(capability.required_permission_scopes || []).join(", ") || "Belum dideklarasikan"}</p>
              {highRisk && !highRiskAllowed && <p className="riskWarning">Scope tambahan diperlukan: platform:capabilities.review.high_risk</p>}
              <label className="reviewReason">Alasan keputusan<input value={reviewReasons[capability.id] || ""} onChange={(event) => setReviewReasons((current) => ({ ...current, [capability.id]: event.target.value }))} minLength={8} maxLength={500} placeholder="Alasan review (min. 8 karakter)" /></label>
              <div className="reviewActions"><button disabled={busy || (highRisk && !highRiskAllowed) || (reviewReasons[capability.id] || "").trim().length < 8} onClick={() => void reviewCapability(capability, "approved")}>Approve request</button><button className="secondaryButton" disabled={busy || (highRisk && !highRiskAllowed) || (reviewReasons[capability.id] || "").trim().length < 8} onClick={() => void reviewCapability(capability, "denied")}>Deny request</button></div>
            </article>;
          })}
          {!capabilities.length && <p className="emptyCell">Tidak ada permintaan capability yang menunggu review.</p>}
        </div>
      </section>}
      {session && operator?.scopes.includes("platform:operations.read") && <section className="panel" id="official-bots">
        <header className="panelHead"><div><h2>Official Allpha AI Agents</h2><p>Roster kandidat dari katalog 500 Skills. Identitas, runtime, policy, dan GLB harus ditautkan dan diverifikasi sebelum aktivasi.</p></div><span className="pill warning">SUPERVISED</span></header>
        <div className="panelActions">{canReview && <button onClick={() => void provisionOfficialBots()} disabled={officialBotsBusy}>Siapkan 500 kandidat</button>}<button className="secondaryButton" onClick={() => void refreshOfficialBots()} disabled={officialBotsBusy}>{officialBotsBusy ? "Memuat…" : "Refresh roster"}</button><span className="muted">Roster teramati: {officialBotsTotal}</span></div>
        <p className="muted">Provisioning hanya membuat roster draft, bukan 500 Agent identity aktif. Aktivasi ditolak backend sampai Agent identity kanonis, policy runtime approved, dan asset GLB terverifikasi tersedia. Aksi lifecycle diaudit.</p>
        <div className="officialBotList">{officialBots.map(bot => <article className="probe officialBot" key={bot.id}>
          <div className="probeText"><b>{bot.display_name}</b><code>{bot.skill_key} · {bot.category_label}</code><p>{bot.skill_description}</p><small>Karakter: {bot.character_archetype_key} · Asset: {bot.character_asset_key || "belum ditautkan"} ({bot.asset_validation_status})</small><small>Agent: {bot.agent_id || "belum ditautkan"} · Policy: {bot.runtime_policy_id || "belum ditautkan"}</small></div>
          <span className={"pill " + (bot.status === "active" ? "online" : "warning")}>{bot.status.toUpperCase()}</span>
          {canControlBots && <div className="agent-card-actions"><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "active"} onClick={() => void officialBotAction(bot, "approve")}>Approve</button><button disabled={officialBotsBusy || bot.status === "active"} onClick={() => void officialBotAction(bot, "activate")}>Aktifkan</button><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "stopped"} onClick={() => void officialBotAction(bot, "stop")}>Stop</button><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "isolated"} onClick={() => void officialBotAction(bot, "isolate")}>Isolasi</button><button className="secondaryButton" disabled={officialBotsBusy || !["stopped","isolated","blocked"].includes(bot.status)} onClick={() => void officialBotAction(bot, "resume_to_draft")}>Kembali ke draft</button></div>}
        </article>)}{!officialBots.length && <p className="emptyCell">Roster belum dimuat atau belum diprovision melalui API.</p>}</div>
      </section>}
      {session && canReadAudit && <section className="panel" id="operator-audit">
        <header className="panelHead"><div><h2>Audit events</h2><p>Event terbaru dari tabel audit khusus operator; token dan payload sensitif tidak ditampilkan.</p></div><span className="pill online">AUDIT READ</span></header>
        <div className="tableWrap"><table><thead><tr><th>Waktu</th><th>Aktor</th><th>Aksi</th><th>Resource</th><th>Hasil</th><th>Request ID</th></tr></thead><tbody>
          {audit.map((event) => <tr key={event.id}><td>{new Date(event.created_at).toLocaleString("id-ID")}</td><td><code>{event.actor_user_id || "system"}</code></td><td>{event.action}</td><td>{event.resource_type}{event.resource_id ? " · " + event.resource_id : ""}</td><td><span className={"pill " + (event.outcome === "allowed" ? "online" : "warning")}>{event.outcome}</span></td><td><code>{event.request_id}</code></td></tr>)}
          {!audit.length && <tr><td colSpan={6} className="emptyCell">Belum ada event audit yang dapat ditampilkan.</td></tr>}
        </tbody></table></div>
      </section>}
      {error && <section className="notice errorNotice" role="alert"><b>!</b><div><strong>Permintaan ditolak / gagal</strong><p>{error}</p></div></section>}
      {notice && <section className="notice successNotice" role="status"><b>✓</b><div><strong>Status</strong><p>{notice}</p></div></section>}
      <section className="panel">
        <header className="panelHead"><div><h2>Service checks</h2><p>Probe publik untuk liveness dan readiness; bukan bukti otorisasi operator.</p></div><button onClick={() => void refreshProbes()} disabled={busy}>{busy ? "Memeriksa…" : "Refresh status"}</button></header>
        {probes.map((probe) => <article className="probe" key={probe.path}><span className={"icon " + probe.status}>{probe.status === "online" ? "✓" : probe.status === "checking" ? "…" : "!"}</span><div className="probeText"><b>{probe.label}</b><code>{probe.path}</code><p>{probe.detail}</p></div><span className={"pill " + probe.status}>{probe.status.toUpperCase()}</span></article>)}
        <footer className="panelFoot"><span>Terakhir diperiksa: {checkedAt || "—"}</span><span>Browser operator → API</span></footer>
      </section>
      <section className="notice"><b>i</b><div><strong>Security boundary aktif</strong><p>Grant pertama harus diberikan melalui kanal administrasi Supabase yang dipercaya. API menolak self-grant dan scope escalation; tindakan istimewa gagal tertutup bila audit tidak tersedia. Migration source-only belum diterapkan ke database.</p></div></section>
      <footer className="pageFoot">Allpha Universe · ENG-P06 · Status berasal dari respons backend aktual.</footer>
    </section>
  </main>;
}
