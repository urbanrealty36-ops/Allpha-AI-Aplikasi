import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, Share, StyleSheet, Text, TextInput, View } from "react-native";
import { NavigationContainer, useNavigation, type NavigationProp } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { SafeAreaProvider } from "react-native-safe-area-context";
import * as SecureStore from "expo-secure-store";
import * as DocumentPicker from "expo-document-picker";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { StatusBar } from "expo-status-bar";
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { CanonicalNativeWorldRenderer } from "./components/spatial/CanonicalNativeWorldRenderer";
import { SpatialNavigationScreen } from "./components/spatial/SpatialNavigationScreen";
import { SpatialThemeCatalogScreen } from "./components/spatial/SpatialThemeCatalogScreen";
import { NotificationsInbox } from "./components/NotificationsInbox";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

type Routes = { Welcome: undefined; Auth: { mode?: "signin" | "signup" } | undefined; Profile: undefined };
type NativeContentItem = { id: string; body: string; content_type: string; visibility: string; status: string; moderation_status: string; version: number; media?: { id: string; filename: string; media_type: string; status: string }[] };
type NativeFeedItem = { id: string; owner_id: string; body: string; content_type: string; published_at?: string | null; created_at: string; media?: { id: string; filename: string; media_type: string; preview_url?: string | null }[]; engagement?: { likes: number; comments: number; saves: number; shares?: number }; viewer_reaction?: string | null; saved?: boolean };
type NativeFeedComment = { id: string; actor_user_id: string; body: string; created_at: string };
type NativeStory = { id: string; owner_id: string; body: string; content_type: string; visibility: string; status: string; moderation_status: string; version: number; created_at: string; published_at?: string | null; expires_at?: string | null; media?: { id: string; filename: string; media_type: string; preview_url?: string | null }[] };


type NativeContentFile = { uri: string; name: string; mimeType?: string | null; size?: number | null };
type AgentIdentity = { id: string; handle: string; display_name: string; description?: string; visibility: "private" | "public"; status: "draft" | "active" | "archived"; ownership?: { owner_user_id: string; role: "owner"; status: "active" } };
type CatalogSkill = { key: string; name: string; category: string; category_label: string; description: string; catalog_version?: string; source?: { kind?: string; repository?: string; source_url?: string }; character_profile: { archetype_key: string; display_role: string; asset_key: string | null; asset_status: string } };
type SkillCatalogResponse = { items: CatalogSkill[]; categories: { key: string; label: string; count: number }[] };
type AgentPassport = Pick<AgentIdentity, "id" | "handle" | "display_name" | "description" | "visibility" | "status"> & { disclosure?: string; created_at?: string; skills?: { id: string; name: string; slug: string; version: number; description?: string }[]; capabilities?: { id: string; capability_key: string; description?: string; risk_level: string }[] };
type RegisteredTool = { key: string; version: string; name: string; description: string; risk_level: string; required_permission_scopes: string[]; executable: boolean };
type AgentSkill = { id: string; slug: string; name: string; description?: string; status: "draft" | "published" | "archived"; version: number; required_permission_scopes?: string[]; tool_dependencies?: string[] };
type AgentCapability = { id: string; capability_key: string; description?: string; status: "requested" | "approved" | "denied" | "revoked"; risk_level: string };
type RuntimeSession = { id: string; owner_user_id: string; agent_id: string; title: string; status: string; created_at: string; last_activity_at: string };
type RuntimeSkill = { id: string; slug: string; name: string; status: "draft" | "published" | "archived"; version: number; tool_dependencies?: string[] };
type ChallengeSkill = { id: string; agent_id: string; slug: string; name: string; status: string; version: number; tests?: Record<string, unknown>[]; hidden_challenges_available?: boolean; evaluation_rubric_available?: boolean };
type ChallengeRun = { id: string; agent_id: string; skill_id: string; agent_version: number; skill_version: number; challenge_key: string; status: string; challenge_input: Record<string, unknown>; evaluation_result?: Record<string, unknown> | null; evidence_digest?: string | null; runtime_evidence_digest?: string | null; previous_version_comparison?: Record<string, unknown> | null; release_decision?: string | null; release_decision_reason?: string | null; created_at: string };
type RuntimeTask = { id: string; session_id: string; skill_id: string; tool_key: string; state: string; input_payload?: Record<string, unknown>; output_payload?: Record<string, unknown> | null; error_code?: string | null; created_at: string; updated_at: string; trace_id: string };
type KnowledgeSource = { id: string; filename: string; size_bytes: number; sha256: string; status: string; processing_stage: string; error_code?: string | null; created_at: string; latest_job?: { id: string; status: string; stage: string; attempt: number; progress: number; error_code?: string | null } | null };
type KnowledgeRetrievalResult = { source_id: string; source_version: number; chunk_id: string; content: string; content_sha256: string; source_location: Record<string, unknown>; sensitivity: string; retrieval_method: "vector" | "keyword" | "hybrid"; score: number; provider_id?: string | null; model_id?: string | null; model_version?: string | null; index_generation?: string | null };
type Profile = { id: string; username: string | null; display_name: string; avatar_url: string | null; bio: string; locale: "id-ID" | "en-US"; visibility: "public" | "private"; account_status?: "active" | "deactivation_requested"; created_at?: string };
type Settings = { theme: "light" | "dark" | "system"; notification_preferences: { product_updates: boolean; security_alerts: boolean; social_activity: boolean }; privacy_settings: { discoverable_by_username: boolean }; updated_at?: string };
type SocialEdge = { id: string; target_user_id?: string; actor_user_id?: string; edge_type: "follow" | "block" | "mute"; status?: string };
type SocialInterest = { interest_key: string; preference: "interested" | "not_interested" };
type NativeConversation = { id: string; title?: string | null; kind: "human" | "agent"; last_message?: { body: string; created_at: string; delivery_status: string } };
type NativeMessage = { id: string; body: string; sender_type: string; sender_user_id?: string; created_at: string; delivery_status: string };
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

function createMessageId() { return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => { const r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 3 | 8)).toString(16); }); }

function Profile({ session, initialTab = "profile" }: { session: Session; initialTab?: "profile" | "agents" | "feed" }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [tab, setTab] = useState<"profile" | "settings" | "notifications" | "social" | "consents" | "agents" | "challenges" | "content" | "feed" | "reels" | "stories" | "discovery" | "messages" | "communities">(initialTab);
  const [agents, setAgents] = useState<AgentIdentity[]>([]);
  const [agentLoading, setAgentLoading] = useState(false);
  const [contentItems, setContentItems] = useState<NativeContentItem[]>([]);
  const [contentBody, setContentBody] = useState("");
  const [contentVisibility, setContentVisibility] = useState<"public" | "followers" | "private">("public");
  const [contentFile, setContentFile] = useState<NativeContentFile | null>(null);
  const [contentBusy, setContentBusy] = useState(false);
  const [feedItems, setFeedItems] = useState<NativeFeedItem[]>([]);
  const [reelsItems, setReelsItems] = useState<NativeFeedItem[]>([]);
  const [storyItems, setStoryItems] = useState<NativeStory[]>([]);
  const [activeStories, setActiveStories] = useState<NativeStory[]>([]);
  const [storyBody, setStoryBody] = useState("");
  const [storyVisibility, setStoryVisibility] = useState<"public" | "followers" | "private">("public");
  const [storyTtl, setStoryTtl] = useState(24);
  const [storyFile, setStoryFile] = useState<NativeContentFile | null>(null);
  const [storyBusy, setStoryBusy] = useState(false);
  const [reelsCursor, setReelsCursor] = useState<string | null>(null);
  const [reelsBusy, setReelsBusy] = useState(false);
  const [feedBusy, setFeedBusy] = useState(false);
  const [feedCursor, setFeedCursor] = useState<string | null>(null);
  const [feedMode, setFeedMode] = useState<"for_you" | "recent">("for_you");
  const [feedPersonalization, setFeedPersonalization] = useState(true);
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [messageConversations, setMessageConversations] = useState<NativeConversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<NativeConversation | null>(null);
  const [conversationMessages, setConversationMessages] = useState<NativeMessage[]>([]);
  const [messageRecipient, setMessageRecipient] = useState("");
  const [messageDraft, setMessageDraft] = useState("");
  const [messageBusy, setMessageBusy] = useState(false);
  const [messageError, setMessageError] = useState("");
  const [pendingNativeMessageId, setPendingNativeMessageId] = useState<string | null>(null);
  const [messageRealtimeStatus, setMessageRealtimeStatus] = useState("connecting");
  const [communityItems, setCommunityItems] = useState<{id:string;name:string;slug:string;description:string;visibility:string;membership_role?:string|null}[]>([]);
  const [workspaceItems, setWorkspaceItems] = useState<{id:string;title:string;description:string;visibility:string;membership_role?:string}[]>([]);
  const [activeCommunity, setActiveCommunity] = useState<{id:string;name:string;slug:string;description:string;visibility:string;membership_role?:string|null}|null>(null);
  const [communityPosts, setCommunityPosts] = useState<{id:string;body:string;post_type:string;created_at:string;is_pinned?:boolean}[]>([]);
  const [communityMissions, setCommunityMissions] = useState<{id:string;title:string;description:string;target_count:number;my_progress?:{progress_count:number;status:string}}[]>([]);
  const [missionDraftTitle, setMissionDraftTitle] = useState("");
  const [missionDraftDescription, setMissionDraftDescription] = useState("");
  const [missionDraftTarget, setMissionDraftTarget] = useState("1");
  const [communityDraftName, setCommunityDraftName] = useState("");
  const [communityDraftSlug, setCommunityDraftSlug] = useState("");
  const [communityPostDraft, setCommunityPostDraft] = useState("");
  const [communityPostType, setCommunityPostType] = useState<"discussion"|"resource">("discussion");
  const [inviteTokenDraft, setInviteTokenDraft] = useState("");
  const [createdInviteToken, setCreatedInviteToken] = useState("");
  const [workspaceDraftName, setWorkspaceDraftName] = useState("");
  const [activeWorkspace, setActiveWorkspace] = useState<{id:string;title:string;membership_role?:string}|null>(null);
  const [communityAgentDirectory, setCommunityAgentDirectory] = useState<{id:string;handle:string;display_name:string;version:number}[]>([]);
  const [selectedCommunityAgentId, setSelectedCommunityAgentId] = useState("");
  const [communityGrantScopes, setCommunityGrantScopes] = useState<string[]>(["read_published_content"]);
  const [communityResourceGrants, setCommunityResourceGrants] = useState<{id:string;agent_id:string;agent_version:number;resource_type:"community"|"workspace";scopes:string[];status:"active"|"revoked";expires_at:string|null}[]>([]);
  const [workspaceDocs, setWorkspaceDocs] = useState<{id:string;title:string;body?:string;version:number}[]>([]);
  const [activeWorkspaceDoc, setActiveWorkspaceDoc] = useState<{id:string;title:string;body?:string;version:number}|null>(null);
  const [workspaceDocTitle, setWorkspaceDocTitle] = useState("");
  const [workspaceDocBody, setWorkspaceDocBody] = useState("");
  const [discoveryItems, setDiscoveryItems] = useState<{id:string;body:string;content_type:string;created_at:string;published_at?:string|null}[]>([]);
  const [discoveryTrends, setDiscoveryTrends] = useState<{topic:string;content_count:number;example_content_id:string}[]>([]);
  const [discoveryTrendsBusy, setDiscoveryTrendsBusy] = useState(false);
  const [discoveryTrendsError, setDiscoveryTrendsError] = useState("");
  const [discoveryRecommendations, setDiscoveryRecommendations] = useState<NativeFeedItem[]>([]);
  const [discoveryRecommendationsBusy, setDiscoveryRecommendationsBusy] = useState(false);
  const [discoveryRecommendationsError, setDiscoveryRecommendationsError] = useState("");
  const [discoveryBusy, setDiscoveryBusy] = useState(false);
  const [discoveryError, setDiscoveryError] = useState("");
  const [feedCommentDrafts, setFeedCommentDrafts] = useState<Record<string, string>>({});
  const [feedComments, setFeedComments] = useState<Record<string, NativeFeedComment[]>>({});
  const [feedCommentsOpen, setFeedCommentsOpen] = useState<Record<string, boolean>>({});
  const [agentHandle, setAgentHandle] = useState("");
  const [agentName, setAgentName] = useState("");
  const [agentDescription, setAgentDescription] = useState("");
  const [skillCatalog, setSkillCatalog] = useState<CatalogSkill[]>([]);
  const [skillCatalogQuery, setSkillCatalogQuery] = useState("");
  const [selectedCatalogSkill, setSelectedCatalogSkill] = useState("");
  const [skillCatalogLoading, setSkillCatalogLoading] = useState(true);
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
  const [challengeNonce, setChallengeNonce] = useState("");
  const [challengeReleaseReason, setChallengeReleaseReason] = useState("");
  const [challengeComparison, setChallengeComparison] = useState<Record<string, unknown> | null>(null);
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
  const [spatialSceneKey, setSpatialSceneKey] = useState(""); const [spatialActiveKey, setSpatialActiveKey] = useState("");
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [retry, setRetry] = useState(0);
  const [pushRegistrationStatus, setPushRegistrationStatus] = useState("Memeriksa konfigurasi push…");
  const [pushRegistrationRetry, setPushRegistrationRetry] = useState(0);
  async function apiRequest(path: string, init: RequestInit = {}) {
    const headers: Record<string, string> = { Authorization: "Bearer " + session.access_token, Accept: "application/json" };
    if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
    Object.assign(headers, init.headers || {});
    const response = await fetch(apiBase + path, {
      ...init,
      headers,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Permintaan gagal (" + response.status + ").");
    return body;
  }

  useEffect(() => {
    let active = true;
    let registeredDeviceId: string | null = null;
    const responseListener = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data as Record<string, unknown>;
      if (data.type === "community_invite_accepted") {
        setTab("communities");
        void loadCommunityWorkspace();
        return;
      }
      if (data.type !== "message" || typeof data.conversationId !== "string") return;
      setTab("messages");
      void (async () => {
        try {
          const result = await apiRequest("/v1/messages/conversations") as { items?: NativeConversation[] };
          const conversation = (result.items || []).find(item => item.id === data.conversationId);
          if (conversation) await openMessageConversation(conversation);
        } catch (cause) {
          setMessageError(cause instanceof Error ? cause.message : "Percakapan dari notifikasi tidak dapat dibuka.");
        }
      })();
    });

    void (async () => {
      const platform = Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : null;
      if (!platform) {
        setPushRegistrationStatus("Push hanya tersedia pada build native Android/iOS.");
        return;
      }
      const projectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID
        || Constants.expoConfig?.extra?.eas?.projectId
        || Constants.easConfig?.projectId;
      if (!projectId) {
        setPushRegistrationStatus("Push belum aktif: EXPO_PUBLIC_EAS_PROJECT_ID belum dikonfigurasi.");
        return;
      }
      const preferenceResult = await apiRequest("/v1/notifications/preferences") as { preferences?: { push_enabled?: boolean } };
      if (preferenceResult.preferences?.push_enabled === false) {
        setPushRegistrationStatus("Push dinonaktifkan di preferensi notifikasi.");
        return;
      }
      let permission = await Notifications.getPermissionsAsync();
      if (!permission.granted) permission = await Notifications.requestPermissionsAsync();
      if (!permission.granted) {
        setPushRegistrationStatus("Izin notifikasi belum diberikan pada perangkat ini.");
        return;
      }
      if (platform === "android") {
        await Notifications.setNotificationChannelAsync("default", {
          name: "Allpha",
          importance: Notifications.AndroidImportance.DEFAULT,
        });
      }
      const token = await Notifications.getExpoPushTokenAsync({ projectId });
      if (!active) return;
      const result = await apiRequest("/v1/notifications/devices", {
        method: "POST",
        body: JSON.stringify({ expo_push_token: token.data, platform }),
      }) as { device?: { id?: string } };
      const newDeviceId = result.device?.id || null;
      if (!active && newDeviceId) {
        void fetch(apiBase + "/v1/notifications/devices/" + encodeURIComponent(newDeviceId), {
          method: "DELETE", headers: { Authorization: "Bearer " + session.access_token },
        }).catch(() => undefined);
        return;
      }
      registeredDeviceId = newDeviceId;
      if (active) setPushRegistrationStatus("Token push perangkat berhasil didaftarkan.");
    })().catch(() => {
      if (active) setPushRegistrationStatus("Registrasi push belum berhasil; periksa build native dan konfigurasi provider.");
    });

    return () => {
      active = false;
      responseListener.remove();
      if (registeredDeviceId) {
        void fetch(apiBase + "/v1/notifications/devices/" + encodeURIComponent(registeredDeviceId), {
          method: "DELETE",
          headers: { Authorization: "Bearer " + session.access_token },
        }).catch(() => undefined);
      }
    };
  }, [session.access_token, pushRegistrationRetry]);

  useEffect(() => {
    if (!activeConversation || tab !== "messages" || !supabase) return;
    let stopped = false;
    let channel: any = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const connect = () => {
      if (stopped || !supabase) return;
      channel = supabase.channel("native-messages:" + activeConversation.id + ":" + createMessageId())
        .on("postgres_changes", { event: "*", schema: "public", table: "messages", filter: "conversation_id=eq." + activeConversation.id }, () => { void openMessageConversation(activeConversation); })
        .subscribe((status: string) => {
          if (stopped) return;
          setMessageRealtimeStatus(status.toLowerCase());
          if (status === "SUBSCRIBED") void openMessageConversation(activeConversation);
          else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT" || status === "CLOSED") {
            if (retryTimer) clearTimeout(retryTimer);
            retryTimer = setTimeout(() => { if (channel && supabase) void supabase.removeChannel(channel); connect(); }, 2500);
          }
        });
    };
    connect();
    return () => { stopped = true; if (retryTimer) clearTimeout(retryTimer); if (channel && supabase) void supabase.removeChannel(channel); };
  }, [activeConversation?.id, tab, session]);
  async function loadMessageConversations() {
    setMessageBusy(true); setMessageError("");
    try { const result = await apiRequest("/v1/messages/conversations") as { items?: NativeConversation[] }; setMessageConversations(result.items ?? []); }
    catch (cause) { setMessageError(cause instanceof Error ? cause.message : "Percakapan gagal dimuat."); }
    finally { setMessageBusy(false); }
  }
  async function openMessageConversation(conversation: NativeConversation) {
    setActiveConversation(conversation); setMessageError("");
    try { const result = await apiRequest("/v1/messages/conversations/" + encodeURIComponent(conversation.id) + "/messages") as { items?: NativeMessage[] }; setConversationMessages(result.items ?? []); await apiRequest("/v1/messages/conversations/" + encodeURIComponent(conversation.id) + "/read", { method: "POST", body: "{}" }); }
    catch (cause) { setMessageError(cause instanceof Error ? cause.message : "Pesan gagal dimuat."); }
  }
  async function startMessageConversation() {
    if (!messageRecipient.trim()) return; setMessageBusy(true); setMessageError("");
    try { const result = await apiRequest("/v1/messages/conversations", { method: "POST", body: JSON.stringify({ recipient_user_id: messageRecipient.trim() }) }) as { conversation?: NativeConversation }; if (result.conversation) { setActiveConversation(result.conversation); setConversationMessages([]); } setMessageRecipient(""); await loadMessageConversations(); }
    catch (cause) { setMessageError(cause instanceof Error ? cause.message : "Percakapan gagal dibuat."); }
    finally { setMessageBusy(false); }
  }
  async function sendNativeMessage() {
    if (!activeConversation || !messageDraft.trim()) return; setMessageBusy(true); setMessageError(""); const clientMessageId = pendingNativeMessageId || createMessageId(); setPendingNativeMessageId(clientMessageId);
    try { const result = await apiRequest("/v1/messages/conversations/" + encodeURIComponent(activeConversation.id) + "/messages", { method: "POST", body: JSON.stringify({ body: messageDraft.trim(), client_message_id: clientMessageId }) }) as { message?: NativeMessage; agent_reply?: { status: string; message?: NativeMessage; error_code?: string } }; if (result.message) setConversationMessages(old => [...old.filter(item => item.id !== result.message!.id), result.message!]); if (result.agent_reply?.message) setConversationMessages(old => [...old.filter(item => item.id !== result.agent_reply!.message!.id), result.agent_reply!.message!]); if (result.agent_reply?.status === "unavailable") setMessageError("Pesan tersimpan, tetapi balasan Agent belum tersedia (" + result.agent_reply.error_code + ")."); setMessageDraft(""); setPendingNativeMessageId(null); await loadMessageConversations(); }
    catch (cause) { setMessageError(cause instanceof Error ? cause.message : "Pesan gagal dikirim."); }
    finally { setMessageBusy(false); }
  }
  async function loadMyContent() {
    setContentBusy(true); setError(""); setMessage("");
    try { const result = await apiRequest("/v1/content/mine") as { items?: NativeContentItem[] }; setContentItems(result.items ?? []); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Konten tidak dapat dimuat."); }
    finally { setContentBusy(false); }
  }

  async function loadDiscoveryRecommendations() {
    setDiscoveryRecommendationsBusy(true); setDiscoveryRecommendationsError("");
    try {
      const result = await apiRequest("/v1/recommendations?limit=10") as { items?: NativeFeedItem[] };
      setDiscoveryRecommendations(result.items ?? []);
    } catch (cause) { setDiscoveryRecommendationsError(cause instanceof Error ? cause.message : "Rekomendasi belum dapat dimuat."); }
    finally { setDiscoveryRecommendationsBusy(false); }
  }
  async function loadDiscoveryTrends() {
    setDiscoveryTrendsBusy(true); setDiscoveryTrendsError("");
    try {
      const response = await fetch(apiBase + "/v1/trends?limit=10", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const payload = await response.json() as { items?: {topic:string;content_count:number;example_content_id:string}[]; error?: {message?:string} };
      if (!response.ok) throw new Error(payload.error?.message || "Tren belum dapat dimuat.");
      setDiscoveryTrends(payload.items || []);
    } catch (cause) { setDiscoveryTrendsError(cause instanceof Error ? cause.message : "Tren belum dapat dimuat."); }
    finally { setDiscoveryTrendsBusy(false); }
  }
  async function runDiscoverySearch(value = discoveryQuery) {
    if (value.trim().length < 2) { setDiscoveryError("Masukkan minimal 2 karakter."); return; }
    setDiscoveryBusy(true); setDiscoveryError("");
    try {
      const response = await fetch(apiBase + "/v1/search?q=" + encodeURIComponent(value.trim()) + "&limit=30", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const payload = await response.json() as { items?: {id:string;body:string;content_type:string;created_at:string;published_at?:string|null}[]; error?: {message?:string} };
      if (!response.ok) throw new Error(payload.error?.message || "Pencarian gagal.");
      setDiscoveryItems(payload.items || []);
    } catch (cause) { setDiscoveryError(cause instanceof Error ? cause.message : "Pencarian gagal."); setDiscoveryItems([]); }
    finally { setDiscoveryBusy(false); }
  }

  async function loadNativeFeed(reset = true) {
    setFeedBusy(true); setError("");
    try {
      const params = new URLSearchParams({ mode: feedMode, limit: "10" });
      if (!reset && feedCursor) params.set("cursor", feedCursor);
      const result = await apiRequest("/v1/feed?" + params.toString()) as { items?: NativeFeedItem[]; next_cursor?: string | null; mode?: "for_you" | "recent"; personalization_enabled?: boolean };
      setFeedItems(current => reset ? (result.items ?? []) : [...current, ...(result.items ?? [])]);
      setFeedCursor(result.next_cursor ?? null);
      if (result.mode) setFeedMode(result.mode);
      if (typeof result.personalization_enabled === "boolean") setFeedPersonalization(result.personalization_enabled);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Feed tidak dapat dimuat."); }
    finally { setFeedBusy(false); }
  }
  async function loadNativeReels(reset = true) {
    setReelsBusy(true); setError(""); setMessage("");
    try {
      const params = new URLSearchParams({ mode: "recent", limit: "20" });
      if (!reset && reelsCursor) params.set("cursor", reelsCursor);
      const result = await apiRequest("/v1/reels?" + params.toString()) as { items?: NativeFeedItem[]; next_cursor?: string | null };
      setReelsItems(current => reset ? (result.items ?? []) : [...current, ...(result.items ?? [])]);
      setReelsCursor(result.next_cursor ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reels tidak dapat dimuat."); }
    finally { setReelsBusy(false); }
  }
  async function loadNativeStories() {
    setStoryBusy(true); setError(""); setMessage("");
    try {
      const [mine, active] = await Promise.all([
        apiRequest("/v1/stories/mine?limit=50") as Promise<{ items?: NativeStory[] }>,
        apiRequest("/v1/stories?limit=30") as Promise<{ items?: NativeStory[] }>,
      ]);
      setStoryItems(mine.items ?? []); setActiveStories(active.items ?? []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Stories tidak dapat dimuat."); }
    finally { setStoryBusy(false); }
  }
  async function chooseStoryMedia() {
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm"], copyToCacheDirectory: true, multiple: false });
      if (result.canceled || !result.assets?.[0]) return;
      const asset = result.assets[0];
      if (!asset.mimeType || !["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm"].includes(asset.mimeType)) throw new Error("Story mendukung JPG, PNG, WebP, MP4, dan WebM.");
      const max = asset.mimeType.startsWith("video/") ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
      if (asset.size && asset.size > max) throw new Error("Ukuran media melampaui batas.");
      setStoryFile({ uri: asset.uri, name: asset.name, mimeType: asset.mimeType, size: asset.size });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pemilihan media Story gagal."); }
  }
  async function createNativeStory() {
    if (!storyBody.trim() && !storyFile) { setError("Isi teks atau pilih gambar/video terlebih dahulu."); return; }
    setStoryBusy(true); setError(""); setMessage("");
    try {
      const created = await apiRequest("/v1/stories", { method: "POST", body: JSON.stringify({ body: storyBody.trim(), visibility: storyVisibility, expires_after_hours: storyTtl }) }) as { item: NativeStory };
      if (storyFile) {
        const form = new FormData();
        form.append("file", { uri: storyFile.uri, name: storyFile.name, type: storyFile.mimeType } as unknown as Blob);
        await apiRequest("/v1/content/" + encodeURIComponent(created.item.id) + "/media", { method: "POST", body: form });
      }
      const result = await apiRequest("/v1/content/" + encodeURIComponent(created.item.id) + "/publish", { method: "POST" }) as { message?: string };
      setStoryBody(""); setStoryFile(null); setMessage(result.message || "Story dikirim untuk moderasi.");
      await loadNativeStories();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Story tidak dapat disimpan."); }
    finally { setStoryBusy(false); }
  }
  async function archiveNativeStory(story: NativeStory) {
    setStoryBusy(true); setError(""); setMessage("");
    try { await apiRequest("/v1/stories/" + encodeURIComponent(story.id), { method: "DELETE" }); setMessage("Story diarsipkan."); await loadNativeStories(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Story tidak dapat diarsipkan."); }
    finally { setStoryBusy(false); }
  }

  async function saveNativeFeedPreferences(enabled: boolean, mode: "for_you" | "recent") {
    setFeedBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/v1/feed/preferences", { method: "PUT", body: JSON.stringify({ personalization_enabled: enabled, ranking_mode: mode }) });
      setFeedPersonalization(enabled); setFeedMode(mode); setMessage("Preferensi feed disimpan.");
      const result = await apiRequest("/v1/feed?mode=" + mode + "&limit=10") as { items?: NativeFeedItem[]; next_cursor?: string | null; mode?: "for_you" | "recent" };
      setFeedItems(result.items ?? []); setFeedCursor(result.next_cursor ?? null); if (result.mode) setFeedMode(result.mode);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Preferensi feed gagal disimpan."); }
    finally { setFeedBusy(false); }
  }
  async function nativeFeedAction(item: NativeFeedItem, action: "like" | "save" | "report", reportReason: "spam" | "harassment" | "privacy" | "misinformation" | "other" = "other") {
    setFeedBusy(true); setError(""); setMessage("");
    try {
      if (action === "like") await apiRequest("/v1/feed/" + encodeURIComponent(item.id) + "/reaction", { method: item.viewer_reaction ? "DELETE" : "PUT", body: item.viewer_reaction ? undefined : JSON.stringify({ reaction: "like" }) });
      else if (action === "save") await apiRequest("/v1/feed/" + encodeURIComponent(item.id) + "/save", { method: item.saved ? "DELETE" : "PUT" });
      else { await apiRequest("/v1/feed/" + encodeURIComponent(item.id) + "/report", { method: "POST", body: JSON.stringify({ reason: reportReason }) }); setMessage("Laporan dikirim untuk ditinjau."); }
      if (action !== "report") await loadNativeFeed(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Interaksi feed gagal."); }
    finally { setFeedBusy(false); }
  }
  async function shareNativeContent(item: NativeFeedItem) {
    setFeedBusy(true); setError(""); setMessage("");
    try {
      const result = await apiRequest("/v1/feed/" + encodeURIComponent(item.id) + "/share", {
        method: "POST", body: JSON.stringify({ share_target: "native_share" }),
      }) as { share_url: string };
      await Share.share({ message: result.share_url, url: result.share_url });
      setMessage("Tautan berbagi disiapkan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Berbagi konten gagal."); }
    finally { setFeedBusy(false); }
  }
  function chooseNativeReportReason(item: NativeFeedItem) {
    Alert.alert("Laporkan konten", "Pilih alasan laporan", [
      { text: "Spam", onPress: () => void nativeFeedAction(item, "report", "spam") },
      { text: "Pelecehan", onPress: () => void nativeFeedAction(item, "report", "harassment") },
      { text: "Privasi", onPress: () => void nativeFeedAction(item, "report", "privacy") },
      { text: "Misinformasi", onPress: () => void nativeFeedAction(item, "report", "misinformation") },
      { text: "Lainnya", onPress: () => void nativeFeedAction(item, "report", "other") },
      { text: "Batal", style: "cancel" },
    ]);
  }
  async function submitNativeFeedComment(item: NativeFeedItem) {
    const body = (feedCommentDrafts[item.id] || "").trim(); if (!body) return;
    setFeedBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/v1/feed/" + encodeURIComponent(item.id) + "/comments", { method: "POST", body: JSON.stringify({ body }) });
      setFeedCommentDrafts(current => ({ ...current, [item.id]: "" })); setMessage("Komentar dikirim.");
      await loadNativeFeed(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar gagal dikirim."); }
    finally { setFeedBusy(false); }
  }

  async function toggleNativeComments(item: NativeFeedItem) {
    const opening = !feedCommentsOpen[item.id];
    setFeedCommentsOpen(current => ({ ...current, [item.id]: opening }));
    if (!opening || feedComments[item.id]) return;
    setFeedBusy(true); setError("");
    try {
      const result = await apiRequest("/v1/feed/" + encodeURIComponent(item.id) + "/comments") as { items?: NativeFeedComment[] };
      setFeedComments(current => ({ ...current, [item.id]: result.items ?? [] }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Komentar tidak dapat dimuat."); }
    finally { setFeedBusy(false); }
  }
  async function chooseContentMedia() {
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "audio/mpeg", "audio/mp4", "audio/aac", "audio/ogg", "audio/wav", "audio/webm"], copyToCacheDirectory: true, multiple: false });
      if (result.canceled || !result.assets?.[0]) return;
      const asset = result.assets[0];
      const allowed = ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "audio/mpeg", "audio/mp4", "audio/aac", "audio/ogg", "audio/wav", "audio/webm"];
      if (!asset.mimeType || !allowed.includes(asset.mimeType)) throw new Error("Format media harus JPG, PNG, WebP, MP4, WebM, MP3, M4A, AAC, OGG, WAV, atau audio WebM.");
      const max = asset.mimeType.startsWith("video/") || asset.mimeType.startsWith("audio/") ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
      if (asset.size && asset.size > max) throw new Error("Ukuran file melampaui batas format media.");
      setContentFile({ uri: asset.uri, name: asset.name, mimeType: asset.mimeType, size: asset.size });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pemilihan media gagal."); }
  }
  async function createNativeContentDraft() {
    if (!contentBody.trim() && !contentFile) { setError("Isi teks atau pilih media terlebih dahulu."); return; }
    setContentBusy(true); setError(""); setMessage("");
    try {
      const contentType = contentFile ? (contentFile.mimeType?.startsWith("video/") ? "video" : contentFile.mimeType?.startsWith("audio/") ? "audio" : "image") : "text";
      const created = await apiRequest("/v1/content", { method: "POST", body: JSON.stringify({ body: contentBody.trim(), visibility: contentVisibility, content_type: contentType }) }) as { item: NativeContentItem };
      setContentItems(current => [created.item, ...current.filter(item => item.id !== created.item.id)]);
      if (contentFile) {
        const form = new FormData();
        form.append("file", { uri: contentFile.uri, name: contentFile.name, type: contentFile.mimeType } as unknown as Blob);
        const response = await fetch(apiBase + "/v1/content/" + encodeURIComponent(created.item.id) + "/media", { method: "POST", headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" }, body: form });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result?.error?.message || result?.detail?.message || "Unggah media gagal. Draft tetap tersimpan.");
      }
      setContentBody(""); setContentFile(null); setMessage("Draft konten tersimpan melalui FastAPI.");
      const result = await apiRequest("/v1/content/mine") as { items?: NativeContentItem[] }; setContentItems(result.items ?? []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft gagal disimpan.");
      try { const result = await apiRequest("/v1/content/mine") as { items?: NativeContentItem[] }; setContentItems(result.items ?? []); } catch {}
    } finally { setContentBusy(false); }
  }
  async function submitNativeContent(item: NativeContentItem) {
    setContentBusy(true); setError(""); setMessage("");
    try { const result = await apiRequest("/v1/content/" + encodeURIComponent(item.id) + "/publish", { method: "POST" }) as { message?: string }; setMessage(result.message || "Konten dikirim untuk moderasi."); const data = await apiRequest("/v1/content/mine") as { items?: NativeContentItem[] }; setContentItems(data.items ?? []); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pengiriman konten gagal."); }
    finally { setContentBusy(false); }
  }
  async function retryNativeContent(item: NativeContentItem) {
    setContentBusy(true); setError(""); setMessage("");
    try {
      const result = await apiRequest("/v1/content/" + encodeURIComponent(item.id) + "/retry", { method: "POST" }) as { message?: string };
      setMessage(result.message || "Draft dipulihkan; periksa kembali sebelum mengirim.");
      const data = await apiRequest("/v1/content/mine") as { items?: NativeContentItem[] };
      setContentItems(data.items ?? []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Pemulihan draft gagal.");
    } finally { setContentBusy(false); }
  }
  async function previewNativeContent(item: NativeContentItem) {
    setContentBusy(true); setError(""); setMessage("");
    try {
      const result = await apiRequest("/v1/content/" + encodeURIComponent(item.id) + "/preview") as { media?: { preview_url?: string | null }[] };
      const url = result.media?.find(media => media.preview_url)?.preview_url;
      if (url) await Linking.openURL(url); else setMessage(item.body || "Konten ini belum memiliki media untuk pratinjau.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pratinjau gagal dimuat."); }
    finally { setContentBusy(false); }
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
    setChallengeBusy(true); setError(""); setMessage(""); setChallengeNonce(""); setChallengeRun(null); setChallengeComparison(null); setChallengeReleaseReason("");
    try {
      const body = await apiRequest("/v1/skill-challenges/runs", { method: "POST", body: JSON.stringify({
        agent_id: challengeAgentId, skill_id: challengeSkillId, test_key: challengeTestKey === "__hidden__" ? null : challengeTestKey,
        idempotency_key: "native-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12)
      }) }) as { run: ChallengeRun; nonce?: string };
      setChallengeRun(body.run); setChallengeNonce(body.nonce ?? "");
      setMessage(body.nonce ? "Challenge diterbitkan. Jalankan Skill melalui runtime sebelum nonce kedaluwarsa." : "Run lama ditemukan tanpa nonce. Terbitkan run baru untuk menghindari replay.");
      await loadChallengeRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Challenge tidak dapat diterbitkan."); }
    finally { setChallengeBusy(false); }
  }
  async function submitNativeChallenge() {
    if (!challengeRun || !challengeNonce) return;
    setChallengeBusy(true); setError(""); setMessage("");
    try {
      const body = await apiRequest("/v1/skill-challenges/runs/" + encodeURIComponent(challengeRun.id) + "/execute", {
        method: "POST", body: JSON.stringify({ nonce: challengeNonce })
      }) as { run: ChallengeRun; achievement?: { key: string; status: string } | null; reward?: { status: string; reason: string } };
      setChallengeRun(body.run); setChallengeNonce("");
      setMessage(body.run.status === "passed" ? "Skill dieksekusi melalui Agent Runtime dan Model Router; bukti runtime tersimpan. Reward finansial mengikuti kebijakan kanonis." : "Eksekusi Skill selesai dan bukti runtime tersimpan.");
      await loadChallengeRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Eksekusi Skill gagal."); }
    finally { setChallengeBusy(false); }
  }
  async function compareNativeChallenge() {
    if (!challengeRun) return;
    setChallengeBusy(true); setError(""); setMessage("");
    try {
      const body = await apiRequest("/v1/skill-challenges/runs/" + encodeURIComponent(challengeRun.id) + "/comparison") as { comparison?: Record<string, unknown> };
      setChallengeComparison(body.comparison ?? null);
      setChallengeRun({ ...challengeRun, previous_version_comparison: body.comparison ?? null });
      setMessage("Perbandingan versi tersimpan. Keputusan tetap milik pemilik Agent.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Perbandingan versi gagal."); }
    finally { setChallengeBusy(false); }
  }

  async function decideNativeChallenge(decision: "release" | "hold") {
    if (!challengeRun || challengeReleaseReason.trim().length < 8) return;
    setChallengeBusy(true); setError(""); setMessage("");
    try {
      const body = await apiRequest("/v1/skill-challenges/runs/" + encodeURIComponent(challengeRun.id) + "/release-decision", {
        method: "POST", body: JSON.stringify({ decision, reason: challengeReleaseReason.trim() })
      }) as { run: ChallengeRun };
      setChallengeRun(body.run);
      setMessage(decision === "release" ? "Keputusan release tercatat; Skill belum dipublikasikan otomatis." : "Keputusan hold tercatat.");
      await loadChallengeRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan pemilik gagal disimpan."); }
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
  const loadAgents = useCallback(async () => {
    setAgentLoading(true); setError("");
    try {
      const response = await fetch(apiBase + "/v1/agents", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Daftar Agent tidak dapat dimuat.");
      setAgents(Array.isArray(body.items) ? body.items : []);
    } catch (e) { setError(e instanceof Error ? e.message : "Daftar Agent tidak dapat dimuat."); }
    finally { setAgentLoading(false); }
  }, [session.access_token]);

  useEffect(() => {
    if (tab === "agents") void loadAgents();
  }, [tab, loadAgents]);
  useEffect(() => {
    let active = true;
    void Promise.all([
      Promise.all([0, 100, 200, 300, 400].map(offset => fetch(apiBase + "/v1/skill-catalog?limit=100&offset=" + offset, { cache: "no-store" })
        .then(async response => { if (!response.ok) throw new Error("Katalog Skill Allpha tidak tersedia."); return await response.json() as SkillCatalogResponse; }))),
      Promise.all([0, 100, 200].map(offset => fetch(apiBase + "/v1/skill-catalog/agency-agents?limit=100&offset=" + offset, { cache: "no-store" })
        .then(async response => { if (!response.ok) throw new Error("Katalog Agency Agents tidak tersedia."); return await response.json() as SkillCatalogResponse; }))),
    ])
      .then(([pages, agencyPages]) => { if (active) setSkillCatalog([...pages.flatMap(page => page.items ?? []), ...agencyPages.flatMap(page => page.items ?? [])]); })
      .catch(() => { if (active) setMessage("Katalog Skill Allpha tidak dapat dimuat; pembuatan Agent dinonaktifkan."); })
      .finally(() => { if (active) setSkillCatalogLoading(false); });
    return () => { active = false; };
  }, []);

  async function createAgent() {
    if (!selectedCatalogSkill) { setError("Pilih satu Skill dari katalog Allpha."); return; }
    const selectedSkill = skillCatalog.find(item => item.key === selectedCatalogSkill);
    if (!selectedSkill) { setError("Skill terpilih tidak ditemukan pada katalog terbaru."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents", { method: "POST", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" }, body: JSON.stringify({ handle: agentHandle.trim().toLowerCase(), display_name: agentName.trim(), description: agentDescription.trim(), persona: { tone: "helpful", language: "id-ID", allpha_skill_key: selectedSkill.key, allpha_skill_catalog_version: selectedSkill.catalog_version ?? "allpha-skill-catalog-v1", allpha_skill_source: selectedSkill.source?.kind === "agency_agent_definition_metadata" ? "agency-agents" : "allpha-500", character_profile: selectedSkill.character_profile }, disclosure: "AI Agent; respons dapat dihasilkan oleh model.", boundaries: { requires_owner_approval_for_external_actions: true, private_owner_data: "owner_only" }, visibility: "private" }) });
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
  async function loadCommunityWorkspace() {
    setBusy(true); setError(""); setMessage("");
    try {
      const [communityResult, workspaceResult] = await Promise.all([
        apiRequest("/v1/communities") as Promise<{items?: typeof communityItems}>,
        apiRequest("/v1/workspaces") as Promise<{items?: typeof workspaceItems}>,
      ]);
      setCommunityItems(communityResult.items || []); setWorkspaceItems(workspaceResult.items || []);
    } catch (e) { setError(e instanceof Error ? e.message : "Komunitas/workspace gagal dimuat."); }
    finally { setBusy(false); }
  }
  async function openNativeCommunity(item: typeof communityItems[number]) {
    setActiveCommunity(item); setActiveWorkspace(null); setActiveWorkspaceDoc(null); setError("");
    try {
      const [postsResult, missionsResult] = await Promise.all([
        apiRequest("/v1/communities/" + encodeURIComponent(item.id) + "/posts") as Promise<{items?: typeof communityPosts}>,
        item.membership_role ? apiRequest("/v1/communities/" + encodeURIComponent(item.id) + "/missions") as Promise<{items?: typeof communityMissions}> : Promise.resolve({items: [] as typeof communityMissions}),
      ]);
      setCommunityPosts(postsResult.items || []);
      setCommunityMissions(missionsResult.items || []);
    } catch (e) { setError(e instanceof Error ? e.message : "Diskusi komunitas gagal dimuat."); }
  }
  async function createNativeCommunity() {
    setBusy(true); setError("");
    try {
      const result = await apiRequest("/v1/communities", {method:"POST",body:JSON.stringify({name:communityDraftName.trim(),slug:communityDraftSlug.trim().toLowerCase(),description:"",visibility:"public"})}) as {community:{id:string;name:string;slug:string;description:string;visibility:string}};
      setCommunityDraftName(""); setCommunityDraftSlug(""); setMessage("Komunitas dibuat."); await loadCommunityWorkspace();
      await openNativeCommunity({...result.community,membership_role:"owner"});
    } catch (e) { setError(e instanceof Error ? e.message : "Komunitas gagal dibuat."); }
    finally { setBusy(false); }
  }
  async function joinNativeCommunity(item: typeof communityItems[number]) {
    setBusy(true); setError("");
    try { await apiRequest("/v1/communities/" + encodeURIComponent(item.id) + "/join",{method:"POST",body:"{}"}); setMessage("Anda bergabung dengan komunitas."); await loadCommunityWorkspace(); await openNativeCommunity({...item,membership_role:"member"}); }
    catch(e) { setError(e instanceof Error ? e.message : "Tidak dapat bergabung."); } finally { setBusy(false); }
  }
  async function publishCommunityPost() {
    if(!activeCommunity || !communityPostDraft.trim()) return;
    setBusy(true); setError("");
    try { await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/posts",{method:"POST",body:JSON.stringify({body:communityPostDraft.trim(),post_type:communityPostType})}); setCommunityPostDraft(""); await openNativeCommunity(activeCommunity); setMessage(communityPostType==="resource"?"Sumber daya diterbitkan.":"Diskusi diterbitkan."); }
    catch(e) { setError(e instanceof Error ? e.message : "Diskusi gagal diterbitkan."); } finally { setBusy(false); }
  }
  async function createNativeInvite() {
    if (!activeCommunity) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/invites", {method:"POST",body:JSON.stringify({role:"member",expires_in_hours:168})}) as {invite:{token:string;expires_at:string}};
      setCreatedInviteToken(result.invite.token);
      await Share.share({message:"Undangan komunitas Allpha: " + result.invite.token + "\nBerlaku sampai " + result.invite.expires_at});
      setMessage("Undangan dibuat. Token hanya ditampilkan saat dibuat; bagikan kepada penerima yang dituju.");
    } catch(e) { setError(e instanceof Error ? e.message + " — periksa hak moderator lalu coba lagi." : "Undangan gagal dibuat/dibagikan."); }
    finally { setBusy(false); }
  }
  async function acceptNativeInvite() {
    const token = inviteTokenDraft.trim();
    if (!token) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/v1/community-invites/" + encodeURIComponent(token) + "/accept", {method:"POST",body:"{}"});
      setInviteTokenDraft(""); setMessage("Undangan diterima. Komunitas kini tersedia di daftar Anda."); await loadCommunityWorkspace();
    } catch(e) { setError(e instanceof Error ? e.message + " — token mungkin kedaluwarsa, sudah dicabut, atau akun sudah menjadi anggota." : "Undangan tidak dapat diterima. Periksa token lalu coba lagi."); }
    finally { setBusy(false); }
  }
  async function toggleNativePostPin(post:{id:string;is_pinned?:boolean}) {
    if (!activeCommunity) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/posts/" + encodeURIComponent(post.id) + "/pin", {method:"PATCH",body:JSON.stringify({pinned:!post.is_pinned})});
      await openNativeCommunity(activeCommunity); setMessage(post.is_pinned ? "Pin sumber daya dilepas." : "Sumber daya disematkan.");
    } catch(e) { setError(e instanceof Error ? e.message + " — muat ulang dan coba lagi." : "Pin sumber daya gagal diperbarui."); }
    finally { setBusy(false); }
  }
  async function moderateNativePost(postId:string) {
    if (!activeCommunity) return;
    Alert.alert("Moderasi konten","Sembunyikan konten ini dari komunitas?",[
      {text:"Batal",style:"cancel"},
      {text:"Sembunyikan",style:"destructive",onPress:()=>{void (async()=>{setBusy(true);setError("");try{await apiRequest("/v1/communities/"+encodeURIComponent(activeCommunity.id)+"/posts/"+encodeURIComponent(postId)+"/moderation",{method:"PATCH",body:JSON.stringify({status:"hidden",reason:"Konten disembunyikan oleh moderator komunitas."})});await openNativeCommunity(activeCommunity);setMessage("Konten disembunyikan.");}catch(e){setError(e instanceof Error?e.message:"Moderasi gagal. Muat ulang lalu coba lagi.");}finally{setBusy(false);}})();}}
    ]);
  }
  async function createNativeMission() {
    if (!activeCommunity || !missionDraftTitle.trim()) return;
    const target = Number(missionDraftTarget);
    if (!Number.isInteger(target) || target < 1 || target > 100000) { setError("Target misi harus bilangan bulat 1–100000."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/missions", {method:"POST",body:JSON.stringify({title:missionDraftTitle.trim(),description:missionDraftDescription.trim(),target_count:target})});
      setMissionDraftTitle(""); setMissionDraftDescription(""); setMissionDraftTarget("1");
      const result = await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/missions") as {items?: typeof communityMissions};
      setCommunityMissions(result.items || []); setMessage("Misi komunitas dibuat.");
    } catch(e) { setError(e instanceof Error ? e.message : "Misi tidak dapat dibuat. Periksa peran komunitas lalu coba lagi."); }
    finally { setBusy(false); }
  }
  async function progressNativeMission(missionId:string) {
    if (!activeCommunity) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const idempotencyKey = createMessageId();
      await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/missions/" + encodeURIComponent(missionId) + "/progress?increment=1", {method:"POST",headers:{"Idempotency-Key":idempotencyKey},body:"{}"});
      const result = await apiRequest("/v1/communities/" + encodeURIComponent(activeCommunity.id) + "/missions") as {items?: typeof communityMissions};
      setCommunityMissions(result.items || []); setMessage("Progres misi diperbarui. Reward belum dikonfigurasi.");
    } catch(e) { setError(e instanceof Error ? e.message + " — coba muat ulang sebelum mengirim progres lagi." : "Progres misi gagal diperbarui. Muat ulang lalu coba lagi."); }
    finally { setBusy(false); }
  }
  async function createNativeWorkspace() {
    setBusy(true); setError("");
    try { const result=await apiRequest("/v1/workspaces",{method:"POST",body:JSON.stringify({title:workspaceDraftName.trim(),description:"",visibility:"private"})}) as {workspace:{id:string;title:string;membership_role?:string}}; setWorkspaceDraftName(""); setMessage("Workspace dibuat."); await loadCommunityWorkspace(); setActiveWorkspace(result.workspace); setActiveCommunity(null); setActiveWorkspaceDoc(null); await loadNativeWorkspaceDocs(result.workspace.id); }
    catch(e) { setError(e instanceof Error ? e.message : "Workspace gagal dibuat."); } finally { setBusy(false); }
  }
  async function openNativeWorkspace(item: typeof workspaceItems[number]) { setActiveWorkspace(item); setActiveCommunity(null); setActiveWorkspaceDoc(null); await loadNativeWorkspaceDocs(item.id); }
  async function loadNativeWorkspaceDocs(id:string) { try { const result=await apiRequest("/v1/workspaces/"+encodeURIComponent(id)+"/documents") as {items?:typeof workspaceDocs}; setWorkspaceDocs(result.items||[]); void apiRequest("/v1/workspaces/"+encodeURIComponent(id)+"/presence",{method:"POST",body:"{}"}).catch(()=>{}); } catch(e) { setError(e instanceof Error ? e.message : "Dokumen workspace gagal dimuat."); } }
  async function createNativeWorkspaceDoc() {
    if(!activeWorkspace || !workspaceDocTitle.trim()) return; setBusy(true); setError("");
    try { const result=await apiRequest("/v1/workspaces/"+encodeURIComponent(activeWorkspace.id)+"/documents",{method:"POST",body:JSON.stringify({title:workspaceDocTitle.trim(),body:workspaceDocBody})}) as {document:typeof activeWorkspaceDoc}; setWorkspaceDocTitle(""); setWorkspaceDocBody(""); if(result.document)setActiveWorkspaceDoc(result.document); await loadNativeWorkspaceDocs(activeWorkspace.id); setMessage("Dokumen workspace dibuat."); }
    catch(e) { setError(e instanceof Error ? e.message : "Dokumen gagal dibuat."); } finally { setBusy(false); }
  }
  async function saveNativeWorkspaceDoc() {
    if(!activeWorkspace || !activeWorkspaceDoc) return; setBusy(true); setError("");
    try { const result=await apiRequest("/v1/workspaces/"+encodeURIComponent(activeWorkspace.id)+"/documents/"+encodeURIComponent(activeWorkspaceDoc.id),{method:"PUT",body:JSON.stringify({title:workspaceDocTitle,body:workspaceDocBody,expected_version:activeWorkspaceDoc.version})}) as {document:typeof activeWorkspaceDoc}; if(result.document)setActiveWorkspaceDoc(result.document); await loadNativeWorkspaceDocs(activeWorkspace.id); setMessage("Versi dokumen tersimpan."); }
    catch(e) { setError(e instanceof Error ? e.message : "Dokumen konflik; buka ulang versi terbaru."); } finally { setBusy(false); }
  }

  async function loadCommunityAgentDirectory() {
    try { const result = await apiRequest("/v1/community-agent-directory") as {items?:{id:string;handle:string;display_name:string;version:number}[]}; const items=result.items||[]; setCommunityAgentDirectory(items); if(!selectedCommunityAgentId&&items[0])setSelectedCommunityAgentId(items[0].id); }
    catch(e) { setError(e instanceof Error?e.message:"Direktori Agent publik gagal dimuat."); }
  }
  async function loadCommunityResourceGrants(resourceType:"community"|"workspace", resourceId:string) {
    try { const result=await apiRequest("/v1/resource-grants?resource_type="+resourceType+"&resource_id="+encodeURIComponent(resourceId)) as {grants?:typeof communityResourceGrants}; setCommunityResourceGrants(result.grants||[]); }
    catch(e) { setError(e instanceof Error?e.message:"Daftar izin Agent gagal dimuat."); }
  }
  async function createCommunityResourceGrant() {
    const resource=activeCommunity?{type:"community" as const,id:activeCommunity.id}:activeWorkspace?{type:"workspace" as const,id:activeWorkspace.id}:null;
    if(!resource||!selectedCommunityAgentId)return;
    const allowed=resource.type==="community"?["read_published_content","create_agent_post","comment"]:["read_workspace_documents","comment"];
    const scopes=communityGrantScopes.filter(scope=>allowed.includes(scope));
    if(!scopes.length){setError("Pilih minimal satu scope yang tersedia.");return;}
    setBusy(true);setError("");setMessage("");
    try { await apiRequest("/v1/agents/"+encodeURIComponent(selectedCommunityAgentId)+"/resource-grants",{method:"POST",body:JSON.stringify({resource_type:resource.type,resource_id:resource.id,scopes})}); setMessage("Grant dan audit dicatat. Partisipasi Agent tetap dinonaktifkan sampai seluruh runtime dan review keamanan selesai."); await loadCommunityResourceGrants(resource.type,resource.id); }
    catch(e) { setError(e instanceof Error?e.message:"Izin Agent gagal disimpan."); }
    finally { setBusy(false); }
  }
  async function revokeCommunityResourceGrant(grant:typeof communityResourceGrants[number]) {
    const resource=activeCommunity?{type:"community" as const,id:activeCommunity.id}:activeWorkspace?{type:"workspace" as const,id:activeWorkspace.id}:null;
    if(!resource)return;
    Alert.alert("Cabut izin Agent","Akses Agent ke resource ini akan dicabut.",[
      {text:"Batal",style:"cancel"},
      {text:"Cabut izin",style:"destructive",onPress:()=>{void (async()=>{setBusy(true);setError("");try{await apiRequest("/v1/agents/"+encodeURIComponent(grant.agent_id)+"/resource-grants/"+encodeURIComponent(grant.id)+"/revoke",{method:"POST",body:JSON.stringify({reason:"Dicabut setelah konfirmasi pemilik resource."})});await loadCommunityResourceGrants(resource.type,resource.id);setMessage("Grant dicabut; audit tercatat.");}catch(e){setError(e instanceof Error?e.message:"Grant gagal dicabut.");}finally{setBusy(false);}})();}}
    ]);
  }
  const field = { ...s.input, flex: 1 } as const;
  return <ScrollView contentContainerStyle={s.page}><Brand/>
    <View style={s.card}>
      <Text style={s.kicker}>HUMAN IDENTITY</Text><Text style={s.title}>Identitas Anda</Text>
      <Text style={s.muted}>{session.user.email || session.user.id}</Text>
      <View style={{ flexDirection: "row", gap: 10 }}>
        <Button title="Profil" secondary={tab !== "profile"} onPress={() => { setTab("profile"); setError(""); setMessage(""); }}/>
        <Button title="Pengaturan & privasi" secondary={tab !== "settings"} onPress={() => { setTab("settings"); setError(""); setMessage(""); }}/><Button title="Notifikasi" secondary={tab !== "notifications"} onPress={() => { setTab("notifications"); setError(""); setMessage(""); }}/><Button title="Social Graph" secondary={tab !== "social"} onPress={() => { setTab("social"); setError(""); setMessage(""); void loadSocialGraph(); }}/><Button title="Riwayat persetujuan" secondary={tab !== "consents"} onPress={() => { setTab("consents"); setError(""); setMessage(""); void loadConsentHistory(); }}/><Button title="AI Agent & Passport" secondary={tab !== "agents"} onPress={() => { setTab("agents"); setError(""); setMessage(""); setAgentPassport(null); void loadAgents(); }}/><Button title="Skill Challenge" secondary={tab !== "challenges"} onPress={() => { setTab("challenges"); setError(""); setMessage(""); if (!challengeAgentId && agents[0]) void loadChallengeCatalog(agents[0].id); void loadChallengeRuns().catch(cause => setError(cause instanceof Error ? cause.message : "Riwayat challenge gagal dimuat.")); }}/><Button title="Creator Studio" secondary={tab !== "content"} onPress={() => { setTab("content"); setError(""); setMessage(""); void loadMyContent(); }}/><Button title="Feed sosial" secondary={tab !== "feed"} onPress={() => { setTab("feed"); setError(""); setMessage(""); void loadNativeFeed(true); }}/><Button title="Search & Discovery" secondary={tab !== "discovery"} onPress={() => { setTab("discovery"); setError(""); setMessage(""); setDiscoveryError(""); void loadDiscoveryTrends(); void loadDiscoveryRecommendations(); }}/><Button title="Pesan" secondary={tab !== "messages"} onPress={() => { setTab("messages"); setError(""); setMessage(""); void loadMessageConversations(); }}/><Button title="Komunitas & Workspace" secondary={tab !== "communities"} onPress={() => { setTab("communities"); setError(""); setMessage(""); void loadCommunityWorkspace(); }}/><Button title="Reels" secondary={tab !== "reels"} onPress={() => { setTab("reels"); setError(""); setMessage(""); void loadNativeReels(true); }}/><Button title="Stories" secondary={tab !== "stories"} onPress={() => { setTab("stories"); setError(""); setMessage(""); void loadNativeStories(); }}/>
      </View>
      {loading ? <ActivityIndicator color="#A5B4FC"/> : error ? <><Text accessibilityRole="alert" style={s.error}>{error}</Text><Button title="Coba lagi" onPress={() => setRetry(n => n + 1)}/></> :
      tab === "discovery" ? <>
        <Text style={s.kicker}>ENG-P17 · SEARCH & DISCOVERY</Text><Text style={s.title}>Cari di Allpha</Text>
        <Text style={s.muted}>Hasil saat ini mencakup konten yang dipublikasikan dan disetujui, mengikuti visibilitas, follow, block, dan mute. Pencarian profil/Agent belum termasuk cakupan ini.</Text>
        <TextInput accessibilityLabel="Cari konten" value={discoveryQuery} onChangeText={setDiscoveryQuery} maxLength={100} style={s.input} placeholder="Cari topik atau kata kunci…" placeholderTextColor="#8B94AC" returnKeyType="search" onSubmitEditing={() => void runDiscoverySearch()}/>
        <Button title={discoveryBusy ? "Mencari…" : "Cari"} disabled={discoveryBusy || discoveryQuery.trim().length < 2} onPress={() => void runDiscoverySearch()}/>
        {!!discoveryError && <Text accessibilityRole="alert" style={s.error}>{discoveryError}</Text>}
        {discoveryItems.length === 0 && !discoveryBusy && <Text style={s.muted}>Belum ada hasil pencarian.</Text>}
        {discoveryItems.map(item => <View key={item.id} style={s.socialRow}><Text style={s.body}>{item.body}</Text><Text style={s.muted}>{item.content_type} · {new Date(item.published_at || item.created_at).toLocaleString()}</Text></View>)}
        <Text style={s.title}>Tren dari konten terbaru</Text>
        {discoveryTrendsBusy ? <ActivityIndicator accessibilityLabel="Memuat tren" color="#A5B4FC"/> : discoveryTrendsError ? <View accessibilityRole="alert" style={s.socialRow}><Text style={s.error}>{discoveryTrendsError}</Text><Button title="Coba lagi" secondary onPress={() => void loadDiscoveryTrends()}/></View> : discoveryTrends.length ? discoveryTrends.map(item => <Button key={item.topic} title={"#" + item.topic + " · " + item.content_count} secondary onPress={() => { setDiscoveryQuery(item.topic); void runDiscoverySearch(item.topic); }}/>) : <Text style={s.muted}>Tren muncul saat ada konten yang dapat diakses.</Text>}
        <Text style={s.title}>Rekomendasi untuk Anda</Text><Text style={s.muted}>Mengikuti ranking feed kanonis dan preferensi personalisasi akun.</Text>
        {discoveryRecommendationsBusy ? <ActivityIndicator accessibilityLabel="Memuat rekomendasi" color="#A5B4FC"/> : discoveryRecommendationsError ? <View accessibilityRole="alert" style={s.socialRow}><Text style={s.error}>{discoveryRecommendationsError}</Text><Button title="Coba lagi" secondary onPress={() => void loadDiscoveryRecommendations()}/></View> : discoveryRecommendations.length ? discoveryRecommendations.map(item => <View key={item.id} style={s.socialRow}><Text style={s.body}>{item.body || "Konten"}</Text><Text style={s.muted}>{item.content_type} · {new Date(item.published_at || item.created_at).toLocaleString()}</Text></View>) : <Text style={s.muted}>Belum ada rekomendasi yang dapat ditampilkan.</Text>}
      </>  : tab === "messages" ? <>
        <Text style={s.kicker}>ENG-P18 · MESSAGING & DELIVERY</Text><Text style={s.title}>Pesan Human / Agent</Text>
        <Text style={s.muted}>Percakapan privat melalui API kanonis dengan status delivery/read dan realtime: {messageRealtimeStatus}.</Text>
        <View style={{ flexDirection: "row", gap: 8 }}><TextInput accessibilityLabel="UUID pengguna penerima" value={messageRecipient} onChangeText={setMessageRecipient} autoCapitalize="none" style={[field,{flex:1}]} placeholder="UUID penerima manusia" placeholderTextColor="#8B94AC"/><Button title="Baru" disabled={messageBusy || !messageRecipient.trim()} onPress={() => void startMessageConversation()}/></View>
        <Button title={messageBusy?"Memuat…":"Muat ulang percakapan"} secondary disabled={messageBusy} onPress={() => void loadMessageConversations()}/>
        {!!messageError && <Text accessibilityRole="alert" style={s.error}>{messageError}</Text>}
        {messageConversations.map(c => <Button key={c.id} title={(activeConversation?.id===c.id?"✓ ":"")+(c.title || (c.kind==="agent"?"Percakapan Agent":"Percakapan Human"))+" · "+(c.last_message?.body || "Belum ada pesan")} secondary={activeConversation?.id!==c.id} onPress={() => void openMessageConversation(c)}/>)}
        {activeConversation && <View style={s.socialRow}><Text style={s.title}>{activeConversation.title || "Percakapan"}</Text>{conversationMessages.map(m => <View key={m.id} style={s.socialRow}><Text style={s.body}>{m.body}</Text><Text style={s.muted}>{new Date(m.created_at).toLocaleString("id-ID")} · {m.delivery_status}</Text></View>)}<TextInput accessibilityLabel="Tulis pesan" value={messageDraft} onChangeText={setMessageDraft} multiline maxLength={10000} style={[field,{minHeight:70,textAlignVertical:"top"}]} placeholder="Tulis pesan…" placeholderTextColor="#8B94AC"/><Button title={messageBusy?"Mengirim…":"Kirim pesan"} disabled={messageBusy || !messageDraft.trim()} onPress={() => void sendNativeMessage()}/></View>}
      </> : tab === "communities" ? <>
        <Text style={s.kicker}>ENG-P19 · COMMUNITIES & WORKSPACES</Text><Text style={s.title}>Komunitas & Kolaborasi</Text>
        <Text style={s.muted}>Akses data melalui FastAPI. Keanggotaan komunitas mengatur diskusi; workspace privat membatasi dokumen pada anggota.</Text>
        <Text style={s.kicker}>BUAT KOMUNITAS PUBLIK</Text>
        <TextInput accessibilityLabel="Nama komunitas" value={communityDraftName} onChangeText={value=>{setCommunityDraftName(value);if(!communityDraftSlug)setCommunityDraftSlug(value.toLowerCase().replace(/[^a-z0-9-]+/g,"-").replace(/^-|-$/g,""));}} style={s.input} placeholder="Nama komunitas" placeholderTextColor="#8B94AC"/>
        <TextInput accessibilityLabel="Slug komunitas" autoCapitalize="none" value={communityDraftSlug} onChangeText={setCommunityDraftSlug} style={s.input} placeholder="slug-komunitas" placeholderTextColor="#8B94AC"/>
        <Button title="Buat komunitas" disabled={busy||communityDraftName.trim().length<2||communityDraftSlug.trim().length<3} onPress={()=>void createNativeCommunity()}/>
        <Text style={s.kicker}>KOMUNITAS</Text>
        {communityItems.length===0?<Text style={s.muted}>Belum ada komunitas yang dapat diakses.</Text>:communityItems.map(item=><View key={item.id} style={s.socialRow}><Button title={(activeCommunity?.id===item.id?"✓ ":"")+item.name+" · "+(item.membership_role||"publik")} secondary={activeCommunity?.id!==item.id} onPress={()=>void openNativeCommunity(item)}/>{!item.membership_role&&item.visibility==="public"&&<Button title="Gabung" secondary disabled={busy} onPress={()=>void joinNativeCommunity(item)}/>}</View>)}
        {activeCommunity&&<View style={s.socialRow}><Text style={s.title}>{activeCommunity.name}</Text>{communityPosts.map(post=><View key={post.id} style={s.socialRow}>{!!post.is_pinned&&<Text style={s.kicker}>SUMBER DAYA DISEMATKAN</Text>}<Text style={s.body}>{post.body}</Text><Text style={s.muted}>{post.post_type} · {new Date(post.created_at).toLocaleString("id-ID")}</Text>{(activeCommunity.membership_role==="owner"||activeCommunity.membership_role==="moderator")&&<View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}>{post.post_type==="resource"&&<Button title={post.is_pinned?"Lepas pin":"Sematkan sumber daya"} secondary onPress={()=>void toggleNativePostPin(post)}/>}<Button title="Sembunyikan" secondary onPress={()=>moderateNativePost(post.id)}/></View>}</View>)}{!!activeCommunity.membership_role&&<><View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}><Button title={communityPostType==="discussion"?"✓ Diskusi":"Diskusi"} secondary={communityPostType!=="discussion"} onPress={()=>setCommunityPostType("discussion")}/><Button title={communityPostType==="resource"?"✓ Sumber daya":"Sumber daya"} secondary={communityPostType!=="resource"} onPress={()=>setCommunityPostType("resource")}/></View><TextInput accessibilityLabel="Tulis diskusi atau sumber daya komunitas" value={communityPostDraft} onChangeText={setCommunityPostDraft} multiline maxLength={5000} style={[field,{minHeight:80}]} placeholder="Bagikan ide atau sumber daya…" placeholderTextColor="#8B94AC"/><Button title={communityPostType==="resource"?"Terbitkan sumber daya":"Terbitkan diskusi"} disabled={busy||!communityPostDraft.trim()} onPress={()=>void publishCommunityPost()}/></>}</View>}
        {(activeCommunity?.membership_role==="owner"||activeCommunity?.membership_role==="moderator")&&<Button title="Buat & bagikan undangan" secondary disabled={busy} onPress={()=>void createNativeInvite()}/>}
        {!!createdInviteToken&&<View style={s.socialRow}><Text style={s.muted}>Token undangan terbaru tersedia untuk dibagikan ulang.</Text><Button title="Bagikan ulang token" secondary onPress={()=>void Share.share({message:"Undangan komunitas Allpha: "+createdInviteToken})}/></View>}
        <Text style={s.kicker}>TERIMA UNDANGAN</Text><TextInput accessibilityLabel="Token undangan komunitas" value={inviteTokenDraft} onChangeText={setInviteTokenDraft} autoCapitalize="none" style={s.input} placeholder="Tempel token undangan" placeholderTextColor="#8B94AC"/><Button title="Terima undangan" disabled={busy||!inviteTokenDraft.trim()} onPress={()=>void acceptNativeInvite()}/>
        <Text style={s.kicker}>WORKSPACE PRIVAT</Text><View style={{flexDirection:"row",gap:8}}><TextInput accessibilityLabel="Nama workspace" value={workspaceDraftName} onChangeText={setWorkspaceDraftName} style={[field,{flex:1}]} placeholder="Nama workspace" placeholderTextColor="#8B94AC"/><Button title="Buat" disabled={busy||workspaceDraftName.trim().length<2} onPress={()=>void createNativeWorkspace()}/></View>
        {workspaceItems.map(item=><Button key={item.id} title={(activeWorkspace?.id===item.id?"✓ ":"")+item.title+" · "+(item.membership_role||"anggota")} secondary={activeWorkspace?.id!==item.id} onPress={()=>void openNativeWorkspace(item)}/>)}
        {activeWorkspace&&<View style={s.socialRow}><Text style={s.title}>{activeWorkspace.title}</Text>{workspaceDocs.map(d=><Button key={d.id} title={d.title+" · v"+d.version} secondary={activeWorkspaceDoc?.id!==d.id} onPress={()=>{setActiveWorkspaceDoc(d);setWorkspaceDocTitle(d.title);setWorkspaceDocBody(d.body||"");void apiRequest("/v1/workspaces/"+encodeURIComponent(activeWorkspace.id)+"/documents/"+encodeURIComponent(d.id)).then((r:any)=>{if(r.document){setActiveWorkspaceDoc(r.document);setWorkspaceDocTitle(r.document.title);setWorkspaceDocBody(r.document.body||"");}}).catch(e=>setError(e instanceof Error?e.message:"Dokumen gagal dimuat."));}}/>)}<TextInput accessibilityLabel="Judul dokumen" value={workspaceDocTitle} onChangeText={setWorkspaceDocTitle} style={s.input} placeholder="Judul dokumen" placeholderTextColor="#8B94AC"/><TextInput accessibilityLabel="Isi dokumen" value={workspaceDocBody} onChangeText={setWorkspaceDocBody} multiline maxLength={50000} style={[s.input,{minHeight:100,textAlignVertical:"top"}]} placeholder="Isi dokumen" placeholderTextColor="#8B94AC"/><Button title="Buat dokumen baru" disabled={busy||!workspaceDocTitle.trim()||!!activeWorkspaceDoc} onPress={()=>void createNativeWorkspaceDoc()}/>{!!activeWorkspaceDoc&&<Button title={"Simpan versi baru v"+(activeWorkspaceDoc.version+1)} disabled={busy||!workspaceDocTitle.trim()} onPress={()=>void saveNativeWorkspaceDoc()}/>}</View>}
        {((activeCommunity?.membership_role==="owner"||activeCommunity?.membership_role==="moderator")||activeWorkspace?.membership_role==="owner")&&<View style={s.socialRow}>
<Text style={s.title}>Izin Agent (ADR-0020)</Text>
<Text style={s.muted}>Pilih Agent publik dan berikan scope eksplisit. Tidak ada pewarisan akses ke private memory, DM, atau dokumen lain. Runtime Agent masih dinonaktifkan.</Text>
<Button title="Muat direktori Agent publik" secondary disabled={busy} onPress={()=>void loadCommunityAgentDirectory()}/>
{communityAgentDirectory.map(agent=><Button key={agent.id} title={(selectedCommunityAgentId===agent.id?"✓ ":"")+agent.display_name+" · @"+agent.handle+" · v"+agent.version} secondary={selectedCommunityAgentId!==agent.id} onPress={()=>setSelectedCommunityAgentId(agent.id)}/>)}
<Text style={s.muted}>Scope yang tersedia</Text>
{(activeCommunity?["read_published_content","create_agent_post","comment"]:["read_workspace_documents","comment"]).map(scope=><Button key={scope} title={(communityGrantScopes.includes(scope)?"✓ ":"")+scope} secondary={!communityGrantScopes.includes(scope)} onPress={()=>setCommunityGrantScopes(old=>old.includes(scope)?old.filter(x=>x!==scope):[...old,scope])}/>)}
<Button title="Setujui scope Agent" disabled={busy||!selectedCommunityAgentId} onPress={()=>void createCommunityResourceGrant()}/>
<Button title="Muat grant resource ini" secondary disabled={busy} onPress={()=>{const r=activeCommunity?{type:"community" as const,id:activeCommunity.id}:activeWorkspace?{type:"workspace" as const,id:activeWorkspace.id}:null;if(r)void loadCommunityResourceGrants(r.type,r.id)}}/>
{communityResourceGrants.map(grant=><View key={grant.id} style={s.socialRow}><Text style={s.muted}>{grant.agent_id} · {grant.scopes.join(", ")} · {grant.status}</Text>{grant.status==="active"&&<Button title="Cabut izin" secondary disabled={busy} onPress={()=>void revokeCommunityResourceGrant(grant)}/>}</View>)}
</View>}
<Text style={s.kicker}>MISI KOMUNITAS</Text>
        {communityMissions.length === 0 && <Text style={s.muted}>Belum ada misi aktif untuk komunitas ini.</Text>}
        {communityMissions.map(mission => {
          const progress = mission.my_progress?.progress_count || 0;
          const complete = mission.my_progress?.status === "completed" || progress >= mission.target_count;
          return <View key={mission.id} style={s.socialRow}>
            <Text style={s.body}>{mission.title}</Text>
            {!!mission.description && <Text style={s.muted}>{mission.description}</Text>}
            <Text style={s.muted}>Progres {Math.min(progress,mission.target_count)}/{mission.target_count} · {complete ? "Selesai" : "Berjalan"}</Text>
            <Button title={complete ? "Misi selesai" : "Tambah progres +1"} secondary disabled={busy || complete} onPress={() => void progressNativeMission(mission.id)}/>
          </View>;
        })}
        {(activeCommunity?.membership_role === "owner" || activeCommunity?.membership_role === "moderator") && <View style={s.socialRow}>
          <Text style={s.title}>Buat misi</Text>
          <TextInput accessibilityLabel="Judul misi" value={missionDraftTitle} onChangeText={setMissionDraftTitle} maxLength={120} style={s.input} placeholder="Judul misi" placeholderTextColor="#8B94AC"/>
          <TextInput accessibilityLabel="Deskripsi misi" value={missionDraftDescription} onChangeText={setMissionDraftDescription} multiline maxLength={2000} style={s.input} placeholder="Deskripsi (opsional)" placeholderTextColor="#8B94AC"/>
          <TextInput accessibilityLabel="Target progres misi" value={missionDraftTarget} onChangeText={setMissionDraftTarget} keyboardType="number-pad" maxLength={6} style={s.input} placeholder="Target progres" placeholderTextColor="#8B94AC"/>
          <Button title="Buat misi" disabled={busy || missionDraftTitle.trim().length < 2} onPress={() => void createNativeMission()}/>
        </View>}
        <Text style={s.muted}>Reward finansial tidak diterbitkan otomatis. Progres diproses oleh API dengan kunci idempotensi.</Text>
      </> : tab === "stories" ? <>
        <Text style={s.kicker}>ENG-P16 · STORIES & MOMENTS</Text><Text style={s.title}>Momen sementara</Text>
        <Text style={s.muted}>Story masuk moderasi sebelum tayang. Kedaluwarsa ditetapkan server saat publikasi disetujui; konten yang sudah berakhir tidak muncul di feed.</Text>
        <TextInput accessibilityLabel="Isi Story" value={storyBody} onChangeText={setStoryBody} multiline maxLength={2000} style={[field,{minHeight:90,textAlignVertical:"top",paddingTop:12}]} placeholder="Apa yang sedang terjadi? (opsional jika ada media)" placeholderTextColor="#8B94AC"/>
        <Text style={s.kicker}>AUDIENCE</Text><View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}><Button title={storyVisibility==="public"?"✓ Publik":"Publik"} secondary={storyVisibility!=="public"} onPress={()=>setStoryVisibility("public")}/><Button title={storyVisibility==="followers"?"✓ Pengikut":"Pengikut"} secondary={storyVisibility!=="followers"} onPress={()=>setStoryVisibility("followers")}/><Button title={storyVisibility==="private"?"✓ Pribadi":"Pribadi"} secondary={storyVisibility!=="private"} onPress={()=>setStoryVisibility("private")}/></View>
        <Text style={s.kicker}>MASA AKTIF</Text><View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}>{([6,12,24,48,72,168] as const).map(hours=><Button key={hours} title={(storyTtl===hours?"✓ ":"")+(hours===168?"7 hari":hours+" jam")} secondary={storyTtl!==hours} onPress={()=>setStoryTtl(hours)}/>)}</View>
        <Button title={storyFile ? "Media: "+storyFile.name : "Pilih gambar/video"} secondary disabled={storyBusy} onPress={()=>void chooseStoryMedia()}/>{storyFile && <Text style={s.muted}>{storyFile.mimeType} · {storyFile.size ? (storyFile.size/1048576).toFixed(2)+" MB" : "ukuran tidak diketahui"}</Text>}
        <Button title={storyBusy ? "Memproses…" : "Kirim Story ke moderasi"} disabled={storyBusy || (!storyBody.trim() && !storyFile)} onPress={()=>void createNativeStory()}/><Button title="Muat ulang Stories" secondary disabled={storyBusy} onPress={()=>void loadNativeStories()}/>
        <Text style={s.kicker}>MOMEN AKTIF</Text>{activeStories.length===0 ? <Text style={s.muted}>Belum ada Story aktif yang dapat Anda lihat.</Text> : activeStories.map(story=><View key={story.id} style={s.socialRow}><Text style={s.body}>{story.body || "Momen media"}</Text><Text style={s.muted}>{story.visibility} · {story.expires_at ? "Berakhir "+new Date(story.expires_at).toLocaleString("id-ID") : "Expiry belum tersedia"}</Text>{(story.media||[]).map(media=>media.preview_url?<Button key={media.id} title={"Buka "+media.filename} secondary onPress={()=>void Linking.openURL(media.preview_url!)}/>:null)}</View>)}
        <Text style={s.kicker}>STORIES SAYA</Text>{storyItems.length===0 ? <Text style={s.muted}>Belum ada Story pada akun ini.</Text> : storyItems.map(story=><View key={story.id} style={s.socialRow}><Text style={s.body}>{story.status} · {story.moderation_status}</Text><Text style={s.muted}>{story.body || "Momen media"} · {story.expires_at ? "Expiry: "+new Date(story.expires_at).toLocaleString("id-ID") : "Expiry dimulai setelah publikasi disetujui"}</Text>{story.status!=="archived" && story.status!=="deleted" && <Button title="Arsipkan Story" secondary disabled={storyBusy} onPress={()=>void archiveNativeStory(story)}/>}</View>)}
      </> : tab === "profile" ? profile ? <>
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
      tab === "notifications" ? <NotificationsInbox session={session} pushStatus={pushRegistrationStatus} onPushPreferenceChange={() => setPushRegistrationRetry(value => value + 1)}/> :
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
          <Text style={s.kicker}>PILIH BIDANG & SKILL AI AGENT</Text>
          <TextInput accessibilityLabel="Cari 500 blueprint + Agency Agents" value={skillCatalogQuery} onChangeText={setSkillCatalogQuery} maxLength={100} style={field} placeholder="Cari di 500 Skill…" placeholderTextColor="#8B94AC"/>
          {skillCatalogLoading ? <ActivityIndicator color="#A5B4FC"/> : skillCatalog.filter(item => !skillCatalogQuery || (item.name + " " + item.category_label + " " + item.description).toLowerCase().includes(skillCatalogQuery.toLowerCase())).slice(0, 12).map(item => <Button key={item.key} title={(selectedCatalogSkill === item.key ? "✓ " : "") + item.name + " · " + item.category_label} secondary onPress={() => setSelectedCatalogSkill(item.key)}/>)}
          {selectedCatalogSkill ? <Text style={s.muted}>Skill dipilih: {skillCatalog.find(item => item.key === selectedCatalogSkill)?.name} · Role AI Character: {skillCatalog.find(item => item.key === selectedCatalogSkill)?.character_profile.display_role}. Asset GLB tetap perlu diverifikasi sebelum dirender.</Text> : <Text style={s.muted}>Pilih satu Skill untuk menentukan bidang dan role karakter AI.</Text>}
          <Button title={busy ? "Membuat…" : "Buat Agent privat"} disabled={busy || skillCatalogLoading || !selectedCatalogSkill || agentName.trim().length < 2 || !/^[a-z0-9_]{3,30}$/.test(agentHandle.trim())} onPress={() => void createAgent()}/>
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
        <Text style={s.muted}>Challenge memakai snapshot Agent/Skill dan rubrik yang dipatok server. Jawaban dinilai oleh evaluator deterministik; tidak ada skor atau reward yang dapat ditentukan oleh klien. Skill dieksekusi server-side melalui Agent Runtime dan Model Router. Challenge tidak dapat diterbitkan atau dieksekusi jika route/policy belum dikonfigurasi.</Text>
        <Text style={s.muted}>Agent</Text>
        {agents.map(agent => <Button key={agent.id} title={(challengeAgentId === agent.id ? "✓ " : "") + agent.display_name + " · " + agent.handle} secondary={challengeAgentId !== agent.id} onPress={() => void loadChallengeCatalog(agent.id)}/>)}
        <Text style={s.muted}>Skill</Text>
        {challengeSkills.map(skill => <Button key={skill.id} title={(challengeSkillId === skill.id ? "✓ " : "") + skill.name + " · v" + skill.version + " · " + skill.status} secondary={challengeSkillId !== skill.id} onPress={() => { setChallengeSkillId(skill.id); setChallengeTestKey(""); setChallengeRun(null); setChallengeNonce(""); }}/>)}
        <Text style={s.muted}>Test case</Text>
        {(challengeSkills.find(skill => skill.id === challengeSkillId)?.tests ?? []).filter(item => typeof item.key === "string").map(item => <Button key={String(item.key)} title={(challengeTestKey === item.key ? "✓ " : "") + String(item.key)} secondary={challengeTestKey !== item.key} onPress={() => setChallengeTestKey(String(item.key))}/>)}
        {challengeSkills.find(skill => skill.id === challengeSkillId)?.hidden_challenges_available && <Button title={challengeTestKey === "__hidden__" ? "✓ Tantangan tersembunyi acak" : "Tantangan tersembunyi acak"} secondary={challengeTestKey !== "__hidden__"} onPress={() => setChallengeTestKey("__hidden__")}/>} 
        {challengeSkillId && !(challengeSkills.find(skill => skill.id === challengeSkillId)?.evaluation_rubric_available) && <Text style={s.warning}>Rubrik evaluasi belum tersedia pada Skill ini.</Text>}
        <Button title={challengeBusy ? "Memproses…" : "Terbitkan challenge"} disabled={challengeBusy || !challengeAgentId || !challengeSkillId || !challengeTestKey} onPress={() => void issueNativeChallenge()}/>
        {challengeRun && <View style={s.socialRow}><Text style={s.kicker}>RUN {challengeRun.id}</Text><Text style={s.body}>Status: {challengeRun.status} · Agent v{challengeRun.agent_version} · Skill v{challengeRun.skill_version}</Text><Text style={s.muted}>Input challenge: {JSON.stringify(challengeRun.challenge_input)}</Text><Text style={s.muted}>Output dibuat server-side dari snapshot Skill; aplikasi tidak mengirim skor atau output kandidat.</Text><Button title="Jalankan Skill & evaluasi" disabled={challengeBusy || !challengeNonce} onPress={() => void submitNativeChallenge()}/>{challengeRun.evaluation_result && <Text style={s.muted}>Hasil: {JSON.stringify(challengeRun.evaluation_result)}{ "\n" }Evidence SHA-256: {challengeRun.evidence_digest || "belum tersedia"}{ "\n" }Runtime evidence: {challengeRun.runtime_evidence_digest || "belum tersedia"}</Text>}<Button title="Bandingkan versi sebelumnya" secondary disabled={challengeBusy || !challengeRun.runtime_evidence_digest} onPress={() => void compareNativeChallenge()}/>{challengeComparison && <Text style={s.muted}>{JSON.stringify(challengeComparison)}</Text>}<TextInput accessibilityLabel="Alasan keputusan pemilik" value={challengeReleaseReason} onChangeText={setChallengeReleaseReason} style={s.input} placeholder="Alasan release atau hold (min. 8 karakter)" placeholderTextColor="#8B94AC"/><Button title="Catat keputusan release" disabled={challengeBusy || challengeRun.status !== "passed" || !challengeComparison || challengeReleaseReason.trim().length < 8 || !!challengeRun.release_decision} onPress={() => void decideNativeChallenge("release")}/><Button title="Catat keputusan hold" secondary disabled={challengeBusy || !challengeRun.runtime_evidence_digest || challengeReleaseReason.trim().length < 8 || !!challengeRun.release_decision} onPress={() => void decideNativeChallenge("hold")}/>{challengeRun.release_decision && <Text style={s.muted}>Keputusan pemilik: {challengeRun.release_decision} — {challengeRun.release_decision_reason}</Text>}</View>}
        <Text style={s.kicker}>RIWAYAT ({challengeRuns.length})</Text>
        {challengeRuns.map(run => <View key={run.id} style={s.socialRow}><Text style={s.body}>{run.challenge_key} · {run.status}</Text><Text style={s.muted}>Agent v{run.agent_version} · Skill v{run.skill_version} · {new Date(run.created_at).toLocaleString()}</Text></View>)}
        <Text style={s.muted}>Achievement hanya berupa bukti non-moneter. Reward finansial/AI Credits tidak diterbitkan sebelum kebijakan resmi dan ledger kanonis mengizinkan.</Text>
      </> : tab === "feed" ? <>
        <Text style={s.kicker}>ENG-P14 · SOCIAL FEED</Text><Text style={s.title}>Feed sosial</Text>
        <Text style={s.muted}>Konten publik yang telah disetujui. Ranking menghormati relasi follow, block, mute, dan preferensi Anda.</Text>
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
          <Button title={feedMode === "for_you" ? "✓ Untuk Anda" : "Untuk Anda"} secondary={feedMode !== "for_you"} disabled={feedBusy} onPress={() => void saveNativeFeedPreferences(feedPersonalization, "for_you")}/>
          <Button title={feedMode === "recent" ? "✓ Terbaru" : "Terbaru"} secondary={feedMode !== "recent"} disabled={feedBusy} onPress={() => void saveNativeFeedPreferences(feedPersonalization, "recent")}/>
          <Button title={feedPersonalization ? "Personalisasi: aktif" : "Personalisasi: mati"} secondary={!feedPersonalization} disabled={feedBusy} onPress={() => void saveNativeFeedPreferences(!feedPersonalization, feedMode)}/>
          <Button title="Muat ulang" secondary disabled={feedBusy} onPress={() => void loadNativeFeed(true)}/>
        </View>
        {feedBusy && <View accessibilityRole="progressbar" style={{ paddingVertical: 10, alignItems: "center" }}><ActivityIndicator color="#A5B4FC"/><Text style={s.muted}>Memuat feed…</Text></View>}
        {!feedBusy && feedItems.length === 0 && <Text style={s.muted}>Belum ada konten publik yang disetujui.</Text>}
        {feedItems.map(item => <View key={item.id} style={s.socialRow}>
          <Text style={s.muted}>Creator {item.owner_id.slice(0, 8)} · {new Date(item.published_at || item.created_at).toLocaleString()}</Text>
          {!!item.body && <Text style={s.body}>{item.body}</Text>}
          {item.media?.map(media => media.preview_url ? <Button key={media.id} title={"Buka " + media.filename} secondary onPress={() => void Linking.openURL(media.preview_url!)}/> : null)}
          <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
            <Button title={(item.viewer_reaction ? "♥ Disukai" : "♡ Suka") + " · " + (item.engagement?.likes ?? 0)} secondary={!!item.viewer_reaction} disabled={feedBusy} onPress={() => void nativeFeedAction(item, "like")}/>
            <Button title={(item.saved ? "Tersimpan" : "Simpan") + " · " + (item.engagement?.saves ?? 0)} secondary={!!item.saved} disabled={feedBusy} onPress={() => void nativeFeedAction(item, "save")}/>
            <Button title={"Bagikan · " + (item.engagement?.shares ?? 0)} secondary disabled={feedBusy} onPress={() => void shareNativeContent(item)}/>
            <Button title="Laporkan" secondary disabled={feedBusy} onPress={() => chooseNativeReportReason(item)}/>
            <Button title={feedCommentsOpen[item.id] ? "Tutup komentar" : "Lihat komentar"} secondary disabled={feedBusy} onPress={() => void toggleNativeComments(item)}/>
          </View>
          {feedCommentsOpen[item.id] && (feedComments[item.id] ?? []).map(comment => <View key={comment.id} style={s.socialRow}>
            <Text style={s.muted}>{comment.actor_user_id.slice(0, 8)} · {new Date(comment.created_at).toLocaleString()}</Text>
            <Text style={s.body}>{comment.body}</Text>
          </View>)}
          <TextInput accessibilityLabel="Tulis komentar feed" value={feedCommentDrafts[item.id] || ""} onChangeText={value => setFeedCommentDrafts(current => ({ ...current, [item.id]: value }))} maxLength={2000} style={field} placeholder="Tulis komentar…" placeholderTextColor="#8B94AC"/>
          <Button title="Kirim komentar" disabled={feedBusy || !(feedCommentDrafts[item.id] || "").trim()} onPress={() => void submitNativeFeedComment(item)}/>
          <Text style={s.muted}>{item.engagement?.comments ?? 0} komentar · sinyal ranking: terbaru, follow, engagement</Text>
        </View>)}
        {feedCursor && <Button title="Muat feed berikutnya" secondary disabled={feedBusy} onPress={() => void loadNativeFeed(false)}/>}
      </> : tab === "reels" ? <>
        <Text style={s.kicker}>ENG-P15 · REELS</Text><Text style={s.title}>Video pendek & audio</Text>
        <Text style={s.muted}>Konten yang lolos moderasi diambil dari API Reels kanonis. Pemutaran memakai URL signed berjangka pendek; tombol putar membuka pemutar media perangkat.</Text>
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
          <Button title="Muat ulang" secondary disabled={reelsBusy} onPress={() => void loadNativeReels(true)}/>
        </View>
        {reelsBusy && <View accessibilityRole="progressbar" style={{ paddingVertical: 10, alignItems: "center" }}><ActivityIndicator color="#A5B4FC"/><Text style={s.muted}>Memuat Reels…</Text></View>}
        {!reelsBusy && reelsItems.length === 0 && <Text style={s.muted}>Belum ada video/audio publik yang disetujui.</Text>}
        {reelsItems.map(item => <View key={item.id} style={[s.socialRow, { gap: 10 }]}>
          <Text style={s.muted}>Creator {item.owner_id.slice(0, 8)} · {new Date(item.published_at || item.created_at).toLocaleString()}</Text>
          {!!item.body && <Text style={s.body}>{item.body}</Text>}
          {item.media?.map(media => media.preview_url ? <View key={media.id} style={s.socialRow}>
            <Text style={s.body}>{media.media_type.startsWith("audio/") ? "♫ Audio" : "▶ Video"} · {media.filename}</Text>
            <Button title={media.media_type.startsWith("audio/") ? "Putar audio" : "Putar video"} onPress={() => void Linking.openURL(media.preview_url!)} />
          </View> : null)}
          <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
            <Button title={(item.viewer_reaction ? "♥ Disukai" : "♡ Suka") + " · " + (item.engagement?.likes ?? 0)} secondary={!!item.viewer_reaction} disabled={reelsBusy} onPress={() => void nativeFeedAction(item, "like")}/>
            <Button title={"Bagikan · " + (item.engagement?.shares ?? 0)} secondary disabled={reelsBusy} onPress={() => void shareNativeContent(item)}/>
          </View>
        </View>)}
        {reelsCursor && <Button title="Muat Reels berikutnya" secondary disabled={reelsBusy} onPress={() => void loadNativeReels(false)}/>}
      </> : tab === "content" ? <>
        <Text style={s.kicker}>ENG-P13 · CREATOR STUDIO</Text><Text style={s.title}>Buat konten</Text>
        <Text style={s.muted}>Draft teks atau media disimpan melalui API. Konten publik baru tayang setelah moderasi.</Text>
        <TextInput accessibilityLabel="Isi konten" value={contentBody} onChangeText={setContentBody} multiline maxLength={10000} style={[s.input, { minHeight: 110, textAlignVertical: "top", paddingTop: 12 }]} placeholder="Apa yang ingin kamu bagikan?" placeholderTextColor="#8B94AC"/>
        <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}><Button title={contentVisibility === "public" ? "✓ Publik" : "Publik"} secondary={contentVisibility !== "public"} onPress={() => setContentVisibility("public")}/><Button title={contentVisibility === "followers" ? "✓ Pengikut" : "Pengikut"} secondary={contentVisibility !== "followers"} onPress={() => setContentVisibility("followers")}/><Button title={contentVisibility === "private" ? "✓ Pribadi" : "Pribadi"} secondary={contentVisibility !== "private"} onPress={() => setContentVisibility("private")}/></View>
        <Button title={contentFile ? "Media: " + contentFile.name : "Pilih gambar/video"} secondary onPress={() => void chooseContentMedia()}/>
        {contentFile && <Text style={s.muted}>{contentFile.mimeType} · {contentFile.size ? (contentFile.size / 1048576).toFixed(2) + " MB" : "ukuran tidak diketahui"}</Text>}
        <Button title={contentBusy ? "Memproses…" : "Simpan draft"} disabled={contentBusy || (!contentBody.trim() && !contentFile)} onPress={() => void createNativeContentDraft()}/>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}><Text style={s.kicker}>KONTEN SAYA ({contentItems.length})</Text><Button title="Muat ulang" secondary disabled={contentBusy} onPress={() => void loadMyContent()}/></View>
        {contentItems.length === 0 ? <Text style={s.muted}>Belum ada konten.</Text> : contentItems.map(item => <View key={item.id} style={s.socialRow}><Text style={s.body}>{item.body || item.media?.map(media => media.filename).join(", ") || "Konten media"}</Text><Text style={s.muted}>{item.content_type} · v{item.version} · {item.status}/{item.moderation_status}</Text><View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}><Button title="Pratinjau" secondary disabled={contentBusy} onPress={() => void previewNativeContent(item)}/>{item.status === "failed" && <Button title="Pulihkan draft" secondary disabled={contentBusy} onPress={() => void retryNativeContent(item)}/>}{["draft","failed"].includes(item.status) && <Button title="Kirim review" disabled={contentBusy} onPress={() => void submitNativeContent(item)}/>}</View></View>)}
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
      <View style={[s.card, { padding: 14, borderRadius: 18 }]}>
        <Text style={s.kicker}>ENG-P22 · SPATIAL RENDERER</Text>
        <Text style={s.title}>Pratinjau World Scene</Text>
        <Text style={s.muted}>Masukkan scene key yang telah dipublikasikan. Aplikasi hanya meminta manifest publik dari API; tidak ada aset contoh atau akses database langsung.</Text>
        <TextInput accessibilityLabel="Scene key publik" value={spatialSceneKey} onChangeText={setSpatialSceneKey} autoCapitalize="none" maxLength={120} style={field} placeholder="scene-key" placeholderTextColor="#8B94AC"/>
        <Button title="Muat scene dari API" disabled={spatialSceneKey.trim().length < 3} onPress={() => setSpatialActiveKey(spatialSceneKey.trim())}/>
        {spatialActiveKey.length >= 3 && <CanonicalNativeWorldRenderer sceneKey={spatialActiveKey}/>}
      </View>
      <View style={[s.card, { padding: 14, borderRadius: 18 }]}><Text style={s.kicker}>ENG-P21 · UNIVERSE NAVIGATION</Text><SpatialNavigationScreen/></View>
      <View style={[s.card, { padding: 14, borderRadius: 18 }]}><Text style={s.kicker}>ENG-P22 · THEME BUILDER / GLB MANIFEST</Text><SpatialThemeCatalogScreen/></View>
      <Button title="Keluar" secondary onPress={() => void supabase?.auth.signOut()}/>
    </View>
    <Text style={s.footnote}>Data identitas, pengaturan dan privasi dibaca/ditulis melalui API resmi. Tidak ada akses database langsung dari aplikasi.</Text>
  </ScrollView>;
}

function Navigator() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [journeyReady, setJourneyReady] = useState(false);
  const [journeyTab, setJourneyTab] = useState<"agents" | "feed">("feed");

  useEffect(() => {
    let active = true;
    const resolveJourney = async (next: Session | null) => {
      if (!active) return;
      setSession(next);
      if (!next) {
        setJourneyTab("feed");
        setJourneyReady(true);
        return;
      }
      setJourneyReady(false);
      try {
        const response = await fetch(apiBase + "/v1/agents", {
          headers: { Authorization: "Bearer " + next.access_token, Accept: "application/json" },
        });
        if (!response.ok) {
          setJourneyTab("agents");
        } else {
          const payload = await response.json() as { items?: AgentIdentity[] };
          setJourneyTab(Array.isArray(payload.items) && payload.items.length > 0 ? "feed" : "agents");
        }
      } catch {
        // Fail closed into the Agent screen; its own API-backed loader shows the actionable error.
        setJourneyTab("agents");
      }
      if (active) setJourneyReady(true);
    };

    if (!supabase) {
      setReady(true);
      setJourneyReady(true);
      return () => { active = false; };
    }
    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error) {
        setReady(true);
        setJourneyReady(true);
        return;
      }
      void resolveJourney(data.session).finally(() => { if (active) setReady(true); });
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      void resolveJourney(next);
    });
    return () => { active = false; data.subscription.unsubscribe(); };
  }, []);

  if (!ready || (session && !journeyReady)) return <View style={s.loading}><ActivityIndicator size="large" color="#A5B4FC"/><Text style={s.muted}>Menyiapkan sesi dan memeriksa identitas AI Agent…</Text></View>;
  return <NavigationContainer linking={{ prefixes: ["allpha://"], config: { screens: { Welcome: "", Auth: "auth", Profile: "profile" } } }><Stack.Navigator key={session?.user.id || "anonymous"} initialRouteName={session ? "Profile" : "Welcome"} screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#0B1020" } }}>{session ? <Stack.Screen name="Profile">{() => <Profile session={session} initialTab={journeyTab}/>}</Stack.Screen> : <><Stack.Screen name="Welcome" component={Welcome}/><Stack.Screen name="Auth" component={Auth}/></>}</Stack.Navigator></NavigationContainer>;
}
export default function App() { return <SafeAreaProvider><StatusBar style="light"/><Navigator/></SafeAreaProvider>; }

const s = StyleSheet.create({
 page:{flexGrow:1,justifyContent:"center",backgroundColor:"#0B1020",padding:22,gap:20},brand:{alignItems:"center",gap:6,marginBottom:8},mark:{width:54,height:54,borderRadius:18,backgroundColor:"#A5B4FC",alignItems:"center",justifyContent:"center",marginBottom:8},markText:{fontSize:28,fontWeight:"900",color:"#10152A"},eyebrow:{color:"#A5B4FC",letterSpacing:3,fontSize:10,fontWeight:"800"},brandTitle:{color:"#F5F7FF",fontSize:34,fontWeight:"800"},muted:{color:"#A5ADC3",fontSize:13,lineHeight:20,textAlign:"center"},card:{backgroundColor:"#141B31",borderColor:"#29314B",borderWidth:1,borderRadius:26,padding:22,gap:15},kicker:{color:"#A5B4FC",letterSpacing:2,fontSize:10,fontWeight:"800"},hero:{color:"#F7F8FF",fontSize:25,fontWeight:"800",lineHeight:32},title:{color:"#F7F8FF",fontSize:22,fontWeight:"800"},body:{color:"#C0C7DA",fontSize:14,lineHeight:22},button:{minHeight:49,borderRadius:14,backgroundColor:"#A5B4FC",padding:14,alignItems:"center",justifyContent:"center",marginTop:2},secondary:{backgroundColor:"transparent",borderWidth:1,borderColor:"#3A4566"},buttonText:{color:"#11162B",fontWeight:"800",fontSize:14},secondaryText:{color:"#E1E6F8"},disabled:{opacity:.45},pressed:{opacity:.8},input:{minHeight:50,backgroundColor:"#0D1326",color:"#F7F8FF",borderColor:"#303A58",borderWidth:1,borderRadius:13,paddingHorizontal:14,fontSize:15},status:{color:"#A5ADC3",fontSize:12},warning:{color:"#FBBF24",fontSize:12,lineHeight:18},error:{color:"#FCA5A5",backgroundColor:"#321D2B",padding:12,borderRadius:10,fontSize:13,lineHeight:19},success:{color:"#86EFAC",backgroundColor:"#12302C",padding:12,borderRadius:10,fontSize:13,lineHeight:19},socialRow:{gap:8,paddingVertical:10,borderBottomWidth:1,borderBottomColor:"#29314B"},footnote:{color:"#747E9A",textAlign:"center",fontSize:11,lineHeight:18},loading:{flex:1,backgroundColor:"#0B1020",alignItems:"center",justifyContent:"center",gap:12}
});
