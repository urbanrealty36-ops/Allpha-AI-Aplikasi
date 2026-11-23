"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import { verifyBackendSession } from "../../lib/auth-validation.mjs";
import AccountDataLifecyclePanel from "./AccountDataLifecyclePanel";

type Profile = {
  id: string; username: string | null; display_name: string; avatar_url: string | null; bio: string;
  visibility: "public" | "private"; locale: "id-ID" | "en-US"; account_status: "active" | "deactivation_requested";
  created_at: string; updated_at: string;
};
type Settings = {
  user_id: string; theme: "light" | "dark" | "system";
  notification_preferences: { product_updates: boolean; security_alerts: boolean; social_activity: boolean };
  privacy_settings: { discoverable_by_username: boolean; allow_interest_matching: boolean }; updated_at: string;
};
type IdentityResponse = { user: { id: string; email?: string; email_confirmed_at?: string }; profile: Profile };
type SettingsResponse = { settings: Settings | null };
type SocialEdge = { id: string; target_user_id?: string; actor_user_id?: string; edge_type: "follow" | "block" | "mute"; status?: string; created_at?: string };
type SocialInterest = { interest_key: string; preference: "interested" | "not_interested"; created_at?: string; updated_at?: string };
type InterestCatalogItem = { interest_key: string; label: string; label_key: string; category: string; aliases?: string[]; sensitivity?: "standard" | "sensitive"; sort_order: number };
type InterestGraphSignal = { interest_key: string; agent_id?: string | null; signal_type: "passion" | "habit"; strength: number; signal_source: string; updated_at: string };
type SocialActorAgent = { id: string; handle: string; display_name: string; status: "active"; ownership_role: "owner" | "operator" };
type DiscoveredSocialUser = { id: string; username: string; display_name?: string | null; avatar_url?: string | null; visibility: "public" | "private" };
type SocialGraph = { outgoing: SocialEdge[]; incoming_followers?: SocialEdge[]; incoming_requests: SocialEdge[]; blocked_by: SocialEdge[]; interests: SocialInterest[]; summary?: { following: number; followers: number; pending_follow_requests: number; blocked: number; muted: number; interests: number; truncated: boolean }; };
type ConsentRecord = { id: string; consent_type: "terms_of_service" | "privacy_policy" | "product_updates" | string; policy_version: string; decision: "granted" | "declined" | "revoked"; source: string; idempotency_key: string; recorded_at: string };
type ConsentPolicyVersions = { terms_of_service: string | null; privacy_policy: string | null; product_updates: string | null };
type AuthSession = { id: string; created_at: string | null; updated_at: string | null; refreshed_at: string | null; not_after: string | null; aal: string | null; user_agent: string | null; ip: string | null; is_current: boolean };
type AuthSessionsResponse = { items: AuthSession[]; current_session_id: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function apiError(response: Response): Promise<string> {
  try { const body = await response.json(); return body?.detail?.message ?? body?.error?.message ?? "Permintaan gagal (" + response.status + ")."; }
  catch { return "Permintaan gagal (" + response.status + ")."; }
}

export default function HomePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(""); const [error, setError] = useState("");
  const [tab, setTab] = useState<"profile" | "settings" | "social" | "consents" | "sessions" | "data">("profile");
  const [authSessions, setAuthSessions] = useState<AuthSession[] | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState("");
  const [consentHistory, setConsentHistory] = useState<ConsentRecord[] | null>(null);
  const [currentPolicyVersions, setCurrentPolicyVersions] = useState<ConsentPolicyVersions>({ terms_of_service: null, privacy_policy: null, product_updates: null });
  const [consentLoading, setConsentLoading] = useState(false);
  const [consentError, setConsentError] = useState("");
  const [socialGraph, setSocialGraph] = useState<SocialGraph | null>(null);
  const [socialLoading, setSocialLoading] = useState(false);
  const [targetUserId, setTargetUserId] = useState("");
  const [socialQuery, setSocialQuery] = useState("");
  const [discoveredSocialUsers, setDiscoveredSocialUsers] = useState<DiscoveredSocialUser[]>([]);
  const [socialDiscoveryLoading, setSocialDiscoveryLoading] = useState(false);
  const [socialDiscoveryError, setSocialDiscoveryError] = useState("");
  const [interestKey, setInterestKey] = useState("");
  const [interestCatalog, setInterestCatalog] = useState<InterestCatalogItem[]>([]);
  const [interestPreference, setInterestPreference] = useState<"interested" | "not_interested">("interested");
  const [interestGraphSignals, setInterestGraphSignals] = useState<InterestGraphSignal[]>([]);
  const [socialAgents, setSocialAgents] = useState<SocialActorAgent[]>([]);
  const [signalAgentId, setSignalAgentId] = useState("");
  const [signalInterestKey, setSignalInterestKey] = useState("");
  const [signalType, setSignalType] = useState<"passion" | "habit">("passion");
  const [signalStrength, setSignalStrength] = useState(0.8);
  const identityRequestSequence = useRef(0);
  const socialRequestSequence = useRef(0);
  const consentRequestSequence = useRef(0);
  const sessionsRequestSequence = useRef(0);
  const sessionsAutoLoadToken = useRef<string | null>(null);

  const loadIdentity = useCallback(async (active: Session) => {
    const sequence = ++identityRequestSequence.current;
    setLoading(true); setError("");
    try {
      const backend = await verifyBackendSession<IdentityResponse>(apiBase, active);
      if (backend.status === "rejected") {
        await supabase?.auth.signOut({ scope: "local" });
        return;
      }
      if (backend.status !== "valid") throw new Error("Sesi belum dapat diverifikasi oleh Allpha API. Sesi lokal dipertahankan; coba lagi.");
      const headers = { Authorization: "Bearer " + active.access_token };
      const settingsResponse = await fetch(apiBase + "/v1/me/settings", { headers, cache: "no-store" });
      if (settingsResponse.status === 401 || settingsResponse.status === 403) {
        await supabase?.auth.signOut({ scope: "local" });
        return;
      }
      if (!settingsResponse.ok) throw new Error(await apiError(settingsResponse));
      const identity = backend.identity;
      const prefs = await settingsResponse.json() as SettingsResponse;
      if (sequence !== identityRequestSequence.current) return;
      setProfile(identity.profile);
      setSettings(prefs.settings ? {
        ...prefs.settings,
        privacy_settings: {
          discoverable_by_username: prefs.settings.privacy_settings?.discoverable_by_username === true,
          allow_interest_matching: prefs.settings.privacy_settings?.allow_interest_matching === true,
        },
      } : null);
    } catch (cause) {
      if (sequence === identityRequestSequence.current) setError(cause instanceof Error ? cause.message : "Data identitas tidak dapat dimuat.");
    } finally { if (sequence === identityRequestSequence.current) setLoading(false); }
  }, [supabase]);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    let authEventSeen = false;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active || authEventSeen) return;
      setSession(data.session);
      sessionsAutoLoadToken.current = null;
      socialRequestSequence.current += 1; consentRequestSequence.current += 1; sessionsRequestSequence.current += 1;
      setSocialGraph(null); setConsentHistory(null); setCurrentPolicyVersions({ terms_of_service: null, privacy_policy: null, product_updates: null }); setAuthSessions(null);
      if (data.session) void loadIdentity(data.session); else {
        identityRequestSequence.current += 1;
        setProfile(null); setSettings(null); setLoading(false);
      }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      authEventSeen = true;
      if (!active) return;
      setSession(next);
      sessionsAutoLoadToken.current = null;
      socialRequestSequence.current += 1; consentRequestSequence.current += 1; sessionsRequestSequence.current += 1;
      setSocialGraph(null); setConsentHistory(null); setAuthSessions(null);
      setSocialLoading(false); setConsentLoading(false); setSessionsLoading(false); setSessionsError("");
      if (next) void loadIdentity(next);
      else {
        identityRequestSequence.current += 1;
        setProfile(null); setSettings(null); setLoading(false);
      }
    });
    return () => {
      active = false;
      identityRequestSequence.current += 1; socialRequestSequence.current += 1; consentRequestSequence.current += 1; sessionsRequestSequence.current += 1;
      listener.subscription.unsubscribe();
    };
  }, [supabase, loadIdentity]);

  // Keep account sub-sections addressable so native deep links and the Web route
  // resolve the same canonical profile/settings/privacy/relationship view.
  useEffect(() => {
    const requestedTab = new URLSearchParams(window.location.search).get("tab");
    if (requestedTab === "profile" || requestedTab === "settings" || requestedTab === "social" || requestedTab === "consents" || requestedTab === "sessions") {
      setTab(requestedTab);
    }
  }, []);

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = "/account";
    const modeParam = mode === "signup" ? "register" : "login";
    // Account settings must not implement a second auth flow. Reuse the
    // canonical onboarding route and preserve the intended destination.
    window.location.assign("/" + modeParam + "?mode=" + modeParam + "&next=" + encodeURIComponent(next));
  }

  async function handleLogout() {
    if (!session || !supabase) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/auth/revoke", {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" },
      });
      if (response.status === 401 || response.status === 403) {
        await supabase.auth.signOut({ scope: "local" });
        return;
      }
      if (!response.ok) throw new Error(await apiError(response));
      const { error: signOutError } = await supabase.auth.signOut({ scope: "local" });
      if (signOutError) throw signOutError;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sesi tidak dapat dicabut.");
    } finally { setSaving(false); }
  }

  const loadAuthSessions = useCallback(async () => {
    if (!session) return;
    const sequence = ++sessionsRequestSequence.current;
    const token = session.access_token;
    setSessionsLoading(true); setSessionsError("");
    try {
      const response = await fetch(apiBase + "/v1/me/sessions", { headers: { Authorization: "Bearer " + token }, cache: "no-store" });
      if (response.status === 401 || response.status === 403) {
        if (sequence === sessionsRequestSequence.current && session?.access_token === token) await supabase?.auth.signOut({ scope: "local" });
        throw new Error("Sesi sudah tidak berlaku. Silakan masuk kembali.");
      }
      if (!response.ok) throw new Error(await apiError(response));
      const payload = await response.json() as AuthSessionsResponse;
      if (sequence === sessionsRequestSequence.current && session?.access_token === token) {
        setAuthSessions(Array.isArray(payload.items) ? payload.items : []);
      }
    } catch (cause) {
      if (sequence === sessionsRequestSequence.current && session?.access_token === token) {
        setSessionsError(cause instanceof Error ? cause.message : "Daftar sesi tidak dapat dimuat.");
      }
    } finally {
      if (sequence === sessionsRequestSequence.current) setSessionsLoading(false);
    }
  }, [session, supabase]);

  // A restored /account?tab=sessions deep link must load the same canonical
  // device inventory as an explicit tab click, once per authenticated token.
  useEffect(() => {
    if (tab !== "sessions" || !session) return;
    if (sessionsAutoLoadToken.current === session.access_token) return;
    sessionsAutoLoadToken.current = session.access_token;
    void loadAuthSessions();
  }, [tab, session?.access_token, loadAuthSessions]);

  async function revokeAuthSession(sessionId: string) {
    if (!session || !window.confirm("Cabut sesi perangkat ini? Perangkat tersebut harus login kembali.")) return;
    setSaving(true); setSessionsError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/sessions/" + encodeURIComponent(sessionId) + "/revoke", {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token },
      });
      if (response.status === 401 || response.status === 403) {
        await supabase?.auth.signOut({ scope: "local" });
        throw new Error("Sesi sudah tidak berlaku. Silakan masuk kembali.");
      }
      if (!response.ok) throw new Error(await apiError(response));
      setMessage("Sesi perangkat berhasil dicabut."); await loadAuthSessions();
    } catch (cause) { setSessionsError(cause instanceof Error ? cause.message : "Sesi tidak dapat dicabut."); }
    finally { setSaving(false); }
  }

  async function revokeOtherAuthSessions() {
    if (!session || !window.confirm("Cabut semua sesi di perangkat lain? Sesi perangkat ini akan tetap aktif.")) return;
    setSaving(true); setSessionsError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/sessions/revoke-others", {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token },
      });
      if (response.status === 401 || response.status === 403) {
        await supabase?.auth.signOut({ scope: "local" });
        throw new Error("Sesi sudah tidak berlaku. Silakan masuk kembali.");
      }
      if (!response.ok) throw new Error(await apiError(response));
      const payload = await response.json() as { revoked_count: number };
      setMessage(payload.revoked_count + " sesi perangkat lain berhasil dicabut."); await loadAuthSessions();
    } catch (cause) { setSessionsError(cause instanceof Error ? cause.message : "Sesi perangkat lain tidak dapat dicabut."); }
    finally { setSaving(false); }
  }

  async function loadConsentHistory() {
    if (!session) return;
    const sequence = ++consentRequestSequence.current;
    const token = session.access_token;
    setConsentLoading(true); setConsentError("");
    try {
      const response = await fetch(apiBase + "/v1/me/consents", { headers: { Authorization: "Bearer " + token }, cache: "no-store" });
      if (!response.ok) throw new Error(await apiError(response));
      const payload = await response.json() as { items?: ConsentRecord[]; current_policy_versions?: Partial<ConsentPolicyVersions> };
      if (sequence === consentRequestSequence.current && session?.access_token === token) {
        setConsentHistory(Array.isArray(payload.items) ? payload.items : []);
        setCurrentPolicyVersions({
          terms_of_service: payload.current_policy_versions?.terms_of_service ?? null,
          privacy_policy: payload.current_policy_versions?.privacy_policy ?? null,
          product_updates: payload.current_policy_versions?.product_updates ?? null,
        });
      }
    } catch (cause) {
      if (sequence === consentRequestSequence.current && session?.access_token === token) setConsentError(cause instanceof Error ? cause.message : "Riwayat persetujuan tidak dapat dimuat.");
    } finally { if (sequence === consentRequestSequence.current) setConsentLoading(false); }
  }

  async function recordProductUpdatesConsent(granted: boolean) {
    if (!session || !currentPolicyVersions.product_updates) {
      setConsentError("Versi kebijakan pembaruan produk belum dikonfigurasi oleh server.");
      return;
    }
    setSaving(true); setConsentError(""); setMessage("");
    try {
      const idempotencyKey = window.crypto?.randomUUID?.() || ("consent-" + Date.now() + "-" + Math.random().toString(36).slice(2, 12));
      const response = await fetch(apiBase + "/v1/me/consents", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + session.access_token,
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          consent_type: "product_updates",
          policy_version: currentPolicyVersions.product_updates,
          granted,
          source: "account_settings",
        }),
      });
      if (!response.ok) throw new Error(await apiError(response));
      setMessage(granted ? "Persetujuan pembaruan produk tercatat." : "Persetujuan pembaruan produk dicabut.");
      await loadConsentHistory();
    } catch (cause) {
      setConsentError(cause instanceof Error ? cause.message : "Persetujuan tidak dapat diperbarui.");
    } finally { setSaving(false); }
  }

  async function loadSocialGraph() {
    if (!session) return;
    const sequence = ++socialRequestSequence.current;
    const token = session.access_token;
    setSocialLoading(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/social-graph", { headers: { Authorization: "Bearer " + token }, cache: "no-store" });
      if (!response.ok) throw new Error(await apiError(response));
      const graph = await response.json() as SocialGraph;
      if (sequence === socialRequestSequence.current && session?.access_token === token) setSocialGraph(graph);
      try {
        const [catalogResponse, signalResponse, agentsResponse] = await Promise.all([
          fetch(apiBase + "/v1/interests/catalog", { headers: { Authorization: "Bearer " + token }, cache: "no-store" }),
          fetch(apiBase + "/v1/me/interest-signals", { headers: { Authorization: "Bearer " + token }, cache: "no-store" }),
          fetch(apiBase + "/v1/social/actor-agents", { headers: { Authorization: "Bearer " + token }, cache: "no-store" }),
        ]);
        if (catalogResponse.ok) {
          const catalog = await catalogResponse.json() as { items?: InterestCatalogItem[] };
          if (sequence === socialRequestSequence.current && session?.access_token === token) setInterestCatalog(catalog.items || []);
        }
        if (signalResponse.ok) {
          const signals = await signalResponse.json() as { items?: InterestGraphSignal[] };
          if (sequence === socialRequestSequence.current && session?.access_token === token) setInterestGraphSignals(signals.items || []);
        }
        if (agentsResponse.ok) {
          const agents = await agentsResponse.json() as { items?: SocialActorAgent[] };
          if (sequence === socialRequestSequence.current && session?.access_token === token) setSocialAgents((agents.items || []).filter(agent => agent.status === "active" && agent.ownership_role === "owner"));
        }
      } catch { /* Catalog loading must not hide the caller's existing graph. */ }
    } catch (cause) {
      if (sequence === socialRequestSequence.current && session?.access_token === token) setError(cause instanceof Error ? cause.message : "Social Graph tidak dapat dimuat.");
    } finally { if (sequence === socialRequestSequence.current) setSocialLoading(false); }
  }

  async function socialRequest(path: string, init: RequestInit = {}) {
    if (!session) throw new Error("Sesi login diperlukan.");
    const response = await fetch(apiBase + path, { ...init, headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", ...(init.headers || {}) } });
    if (!response.ok) throw new Error(await apiError(response));
    return response.status === 204 ? {} : response.json();
  }

  async function addSocialEdge(edgeType: "follow" | "block" | "mute", targetOverride?: string) {
    const target = (targetOverride || targetUserId).trim();
    if (!target) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const result = await socialRequest("/v1/me/social-edges", { method: "POST", body: JSON.stringify({ target_user_id: target, edge_type: edgeType }) }) as { outcome?: string; idempotent_replay?: boolean };
      if (!targetOverride) setTargetUserId("");
      const outcomeMessage = result.outcome === "follow_active" ? "Anda sekarang mengikuti akun ini." : result.outcome === "follow_request_created" ? "Permintaan mengikuti menunggu persetujuan." : result.outcome === "user_blocked" ? "Akun berhasil diblokir." : result.outcome === "user_muted" ? "Akun berhasil dibisukan." : "Relasi sosial tersimpan.";
      setMessage(result.idempotent_replay ? "Relasi tersebut sudah ada; tidak dibuat duplikat." : outcomeMessage);
      await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Relasi sosial gagal disimpan."); }
    finally { setSaving(false); }
  }

  async function removeSocialEdge(edge: SocialEdge) {
    const target = edge.target_user_id || edge.actor_user_id;
    if (!target) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await socialRequest("/v1/me/social-edges/" + encodeURIComponent(target) + "/" + edge.edge_type, { method: "DELETE" });
      setMessage("Relasi berhasil dihapus."); await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Relasi tidak dapat dihapus."); }
    finally { setSaving(false); }
  }

  async function resolveFollowRequest(edgeId: string, accept: boolean) {
    setSaving(true); setError(""); setMessage("");
    try {
      await socialRequest(accept ? "/v1/me/follow-requests/" + encodeURIComponent(edgeId) + "/accept" : "/v1/me/follow-requests/" + encodeURIComponent(edgeId), { method: accept ? "POST" : "DELETE" });
      setMessage(accept ? "Permintaan mengikuti diterima." : "Permintaan mengikuti ditolak."); await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Permintaan mengikuti gagal diproses."); }
    finally { setSaving(false); }
  }

  async function discoverSocialUsers() {
    const query = socialQuery.trim().replace(/^@/, "");
    if (query.length < 3) { setSocialDiscoveryError("Masukkan minimal 3 karakter username."); setDiscoveredSocialUsers([]); return; }
    setSocialDiscoveryLoading(true); setSocialDiscoveryError("");
    try {
      const payload = await socialRequest("/v1/social/discover-users?q=" + encodeURIComponent(query) + "&limit=20") as { items?: DiscoveredSocialUser[] };
      setDiscoveredSocialUsers(payload.items || []);
    } catch (cause) {
      setDiscoveredSocialUsers([]);
      setSocialDiscoveryError(cause instanceof Error ? cause.message : "Pencarian akun belum tersedia.");
    } finally { setSocialDiscoveryLoading(false); }
  }

  async function saveInterest() {
    const key = interestKey.trim();
    if (!key) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await socialRequest("/v1/me/interests", { method: "PUT", body: JSON.stringify({ interest_key: key, preference: interestPreference }) });
      setInterestKey(""); setMessage(interestPreference === "interested" ? "Preferensi minat disimpan." : "Preferensi tidak diminati disimpan."); await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Minat tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function updateInterestPreference(key: string, preference: "interested" | "not_interested") {
    setSaving(true); setError(""); setMessage("");
    try {
      await socialRequest("/v1/me/interests", { method: "PUT", body: JSON.stringify({ interest_key: key, preference }) });
      setMessage(preference === "interested" ? "Minat diaktifkan kembali." : "Minat ditandai tidak diminati.");
      await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Preferensi minat tidak dapat diperbarui."); }
    finally { setSaving(false); }
  }

  async function removeInterest(key: string) {
    setSaving(true); setError(""); setMessage("");
    try {
      await socialRequest("/v1/me/interests/" + encodeURIComponent(key), { method: "DELETE" });
      setMessage("Minat berhasil dihapus."); await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Minat tidak dapat dihapus."); }
    finally { setSaving(false); }
  }

  async function saveInterestGraphSignal() {
    if (!signalInterestKey) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await socialRequest("/v1/me/interest-signals", {
        method: "PUT",
        body: JSON.stringify({
          interest_key: signalInterestKey,
          signal_type: signalType,
          strength: signalStrength,
          signal_source: "user_selected",
          ...(signalAgentId ? { agent_id: signalAgentId } : {}),
        }),
      });
      setSignalInterestKey("");
      setMessage((signalType === "passion" ? "Passion Graph" : "Habit Graph") + (signalAgentId ? " Agent disimpan." : " Human disimpan."));
      await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Passion/Habit Graph tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function removeInterestGraphSignal(signal: InterestGraphSignal) {
    setSaving(true); setError(""); setMessage("");
    try {
      const agentQuery = signal.agent_id ? "?agent_id=" + encodeURIComponent(signal.agent_id) : "";
      await socialRequest("/v1/me/interest-signals/" + signal.signal_type + "/" + encodeURIComponent(signal.interest_key) + agentQuery, { method: "DELETE" });
      setMessage("Sinyal " + signal.signal_type + " dihapus.");
      await loadSocialGraph();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sinyal Graph tidak dapat dihapus."); }
    finally { setSaving(false); }
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session || !profile) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/profile", {
        method: "PATCH", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ username: profile.username || null, display_name: profile.display_name, avatar_url: profile.avatar_url || null, bio: profile.bio, visibility: profile.visibility, locale: profile.locale }),
      });
      if (!response.ok) throw new Error(await apiError(response));
      const data = await response.json(); setProfile(data.profile); setMessage("Profil berhasil disimpan ke Allpha.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Profil tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session || !settings || !profile) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const headers = { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" };
      const profileResponse = await fetch(apiBase + "/v1/me/profile", { method: "PATCH", headers, body: JSON.stringify({ locale: profile.locale }) });
      if (!profileResponse.ok) throw new Error(await apiError(profileResponse));
      const settingsResponse = await fetch(apiBase + "/v1/me/settings", { method: "PATCH", headers, body: JSON.stringify(settingsPayload(settings)) });
      if (!settingsResponse.ok) throw new Error(await apiError(settingsResponse));
      const updatedProfile = await profileResponse.json() as { profile: Profile };
      const updatedSettings = await settingsResponse.json() as SettingsResponse;
      setProfile(updatedProfile.profile); setSettings(updatedSettings.settings); setMessage("Pengaturan berhasil disimpan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pengaturan tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function requestDeactivation() {
    if (!session || !window.confirm("Ajukan permintaan penonaktifan akun? Akun tidak langsung dihapus.")) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/deactivation-request", { method: "POST", headers: { Authorization: "Bearer " + session.access_token } });
      if (!response.ok) throw new Error(await apiError(response));
      const data = await response.json();
      setProfile((current) => current ? { ...current, account_status: data.profile.account_status } : current); setMessage(data.message);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Permintaan tidak dapat dikirim."); }
    finally { setSaving(false); }
  }

  if (!supabase) return <main className="identity-shell"><header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><div className="hidden md:flex items-center gap-4"><a className="text-sm font-semibold text-blue-600 hover:underline" href="/feed">Feed sosial</a><a className="text-sm font-semibold text-blue-600 hover:underline" href="/communities">Komunitas & Workspace</a><a className="text-sm font-semibold text-cyan-600 hover:underline" href="/reels">Reels</a></div><span className="top-note">HUMAN IDENTITY</span></header><section className="config-card"><span className="section-kicker">KONFIGURASI DIBUTUHKAN</span><h1>Hubungkan identitas Allpha</h1><p>Atur <code>NEXT_PUBLIC_SUPABASE_URL</code> dan <code>NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY</code> untuk mengaktifkan login nyata. Tidak ada akun contoh yang ditampilkan.</p></section></main>;

  if (!session) return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><div className="flex gap-4"><a className="text-sm font-semibold text-blue-600 hover:underline" href="/feed">Feed sosial</a><a className="text-sm font-semibold text-blue-600 hover:underline" href="/communities">Komunitas & Workspace</a></div><span className="top-note">HUMAN IDENTITY</span></header>
    <section className="auth-layout"><div className="auth-intro"><span className="section-kicker">AI SOCIAL UNIVERSE</span><h1>Identitas Anda, pusat dari universe Anda.</h1><p>Kelola profil manusia, privasi, dan preferensi akun dari satu tempat.</p><div className="identity-orbit" aria-hidden="true"><span /><i /><b>A</b></div></div>
      <form className="panel auth-panel" onSubmit={handleAuth}><div className="panel-heading"><span className="section-kicker">{mode === "signin" ? "SELAMAT DATANG KEMBALI" : "MULAI DI ALLPHA"}</span><h2>{mode === "signin" ? "Masuk ke Allpha" : "Buat akun manusia"}</h2><p>Autentikasi melalui Supabase.</p></div>
        {mode === "signup" && <label>Nama tampilan<input autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} minLength={2} maxLength={80} required /></label>}
        <label>Email<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Kata sandi<input type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required /></label>
        {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice success" role="status">{message}</p>}
        <button className="button-primary full-width" type="submit" disabled={saving}>{saving ? "Memproses…" : mode === "signin" ? "Masuk" : "Buat akun"}</button>
        <p className="switch-mode">{mode === "signin" ? "Belum memiliki akun?" : "Sudah memiliki akun?"} <button type="button" className="text-button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setMessage(""); }}>{mode === "signin" ? "Daftar" : "Masuk"}</button></p>
      </form></section><footer className="identity-footer"><span>ALLPHA · HUMAN IDENTITY</span><span>Data nyata · Akses berbasis sesi</span></footer></main>;

  return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><div className="account-menu"><span className="signed-in">{session.user.email}</span><a className="button-primary" href="/feed">Buka Feed ↗</a><a className="button-quiet" href="/agents">AI Agent Studio ↗</a><a className="button-quiet" href="/content-studio">Creator Studio ↗</a><a className="button-quiet" href="/billing">Billing & AI Credits ↗</a><a className="button-quiet" href="/reels">Reels ↗</a><button className="button-quiet" disabled={saving} onClick={() => void handleLogout()}>{saving ? "Mencabut sesi…" : "Keluar ↗"}</button></div></header>
    <section className="workspace-heading"><div><span className="section-kicker">RUANG PERSONAL</span><h1>Identitas manusia</h1><p>Profil dan pengaturan yang tersimpan pada akun Allpha Anda.</p></div>
      {profile && <div className="profile-chip">{profile.avatar_url ? <img src={profile.avatar_url} alt="" /> : <span>{(profile.display_name || session.user.email || "A").slice(0, 1).toUpperCase()}</span>}<div><strong>{profile.display_name || "Pengguna Allpha"}</strong><small>{profile.username ? "@" + profile.username : "Username belum diatur"}</small></div></div>}
    </section>
    <nav className="identity-tabs" aria-label="Bagian identitas"><button className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}>Profil</button><button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>Pengaturan</button><button className={tab === "social" ? "active" : ""} onClick={() => { setTab("social"); void loadSocialGraph(); }}>Social Graph</button><button className={tab === "consents" ? "active" : ""} onClick={() => { setTab("consents"); void loadConsentHistory(); }}>Riwayat persetujuan</button><button className={tab === "sessions" ? "active" : ""} onClick={() => setTab("sessions")}>Perangkat & sesi</button><button className={tab === "data" ? "active" : ""} onClick={() => setTab("data")}>Data & akun</button></nav>
    {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice success" role="status">{message}</p>}
    {loading ? <section className="panel loading-panel" role="status">Mengambil profil dan pengaturan dari backend…</section> : !profile || !settings ? <section className="panel loading-panel">{error ? <><p className="muted">Profil dan pengaturan belum berhasil dimuat. Periksa koneksi atau sesi, lalu coba lagi.</p><button type="button" className="button-primary" onClick={() => { if (session) void loadIdentity(session); }}>Coba lagi</button></> : <><p className="muted">Profil belum tersedia.</p><button type="button" className="button-quiet" onClick={() => { if (session) void loadIdentity(session); }}>Muat ulang</button></>}</section> : tab === "social" ? <section className="panel settings-panel social-panel">
      <div className="panel-heading"><span className="section-kicker">SOCIAL GRAPH</span><h2>Relasi dan minat Anda</h2><p>Relasi dan preferensi minat disimpan melalui API terautentikasi. Pencarian akun berdasarkan username belum tersedia; gunakan ID pengguna target.</p></div>
      <div className="social-add-row"><label>Cari akun berdasarkan username<input value={socialQuery} onChange={(e) => setSocialQuery(e.target.value)} placeholder="@username" autoComplete="off" maxLength={40} /></label><button type="button" className="button-primary" disabled={socialDiscoveryLoading || socialQuery.trim().length < 3} onClick={() => void discoverSocialUsers()}>{socialDiscoveryLoading ? "Mencari…" : "Cari akun"}</button></div>
      {socialDiscoveryError && <p className="notice error" role="alert">{socialDiscoveryError}</p>}
      {discoveredSocialUsers.length > 0 && <section className="social-columns" aria-label="Hasil pencarian akun">{discoveredSocialUsers.map((candidate) => <div className="social-row" key={candidate.id}><span><strong>{candidate.display_name || candidate.username}</strong><small className="muted"> @{candidate.username} · {candidate.visibility === "private" ? "Akun privat" : "Akun publik"}</small></span><div className="form-actions"><button type="button" className="button-primary" disabled={saving} onClick={() => void addSocialEdge("follow", candidate.id)}>Ikuti</button><button type="button" className="button-quiet" disabled={saving} onClick={() => void addSocialEdge("block", candidate.id)}>Blokir</button><button type="button" className="button-quiet" disabled={saving} onClick={() => void addSocialEdge("mute", candidate.id)}>Bisukan</button></div></div>)}</section>}
      <div className="social-add-row"><label>ID pengguna target<input value={targetUserId} onChange={(e) => setTargetUserId(e.target.value)} placeholder="UUID akun Allpha" autoComplete="off" /></label><div className="form-actions"><button type="button" className="button-primary" disabled={saving || !targetUserId.trim()} onClick={() => void addSocialEdge("follow")}>Ikuti</button><button type="button" className="button-quiet" disabled={saving || !targetUserId.trim()} onClick={() => void addSocialEdge("block")}>Blokir</button><button type="button" className="button-quiet" disabled={saving || !targetUserId.trim()} onClick={() => void addSocialEdge("mute")}>Bisukan</button></div></div>
      {socialLoading ? <p className="muted" role="status">Memuat relasi…</p> : socialGraph ? <>
        <div className="social-columns">
          <section><h3>Permintaan masuk ({socialGraph.incoming_requests.length})</h3>{socialGraph.incoming_requests.length ? socialGraph.incoming_requests.map((edge) => <div className="social-row" key={edge.id}><code>{edge.actor_user_id}</code><span className="muted">meminta mengikuti</span><div className="form-actions"><button type="button" className="button-primary" disabled={saving} onClick={() => void resolveFollowRequest(edge.id, true)}>Terima</button><button type="button" className="button-quiet" disabled={saving} onClick={() => void resolveFollowRequest(edge.id, false)}>Tolak</button></div></div>) : <p className="muted">Belum ada permintaan masuk.</p>}</section>
          <section><h3>Relasi Anda ({socialGraph.outgoing.length})</h3>{socialGraph.outgoing.length ? socialGraph.outgoing.map((edge) => <div className="social-row" key={edge.id}><code>{edge.target_user_id}</code><span className="muted">{edge.edge_type} · {edge.status || "active"}</span><button type="button" className="button-quiet" disabled={saving} onClick={() => void removeSocialEdge(edge)}>Hapus</button></div>) : <p className="muted">Belum ada relasi.</p>}</section>
        </div>
        <section className="social-followers">
          <h3>Pengikut Anda ({socialGraph.summary?.followers ?? socialGraph.incoming_followers?.length ?? 0})</h3>
          {(socialGraph.incoming_followers || []).length ? socialGraph.incoming_followers!.map((edge) => <div className="social-row" key={edge.id}><code>{edge.actor_user_id}</code><span className="muted">mengikuti Anda</span></div>) : <p className="muted">Belum ada pengikut yang dapat ditampilkan.</p>}
        </section>
        {socialGraph.summary && <div className="social-interest-list" aria-label="Ringkasan Social Graph">
          <span className="social-interest">Mengikuti: {socialGraph.summary.following}</span>
          <span className="social-interest">Pengikut: {socialGraph.summary.followers}</span>
          <span className="social-interest">Permintaan: {socialGraph.summary.pending_follow_requests}</span>
          <span className="social-interest">Diblokir: {socialGraph.summary.blocked}</span>
          <span className="social-interest">Dibisukan: {socialGraph.summary.muted}</span>
          {socialGraph.summary.truncated && <span className="social-interest">Daftar dibatasi 500; pagination lanjutan diperlukan</span>}
        </div>}
        <section className="social-interests"><h3>Minat</h3><div className="social-add-row"><label>Tambah minat<select value={interestKey} onChange={(e) => setInterestKey(e.target.value)}><option value="">Pilih dari katalog Allpha</option>{interestCatalog.map((item) => <option key={item.interest_key} value={item.interest_key}>{item.label}</option>)}</select></label><label>Preferensi<select value={interestPreference} onChange={(e) => setInterestPreference(e.target.value as "interested" | "not_interested")}><option value="interested">Diminati</option><option value="not_interested">Tidak diminati</option></select></label><button type="button" className="button-primary" disabled={saving || !interestKey} onClick={() => void saveInterest()}>Simpan minat</button></div><div className="social-interest-list">{socialGraph.interests.map((item) => <span className="social-interest" key={item.interest_key}><span>{interestCatalog.find((catalogItem) => catalogItem.interest_key === item.interest_key)?.label || item.interest_key} · {item.preference === "interested" ? "Diminati" : "Tidak diminati"}</span><button type="button" className="button-quiet" aria-label={"Ubah preferensi " + item.interest_key} disabled={saving} onClick={() => void updateInterestPreference(item.interest_key, item.preference === "interested" ? "not_interested" : "interested")}>{item.preference === "interested" ? "Tandai tidak diminati" : "Aktifkan minat"}</button><button type="button" aria-label={"Hapus minat " + item.interest_key} disabled={saving} onClick={() => void removeInterest(item.interest_key)}>×</button></span>)}</div>{!socialGraph.interests.length && <p className="muted">Belum ada minat tersimpan.</p>}</section>
        <section className="social-interests" aria-labelledby="passion-habit-title">
          <h3 id="passion-habit-title">Passion Graph & Habit Graph</h3>
          <p className="muted">Simpan afinitas dan pola personalisasi yang Anda pilih sendiri. Allpha tidak menyimpulkan atribut sensitif dari aktivitas. Sinyal hanya dibaca oleh layanan rekomendasi sesuai izin akun.</p>
          <div className="social-add-row">
            <label>Minat kanonis<select value={signalInterestKey} onChange={(event) => setSignalInterestKey(event.target.value)}><option value="">Pilih minat</option>{interestCatalog.map(item => <option key={item.interest_key} value={item.interest_key}>{item.label}</option>)}</select></label>
            <label>Jenis sinyal<select value={signalType} onChange={(event) => setSignalType(event.target.value as "passion" | "habit")}><option value="passion">Passion</option><option value="habit">Habit</option></select></label>
            <label>Simpul Graph<select value={signalAgentId} onChange={(event) => setSignalAgentId(event.target.value)}><option value="">Human</option>{socialAgents.map(agent => <option key={agent.id} value={agent.id}>AI Agent · @{agent.handle}</option>)}</select></label>
            <label>Strength · {signalStrength.toFixed(1)}<input type="range" min="0" max="1" step="0.1" value={signalStrength} onChange={(event) => setSignalStrength(Number(event.target.value))}/></label>
            <button type="button" className="button-primary" disabled={saving || !signalInterestKey} onClick={() => void saveInterestGraphSignal()}>Simpan sinyal</button>
          </div>
          <div className="consent-history-list">
            {interestGraphSignals.map(signal => <article className="social-row" key={(signal.agent_id || "human") + ":" + signal.signal_type + ":" + signal.interest_key}>
              <div><strong>{signal.signal_type === "passion" ? "Passion" : "Habit"} · {interestCatalog.find(item => item.interest_key === signal.interest_key)?.label || signal.interest_key}</strong><p className="muted">{signal.agent_id ? "AI Agent · @" + (socialAgents.find(agent => agent.id === signal.agent_id)?.handle || signal.agent_id) : "Human"} · Strength {signal.strength.toFixed(2)} · Sumber {signal.signal_source}</p></div>
              <button type="button" className="button-quiet" disabled={saving} onClick={() => void removeInterestGraphSignal(signal)}>Hapus</button>
            </article>)}
            {!interestGraphSignals.length && <p className="muted">Belum ada sinyal Passion/Habit yang tersimpan.</p>}
          </div>
        </section>
        {socialGraph.blocked_by.length > 0 && <p className="muted">Akun yang memblokir Anda: {socialGraph.blocked_by.map((edge) => edge.actor_user_id).join(", ")}</p>}
      </> : <div><p className="muted">Data Social Graph belum dimuat atau terjadi gangguan koneksi.</p><button type="button" className="button-quiet" onClick={() => void loadSocialGraph()}>Coba lagi</button></div>}
    </section> : tab === "sessions" ? <section className="panel settings-panel social-panel" aria-labelledby="auth-sessions-title">
      <div className="panel-heading"><span className="section-kicker">KEAMANAN AKUN</span><h2 id="auth-sessions-title">Perangkat & sesi login</h2><p>Daftar sesi aktif akun Anda. Anda dapat mencabut sesi tertentu atau seluruh sesi perangkat lain; sesi saat ini tetap aktif.</p></div>
      <div className="form-actions"><button type="button" className="button-primary" disabled={saving || sessionsLoading || !authSessions?.some((item) => !item.is_current)} onClick={() => void revokeOtherAuthSessions()}>Cabut semua perangkat lain</button><button type="button" className="button-quiet" disabled={sessionsLoading} onClick={() => void loadAuthSessions()}>Muat ulang</button></div>
      {sessionsError && <p className="notice error" role="alert">{sessionsError}</p>}
      {sessionsLoading ? <p className="muted" role="status">Memuat sesi aktif…</p> : authSessions === null ? <p className="muted">Daftar sesi belum dimuat.</p> : authSessions.length === 0 ? <p className="muted">Tidak ada sesi aktif yang terdaftar.</p> : <div className="consent-history-list">{authSessions.map((item) => <article className="social-row" key={item.id}><div><strong>{item.is_current ? "Perangkat ini · Sesi saat ini" : item.user_agent || "Perangkat lain"}</strong><p className="muted">{item.user_agent || "Perangkat tidak teridentifikasi"}{item.ip ? " · " + item.ip : ""}</p><p className="muted">Terakhir diperbarui: {item.updated_at ? new Date(item.updated_at).toLocaleString(profile?.locale || "id-ID") : "Tidak tersedia"} · {item.aal || "AAL tidak tersedia"}</p><small className="muted">Session ID: <code>{item.id}</code></small></div>{item.is_current ? <span className="consent-state">Aktif sekarang</span> : <button type="button" className="button-quiet" disabled={saving} onClick={() => void revokeAuthSession(item.id)}>Cabut sesi</button>}</article>)}</div>}
      <p className="muted">Metadata perangkat berasal dari registri sesi Supabase Auth. Alamat IP hanya ditampilkan kepada pemilik akun.</p>
    </section> : tab === "consents" ? <section className="panel settings-panel social-panel" aria-labelledby="consent-history-title">
      <div className="panel-heading"><span className="section-kicker">PRIVASI & TRANSPARANSI</span><h2 id="consent-history-title">Riwayat & kontrol persetujuan</h2><p>Versi kebijakan berasal dari konfigurasi server yang disetujui. Keputusan dicatat sebagai event append-only; persetujuan pembaruan produk dapat dicabut.</p></div>
      <section className="social-row" aria-label="Versi kebijakan aktif">
        <div><strong>Terms of Service</strong><p className="muted">Versi aktif: <code>{currentPolicyVersions.terms_of_service || "Belum dikonfigurasi"}</code></p></div>
        <div><strong>Privacy Policy</strong><p className="muted">Versi aktif: <code>{currentPolicyVersions.privacy_policy || "Belum dikonfigurasi"}</code></p></div>
        <div><strong>Pembaruan produk</strong><p className="muted">Versi aktif: <code>{currentPolicyVersions.product_updates || "Belum dikonfigurasi"}</code></p></div>
        {(() => {
          const latestProductUpdate = consentHistory?.find((item) => item.consent_type === "product_updates");
          const isGranted = latestProductUpdate?.decision === "granted";
          return <button type="button" className={isGranted ? "button-quiet" : "button-primary"} disabled={saving || consentLoading || !currentPolicyVersions.product_updates} onClick={() => void recordProductUpdatesConsent(!isGranted)}>{isGranted ? "Cabut persetujuan pembaruan produk" : "Izinkan pembaruan produk"}</button>;
        })()}
      </section>
      {consentLoading ? <p className="muted" role="status">Memuat riwayat persetujuan…</p> : consentError ? <div><p className="notice error" role="alert">{consentError}</p><button type="button" className="button-quiet" onClick={() => void loadConsentHistory()}>Coba lagi</button></div> : consentHistory === null ? <p className="muted">Riwayat belum dimuat.</p> : consentHistory.length === 0 ? <div className="social-row"><p className="muted">Belum ada catatan persetujuan pada akun ini.</p><button type="button" className="button-quiet" onClick={() => void loadConsentHistory()}>Muat ulang</button></div> : <div className="consent-history-list">{consentHistory.map((item) => <article className="social-row" key={item.id}><div><strong>{item.consent_type === "terms_of_service" ? "Terms of Service" : item.consent_type === "privacy_policy" ? "Privacy Policy" : "Pembaruan produk"}</strong><p className="muted">Versi tercatat: <code>{item.policy_version}</code> · {item.source}</p><p className="muted">{item.decision === "granted" ? "Diberikan" : item.decision === "revoked" ? "Dicabut" : "Tidak diberikan"} · {item.recorded_at ? new Date(item.recorded_at).toLocaleString("id-ID") : "Waktu tidak tersedia"}</p></div><span className="consent-state">{item.decision === "granted" ? "Aktif" : item.decision === "revoked" ? "Dicabut" : "Ditolak"}</span></article>)}</div>}
      <p className="muted">Tidak ada versi kebijakan atau catatan persetujuan contoh yang dibuat oleh aplikasi.</p>
    </section> : tab === "data" ? <AccountDataLifecyclePanel apiBase={apiBase} accessToken={session.access_token} /> : tab === "profile" ?
      <div className="content-grid"><form className="panel profile-form" onSubmit={saveProfile}>
        <div className="panel-heading"><span className="section-kicker">PROFIL PUBLIK</span><h2>Informasi manusia</h2><p>Perubahan dikirim ke API dan disimpan di database akun Anda.</p></div>
        <div className="avatar-row">{profile.avatar_url ? <img className="avatar-large" src={profile.avatar_url} alt="Avatar profil" /> : <div className="avatar-large avatar-placeholder">{(profile.display_name || "A").slice(0, 1).toUpperCase()}</div>}<div><strong>{profile.display_name || "Nama belum diatur"}</strong><p className="muted">Avatar menggunakan URL gambar yang Anda kelola.</p></div></div>
        <label>Nama tampilan<input value={profile.display_name} maxLength={80} onChange={(e) => setProfile({ ...profile, display_name: e.target.value })} required /></label>
        <label>Username<input value={profile.username ?? ""} minLength={3} maxLength={30} pattern="[a-z0-9_]{3,30}" onChange={(e) => setProfile({ ...profile, username: e.target.value.toLowerCase() || null })} placeholder="nama_pengguna" /><small>3–30 karakter; huruf kecil, angka, dan garis bawah.</small></label>
        <label>URL avatar<input type="url" value={profile.avatar_url ?? ""} maxLength={2048} onChange={(e) => setProfile({ ...profile, avatar_url: e.target.value || null })} placeholder="https://…" /></label>
        <label>Bio<textarea value={profile.bio} maxLength={500} rows={4} onChange={(e) => setProfile({ ...profile, bio: e.target.value })} placeholder="Ceritakan sedikit tentang diri Anda." /></label>
        <div className="field-row"><label>Bahasa<select value={profile.locale} onChange={(e) => setProfile({ ...profile, locale: e.target.value as Profile["locale"] })}><option value="id-ID">Bahasa Indonesia</option><option value="en-US">English (US)</option></select></label><label>Visibilitas profil<select value={profile.visibility} onChange={(e) => setProfile({ ...profile, visibility: e.target.value as Profile["visibility"] })}><option value="public">Publik</option><option value="private">Privat</option></select></label></div>
        <div className="form-actions"><span className="muted">Status akun: {profile.account_status === "active" ? "Aktif" : "Permintaan penonaktifan tercatat"}</span><button className="button-primary" disabled={saving || profile.account_status !== "active"}>{saving ? "Menyimpan…" : "Simpan profil"}</button></div>
      </form><aside className="side-column">
        <section className="panel side-panel"><span className="section-kicker">IDENTITAS AKUN</span><h3>{session.user.email}</h3><p className="muted">{session.user.email_confirmed_at ? "Email telah dikonfirmasi." : "Email belum dikonfirmasi."}</p><div className="detail-line"><span>ID identitas</span><code>{profile.id.slice(0, 8)}…</code></div><div className="detail-line"><span>Bergabung</span><span>{new Date(profile.created_at).toLocaleDateString(profile.locale)}</span></div></section>
        <section className="panel side-panel"><span className="section-kicker">KONTROL AKUN</span><h3>Penonaktifan</h3><p className="muted">Permintaan ini tidak langsung menghapus data atau sesi Anda.</p><button className="button-danger" onClick={() => void requestDeactivation()} disabled={saving || profile.account_status !== "active"}>{profile.account_status === "active" ? "Minta penonaktifan" : "Permintaan tercatat"}</button></section>
      </aside></div> :
      <form className="settings-layout" onSubmit={saveSettings}>
        <section className="panel settings-panel"><div className="panel-heading"><span className="section-kicker">PREFERENSI</span><h2>Pengalaman Anda</h2><p>Preferensi disimpan per akun dan dimuat kembali dari database.</p></div>
          <label>Tema antarmuka<select value={settings.theme} onChange={(e) => setSettings({ ...settings, theme: e.target.value as Settings["theme"] })}><option value="system">Ikuti sistem</option><option value="light">Terang</option><option value="dark">Gelap</option></select></label>
          <label>Bahasa profil<select value={profile.locale} onChange={(e) => setProfile({ ...profile, locale: e.target.value as Profile["locale"] })}><option value="id-ID">Bahasa Indonesia</option><option value="en-US">English (US)</option></select></label>
        </section>
        <section className="panel settings-panel"><div className="panel-heading"><span className="section-kicker">NOTIFIKASI</span><h2>Atur pemberitahuan</h2><p>Preferensi tersimpan; pengiriman notifikasi akan diaktifkan oleh layanan notifikasi.</p></div>
          <PreferenceToggle title="Pembaruan produk" description="Informasi fitur dan pembaruan Allpha." checked={settings.notification_preferences.product_updates} onChange={(checked) => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, product_updates: checked } })} />
          <PreferenceToggle title="Peringatan keamanan" description="Pemberitahuan terkait keamanan akun." checked={settings.notification_preferences.security_alerts} onChange={(checked) => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, security_alerts: checked } })} />
          <PreferenceToggle title="Aktivitas sosial" description="Pemberitahuan interaksi sosial saat fitur tersedia." checked={settings.notification_preferences.social_activity} onChange={(checked) => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, social_activity: checked } })} />
        </section>
        <section className="panel settings-panel"><div className="panel-heading"><span className="section-kicker">PRIVASI</span><h2>Kontrol penemuan profil</h2><p>Visibilitas profil publik dikendalikan pada data profil Anda.</p></div>
          <PreferenceToggle title="Dapat ditemukan melalui username" description="Izinkan profil publik Anda muncul dalam pencarian akun." checked={settings.privacy_settings.discoverable_by_username} onChange={(checked) => setSettings({ ...settings, privacy_settings: { ...settings.privacy_settings, discoverable_by_username: checked, allow_interest_matching: checked ? settings.privacy_settings.allow_interest_matching : false } })} />
          <PreferenceToggle title="Gunakan minat untuk rekomendasi" description="Opt-in agar minat yang Anda pilih dapat dicocokkan secara privat untuk rekomendasi akun. Minat tidak ditampilkan ke pengguna lain." checked={settings.privacy_settings.allow_interest_matching} disabled={!settings.privacy_settings.discoverable_by_username || profile.visibility !== "public"} onChange={(checked) => setSettings({ ...settings, privacy_settings: { ...settings.privacy_settings, allow_interest_matching: checked } })} />
          <div className="detail-line"><span>Visibilitas profil</span><strong>{profile.visibility === "public" ? "Publik" : "Privat"}</strong></div><button className="button-primary" disabled={saving}>{saving ? "Menyimpan…" : "Simpan pengaturan"}</button>
        </section><div className="settings-footer"><span className="muted">Preferensi disimpan melalui API terautentikasi.</span><button type="button" className="button-quiet" onClick={() => setTab("profile")}>Kembali ke profil</button></div>
      </form>}
    <footer className="identity-footer"><span>ALLPHA · HUMAN IDENTITY</span><span>Data akun nyata · Supabase Auth + PostgreSQL</span></footer>
  </main>;
}

function settingsPayload(settings: Settings) {
  return { theme: settings.theme, notification_preferences: settings.notification_preferences, privacy_settings: settings.privacy_settings };
}

function PreferenceToggle({ title, description, checked, onChange, disabled = false }: { title: string; description: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return <label className="preference-toggle"><span><strong>{title}</strong><small>{description}</small></span><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /></label>;
}
