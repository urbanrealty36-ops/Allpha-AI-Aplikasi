import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { NavigationContainer, useNavigation, type NavigationProp } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { SafeAreaProvider } from "react-native-safe-area-context";
import * as SecureStore from "expo-secure-store";
import * as DocumentPicker from "expo-document-picker";
import { StatusBar } from "expo-status-bar";
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";

type Routes = { Welcome: undefined; Auth: { mode?: "signin" | "signup" } | undefined; Profile: undefined };
type AgentIdentity = { id: string; handle: string; display_name: string; description?: string; visibility: "private" | "public"; status: "draft" | "active" | "archived"; ownership?: { owner_user_id: string; role: "owner"; status: "active" } };
type AgentPassport = Pick<AgentIdentity, "id" | "handle" | "display_name" | "description" | "visibility" | "status"> & { disclosure?: string; created_at?: string; skills?: { id: string; name: string; slug: string; version: number; description?: string }[]; capabilities?: { id: string; capability_key: string; description?: string; risk_level: string }[] };
type RegisteredTool = { key: string; version: string; name: string; description: string; risk_level: string; required_permission_scopes: string[]; executable: boolean };
type AgentSkill = { id: string; slug: string; name: string; description?: string; status: "draft" | "published" | "archived"; version: number; required_permission_scopes?: string[]; tool_dependencies?: string[] };
type AgentCapability = { id: string; capability_key: string; description?: string; status: "requested" | "approved" | "denied" | "revoked"; risk_level: string };
type RuntimeSession = { id: string; owner_user_id: string; agent_id: string; title: string; status: string; created_at: string; last_activity_at: string };
type RuntimeSkill = { id: string; slug: string; name: string; status: "draft" | "published" | "archived"; version: number; tool_dependencies?: string[] };
type ChallengeSkill = { id: string; agent_id: string; slug: string; name: string; status: string; version: number; tests?: Record<string, unknown>[]; evaluation_rubric_available?: boolean };
type ChallengeRun = { id: string; agent_id: string; skill_id: string; agent_version: number; skill_version: number; challenge_key: string; status: string; challenge_input: Record<string, unknown>; evaluation_result?: Record<string, unknown> | null; evidence_digest?: string | null; created_at: string };
type RuntimeTask = { id: string; session_id: string; skill_id: string; tool_key: string; state: string; input_payload?: Record<string, unknown>; output_payload?: Record<string, unknown> | null; error_code?: string | null; created_at: string; updated_at: string; trace_id: string };
type KnowledgeSource = { id: string; filename: string; size_bytes: number; sha256: string; status: string; processing_stage: string; error_code?: string | null; created_at: string; latest_job?: { id: string; status: string; stage: string; attempt: number; progress: number; error_code?: string | null } | null };
type KnowledgeRetrievalResult = { source_id: string; source_version: number; chunk_id: string; content: string; content_sha256: string; source_location: Record<string, unknown>; sensitivity: string; retrieval_method: "vector" | "keyword" | "hybrid"; score: number; provider_id?: string | null; model_id?: string | null; model_version?: string | null; index_generation?: string | null };
type Profile = { id: string; username: string | null; display_name: string; avatar_url: string | null; bio: string; locale: "id-ID" | "en-US"; visibility: "public" | "private"; account_status?: "active" | "deactivation_requested"; created_at?: string };
type Settings = { theme: "light" | "dark" | "system"; notification_preferences: { product_updates: boolean; security_alerts: boolean; social_activity: boolean }; privacy_settings: { discoverable_by_username: boolean }; updated_at?: string };
type SocialEdge = { id: string; target_user_id?: string; actor_user_id?: string; edge_type: "follow" | "block" | "mute"; status?: string };
type SocialInterest = { interest_key: string; preference: "interested" | "not_interested" };
type SocialGraph = { outgoing: SocialEdge[]; incoming_requests: SocialEdge[]; blocked_by: SocialEdge[]; interests: SocialInterest[] };
type ConsentRecord = { consent_type: "terms_of_service" | "privacy_policy" | string; policy_version: string; granted: boolean; recorded_at: string };
const apiBase = (process.env.EXPO_PUBLIC_API_BASE_URL || (__DEV__ ? (Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000") : "https://api.allpha.web.id")).replace(/\/$/, "");
const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || "";
const supabaseKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const configured = Boolean(supabaseUrl && supabaseKey);

// Chunking keeps larger auth sessions within platform secure-storage item limits.
const secureStorage = {
  async getItem(key: string) {
    const n = Number(await SecureStore.getItemAsync(key + ":count") || 0);
    if (n > 0 && n <= 30) {
      const parts = await Promise.all(Array.from({ length: n }, (_, i) => SecureStore.getItemAsync(key + ":" + i)));
      return parts.every((part) => part !== null) ? parts.join("") : null;
    }
    return SecureStore.getItemAsync(key);
  },
  async setItem(key: string, value: string) {
    const chunks = value.match(/[\s\S]{1,1800}/g) || [""];
    if (chunks.length > 30) throw new Error("Sesi terlalu besar untuk penyimpanan aman perangkat.");
    const oldCount = Number(await SecureStore.getItemAsync(key + ":count") || 0);
    await SecureStore.deleteItemAsync(key).catch(() => undefined);
    for (let i = 0; i < Math.max(oldCount, chunks.length); i++) {
      if (i < chunks.length) await SecureStore.setItemAsync(key + ":" + i, chunks[i]);
      else await SecureStore.deleteItemAsync(key + ":" + i).catch(() => undefined);
    }
    await SecureStore.setItemAsync(key + ":count", String(chunks.length));
  },
  async removeItem(key: string) {
    const n = Number(await SecureStore.getItemAsync(key + ":count") || 0);
    await Promise.all(Array.from({ length: Math.min(n, 30) }, (_, i) => SecureStore.deleteItemAsync(key + ":" + i).catch(() => undefined)));
    await SecureStore.deleteItemAsync(key + ":count").catch(() => undefined);
    await SecureStore.deleteItemAsync(key).catch(() => undefined);
  }
};
const supabase: SupabaseClient | null = configured ? createClient(supabaseUrl, supabaseKey, {
  auth: { storage: secureStorage, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, flowType: "pkce" }
}) : null;
const Stack = createNativeStackNavigator<Routes>();

function Button({ title, onPress, secondary = false, disabled = false }: { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={({ pressed }) => [s.button, secondary && s.secondary, disabled && s.disabled, pressed && s.pressed]}><Text style={[s.buttonText, secondary && s.secondaryText]}>{title}</Text></Pressable>;
}
function Brand() { return <View style={s.brand}><View style={s.mark}><Text style={s.markText}>A</Text></View><Text style={s.eyebrow}>AI SOCIAL UNIVERSE</Text><Text style={s.brandTitle}>Allpha</Text><Text style={s.muted}>Satu universe untuk manusia dan AI Agent.</Text></View>; }

function Welcome() {
  const nav = useNavigation<NavigationProp<Routes>>();
  const [health, setHealth] = useState("Memeriksa API…");
  useEffect(() => { let active = true; fetch(apiBase + "/healthz").then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(b => { if (active) setHealth(b.status === "ok" ? "API terhubung" : "API memberi status tidak dikenal"); }).catch(() => { if (active) setHealth("API tidak terjangkau"); }); return () => { active = false; }; }, []);
  return <ScrollView contentContainerStyle={s.page}><Brand/><View style={s.card}><Text style={s.kicker}>YOUR WORLD. YOUR AGENT.</Text><Text style={s.hero}>Temukan dunia yang terhubung.</Text><Text style={s.body}>Mulai dengan identitas manusia, lalu hubungkan perjalanan Anda ke AI Agent dan universe sosial Allpha.</Text><Text style={s.status}>●  {health}</Text>{!configured && <Text style={s.warning}>Autentikasi belum dikonfigurasi. Atur EXPO_PUBLIC_SUPABASE_URL dan EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY.</Text>}<Button title="Masuk" onPress={() => nav.navigate("Auth", { mode: "signin" })} disabled={!configured}/><Button title="Buat akun" secondary onPress={() => nav.navigate("Auth", { mode: "signup" })} disabled={!configured}/></View><Text style={s.footnote}>Native Android & iOS · sesi tersimpan di secure storage</Text></ScrollView>;
}

function Auth({ route }: { route: { params?: { mode?: "signin" | "signup" } } }) {
  const nav = useNavigation<NavigationProp<Routes>>();
  const [mode, setMode] = useState<"signin" | "signup">(route.params?.mode || "signin");
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(""); const [error, setError] = useState("");
  async function submit() {
    if (!supabase) return; setBusy(true); setError(""); setMessage("");
    try {
      if (mode === "signup") {
        if (!name.trim()) throw new Error("Nama tampilan wajib diisi.");
        const { data, error: e } = await supabase.auth.signUp({ email: email.trim(), password, options: { data: { display_name: name.trim(), locale: "id-ID" } } });
        if (e) throw e; setMessage(data.session ? "Akun berhasil dibuat." : "Akun dibuat. Periksa email untuk konfirmasi sebelum masuk.");
      } else { const { error: e } = await supabase.auth.signInWithPassword({ email: email.trim(), password }); if (e) throw e; }
    } catch (e) { setError(e instanceof Error ? e.message : "Autentikasi gagal. Coba lagi."); }
    finally { setBusy(false); }
  }
  return <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}><ScrollView contentContainerStyle={s.page}><Brand/><View style={s.card}><Text style={s.title}>{mode === "signin" ? "Selamat datang kembali" : "Buat identitas Anda"}</Text>{mode === "signup" && <TextInput accessibilityLabel="Nama tampilan" placeholder="Nama tampilan" placeholderTextColor="#8B94AC" value={name} onChangeText={setName} style={s.input}/>}<TextInput accessibilityLabel="Email" autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="Email" placeholderTextColor="#8B94AC" value={email} onChangeText={setEmail} style={s.input}/><TextInput accessibilityLabel="Kata sandi" secureTextEntry autoCapitalize="none" placeholder="Kata sandi (min. 8 karakter)" placeholderTextColor="#8B94AC" value={password} onChangeText={setPassword} style={s.input}/>{!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}{!!message && <Text accessibilityRole="alert" style={s.success}>{message}</Text>}{busy && <ActivityIndicator color="#A5B4FC"/>}<Button title={busy ? "Memproses…" : mode === "signin" ? "Masuk dengan aman" : "Daftar"} disabled={busy || !email.trim() || password.length < 8 || (mode === "signup" && !name.trim())} onPress={() => void submit()}/><Button title={mode === "signin" ? "Belum punya akun? Daftar" : "Sudah punya akun? Masuk"} secondary onPress={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setMessage(""); }}/><Button title="Kembali" secondary onPress={() => nav.goBack()}/></View></ScrollView></KeyboardAvoidingView>;
}

function Profile({ session }: { session: Session }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [tab, setTab] = useState<"profile" | "settings" | "social" | "consents" | "agents" | "challenges">("profile");
  const [agents, setAgents] = useState<AgentIdentity[]>([]);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentHandle, setAgentHandle] = useState("");
  const [agentName, setAgentName] = useState("");
  const [agentDescription, setAgentDescription] = useState("");
  const [studioAgentId, setStudioAgentId] = useState<string | null>(null);
  const [studioSkills, setStudioSkills] = useState<AgentSkill[]>([]);
  const [registeredTools, setRegisteredTools] = useState<RegisteredTool[]>([]);
  const [studioToolDependencies, setStudioToolDependencies] = useState<string[]>([]);
  const [studioCapabilities, setStudioCapabilities] = useState<AgentCapability[]>([]);
  const [knowledgeSources, setKnowledgeSources] = useState<KnowledgeSource[]>([]);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [retrievalResults, setRetrievalResults] = useState<KnowledgeRetrievalResult[]>([]);
  const [retrievalTraceId, setRetrievalTraceId] = useState("");
  const [retrievalLoading, setRetrievalLoading] = useState(false);
  const [retrievalError, setRetrievalError] = useState("");
  const retrievalRequestSequence = useRef(0);
  const [studioSlug, setStudioSlug] = useState("");
  const [studioSkillName, setStudioSkillName] = useState("");
  const [studioInstructions, setStudioInstructions] = useState("");
  const [studioScope, setStudioScope] = useState("");
  const [studioCapabilityKey, setStudioCapabilityKey] = useState("");
  const [studioCapabilityDescription, setStudioCapabilityDescription] = useState("");
  const [agentPassport, setAgentPassport] = useState<AgentPassport | null>(null);
  const [runtimeSessions, setRuntimeSessions] = useState<Record<string, RuntimeSession[]>>({});
  const [runtimeSessionBusy, setRuntimeSessionBusy] = useState<string | null>(null);
  const [runtimeSkills, setRuntimeSkills] = useState<Record<string, RuntimeSkill[]>>({});
  const [runtimeTools, setRuntimeTools] = useState<Record<string, RegisteredTool[]>>({});
  const [runtimeTasks, setRuntimeTasks] = useState<Record<string, RuntimeTask[]>>({});
  const [runtimeSkillBySession, setRuntimeSkillBySession] = useState<Record<string, string>>({});
  const [runtimeToolBySession, setRuntimeToolBySession] = useState<Record<string, string>>({});
  const [runtimeInputsBySession, setRuntimeInputsBySession] = useState<Record<string, string>>({});
  const [runtimeTaskBusy, setRuntimeTaskBusy] = useState<string | null>(null);
  const [challengeAgentId, setChallengeAgentId] = useState("");
  const [challengeSkills, setChallengeSkills] = useState<ChallengeSkill[]>([]);
  const [challengeSkillId, setChallengeSkillId] = useState("");
  const [challengeTestKey, setChallengeTestKey] = useState("");
  const [challengeSubmission, setChallengeSubmission] = useState("{}");
  const [challengeNonce, setChallengeNonce] = useState("");
  const [challengeRun, setChallengeRun] = useState<ChallengeRun | null>(null);
  const [challengeRuns, setChallengeRuns] = useState<ChallengeRun[]>([]);
  const [challengeBusy, setChallengeBusy] = useState(false);
  const [consentHistory, setConsentHistory] = useState<ConsentRecord[] | null>(null);
  const [consentLoading, setConsentLoading] = useState(false);
  const [consentError, setConsentError] = useState("");
  const [socialGraph, setSocialGraph] = useState<SocialGraph | null>(null);
  const [socialLoading, setSocialLoading] = useState(false);
  const [targetUserId, setTargetUserId] = useState("");
  const [interestKey, setInterestKey] = useState("");
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [retry, setRetry] = useState(0);
  async function apiRequest(path: string, init: RequestInit = {}) {
    const response = await fetch(apiBase + path, {
      ...init,
      headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Permintaan gagal (" + response.status + ").");
    return body;
  }
  async function loadRuntimeCatalog(agentId: string) {
    const [skillsBody, toolsBody] = await Promise.all([
      apiRequest("/v1/agents/" + encodeURIComponent(agentId) + "/skills"),
      apiRequest("/v1/tools"),
    ]) as [{ items?: RuntimeSkill[] }, { items?: RegisteredTool[] }];
    setRuntimeSkills(current => ({ ...current, [agentId]: skillsBody.items ?? [] }));
    setRuntimeTools(current => ({ ...current, [agentId]: (toolsBody.items ?? []).filter(tool => tool.executable) }));
  }
  async function loadRuntimeSessionTasks(sessionId: string) {
    const body = await apiRequest("/v1/agent-runtime/sessions/" + encodeURIComponent(sessionId)) as { tasks?: RuntimeTask[] };
    setRuntimeTasks(current => ({ ...current, [sessionId]: body.tasks ?? [] }));
  }
  async function loadRuntimeSessions(agentId: string) {
    setRuntimeSessionBusy(agentId); setError("");
    try {
      const body = await apiRequest("/v1/agent-runtime/sessions?limit=100") as { items?: RuntimeSession[] };
      const items = (body.items ?? []).filter(item => item.agent_id === agentId);
      setRuntimeSessions(current => ({ ...current, [agentId]: items }));
      await loadRuntimeCatalog(agentId);
      await Promise.all(items.map(item => loadRuntimeSessionTasks(item.id)));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sesi runtime tidak dapat dimuat."); }
    finally { setRuntimeSessionBusy(null); }
  }
  async function createRuntimeSession(agent: AgentIdentity) {
    setRuntimeSessionBusy(agent.id); setError(""); setMessage("");
    try {
      const body = await apiRequest("/v1/agent-runtime/sessions", {
        method: "POST", body: JSON.stringify({ agent_id: agent.id, title: "Percakapan " + agent.display_name }),
      }) as { session: RuntimeSession };
      setRuntimeSessions(current => ({ ...current, [agent.id]: [body.session, ...(current[agent.id] ?? []).filter(item => item.id !== body.session.id)] }));
      setRuntimeTasks(current => ({ ...current, [body.session.id]: [] }));
      await loadRuntimeCatalog(agent.id);
      setMessage("Sesi runtime tersimpan melalui FastAPI. Pilih Skill terpublikasi untuk membuat task.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sesi runtime tidak dapat dibuat."); }
    finally { setRuntimeSessionBusy(null); }
  }
  async function createRuntimeTask(item: RuntimeSession) {
    const skillId = runtimeSkillBySession[item.id], toolKey = runtimeToolBySession[item.id];
    if (!skillId || !toolKey) { setError("Pilih Skill terpublikasi dan tool yang dideklarasikan."); return; }
    setRuntimeTaskBusy(item.id); setError(""); setMessage("");
    try {
      let inputs: Record<string, unknown>;
      try {
        const parsed: unknown = JSON.parse(runtimeInputsBySession[item.id] || "{}");
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Input task harus berupa objek JSON.");
        inputs = parsed as Record<string, unknown>;
      } catch (cause) { throw new Error(cause instanceof Error ? cause.message : "Input JSON tidak valid."); }
      const idempotencyKey = "native-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
      const body = await apiRequest("/v1/agent-runtime/tasks", {
        method: "POST", body: JSON.stringify({ session_id: item.id, skill_id: skillId, tool_key: toolKey, inputs, idempotency_key: idempotencyKey }),
      }) as { task: RuntimeTask; idempotent_replay?: boolean };
      setRuntimeTasks(current => ({ ...current, [item.id]: [body.task, ...(current[item.id] ?? []).filter(task => task.id !== body.task.id)] }));
      setRuntimeInputsBySession(current => ({ ...current, [item.id]: "{}" }));
      setMessage(body.idempotent_replay ? "Task sudah pernah diterima; status dipulihkan." : "Task tersimpan melalui API. Eksekusi tetap membutuhkan policy runtime yang disetujui.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Task tidak dapat dibuat."); }
    finally { setRuntimeTaskBusy(null); }
  }
  async function runtimeTaskAction(item: RuntimeSession, task: RuntimeTask, action: "execute" | "cancel" | "recover") {
    setRuntimeTaskBusy(task.id); setError(""); setMessage("");
    try {
      const body = await apiRequest("/v1/agent-runtime/tasks/" + encodeURIComponent(task.id) + "/" + action, { method: "POST", body: "{}" }) as { task: RuntimeTask };
      setRuntimeTasks(current => ({ ...current, [item.id]: (current[item.id] ?? []).map(value => value.id === task.id ? body.task : value) }));
      setMessage(action === "execute" ? "Permintaan eksekusi diproses oleh API." : action === "cancel" ? "Permintaan pembatalan diproses oleh API." : "Status dipulihkan tanpa replay otomatis.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Operasi task gagal."); }
    finally { setRuntimeTaskBusy(null); }
  }
  async function loadChallengeCatalog(agentId: string) {
    setChallengeAgentId(agentId); setChallengeSkillId(""); setChallengeTestKey(""); setChallengeRun(null); setChallengeNonce("");
    try {
      const body = await apiRequest("/v1/skill-challenges/catalog?agent_id=" + encodeURIComponent(agentId)) as { items?: ChallengeSkill[] };
      setChallengeSkills(body.items ?? []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Skill challenge tidak dapat dimuat."); }
  }
  async function loadChallengeRuns() {
    const body = await apiRequest("/v1/skill-challenges/runs?limit=50") as { items?: ChallengeRun[] };
    setChallengeRuns(body.items ?? []);
  }
  async function issueNativeChallenge() {
    if (!challengeAgentId || !challengeSkillId || !challengeTestKey) { setError("Pilih Agent, Skill, dan test case."); return; }
    setChallengeBusy(true); setError(""); setMessage(""); setChallengeNonce(""); setChallengeRun(null);
    try {
      const body = await apiRequest("/v1/skill-challenges/runs", { method: "POST", body: JSON.stringify({
        agent_id: challengeAgentId, skill_id: challengeSkillId, test_key: challengeTestKey,
        idempotency_key: "native-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12)
      }) }) as { run: ChallengeRun; nonce?: string };
      setChallengeRun(body.run); setChallengeNonce(body.nonce ?? ""); setChallengeSubmission(JSON.stringify(body.run.challenge_input ?? {}, null, 2));
      setMessage(body.nonce ? "Challenge diterbitkan. Isi output JSON lalu kirim sebelum nonce kedaluwarsa." : "Run lama ditemukan tanpa nonce. Terbitkan run baru untuk menghindari replay.");
      await loadChallengeRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Challenge tidak dapat diterbitkan."); }
    finally { setChallengeBusy(false); }
  }
  async function submitNativeChallenge() {
    if (!challengeRun || !challengeNonce) return;
    setChallengeBusy(true); setError(""); setMessage("");
    try {
      const parsed: unknown = JSON.parse(challengeSubmission);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Jawaban harus berupa object JSON.");
      const body = await apiRequest("/v1/skill-challenges/runs/" + encodeURIComponent(challengeRun.id) + "/submit", {
        method: "POST", body: JSON.stringify({ nonce: challengeNonce, submission: parsed })
      }) as { run: ChallengeRun; achievement?: { key: string; status: string } | null; reward?: { status: string; reason: string } };
      setChallengeRun(body.run); setChallengeNonce("");
      setMessage(body.run.status === "passed" ? "Lulus. Bukti achievement tersimpan; reward tidak diterbitkan tanpa kebijakan yang disetujui." : "Evaluasi tersimpan. Periksa status dan bukti hasil.");
      await loadChallengeRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Evaluasi challenge gagal."); }
    finally { setChallengeBusy(false); }
  }
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    Promise.all([apiRequest("/v1/me"), apiRequest("/v1/me/settings")])
      .then(([identity, preferences]) => {
        if (active) { setProfile(identity.profile || null); setSettings(preferences.settings || null); }
      }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Koneksi gagal."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session.access_token, retry]);
  async function loadConsentHistory() {
    setConsentLoading(true); setConsentError("");
    try {
      const payload = await apiRequest("/v1/me/consents") as { items?: ConsentRecord[] };
      setConsentHistory(Array.isArray(payload.items) ? payload.items : []);
    } catch (cause) {
      setConsentError(cause instanceof Error ? cause.message : "Riwayat persetujuan tidak dapat dimuat.");
    } finally { setConsentLoading(false); }
  }
  async function loadSocialGraph() {
    setSocialLoading(true); setError(""); setMessage("");
    try { setSocialGraph(await apiRequest("/v1/me/social-graph") as SocialGraph); }
    catch (e) { setError(e instanceof Error ? e.message : "Social Graph tidak dapat dimuat."); }
    finally { setSocialLoading(false); }
  }
  async function addSocialEdge(edgeType: "follow" | "block" | "mute") {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/v1/me/social-edges", { method: "POST", body: JSON.stringify({ target_user_id: targetUserId.trim(), edge_type: edgeType }) });
      setTargetUserId(""); setMessage(edgeType === "follow" ? "Permintaan mengikuti dikirim." : edgeType === "block" ? "Akun diblokir." : "Akun dibisukan.");
      await loadSocialGraph();
    } catch (e) { setError(e instanceof Error ? e.message : "Relasi sosial gagal disimpan."); }
    finally { setBusy(false); }
  }
  async function removeSocialEdge(edge: SocialEdge) {
    const target = edge.target_user_id || edge.actor_user_id;
    if (!target) return;
    setBusy(true); setError(""); setMessage("");
    try { await apiRequest("/v1/me/social-edges/" + encodeURIComponent(target) + "/" + edge.edge_type, { method: "DELETE" }); setMessage("Relasi dihapus."); await loadSocialGraph(); }
    catch (e) { setError(e instanceof Error ? e.message : "Relasi tidak dapat dihapus."); }
    finally { setBusy(false); }
  }
  async function resolveFollowRequest(edgeId: string, accept: boolean) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest(accept ? "/v1/me/follow-requests/" + encodeURIComponent(edgeId) + "/accept" : "/v1/me/follow-requests/" + encodeURIComponent(edgeId), { method: accept ? "POST" : "DELETE" });
      setMessage(accept ? "Permintaan diterima." : "Permintaan ditolak."); await loadSocialGraph();
    } catch (e) { setError(e instanceof Error ? e.message : "Permintaan gagal diproses."); }
    finally { setBusy(false); }
  }
  async function saveInterest() {
    const key = interestKey.trim().toLowerCase(); if (!key) return;
    setBusy(true); setError(""); setMessage("");
    try { await apiRequest("/v1/me/interests", { method: "PUT", body: JSON.stringify({ interest_key: key, preference: "interested" }) }); setInterestKey(""); setMessage("Minat tersimpan."); await loadSocialGraph(); }
    catch (e) { setError(e instanceof Error ? e.message : "Minat tidak dapat disimpan."); }
    finally { setBusy(false); }
  }
  async function removeInterest(key: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiRequest("/v1/me/interests/" + encodeURIComponent(key), { method: "DELETE" }); setMessage("Minat dihapus."); await loadSocialGraph(); }
    catch (e) { setError(e instanceof Error ? e.message : "Minat tidak dapat dihapus."); }
    finally { setBusy(false); }
  }
  async function saveProfile() {
    if (!profile) return; setBusy(true); setError(""); setMessage("");
    try {
      const data = await apiRequest("/v1/me/profile", { method: "PATCH", body: JSON.stringify({
        username: profile.username || null, display_name: profile.display_name, avatar_url: profile.avatar_url || null,
        bio: profile.bio, visibility: profile.visibility, locale: profile.locale,
      }) });
      setProfile((current) => current ? { ...current, ...data.profile } : current); setMessage("Profil berhasil disimpan.");
    } catch (e) { setError(e instanceof Error ? e.message : "Profil tidak dapat disimpan."); }
    finally { setBusy(false); }
  }
  async function saveSettings() {
    if (!profile || !settings) return; setBusy(true); setError(""); setMessage("");
    try {
      const [identity, prefs] = await Promise.all([
        apiRequest("/v1/me/profile", { method: "PATCH", body: JSON.stringify({ locale: profile.locale }) }),
        apiRequest("/v1/me/settings", { method: "PATCH", body: JSON.stringify({ theme: settings.theme, notification_preferences: settings.notification_preferences, privacy_settings: settings.privacy_settings }) }),
      ]);
      setProfile((current) => current ? { ...current, ...identity.profile } : current);
      setSettings(prefs.settings); setMessage("Pengaturan privasi dan preferensi berhasil disimpan.");
    } catch (e) { setError(e instanceof Error ? e.message : "Pengaturan tidak dapat disimpan."); }
    finally { setBusy(false); }
  }
  async function requestDeactivation() {
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await apiRequest("/v1/me/deactivation-request", { method: "POST", body: "{}" });
      setProfile((current) => current ? { ...current, account_status: data.profile.account_status } : current);
      setMessage(data.message || "Permintaan penonaktifan akun tercatat.");
    } catch (e) { setError(e instanceof Error ? e.message : "Permintaan penonaktifan gagal."); }
    finally { setBusy(false); }
  }
  async function loadAgents() {
    setAgentLoading(true); setError("");
    try {
      const response = await fetch(apiBase + "/v1/agents", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || "Daftar Agent tidak dapat dimuat.");
      setAgents(Array.isArray(body.items) ? body.items : []);
    } catch (e) { setError(e instanceof Error ? e.message : "Daftar Agent tidak dapat dimuat."); }
    finally { setAgentLoading(false); }
  }
  async function createAgent() {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents", { method: "POST", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" }, body: JSON.stringify({ handle: agentHandle.trim().toLowerCase(), display_name: agentName.trim(), description: agentDescription.trim(), persona: { tone: "helpful", language: "id-ID" }, disclosure: "AI Agent; respons dapat dihasilkan oleh model.", boundaries: { requires_owner_approval_for_external_actions: true, private_owner_data: "owner_only" }, visibility: "private" }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || "Agent tidak dapat dibuat.");
      setAgentHandle(""); setAgentName(""); setAgentDescription(""); setMessage("Identitas Agent dibuat dan pemilik ditetapkan oleh server."); await loadAgents();
    } catch (e) { setError(e instanceof Error ? e.message : "Agent tidak dapat dibuat."); }
    finally { setBusy(false); }
  }
  async function updateAgent(agent: AgentIdentity, changes: Partial<Pick<AgentIdentity, "visibility" | "status">>) {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(agent.id), { method: "PATCH", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" }, body: JSON.stringify(changes) });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || "Status Agent tidak dapat diperbarui.");
      setMessage("Identitas Agent diperbarui."); await loadAgents();
    } catch (e) { setError(e instanceof Error ? e.message : "Status Agent tidak dapat diperbarui."); }
    finally { setBusy(false); }
  }
  async function loadPassport(handle: string) {
    setAgentPassport(null); setError(""); setMessage(""); setAgentLoading(true);
    try {
      const response = await fetch(apiBase + "/v1/agent-passports/" + encodeURIComponent(handle), { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || "Passport publik tidak tersedia.");
      setAgentPassport({ ...body.passport, skills: Array.isArray(body.skills) ? body.skills : [], capabilities: Array.isArray(body.capabilities) ? body.capabilities : [] });
    } catch (e) { setError(e instanceof Error ? e.message : "Passport tidak dapat dimuat."); }
    finally { setAgentLoading(false); }
  }
  async function loadAgentStudio(agentId: string) {
    retrievalRequestSequence.current += 1; setStudioAgentId(agentId); setRetrievalQuery(""); setRetrievalResults([]); setRetrievalTraceId(""); setRetrievalError(""); setRetrievalLoading(false); setAgentLoading(true); setError("");
    try {
      const headers = { Authorization: "Bearer " + session.access_token };
      const [skillsResponse, capabilitiesResponse, toolsResponse, knowledgeResponse] = await Promise.all([
        fetch(apiBase + "/v1/agents/" + encodeURIComponent(agentId) + "/skills", { headers, cache: "no-store" }),
        fetch(apiBase + "/v1/agents/" + encodeURIComponent(agentId) + "/capabilities", { headers, cache: "no-store" }),
        fetch(apiBase + "/v1/tools", { headers, cache: "no-store" }),
        fetch(apiBase + "/v1/agents/" + encodeURIComponent(agentId) + "/knowledge/sources", { headers, cache: "no-store" }),
      ]);
      const [skillsBody, capabilitiesBody, toolsBody, knowledgeBody] = await Promise.all([skillsResponse.json(), capabilitiesResponse.json(), toolsResponse.json(), knowledgeResponse.json()]);
      if (!skillsResponse.ok) throw new Error(skillsBody?.error?.message || "Skills tidak dapat dimuat.");
      if (!capabilitiesResponse.ok) throw new Error(capabilitiesBody?.error?.message || "Capabilities tidak dapat dimuat.");
      if (!toolsResponse.ok) throw new Error(toolsBody?.error?.message || "Tool Registry tidak dapat dimuat.");
      if (!knowledgeResponse.ok) throw new Error(knowledgeBody?.error?.message || "Sumber pengetahuan tidak dapat dimuat.");
      setStudioSkills(Array.isArray(skillsBody.items) ? skillsBody.items : []);
      setStudioCapabilities(Array.isArray(capabilitiesBody.items) ? capabilitiesBody.items : []);
      setRegisteredTools(Array.isArray(toolsBody.items) ? toolsBody.items.filter((tool: RegisteredTool) => tool.executable) : []);
      setKnowledgeSources(Array.isArray(knowledgeBody.items) ? knowledgeBody.items : []);
    } catch (e) { setError(e instanceof Error ? e.message : "Agent Studio tidak dapat dimuat."); }
    finally { setAgentLoading(false); }
  }
  async function loadKnowledgeSources(agentId = studioAgentId) {
    if (!agentId) return;
    setKnowledgeLoading(true);
    try {
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(agentId) + "/knowledge/sources", { headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" }, cache: "no-store" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message || "Sumber pengetahuan tidak dapat dimuat.");
      setKnowledgeSources(Array.isArray(body.items) ? body.items : []);
    } catch (e) { setError(e instanceof Error ? e.message : "Sumber pengetahuan tidak dapat dimuat."); }
    finally { setKnowledgeLoading(false); }
  }
  async function retrieveKnowledgeContext() {
    if (!studioAgentId || !retrievalQuery.trim() || retrievalLoading) return;
    const requestSequence = ++retrievalRequestSequence.current;
    setRetrievalLoading(true); setRetrievalError(""); setRetrievalResults([]); setRetrievalTraceId("");
    try {
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(studioAgentId) + "/knowledge/retrieve", {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ query: retrievalQuery.trim(), limit: 8 }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Retrieval gagal (" + response.status + ").");
      if (requestSequence !== retrievalRequestSequence.current) return;
      setRetrievalTraceId(typeof body.trace_id === "string" ? body.trace_id : "");
      setRetrievalResults(Array.isArray(body.results) ? body.results : []);
    } catch (e) {
      if (requestSequence === retrievalRequestSequence.current) setRetrievalError(e instanceof Error ? e.message : "Retrieval tidak dapat dijalankan.");
    } finally { if (requestSequence === retrievalRequestSequence.current) setRetrievalLoading(false); }
  }

  async function uploadKnowledgeDocument() {
    if (!studioAgentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const picked = await DocumentPicker.getDocumentAsync({ type: ["application/pdf", "text/markdown", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"], copyToCacheDirectory: true });
      if (picked.canceled || !picked.assets?.[0]) return;
      const asset = picked.assets[0];
      if (asset.size != null && asset.size > 15 * 1024 * 1024) throw new Error("Ukuran dokumen maksimum 15 MiB.");
      const form = new FormData();
      form.append("file", { uri: asset.uri, name: asset.name, type: asset.mimeType || "application/octet-stream" } as any);
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(studioAgentId) + "/knowledge/sources", { method: "POST", headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" }, body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Dokumen gagal diunggah.");
      setMessage("Dokumen masuk karantina privat; pemrosesan menunggu pemindai malware.");
      await loadKnowledgeSources(studioAgentId);
    } catch (e) { setError(e instanceof Error ? e.message : "Dokumen gagal diunggah."); }
    finally { setBusy(false); }
  }
  async function knowledgeSourceAction(source: KnowledgeSource, action: "process" | "retry" | "delete") {
    if (!studioAgentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(studioAgentId) + "/knowledge/sources/" + encodeURIComponent(source.id) + (action === "delete" ? "" : "/" + action), {
        method: action === "delete" ? "DELETE" : "POST",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", ...(action === "retry" ? { "Content-Type": "application/json" } : {}) },
        ...(action === "retry" ? { body: JSON.stringify({ reason: "retry dari Native Agent Studio" }) } : {}),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Operasi sumber pengetahuan gagal.");
      setMessage(action === "delete" ? "Penghapusan sumber diminta." : "Permintaan pemrosesan selesai; periksa status sumber.");
      await loadKnowledgeSources(studioAgentId);
    } catch (e) { setError(e instanceof Error ? e.message : "Operasi sumber pengetahuan gagal."); }
    finally { setBusy(false); }
  }
  function confirmKnowledgeDelete(source: KnowledgeSource) {
    Alert.alert("Hapus dokumen?", "Dokumen dan chunk turunannya akan dihapus.", [
      { text: "Batal", style: "cancel" },
      { text: "Hapus", style: "destructive", onPress: () => void knowledgeSourceAction(source, "delete") },
    ]);
  }

  async function createStudioSkill() {
    if (!studioAgentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(studioAgentId) + "/skills", {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({
          slug: studioSlug.trim().toLowerCase(), name: studioSkillName.trim(), instructions: studioInstructions.trim(),
          tool_dependencies: studioToolDependencies,
          required_permission_scopes: studioScope.split(",").map(x => x.trim()).filter(Boolean),
          constraints: { external_actions_require_owner_approval: true },
          budget_limits: { max_runtime_seconds: 30, max_tool_calls: 5 }, changelog: "Versi awal",
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || "Skill tidak dapat dibuat.");
      setStudioSlug(""); setStudioSkillName(""); setStudioInstructions(""); setStudioToolDependencies([]);
      setMessage("Skill disimpan sebagai draft; belum memberikan izin runtime."); await loadAgentStudio(studioAgentId);
    } catch (e) { setError(e instanceof Error ? e.message : "Skill tidak dapat dibuat."); }
    finally { setBusy(false); }
  }
  async function requestStudioCapability() {
    if (!studioAgentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents/" + encodeURIComponent(studioAgentId) + "/capabilities", {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ capability_key: studioCapabilityKey.trim().toLowerCase(), description: studioCapabilityDescription.trim(), required_permission_scopes: studioScope.split(",").map(x => x.trim()).filter(Boolean), risk_level: "low" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || "Capability tidak dapat diminta.");
      setStudioCapabilityKey(""); setStudioCapabilityDescription("");
      setMessage("Capability tercatat sebagai permintaan; runtime_authorized tetap false."); await loadAgentStudio(studioAgentId);
    } catch (e) { setError(e instanceof Error ? e.message : "Capability tidak dapat diminta."); }
    finally { setBusy(false); }
  }
  const field = { ...s.input, flex: 1 } as const;
  return <ScrollView contentContainerStyle={s.page}><Brand/>
    <View style={s.card}>
      <Text style={s.kicker}>HUMAN IDENTITY</Text><Text style={s.title}>Identitas Anda</Text>
      <Text style={s.muted}>{session.user.email || session.user.id}</Text>
      <View style={{ flexDirection: "row", gap: 10 }}>
        <Button title="Profil" secondary={tab !== "profile"} onPress={() => { setTab("profile"); setError(""); setMessage(""); }}/>
        <Button title="Pengaturan & privasi" secondary={tab !== "settings"} onPress={() => { setTab("settings"); setError(""); setMessage(""); }}/><Button title="Social Graph" secondary={tab !== "social"} onPress={() => { setTab("social"); setError(""); setMessage(""); void loadSocialGraph(); }}/><Button title="Riwayat persetujuan" secondary={tab !== "consents"} onPress={() => { setTab("consents"); setError(""); setMessage(""); void loadConsentHistory(); }}/><Button title="AI Agent & Passport" secondary={tab !== "agents"} onPress={() => { setTab("agents"); setError(""); setMessage(""); setAgentPassport(null); void loadAgents(); }}/><Button title="Skill Challenge" secondary={tab !== "challenges"} onPress={() => { setTab("challenges"); setError(""); setMessage(""); if (!challengeAgentId && agents[0]) void loadChallengeCatalog(agents[0].id); void loadChallengeRuns().catch(cause => setError(cause instanceof Error ? cause.message : "Riwayat challenge gagal dimuat.")); }}/>
      </View>
      {loading ? <ActivityIndicator color="#A5B4FC"/> : error ? <><Text accessibilityRole="alert" style={s.error}>{error}</Text><Button title="Coba lagi" onPress={() => setRetry(n => n + 1)}/></> :
      tab === "profile" ? profile ? <>
        <Text style={s.muted}>Perubahan disimpan melalui API Allpha dan sesi akun Anda.</Text>
        <Text style={s.muted}>Nama tampilan</Text><TextInput accessibilityLabel="Nama tampilan" value={profile.display_name} onChangeText={display_name => setProfile({ ...profile, display_name })} maxLength={80} style={field} placeholder="Nama tampilan" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>Username (huruf kecil, angka, _)</Text><TextInput accessibilityLabel="Username" autoCapitalize="none" value={profile.username || ""} onChangeText={value => setProfile({ ...profile, username: value.toLowerCase() || null })} maxLength={30} style={field} placeholder="nama_pengguna" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>URL avatar</Text><TextInput accessibilityLabel="URL avatar" autoCapitalize="none" keyboardType="url" value={profile.avatar_url || ""} onChangeText={value => setProfile({ ...profile, avatar_url: value || null })} style={field} placeholder="https://…" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>Bio</Text><TextInput accessibilityLabel="Bio" multiline value={profile.bio} onChangeText={bio => setProfile({ ...profile, bio })} maxLength={500} style={[field, { minHeight: 90, textAlignVertical: "top" }]} placeholder="Ceritakan tentang diri Anda" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>Bahasa</Text><View style={{ flexDirection: "row", gap: 8 }}><Button title="Bahasa Indonesia" secondary={profile.locale !== "id-ID"} onPress={() => setProfile({ ...profile, locale: "id-ID" })}/><Button title="English" secondary={profile.locale !== "en-US"} onPress={() => setProfile({ ...profile, locale: "en-US" })}/></View>
        <Text style={s.muted}>Visibilitas profil</Text><View style={{ flexDirection: "row", gap: 8 }}><Button title="Publik" secondary={profile.visibility !== "public"} onPress={() => setProfile({ ...profile, visibility: "public" })}/><Button title="Privat" secondary={profile.visibility !== "private"} onPress={() => setProfile({ ...profile, visibility: "private" })}/></View>
        <Button title={busy ? "Menyimpan…" : "Simpan profil"} disabled={busy || profile.account_status === "deactivation_requested"} onPress={() => void saveProfile()}/>
        <Text style={s.muted}>Status akun: {profile.account_status === "deactivation_requested" ? "Permintaan penonaktifan tercatat" : "Aktif"}</Text>
        <Button title={profile.account_status === "deactivation_requested" ? "Penonaktifan diminta" : "Minta penonaktifan akun"} secondary disabled={busy || profile.account_status === "deactivation_requested"} onPress={() => void requestDeactivation()}/>
      </> : <Text style={s.muted}>Profil belum tersedia.</Text> :
      tab === "settings" ? settings ? <>
        <Text style={s.kicker}>PREFERENSI</Text><Text style={s.body}>Tema aplikasi</Text>
        <View style={{ flexDirection: "row", gap: 8 }}><Button title="Sistem" secondary={settings.theme !== "system"} onPress={() => setSettings({ ...settings, theme: "system" })}/><Button title="Terang" secondary={settings.theme !== "light"} onPress={() => setSettings({ ...settings, theme: "light" })}/><Button title="Gelap" secondary={settings.theme !== "dark"} onPress={() => setSettings({ ...settings, theme: "dark" })}/></View>
        <Text style={s.kicker}>NOTIFIKASI</Text>
        {(["product_updates", "security_alerts", "social_activity"] as const).map((key) => <Button key={key} title={(settings.notification_preferences[key] ? "✓ " : "○ ") + ({ product_updates: "Pembaruan produk", security_alerts: "Peringatan keamanan", social_activity: "Aktivitas sosial" }[key])} secondary={!settings.notification_preferences[key]} onPress={() => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, [key]: !settings.notification_preferences[key] } })}/>)}
        <Text style={s.kicker}>PRIVASI</Text><Text style={s.body}>Temukan profil melalui username</Text>
        <View style={{ flexDirection: "row", gap: 8 }}><Button title="Dapat ditemukan" secondary={!settings.privacy_settings.discoverable_by_username} onPress={() => setSettings({ ...settings, privacy_settings: { ...settings.privacy_settings, discoverable_by_username: true } })}/><Button title="Tidak ditemukan" secondary={settings.privacy_settings.discoverable_by_username} onPress={() => setSettings({ ...settings, privacy_settings: { ...settings.privacy_settings, discoverable_by_username: false } })}/></View>
        <Button title={busy ? "Menyimpan…" : "Simpan pengaturan"} disabled={busy} onPress={() => void saveSettings()}/>
      </> : <Text style={s.muted}>Pengaturan belum tersedia.</Text> : tab === "consents" ? <>
        <Text style={s.kicker}>PRIVASI & TRANSPARANSI</Text><Text style={s.title}>Riwayat persetujuan</Text>
        <Text style={s.body}>Bagian ini hanya menampilkan catatan yang sudah tersimpan melalui API Allpha. Persetujuan baru belum dapat direkam sampai versi resmi Terms of Service dan Privacy Policy ditetapkan.</Text>
        {consentLoading ? <ActivityIndicator color="#A5B4FC"/> : consentError ? <><Text accessibilityRole="alert" style={s.error}>{consentError}</Text><Button title="Coba lagi" secondary onPress={() => void loadConsentHistory()}/></> : consentHistory === null ? <Text style={s.muted}>Riwayat belum dimuat.</Text> : consentHistory.length === 0 ? <Text style={s.muted}>Belum ada catatan persetujuan pada akun ini.</Text> : consentHistory.map((item, index) => <View key={item.consent_type + ":" + item.policy_version + ":" + item.recorded_at + ":" + index} style={s.socialRow}><Text style={s.body}>{item.consent_type === "terms_of_service" ? "Terms of Service" : item.consent_type === "privacy_policy" ? "Privacy Policy" : item.consent_type}</Text><Text style={s.muted}>Versi tercatat: {item.policy_version}</Text><Text style={s.muted}>{item.granted ? "Diberikan" : "Tidak diberikan"} · {item.recorded_at ? new Date(item.recorded_at).toLocaleString("id-ID") : "Waktu tidak tersedia"}</Text></View>)}
        <Text style={s.muted}>Tidak ada versi kebijakan atau catatan persetujuan contoh yang dibuat oleh aplikasi.</Text>
        <Button title="Muat ulang riwayat" secondary disabled={consentLoading} onPress={() => void loadConsentHistory()}/>
      </> : tab === "agents" ? <>
        <Text style={s.kicker}>AI AGENT IDENTITY</Text><Text style={s.title}>Agent Studio & Passport</Text>
        <Text style={s.muted}>Identitas Agent terpisah dari Human. Ownership ditentukan backend dari sesi terautentikasi; tidak ada owner ID dari client.</Text>
        {agentPassport ? <View style={s.socialRow}><Text style={s.title}>{agentPassport.display_name}</Text><Text style={s.body}>@{agentPassport.handle} · {agentPassport.status} · {agentPassport.visibility}</Text><Text style={s.body}>{agentPassport.description || "Tanpa deskripsi publik."}</Text><Text style={s.muted}>{agentPassport.disclosure || "AI Agent; respons dapat dihasilkan oleh model."}</Text><Text style={s.kicker}>PUBLISHED SKILLS</Text>{agentPassport.skills?.length ? agentPassport.skills.map(skill => <Text key={skill.id} style={s.body}>{skill.name} · {skill.slug} · v{skill.version}</Text>) : <Text style={s.muted}>Belum ada Skill yang dipublikasikan.</Text>}<Text style={s.kicker}>VERIFIED CAPABILITIES</Text>{agentPassport.capabilities?.length ? agentPassport.capabilities.map(cap => <Text key={cap.id} style={s.body}>{cap.capability_key} · {cap.risk_level} risk</Text>) : <Text style={s.muted}>Belum ada capability yang disetujui untuk ditampilkan.</Text>}<Button title="Kembali ke daftar" secondary onPress={() => setAgentPassport(null)}/></View> : <>
          <TextInput accessibilityLabel="Nama Agent" value={agentName} onChangeText={setAgentName} maxLength={80} style={field} placeholder="Nama Agent" placeholderTextColor="#8B94AC"/>
          <TextInput accessibilityLabel="Handle Agent" value={agentHandle} onChangeText={value => setAgentHandle(value.toLowerCase())} autoCapitalize="none" maxLength={30} style={field} placeholder="handle_agent (3–30 karakter)" placeholderTextColor="#8B94AC"/>
          <TextInput accessibilityLabel="Deskripsi Agent" value={agentDescription} onChangeText={setAgentDescription} maxLength={1000} style={field} placeholder="Deskripsi Agent" placeholderTextColor="#8B94AC"/>
          <Button title={busy ? "Membuat…" : "Buat Agent privat"} disabled={busy || agentName.trim().length < 2 || !/^[a-z0-9_]{3,30}$/.test(agentHandle.trim())} onPress={() => void createAgent()}/>
          <Button title="Muat ulang daftar" secondary disabled={agentLoading} onPress={() => void loadAgents()}/>
          {agentLoading ? <ActivityIndicator color="#A5B4FC"/> : agents.length ? agents.map(agent => <View key={agent.id} style={s.socialRow}><Text style={s.body}>{agent.display_name} · @{agent.handle}</Text><Text style={s.muted}>{agent.status} · {agent.visibility} · {agent.ownership?.role || "owner"}</Text><View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}><Button title="Lihat Passport" secondary disabled={agent.status !== "active" || agent.visibility !== "public"} onPress={() => void loadPassport(agent.handle)}/><Button title={agent.visibility === "public" ? "Jadikan privat" : "Publikasikan"} disabled={busy || agent.status === "archived"} onPress={() => void updateAgent(agent, { visibility: agent.visibility === "public" ? "private" : "public", status: "active" })}/><Button title="Arsipkan" secondary disabled={busy || agent.status === "archived"} onPress={() => void updateAgent(agent, { status: "archived", visibility: "private" })}/><Button title="Kelola Skills & Tools" secondary onPress={() => void loadAgentStudio(agent.id)}/><Button title={runtimeSessionBusy === agent.id ? "Memuat…" : "Buat sesi runtime"} disabled={runtimeSessionBusy !== null} secondary onPress={() => void createRuntimeSession(agent)}/><Button title="Muat sesi & task" disabled={runtimeSessionBusy !== null} secondary onPress={() => void loadRuntimeSessions(agent.id)}/></View>{(runtimeSessions[agent.id] ?? []).map(item => {
            const selectedSkill = (runtimeSkills[agent.id] ?? []).find(skill => skill.id === runtimeSkillBySession[item.id]);
            const allowedToolKeys = selectedSkill?.tool_dependencies ?? [];
            const tasks = runtimeTasks[item.id] ?? [];
            return <View key={item.id} style={s.socialRow}>
              <Text style={s.body}>{item.title} · {item.status}</Text><Text style={s.muted}>{new Date(item.last_activity_at).toLocaleString("id-ID")} · {item.id}</Text>
              <Text style={s.kicker}>SKILL TERPUBLIKASI</Text>
              {(runtimeSkills[agent.id] ?? []).filter(skill => skill.status === "published").map(skill => <Button key={skill.id} title={(runtimeSkillBySession[item.id] === skill.id ? "✓ " : "") + skill.name + " · v" + skill.version} secondary disabled={runtimeTaskBusy === item.id} onPress={() => { setRuntimeSkillBySession(current => ({ ...current, [item.id]: skill.id })); setRuntimeToolBySession(current => ({ ...current, [item.id]: "" })); }}/>)}
              {!(runtimeSkills[agent.id] ?? []).some(skill => skill.status === "published") && <Text style={s.muted}>Belum ada Skill terpublikasi. Draft tidak dapat dieksekusi.</Text>}
              <Text style={s.kicker}>TOOL YANG DIDEKLARASIKAN SKILL</Text>
              {(runtimeTools[agent.id] ?? []).filter(tool => allowedToolKeys.includes(tool.key)).map(tool => <Button key={tool.key} title={(runtimeToolBySession[item.id] === tool.key ? "✓ " : "") + tool.name + " · " + tool.key} secondary disabled={!selectedSkill || runtimeTaskBusy === item.id} onPress={() => setRuntimeToolBySession(current => ({ ...current, [item.id]: tool.key }))}/>)}
              <TextInput accessibilityLabel="Input task JSON" value={runtimeInputsBySession[item.id] ?? "{}"} onChangeText={value => setRuntimeInputsBySession(current => ({ ...current, [item.id]: value }))} multiline style={[field,{minHeight:72,textAlignVertical:"top"}]} placeholder="{ } input task JSON" placeholderTextColor="#8B94AC"/>
              <Button title={runtimeTaskBusy === item.id ? "Membuat task…" : "Buat task"} disabled={runtimeTaskBusy === item.id || !selectedSkill || !runtimeToolBySession[item.id]} onPress={() => void createRuntimeTask(item)}/>
              <Text style={s.kicker}>TASK LIFECYCLE</Text>
              {tasks.length === 0 ? <Text style={s.muted}>Belum ada task pada sesi ini.</Text> : tasks.map(task => <View key={task.id} style={s.card}>
                <Text style={s.body}>{task.tool_key} · {task.state}</Text><Text style={s.muted}>ID: {task.id} · {task.error_code ?? "Tanpa error"}</Text>
                {task.output_payload && <Text style={s.muted}>Output: {JSON.stringify(task.output_payload)}</Text>}
                <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
                  <Button title="Jalankan" secondary disabled={runtimeTaskBusy === task.id || task.state !== "created"} onPress={() => void runtimeTaskAction(item, task, "execute")}/>
                  <Button title="Batalkan" secondary disabled={runtimeTaskBusy === task.id || !["created","queued","waiting_for_approval","waiting_for_input"].includes(task.state)} onPress={() => void runtimeTaskAction(item, task, "cancel")}/>
                  <Button title="Pulihkan" secondary disabled={runtimeTaskBusy === task.id || ["succeeded","partially_succeeded","failed","cancelled","timed_out","budget_exhausted"].includes(task.state)} onPress={() => void runtimeTaskAction(item, task, "recover")}/>
                </View>
              </View>)}
            </View>;
          })}</View>) : <Text style={s.muted}>Belum ada Agent. Buat identitas pertama Anda.</Text>}
          {studioAgentId && <View style={s.socialRow}><Text style={s.kicker}>AGENT STUDIO · SKILLS & CAPABILITIES</Text><Text style={s.muted}>Kelola prosedur dan deklarasi capability. Deklarasi tidak memberi izin eksekusi; runtime wajib memeriksa policy pada setiap aksi.</Text><TextInput accessibilityLabel="Slug Skill" value={studioSlug} onChangeText={setStudioSlug} autoCapitalize="none" maxLength={60} style={field} placeholder="summarize_text" placeholderTextColor="#8B94AC"/><TextInput accessibilityLabel="Nama Skill" value={studioSkillName} onChangeText={setStudioSkillName} maxLength={100} style={field} placeholder="Nama Skill" placeholderTextColor="#8B94AC"/><TextInput accessibilityLabel="Instruksi Skill" value={studioInstructions} onChangeText={setStudioInstructions} multiline maxLength={12000} style={[field,{minHeight:80,textAlignVertical:"top"}]} placeholder="Instruksi dan batasan prosedural" placeholderTextColor="#8B94AC"/><Text style={s.kicker}>TOOL DEPENDENCIES · REGISTRY</Text>{registeredTools.length ? registeredTools.map(tool => <Pressable key={tool.key} accessibilityRole="checkbox" accessibilityState={{ checked: studioToolDependencies.includes(tool.key) }} onPress={() => setStudioToolDependencies(current => current.includes(tool.key) ? current.filter(key => key !== tool.key) : [...current, tool.key])} style={[s.socialRow, { flexDirection: "row", alignItems: "flex-start", gap: 10 }]}><Text style={s.body}>{studioToolDependencies.includes(tool.key) ? "☑" : "□"}</Text><View style={{ flex: 1 }}><Text style={s.body}>{tool.name} · {tool.key} · v{tool.version}</Text><Text style={s.muted}>{tool.description} · risiko {tool.risk_level}</Text></View></Pressable>) : <Text style={s.muted}>Tidak ada tool executable atau registry belum termuat.</Text>}<TextInput accessibilityLabel="Permission scopes Skill" value={studioScope} onChangeText={setStudioScope} style={field} placeholder="content:read (pisahkan koma)" placeholderTextColor="#8B94AC"/><Button title={busy ? "Menyimpan…" : "Buat Skill draft"} disabled={busy || studioSlug.trim().length < 3 || studioSkillName.trim().length < 2} onPress={() => void createStudioSkill()}/><View style={[s.card, { padding: 14, borderRadius: 18 }]}><Text style={s.kicker}>KNOWLEDGE SOURCES</Text><Text style={s.title}>Pengetahuan Agent</Text><Text style={s.muted}>PDF, Markdown, TXT, DOCX · maks. 15 MiB. Dokumen tetap privat sampai pipeline indexing dan evaluasi selesai.</Text><View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}><Button title={busy ? "Menunggu…" : "Pilih & unggah dokumen"} disabled={busy} onPress={() => void uploadKnowledgeDocument()}/><Button title="Muat ulang" secondary disabled={knowledgeLoading} onPress={() => void loadKnowledgeSources()}/></View>{knowledgeLoading ? <ActivityIndicator color="#A5B4FC"/> : knowledgeSources.length ? knowledgeSources.map(source => <View key={source.id} style={s.socialRow}><Text style={s.body}>{source.filename}</Text><Text style={s.muted}>{(source.size_bytes / 1024).toFixed(1)} KiB · {source.status}</Text><Text style={s.muted}>Tahap: {source.processing_stage}{source.error_code ? " · " + source.error_code : ""}</Text>{source.latest_job && <Text style={s.status}>Job: {source.latest_job.status} · {source.latest_job.stage} · {source.latest_job.progress}% · percobaan {source.latest_job.attempt}{source.latest_job.error_code ? " · " + source.latest_job.error_code : ""}</Text>}<Text style={s.status}>SHA-256: {source.sha256.slice(0, 16)}…</Text><View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>{(source.status === "quarantined" || source.status === "failed") && <Button title={source.status === "failed" ? "Coba lagi" : "Proses"} secondary disabled={busy} onPress={() => void knowledgeSourceAction(source, source.status === "failed" ? "retry" : "process")}/>}<Button title="Hapus" secondary disabled={busy} onPress={() => confirmKnowledgeDelete(source)}/></View></View>) : <Text style={s.muted}>Belum ada sumber pengetahuan untuk Agent ini.</Text>}</View><View style={[s.card, { padding: 14, borderRadius: 18 }]}>
        <Text style={s.kicker}>API CONTEXT RETRIEVAL</Text><Text style={s.title}>Uji konteks Agent</Text>
        <Text style={s.muted}>Mengambil potongan knowledge milik Agent ini melalui API terautentikasi. Ini preview retrieval dari sumber nyata, bukan jawaban generatif Agent. Policy sensitivitas tetap ditentukan server.</Text>
        <TextInput accessibilityLabel="Query retrieval knowledge" value={retrievalQuery} onChangeText={setRetrievalQuery} maxLength={4000} multiline style={[field, { minHeight: 84, textAlignVertical: "top" }]} placeholder="Masukkan pertanyaan untuk mencari konteks…" placeholderTextColor="#8B94AC"/>
        <Button title={retrievalLoading ? "Mengambil konteks…" : "Ambil konteks dari API"} disabled={retrievalLoading || !retrievalQuery.trim()} onPress={() => void retrieveKnowledgeContext()}/>
        {retrievalLoading && <View accessibilityRole="progressbar" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}><ActivityIndicator color="#A5B4FC"/><Text style={s.muted}>API sedang mencari knowledge yang diizinkan…</Text></View>}
        {!!retrievalError && <View accessibilityRole="alert" style={s.socialRow}><Text style={s.error}>{retrievalError}</Text><Text style={s.muted}>Jika API mengembalikan 503, retrieval belum dikonfigurasi. Tidak ada data contoh yang ditampilkan.</Text><Button title="Coba lagi" secondary disabled={retrievalLoading || !retrievalQuery.trim()} onPress={() => void retrieveKnowledgeContext()}/></View>}
        {!retrievalLoading && !retrievalError && !!retrievalTraceId && <Text style={s.muted}>Trace ID: {retrievalTraceId} · hasil dari API Allpha</Text>}
        {!retrievalLoading && !retrievalError && !!retrievalTraceId && retrievalResults.length === 0 && <Text style={s.muted}>API mengembalikan 0 hasil untuk query ini.</Text>}
        {retrievalResults.map((item, index) => <View key={item.chunk_id} style={s.socialRow}>
          <Text style={s.body}>Potongan {index + 1} · sumber {item.source_id} · v{item.source_version}</Text>
          <Text style={s.muted}>{item.retrieval_method} · skor {Number.isFinite(item.score) ? item.score.toFixed(3) : "—"} · sensitivitas {item.sensitivity}</Text>
          <Text style={s.body}>{item.content}</Text>
          <Text style={s.muted}>Chunk: {item.chunk_id}</Text><Text style={s.muted}>SHA-256: {item.content_sha256}</Text><Text style={s.muted}>Lokasi sumber: {JSON.stringify(item.source_location)}</Text>
          {(item.provider_id || item.model_id || item.model_version || item.index_generation) && <Text style={s.muted}>Indeks: {[item.provider_id, item.model_id, item.model_version, item.index_generation].filter(Boolean).join(" · ")}</Text>}
        </View>)}
      </View><Text style={s.kicker}>SKILLS ({studioSkills.length})</Text>{studioSkills.map(skill => <View key={skill.id} style={s.socialRow}><Text style={s.body}>{skill.name} · {skill.slug} · v{skill.version}</Text><Text style={s.muted}>{skill.status} · scopes: {skill.required_permission_scopes?.join(", ") || "belum ditentukan"}</Text></View>)}<TextInput accessibilityLabel="Capability key" value={studioCapabilityKey} onChangeText={setStudioCapabilityKey} autoCapitalize="none" style={field} placeholder="calendar.read" placeholderTextColor="#8B94AC"/><TextInput accessibilityLabel="Deskripsi capability" value={studioCapabilityDescription} onChangeText={setStudioCapabilityDescription} style={field} placeholder="Tujuan capability" placeholderTextColor="#8B94AC"/><Button title={busy ? "Menyimpan…" : "Ajukan capability"} secondary disabled={busy || studioCapabilityKey.trim().length < 3} onPress={() => void requestStudioCapability()}/><Text style={s.kicker}>CAPABILITIES ({studioCapabilities.length})</Text>{studioCapabilities.map(cap => <View key={cap.id} style={s.socialRow}><Text style={s.body}>{cap.capability_key} · {cap.status}</Text><Text style={s.muted}>Risiko: {cap.risk_level} · bukan izin runtime</Text></View>)}<Button title="Tutup Agent Studio" secondary onPress={() => { retrievalRequestSequence.current += 1; setStudioAgentId(null); setRetrievalQuery(""); setRetrievalResults([]); setRetrievalTraceId(""); setRetrievalError(""); }}/></View>}
        </>}
      </> : tab === "challenges" ? <>
        <Text style={s.kicker}>ENG-P12 · SKILL CHALLENGE</Text><Text style={s.title}>Evaluasi versi Skill</Text>
        <Text style={s.muted}>Challenge memakai snapshot Agent/Skill dan rubrik yang dipatok server. Jawaban dinilai oleh evaluator deterministik; tidak ada skor atau reward yang dapat ditentukan oleh klien. Pada slice ini pengguna mengirim output kandidat; eksekusi Skill/Agent otomatis belum diaktifkan.</Text>
        <Text style={s.muted}>Agent</Text>
        {agents.map(agent => <Button key={agent.id} title={(challengeAgentId === agent.id ? "✓ " : "") + agent.display_name + " · " + agent.handle} secondary={challengeAgentId !== agent.id} onPress={() => void loadChallengeCatalog(agent.id)}/>)}
        <Text style={s.muted}>Skill</Text>
        {challengeSkills.map(skill => <Button key={skill.id} title={(challengeSkillId === skill.id ? "✓ " : "") + skill.name + " · v" + skill.version + " · " + skill.status} secondary={challengeSkillId !== skill.id} onPress={() => { setChallengeSkillId(skill.id); setChallengeTestKey(""); setChallengeRun(null); setChallengeNonce(""); }}/>)}
        <Text style={s.muted}>Test case</Text>
        {(challengeSkills.find(skill => skill.id === challengeSkillId)?.tests ?? []).filter(item => typeof item.key === "string").map(item => <Button key={String(item.key)} title={(challengeTestKey === item.key ? "✓ " : "") + String(item.key)} secondary={challengeTestKey !== item.key} onPress={() => setChallengeTestKey(String(item.key))}/>)}
        {challengeSkillId && !(challengeSkills.find(skill => skill.id === challengeSkillId)?.evaluation_rubric_available) && <Text style={s.warning}>Rubrik evaluasi belum tersedia pada Skill ini.</Text>}
        <Button title={challengeBusy ? "Memproses…" : "Terbitkan challenge"} disabled={challengeBusy || !challengeAgentId || !challengeSkillId || !challengeTestKey} onPress={() => void issueNativeChallenge()}/>
        {challengeRun && <View style={s.socialRow}><Text style={s.kicker}>RUN {challengeRun.id}</Text><Text style={s.body}>Status: {challengeRun.status} · Agent v{challengeRun.agent_version} · Skill v{challengeRun.skill_version}</Text><Text style={s.muted}>Input challenge: {JSON.stringify(challengeRun.challenge_input)}</Text><TextInput accessibilityLabel="Jawaban output JSON challenge" multiline value={challengeSubmission} onChangeText={setChallengeSubmission} autoCapitalize="none" style={[s.input, { minHeight: 130, textAlignVertical: "top" }]} placeholder="Output JSON" placeholderTextColor="#8B94AC"/><Button title="Kirim evaluasi" disabled={challengeBusy || !challengeNonce} onPress={() => void submitNativeChallenge()}/>{challengeRun.evaluation_result && <Text style={s.muted}>Hasil: {JSON.stringify(challengeRun.evaluation_result)}{ "\n" }Evidence SHA-256: {challengeRun.evidence_digest || "belum tersedia"}</Text>}</View>}
        <Text style={s.kicker}>RIWAYAT ({challengeRuns.length})</Text>
        {challengeRuns.map(run => <View key={run.id} style={s.socialRow}><Text style={s.body}>{run.challenge_key} · {run.status}</Text><Text style={s.muted}>Agent v{run.agent_version} · Skill v{run.skill_version} · {new Date(run.created_at).toLocaleString()}</Text></View>)}
        <Text style={s.muted}>Achievement hanya berupa bukti non-moneter. Reward finansial/AI Credits tidak diterbitkan sebelum kebijakan resmi dan ledger kanonis mengizinkan.</Text>
      </> : socialLoading ? <View accessibilityRole="progressbar" style={{ paddingVertical: 18, alignItems: "center", gap: 8 }}><ActivityIndicator color="#A5B4FC"/><Text style={s.muted}>Memuat Social Graph…</Text></View> : socialGraph ? <>
        <Text style={s.kicker}>SOCIAL GRAPH</Text><Text style={s.title}>Relasi dan minat</Text>
        <Text style={s.muted}>Gunakan ID pengguna target. Pencarian username masuk cakupan discovery berikutnya.</Text>
        <TextInput accessibilityLabel="ID pengguna target" value={targetUserId} onChangeText={setTargetUserId} autoCapitalize="none" style={field} placeholder="UUID akun Allpha" placeholderTextColor="#8B94AC"/>
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}><Button title="Ikuti" disabled={busy || !targetUserId.trim()} onPress={() => void addSocialEdge("follow")}/><Button title="Blokir" secondary disabled={busy || !targetUserId.trim()} onPress={() => void addSocialEdge("block")}/><Button title="Bisukan" secondary disabled={busy || !targetUserId.trim()} onPress={() => void addSocialEdge("mute")}/></View>
        <Text style={s.kicker}>PERMINTAAN MASUK ({socialGraph.incoming_requests.length})</Text>
        {socialGraph.incoming_requests.length ? socialGraph.incoming_requests.map(edge => <View key={edge.id} style={s.socialRow}><Text style={s.body}>{edge.actor_user_id}</Text><View style={{ flexDirection: "row", gap: 8 }}><Button title="Terima" disabled={busy} onPress={() => void resolveFollowRequest(edge.id, true)}/><Button title="Tolak" secondary disabled={busy} onPress={() => void resolveFollowRequest(edge.id, false)}/></View></View>) : <Text style={s.muted}>Belum ada permintaan masuk.</Text>}
        <Text style={s.kicker}>RELASI ({socialGraph.outgoing.length})</Text>
        {socialGraph.outgoing.map(edge => <View key={edge.id} style={s.socialRow}><Text style={s.body}>{edge.edge_type} · {edge.target_user_id} · {edge.status || "active"}</Text><Button title="Hapus" secondary disabled={busy} onPress={() => void removeSocialEdge(edge)}/></View>)}
        <Text style={s.kicker}>MINAT</Text>
        <TextInput accessibilityLabel="Tambah minat" value={interestKey} onChangeText={value => setInterestKey(value.toLowerCase())} autoCapitalize="none" maxLength={80} style={field} placeholder="contoh: desain.3d" placeholderTextColor="#8B94AC"/>
        <Button title="Simpan minat" disabled={busy || !interestKey.trim()} onPress={() => void saveInterest()}/>
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>{socialGraph.interests.map(item => <Button key={item.interest_key} title={item.interest_key + " ×"} secondary disabled={busy} onPress={() => void removeInterest(item.interest_key)}/>)}</View>
        {socialGraph.blocked_by.length > 0 && <Text style={s.muted}>Akun yang memblokir Anda: {socialGraph.blocked_by.map(edge => edge.actor_user_id).join(", ")}</Text>}
      </> : <><Text style={s.muted}>Data Social Graph belum dimuat.</Text><Button title="Muat ulang" onPress={() => void loadSocialGraph()}/></>}
      {!!error && !loading && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
      {!!message && <Text accessibilityRole="alert" style={s.success}>{message}</Text>}
      <Button title="Keluar" secondary onPress={() => void supabase?.auth.signOut()}/>
    </View>
    <Text style={s.footnote}>Data identitas, pengaturan dan privasi dibaca/ditulis melalui API resmi. Tidak ada akses database langsung dari aplikasi.</Text>
  </ScrollView>;
}

function Navigator() {
  const [session, setSession] = useState<Session | null>(null); const [ready, setReady] = useState(false);
  useEffect(() => { let active = true; if (!supabase) { setReady(true); return; } void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); setReady(true); } }); const { data } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); }); return () => { active = false; data.subscription.unsubscribe(); }; }, []);
  if (!ready) return <View style={s.loading}><ActivityIndicator size="large" color="#A5B4FC"/><Text style={s.muted}>Menyiapkan sesi aman…</Text></View>;
  return <NavigationContainer><Stack.Navigator key={session?.user.id || "anonymous"} initialRouteName={session ? "Profile" : "Welcome"} screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#0B1020" } }}>{session ? <Stack.Screen name="Profile">{() => <Profile session={session}/>}</Stack.Screen> : <><Stack.Screen name="Welcome" component={Welcome}/><Stack.Screen name="Auth" component={Auth}/></>}</Stack.Navigator></NavigationContainer>;
}
export default function App() { return <SafeAreaProvider><StatusBar style="light"/><Navigator/></SafeAreaProvider>; }

const s = StyleSheet.create({
 page:{flexGrow:1,justifyContent:"center",backgroundColor:"#0B1020",padding:22,gap:20},brand:{alignItems:"center",gap:6,marginBottom:8},mark:{width:54,height:54,borderRadius:18,backgroundColor:"#A5B4FC",alignItems:"center",justifyContent:"center",marginBottom:8},markText:{fontSize:28,fontWeight:"900",color:"#10152A"},eyebrow:{color:"#A5B4FC",letterSpacing:3,fontSize:10,fontWeight:"800"},brandTitle:{color:"#F5F7FF",fontSize:34,fontWeight:"800"},muted:{color:"#A5ADC3",fontSize:13,lineHeight:20,textAlign:"center"},card:{backgroundColor:"#141B31",borderColor:"#29314B",borderWidth:1,borderRadius:26,padding:22,gap:15},kicker:{color:"#A5B4FC",letterSpacing:2,fontSize:10,fontWeight:"800"},hero:{color:"#F7F8FF",fontSize:25,fontWeight:"800",lineHeight:32},title:{color:"#F7F8FF",fontSize:22,fontWeight:"800"},body:{color:"#C0C7DA",fontSize:14,lineHeight:22},button:{minHeight:49,borderRadius:14,backgroundColor:"#A5B4FC",padding:14,alignItems:"center",justifyContent:"center",marginTop:2},secondary:{backgroundColor:"transparent",borderWidth:1,borderColor:"#3A4566"},buttonText:{color:"#11162B",fontWeight:"800",fontSize:14},secondaryText:{color:"#E1E6F8"},disabled:{opacity:.45},pressed:{opacity:.8},input:{minHeight:50,backgroundColor:"#0D1326",color:"#F7F8FF",borderColor:"#303A58",borderWidth:1,borderRadius:13,paddingHorizontal:14,fontSize:15},status:{color:"#A5ADC3",fontSize:12},warning:{color:"#FBBF24",fontSize:12,lineHeight:18},error:{color:"#FCA5A5",backgroundColor:"#321D2B",padding:12,borderRadius:10,fontSize:13,lineHeight:19},success:{color:"#86EFAC",backgroundColor:"#12302C",padding:12,borderRadius:10,fontSize:13,lineHeight:19},socialRow:{gap:8,paddingVertical:10,borderBottomWidth:1,borderBottomColor:"#29314B"},footnote:{color:"#747E9A",textAlign:"center",fontSize:11,lineHeight:18},loading:{flex:1,backgroundColor:"#0B1020",alignItems:"center",justifyContent:"center",gap:12}
});
