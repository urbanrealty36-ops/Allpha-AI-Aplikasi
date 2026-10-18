"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

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
type AgencySkillDraft = { skill_id: string; version_key: string; name?: string; category?: string; description?: string; status: "draft"; immutable: boolean; executable: boolean; content_sha256: string; review: { review_status: string; manual_security_review: string; security_flags?: string[] }; character_profile: { role?: string; asset_key?: string | null; asset_status?: string } };
type AgencySkillDraftDetail = AgencySkillDraft & { source_instructions_markdown: string; adapted_instructions: string; provenance: { commit: string; path: string; source_url: string; license: string } };
type AgencyReconciliationCandidate = { allpha_source_id: string; allpha_name?: string; similarity: number; shared_terms: string[]; agency_only_terms: string[]; allpha_only_terms: string[]; difference_summary: string; merge_decision: "none" };
type AgencyReconciliationRow = { agency_source_id: string; agency_name?: string; agency_description?: string; agency_category?: string; candidate_strength: string; canonical_identity_merge: false; candidates: AgencyReconciliationCandidate[] };
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
  const [officialBotsOffset, setOfficialBotsOffset] = useState(0);
  const [officialBotsBusy, setOfficialBotsBusy] = useState(false);
  const [officialBotCatalogSource, setOfficialBotCatalogSource] = useState<"allpha-500" | "agency-agents">("allpha-500");
  const [agencyDrafts, setAgencyDrafts] = useState<AgencySkillDraft[]>([]);
  const [agencyDraftsTotal, setAgencyDraftsTotal] = useState(0);
  const [agencyDraftImportStatus, setAgencyDraftImportStatus] = useState("not_loaded");
  const [agencyDraftDetail, setAgencyDraftDetail] = useState<AgencySkillDraftDetail | null>(null);
  const [agencyDraftsBusy, setAgencyDraftsBusy] = useState(false);
  const [agencyReconciliationSummary, setAgencyReconciliationSummary] = useState<{ candidate_count?: number; strong_candidate_count?: number; weak_candidate_count?: number; no_textual_overlap_count?: number; status?: string } | null>(null);
  const [agencyReconciliationRows, setAgencyReconciliationRows] = useState<AgencyReconciliationRow[]>([]);
  const [agencyReconciliationTotal, setAgencyReconciliationTotal] = useState(0);
  const [agencyReconciliationOffset, setAgencyReconciliationOffset] = useState(0);
  const [agencyReconciliationQuery, setAgencyReconciliationQuery] = useState("");
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>({});
  const [targetUser, setTargetUser] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<OperatorScope[]>([]);
  const [grantReason, setGrantReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkedAt, setCheckedAt] = useState("");
  const [runtimePreflight, setRuntimePreflight] = useState<{
    httpStatus: number; status?: string; failure_category?: string;
    dependencies?: Record<string, string>; route?: Record<string, unknown>;
    runtime_policy?: string; active_tariff?: string; metering_sink?: string;
    request_id?: string;
  } | null>(null);
  const [runtimePreflightBusy, setRuntimePreflightBusy] = useState(false);
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

  const loadOperatorData = useCallback(async (activeSession: AuthSession) => {
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
    if (access.operator.scopes.includes("platform:capabilities.review")) {
      const draftsResponse = await adminFetch("/v1/admin/skill-drafts/agency-agents?limit=50&offset=0", activeSession, setSession);
      const draftsBody = await responseBody<{ items: AgencySkillDraft[]; total: number; import_status: string }>(draftsResponse);
      setAgencyDrafts(draftsBody.items ?? []); setAgencyDraftsTotal(draftsBody.total ?? 0); setAgencyDraftImportStatus(draftsBody.import_status ?? "unknown");
      const reconciliationResponse = await adminFetch("/v1/admin/skill-drafts/agency-agents/reconciliation/summary", activeSession, setSession);
      setAgencyReconciliationSummary(await responseBody<{ candidate_count?: number; strong_candidate_count?: number; weak_candidate_count?: number; no_textual_overlap_count?: number; status?: string }>(reconciliationResponse));
      const reconciliationItemsResponse = await adminFetch("/v1/admin/skill-drafts/agency-agents/reconciliation/items?limit=50&offset=0", activeSession, setSession);
      const reconciliationItems = await responseBody<{ items: AgencyReconciliationRow[]; total: number }>(reconciliationItemsResponse);
      setAgencyReconciliationRows(reconciliationItems.items ?? []); setAgencyReconciliationTotal(reconciliationItems.total ?? 0); setAgencyReconciliationOffset(0);
    } else { setAgencyDrafts([]); setAgencyDraftsTotal(0); setAgencyDraftImportStatus("restricted"); setAgencyReconciliationSummary(null); }
    if (access.operator.scopes.includes("platform:operations.read")) {
      const botResponse = await adminFetch("/v1/admin/official-bots?limit=50&offset=0", activeSession, setSession);
      const botBody = await responseBody<{ items: OfficialBot[]; total?: number }>(botResponse);
      setOfficialBots(botBody.items ?? []); setOfficialBotsTotal(botBody.total ?? (botBody.items?.length ?? 0)); setOfficialBotsOffset(0);
    } else { setOfficialBots([]); setOfficialBotsTotal(0); }
  }, []);

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
  }, [session, loadOperatorData]);

  async function refreshAgencyReconciliation(offset = agencyReconciliationOffset, query = agencyReconciliationQuery) {
    if (!session) return;
    setAgencyDraftsBusy(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "50", offset: String(offset) });
      if (query.trim()) params.set("q", query.trim());
      const response = await adminFetch("/v1/admin/skill-drafts/agency-agents/reconciliation/items?" + params.toString(), session, setSession);
      const body = await responseBody<{ items: AgencyReconciliationRow[]; total: number }>(response);
      setAgencyReconciliationRows(body.items ?? []); setAgencyReconciliationTotal(body.total ?? 0); setAgencyReconciliationOffset(offset);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Rekonsiliasi katalog tidak dapat dimuat."); }
    finally { setAgencyDraftsBusy(false); }
  }

  async function viewAgencySkillDraft(skillId: string) {
    if (!session) return;
    setAgencyDraftsBusy(true); setError(""); setAgencyDraftDetail(null);
    try {
      const response = await adminFetch("/v1/admin/skill-drafts/agency-agents/" + encodeURIComponent(skillId), session, setSession);
      setAgencyDraftDetail(await responseBody<AgencySkillDraftDetail>(response));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Draft Skill tidak dapat dimuat."); }
    finally { setAgencyDraftsBusy(false); }
  }

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

  async function refreshOfficialBots(activeSession = session, offset = officialBotsOffset) {
    if (!activeSession) return;
    setOfficialBotsBusy(true); setError("");
    try {
      const response = await adminFetch("/v1/admin/official-bots?limit=50&offset=" + offset, activeSession, setSession);
      const body = await responseBody<{ items: OfficialBot[]; total?: number }>(response);
      setOfficialBots(body.items ?? []); setOfficialBotsTotal(body.total ?? (body.items?.length ?? 0)); setOfficialBotsOffset(offset);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Roster Official Bot tidak dapat dimuat."); }
    finally { setOfficialBotsBusy(false); }
  }

  async function provisionOfficialBots() {
    if (!session || !canReview) return;
    const sourceLabel = officialBotCatalogSource === "agency-agents" ? "Agency Agents (metadata-only)" : "Allpha 500 blueprint";
    if (!window.confirm("Siapkan kandidat Official Bot dari sumber " + sourceLabel + "? Ini membuat roster draft saja; tidak mengaktifkan runtime atau memverifikasi aset GLB.")) return;
    setOfficialBotsBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/official-bots/provision", session, setSession, { method: "POST", body: JSON.stringify({ limit: 500, catalog_source: officialBotCatalogSource }) });
      const body = await responseBody<{ roster_count_observed: number; catalog_count: number; message: string }>(response);
      setNotice(body.message + " Sumber: " + officialBotCatalogSource + "; katalog: " + body.catalog_count + "; roster teramati: " + body.roster_count_observed + ".");
      setOfficialBotsOffset(0);
      await refreshOfficialBots(session, 0);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Provision roster gagal."); }
    finally { setOfficialBotsBusy(false); }
  }

  async function provisionAllOfficialBots() {
    if (!session || !canReview) return;
    if (!window.confirm("Provision 500 Allpha blueprint + 282 Agency metadata menjadi roster draft? Ini tidak membuat Skill executable, tidak memverifikasi/mempublikasikan GLB, dan tidak mengaktifkan runtime.")) return;
    setOfficialBotsBusy(true); setError(""); setNotice("");
    try {
      const sources: Array<"allpha-500" | "agency-agents"> = ["allpha-500", "agency-agents"];
      const results: string[] = [];
      for (const source of sources) {
        setNotice("Menyiapkan roster kandidat: " + source + "…");
        const response = await adminFetch("/v1/admin/official-bots/provision", session, setSession, {
          method: "POST",
          body: JSON.stringify({ limit: 500, catalog_source: source }),
        });
        const body = await responseBody<{ roster_count_observed: number; catalog_count: number; catalog_source: string; message: string }>(response);
        results.push(source + ": katalog " + body.catalog_count + ", roster teramati " + body.roster_count_observed);
      }
      setNotice("Provision roster selesai. " + results.join(" · ") + ". Semua kandidat tetap draft; runtime tidak diaktifkan.");
      await refreshOfficialBots(session, 0);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Provision kedua katalog gagal.");
    } finally {
      setOfficialBotsBusy(false);
    }
  }

  async function provisionOfficialBotIdentities() {
    if (!session || !canControlBots) return;
    if (!window.confirm("Buat identitas Agent kanonis untuk semua kandidat draft yang belum memiliki identity? Batch maksimal 50, bisa dilanjutkan ulang, dan tidak mengaktifkan Agent/Bot. Pastikan platform owner UUID telah dikonfigurasi di API.")) return;
    setOfficialBotsBusy(true); setError(""); setNotice("");
    let all: OfficialBot[] = [];
    let offset = 0;
    let total = 0;
    try {
      do {
        const response = await adminFetch("/v1/admin/official-bots?limit=100&offset=" + offset, session, setSession);
        const body = await responseBody<{ items: OfficialBot[]; total?: number }>(response);
        const page = body.items ?? [];
        all = all.concat(page);
        total = body.total ?? all.length;
        if (!page.length) break;
        offset += page.length;
      } while (offset < total && offset < 2000);

      const pending = all.filter(bot => !bot.agent_id && (bot.status === "draft" || bot.status === "pending_approval"));
      if (!pending.length) {
        setNotice("Tidak ada roster draft yang membutuhkan Agent identity. Total roster terbaca: " + all.length + ".");
        return;
      }

      let succeeded = 0;
      let failed = 0;
      const failureDetails: string[] = [];
      for (let index = 0; index < pending.length; index += 50) {
        const batch = pending.slice(index, index + 50);
        setNotice("Provision Agent identity " + Math.min(index + batch.length, pending.length) + "/" + pending.length + "…");
        const response = await adminFetch("/v1/admin/official-bots/provision-identities", session, setSession, {
          method: "POST",
          body: JSON.stringify({ bot_ids: batch.map(bot => bot.id) }),
        });
        const body = await responseBody<{ requested: number; succeeded: number; failed: number; items: Array<{ bot_id: string; status: string; code?: string }> }>(response);
        succeeded += body.succeeded ?? 0;
        failed += body.failed ?? 0;
        for (const item of body.items ?? []) {
          if (item.status === "failed" && failureDetails.length < 8) {
            failureDetails.push(item.bot_id + " (" + (item.code || "unknown") + ")");
          }
        }
      }

      setNotice("Provision identity selesai: " + succeeded + " berhasil/already linked, " + failed + " gagal dari " + pending.length + " kandidat. Runtime activation: tidak dilakukan." +
        (failureDetails.length ? " Contoh gagal: " + failureDetails.join(", ") : ""));
      await refreshOfficialBots(session, 0);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Provision identity batch gagal. Jalankan ulang untuk melanjutkan; RPC identitas dirancang idempoten.");
    } finally {
      setOfficialBotsBusy(false);
    }
  }

  async function linkOfficialBotRuntime(bot: OfficialBot) {
    if (!session || !canControlBots) return;
    const agentId = window.prompt("UUID Agent identity kanonis untuk " + bot.display_name + ":");
    if (!agentId) return;
    const policyId = window.prompt("UUID runtime policy yang sudah berstatus approved:");
    if (!policyId) return;
    const assetKey = window.prompt("Key asset GLB dari katalog asset kanonis (bukan nama file bebas):");
    if (!assetKey || assetKey.trim().length < 3) return;
    const reason = window.prompt("Alasan penautan runtime (minimal 8 karakter):", "Penautan runtime ditinjau Super Admin");
    if (!reason || reason.trim().length < 8) return;
    setOfficialBotsBusy(true); setError(""); setNotice("");
    try {
      const response = await adminFetch("/v1/admin/official-bots/" + encodeURIComponent(bot.id) + "/links", session, setSession, {
        method: "PATCH", body: JSON.stringify({ agent_id: agentId.trim(), runtime_policy_id: policyId.trim(), character_asset_key: assetKey.trim() }),
      });
      const body = await responseBody<{ bot: OfficialBot; activation: string }>(response);
      setNotice("Tautan runtime tersimpan untuk review. Status asset tetap " + body.bot.asset_validation_status + "; aktivasi belum diizinkan.");
      await refreshOfficialBots();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Penautan runtime gagal."); }
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

  async function runRuntimePreflight() {
    if (!session) {
      setError("Login operator diperlukan untuk menjalankan runtime preflight.");
      return;
    }
    setRuntimePreflightBusy(true);
    setRuntimePreflight(null);
    setError("");
    setNotice("");
    try {
      const response = await adminFetch("/v1/system/runtime-preflight", session, setSession);
      const body = await response.json().catch(() => ({})) as {
        status?: string; failure_category?: string; dependencies?: Record<string, string>;
        route?: Record<string, unknown>; runtime_policy?: string; active_tariff?: string;
        metering_sink?: string; request_id?: string;
      };
      setRuntimePreflight({ ...body, httpStatus: response.status });
      if (response.ok && body.status === "ready") {
        setNotice("Runtime preflight berhasil melalui sesi Supabase yang terautentikasi. Tidak ada panggilan model yang dijalankan.");
      } else {
        setError("Runtime belum siap. Kategori: " + (body.failure_category || "runtime_unavailable") + ". Tidak ada panggilan model yang dijalankan.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Runtime preflight gagal dikirim.");
    } finally {
      setRuntimePreflightBusy(false);
    }
  }

  function logout() {
    setSession(null); setOperator(null); setAudit([]); setGrants([]); setCapabilities([]); setRuntimePreflight(null); setError(""); setNotice("");
  }

  return <main className="shell">
    <aside className="sidebar">
      <Link className="brand" href="/"><span className="mark">A</span><span><b>ALLPHA</b><small>CONTROL PLANE</small></span></Link>
      <p className="navLabel">OPERATIONS</p>
      <a className="nav active" href="#overview">◈ &nbsp; Overview</a>
      <Link className="nav" href="/costs">▤ &nbsp; Model cost CRUD</Link>
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
      {session && <section className="panel" id="runtime-preflight">
        <header className="panelHead"><div><h2>AI Runtime preflight</h2><p>Request menggunakan access token sesi aktif melalui helper API yang menangani refresh token. Pemeriksaan ini tidak memanggil model dan tidak menimbulkan biaya inference.</p></div><span className={"pill " + (runtimePreflight?.httpStatus === 200 ? "online" : "warning")}>{runtimePreflight ? "HTTP " + runtimePreflight.httpStatus : "NOT CHECKED"}</span></header>
        <div className="panelActions"><button onClick={() => void runRuntimePreflight()} disabled={runtimePreflightBusy}>{runtimePreflightBusy ? "Memeriksa runtime…" : "Jalankan preflight terautentikasi"}</button><span className="muted">Sesi: {session.user.email || session.user.id}</span></div>
        {runtimePreflight && <><p className="muted">Status: <strong>{runtimePreflight.status || "unknown"}</strong>{runtimePreflight.failure_category ? " · kategori: " + runtimePreflight.failure_category : ""}{runtimePreflight.request_id ? " · request: " + runtimePreflight.request_id : ""}</p>
          <div className="tableWrap"><table><thead><tr><th>Dependency</th><th>Status</th></tr></thead><tbody>
            {Object.entries(runtimePreflight.dependencies || {
              provider_route: runtimePreflight.route ? "configured" : "not_reported",
              runtime_policy: runtimePreflight.runtime_policy || "not_reported",
              active_tariff: runtimePreflight.active_tariff || "not_reported",
              metering_sink: runtimePreflight.metering_sink || "not_reported",
            }).map(([key, value]) => <tr key={key}><td>{key}</td><td><span className={"pill " + (["ready", "configured", "approved", "verified"].includes(value) ? "online" : "warning")}>{value}</span></td></tr>)}
          </tbody></table></div>
          {runtimePreflight.route && <details><summary>Snapshot rute dan batas runtime</summary><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{JSON.stringify(runtimePreflight.route, null, 2)}</pre></details>}
        </>}
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
        <div className="panelActions">{canReview && <><label className="muted">Sumber katalog <select value={officialBotCatalogSource} onChange={event => setOfficialBotCatalogSource(event.target.value as "allpha-500" | "agency-agents")} disabled={officialBotsBusy}><option value="allpha-500">Allpha · 500 blueprint</option><option value="agency-agents">Agency Agents · metadata-only</option></select></label><button onClick={() => void provisionOfficialBots()} disabled={officialBotsBusy}>Siapkan kandidat</button><button className="secondaryButton" onClick={() => void provisionAllOfficialBots()} disabled={officialBotsBusy}>Siapkan 500 + 282</button></>}{canControlBots && <button onClick={() => void provisionOfficialBotIdentities()} disabled={officialBotsBusy || !officialBotsTotal}>Provision Agent identities</button>}<button className="secondaryButton" onClick={() => void refreshOfficialBots()} disabled={officialBotsBusy}>{officialBotsBusy ? "Memuat…" : "Refresh roster"}</button><span className="muted">Roster: {officialBotsTotal} · Halaman {Math.floor(officialBotsOffset / 50) + 1}</span><button className="secondaryButton" onClick={() => void refreshOfficialBots(session, Math.max(0, officialBotsOffset - 50))} disabled={officialBotsBusy || officialBotsOffset === 0}>Sebelumnya</button><button className="secondaryButton" onClick={() => void refreshOfficialBots(session, officialBotsOffset + 50)} disabled={officialBotsBusy || officialBotsOffset + officialBots.length >= officialBotsTotal}>Berikutnya</button></div>
        <p className="muted">Provisioning hanya membuat roster draft. Aktivasi dinonaktifkan sampai Skill version kanonis, Agent identity, policy/tool/budget binding, GLB terverifikasi, dispatcher runtime, dan kill/cancellation benar-benar tersedia. Stop/isolate tidak boleh ditampilkan sebagai kill switch sebelum dispatch runtime terhubung.</p>
        <div className="officialBotList">{officialBots.map(bot => <article className="probe officialBot" key={bot.id}>
          <div className="probeText"><b>{bot.display_name}</b><code>{bot.skill_key} · {bot.category_label}</code><p>{bot.skill_description}</p><small>Karakter: {bot.character_archetype_key} · Asset: {bot.character_asset_key || "belum ditautkan"} ({bot.asset_validation_status})</small><small>Agent: {bot.agent_id || "belum ditautkan"} · Policy: {bot.runtime_policy_id || "belum ditautkan"}</small></div>
          <span className={"pill " + (bot.status === "active" ? "online" : "warning")}>{bot.status.toUpperCase()}</span>
          {canControlBots && <div className="agent-card-actions"><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "active"} onClick={() => void linkOfficialBotRuntime(bot)}>Tautkan runtime</button><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "active"} onClick={() => void officialBotAction(bot, "approve")}>Approve</button><button disabled title="Dispatcher runtime kanonis dan kill switch belum tersedia">Aktifkan · runtime belum siap</button><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "stopped" || bot.status === "active"} title={bot.status === "active" ? "Kill/cancellation runtime belum tersedia; status tidak dapat diubah dengan aman." : undefined} onClick={() => void officialBotAction(bot, "stop")}>Stop</button><button className="secondaryButton" disabled={officialBotsBusy || bot.status === "isolated" || bot.status === "active"} title={bot.status === "active" ? "Runtime isolation belum tersedia." : undefined} onClick={() => void officialBotAction(bot, "isolate")}>Isolasi</button><button className="secondaryButton" disabled={officialBotsBusy || !["stopped","isolated","blocked"].includes(bot.status)} onClick={() => void officialBotAction(bot, "resume_to_draft")}>Kembali ke draft</button></div>}
        </article>)}{!officialBots.length && <p className="emptyCell">Roster belum dimuat atau belum diprovision melalui API.</p>}</div>
      </section>}
      {session && canReview && <section className="panel" id="agency-skill-drafts">
        <header className="panelHead"><div><h2>Agency Skill drafts</h2><p>Instruksi sumber dipatok, checksum diverifikasi, tetapi tetap draft non-executable sampai tinjauan manual dan policy/tool binding selesai.</p></div><span className="pill warning">{agencyDraftImportStatus.toUpperCase()}</span></header>
        <div className="summary"><article><label>Draft terimpor</label><strong>{agencyDraftsTotal} <span>/ 282</span></strong><small>Versi immutable</small></article><article><label>Pasangan kandidat</label><strong>{agencyReconciliationSummary?.candidate_count ?? "—"}</strong><small>{agencyReconciliationSummary?.status || "Belum tersedia"}</small></article><article><label>Strong / weak / no overlap</label><strong>{agencyReconciliationSummary ? `${agencyReconciliationSummary.strong_candidate_count ?? 0} / ${agencyReconciliationSummary.weak_candidate_count ?? 0} / ${agencyReconciliationSummary.no_textual_overlap_count ?? 0}` : "—"}</strong><small>Heuristik teks, bukan keputusan merge</small></article><article><label>Eksekusi diizinkan</label><strong>0</strong><small>Semua draft non-executable</small></article></div>
        <div className="tableWrap"><table><thead><tr><th>Skill / sumber</th><th>Checksum SHA-256</th><th>Review</th><th>Aksi</th></tr></thead><tbody>
          {agencyDrafts.map((draft) => <tr key={draft.skill_id}><td><strong>{draft.name || draft.skill_id}</strong><br/><code>{draft.skill_id}</code><br/><small>{draft.category || "—"} · {draft.version_key}</small><br/><small>AI Character role: {draft.character_profile.role || draft.name || "belum ditentukan"} · asset: {draft.character_profile.asset_status || "needs_catalog_mapping"} · asset_key: {draft.character_profile.asset_key || "null"}</small></td><td><code>{draft.content_sha256.slice(0, 16)}…</code></td><td><span className="pill warning">{draft.review.review_status}</span><br/><small>Manual: {draft.review.manual_security_review}</small></td><td><button className="secondaryButton" disabled={agencyDraftsBusy} onClick={() => void viewAgencySkillDraft(draft.skill_id)}>Lihat instruksi</button></td></tr>)}
          {!agencyDrafts.length && <tr><td colSpan={4} className="emptyCell">Draft belum tersedia. Workflow impor harus berhasil sebelum isi instruksi muncul.</td></tr>}
        </tbody></table></div>
        <header className="panelHead"><div><h3>Rekonsiliasi kapabilitas 282 × 500</h3><p>Kesamaan berbasis token nama/deskripsi/kategori; istilah khusus masing-masing sumber ditampilkan. ID sumber dipertahankan dan tidak ada penggabungan otomatis.</p></div></header>
        <div className="panelActions"><input aria-label="Cari kandidat rekonsiliasi" value={agencyReconciliationQuery} onChange={event => setAgencyReconciliationQuery(event.target.value)} placeholder="Cari Agency / Allpha source ID" maxLength={120}/><button className="secondaryButton" disabled={agencyDraftsBusy} onClick={() => void refreshAgencyReconciliation(0, agencyReconciliationQuery)}>Cari</button><span className="muted">Baris {agencyReconciliationOffset + 1}–{Math.min(agencyReconciliationOffset + agencyReconciliationRows.length, agencyReconciliationTotal)} dari {agencyReconciliationTotal}</span><button className="secondaryButton" disabled={agencyDraftsBusy || agencyReconciliationOffset === 0} onClick={() => void refreshAgencyReconciliation(Math.max(0, agencyReconciliationOffset - 50))}>Sebelumnya</button><button className="secondaryButton" disabled={agencyDraftsBusy || agencyReconciliationOffset + agencyReconciliationRows.length >= agencyReconciliationTotal} onClick={() => void refreshAgencyReconciliation(agencyReconciliationOffset + 50)}>Berikutnya</button></div>
        <div className="tableWrap"><table><thead><tr><th>Agency source</th><th>Kandidat Allpha</th><th>Kesamaan & perbedaan</th><th>Keputusan</th></tr></thead><tbody>
          {agencyReconciliationRows.map(row => <tr key={row.agency_source_id}><td><strong>{row.agency_name || row.agency_source_id}</strong><br/><code>{row.agency_source_id}</code><br/><small>{row.agency_category} · {row.candidate_strength}</small><p>{row.agency_description}</p></td><td>{row.candidates.map(candidate => <div key={candidate.allpha_source_id} style={{marginBottom:12}}><strong>{candidate.allpha_name || candidate.allpha_source_id}</strong><br/><code>{candidate.allpha_source_id}</code><br/><small>Skor heuristik: {Math.round(candidate.similarity * 100)}%</small></div>)}{!row.candidates.length && <span className="muted">Tidak ada overlap tekstual</span>}</td><td>{row.candidates.map(candidate => <div key={candidate.allpha_source_id} style={{marginBottom:12}}><small>Shared: {candidate.shared_terms.join(", ") || "—"}</small><br/><small>Perbedaan: {candidate.difference_summary}</small></div>)}</td><td><span className="pill warning">NO AUTO-MERGE</span></td></tr>)}
          {!agencyReconciliationRows.length && <tr><td colSpan={4} className="emptyCell">Kandidat rekonsiliasi belum tersedia.</td></tr>}
        </tbody></table></div>
        {agencyDraftDetail && <article className="probe"><div className="probeText"><b>{agencyDraftDetail.name} · {agencyDraftDetail.version_key}</b><p>License: {agencyDraftDetail.provenance.license} · Commit: <code>{agencyDraftDetail.provenance.commit.slice(0, 12)}</code></p><p>Source: <a href={agencyDraftDetail.provenance.source_url} target="_blank" rel="noreferrer">{agencyDraftDetail.provenance.path}</a></p><p>Flags otomatis: {(agencyDraftDetail.review.security_flags || []).join(", ") || "Tidak ada pola terdeteksi; ini bukan jaminan bebas risiko."}</p><p>Checksum: <code>{agencyDraftDetail.content_sha256}</code></p><p>AI Character role: {agencyDraftDetail.character_profile.role || agencyDraftDetail.name} · Asset status: {agencyDraftDetail.character_profile.asset_status || "needs_catalog_mapping"} · asset_key: <code>{agencyDraftDetail.character_profile.asset_key || "null"}</code></p><details><summary>Instruksi adaptasi Allpha</summary><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:360,overflow:"auto"}}>{agencyDraftDetail.adapted_instructions}</pre></details><details><summary>Instruksi sumber asli</summary><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:360,overflow:"auto"}}>{agencyDraftDetail.source_instructions_markdown}</pre></details></div><button className="secondaryButton" onClick={() => setAgencyDraftDetail(null)}>Tutup</button></article>}
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
      <footer className="pageFoot">Allpha Universe · ENG-P34 · Status berasal dari respons backend aktual.</footer>
    </section>
  </main>;
}
