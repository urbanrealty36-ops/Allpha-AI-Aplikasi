import assert from "node:assert/strict";
import { findInvalidMeshoptFallbackBuffers } from "../../../tools/3d-assets/meshopt-fallback-compat.mjs";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { createSecureSessionStorage } from "../lib/secure-session-storage.mjs";
const require = createRequire(import.meta.url);
const app=readFileSync(new URL("../App.tsx",import.meta.url),"utf8");
const cfg=JSON.parse(readFileSync(new URL("../app.json",import.meta.url),"utf8"));
const pkg=JSON.parse(readFileSync(new URL("../package.json",import.meta.url),"utf8"));
assert.equal(cfg.expo.ios.bundleIdentifier,"com.allpha.universe");
assert.equal(cfg.expo.android.package,"com.allpha.universe");
const resolveAppConfig = require("../app.config.js");
const previousEasProjectId = process.env.EAS_PROJECT_ID;
process.env.EAS_PROJECT_ID = "00000000-0000-4000-8000-000000000001";
const resolvedExpoConfig = resolveAppConfig({ config: cfg.expo });
assert.equal(resolvedExpoConfig.extra.eas.projectId, "00000000-0000-4000-8000-000000000001", "EAS_PROJECT_ID from CI must be linked into Expo config for EAS builds and push registration");
if (previousEasProjectId === undefined) delete process.env.EAS_PROJECT_ID;
else process.env.EAS_PROJECT_ID = previousEasProjectId;
assert.ok(pkg.dependencies.expo && pkg.dependencies["expo-secure-store"]);
assert.match(app,/signInWithPassword/); assert.match(app,/signUp\(/);
assert.match(app,/Authorization: "Bearer " \+ session.access_token/);
assert.match(app,/import \* as SecureStore from "expo-secure-store"/); assert.match(app,/createSecureSessionStorage\(SecureStore\)/); assert.match(app,/https:\/\/api\.allpha\.web\.id/); assert.match(app,/\/healthz/);
assert.match(app,/\/v1\/me\/consents/); assert.match(app,/Riwayat persetujuan/);
assert.match(app,/versi resmi Terms of Service dan Privacy Policy ditetapkan/);
assert.match(app,/const \[socialLoading, setSocialLoading\] = useState\(false\)/);
assert.match(app,/Memuat Social Graph…/);
assert.match(app,/finally \{ setSocialLoading\(false\); \}/);
assert.match(app,/AI Agent & Passport/);
assert.match(app,/\/v1\/agents/);
assert.match(app,/\/v1\/agent-passports\//);
assert.match(app,/Buat Agent privat/);
assert.match(app,/owner ID dari client/);
assert.match(app,/Publikasikan/);
assert.match(app,/Arsipkan/);
assert.match(app,/Kelola Skills & Tools/);
assert.match(app,/\/v1\/agents\/\"? \+ encodeURIComponent\(studioAgentId\) \+ \"\/knowledge\/retrieve/);
assert.match(app,/API CONTEXT RETRIEVAL/);
assert.match(app,/setRetrievalLoading\(true\)/);
assert.match(app,/setRetrievalError\(e instanceof Error/);
assert.match(app,/item\.content_sha256/);
assert.match(app,/item\.source_location/);
assert.match(app,/item\.retrieval_method/);
assert.match(app,/Coba lagi/);
assert.match(app,/\/skills/); assert.match(app,/\/capabilities/);
assert.match(app,/runtime_authorized tetap false/);
assert.match(app,/bukan izin runtime/);
assert.doesNotMatch(app,/policy-test-v1|terms-test-v1/);
assert.doesNotMatch(app,/service_role|SUPABASE_SERVICE_ROLE_KEY/i);
assert.ok(existsSync(new URL("../README.md",import.meta.url)));

for (const contract of [
  "/v1/agent-runtime/tasks", "createRuntimeTask", "runtimeTaskAction",
  "idempotency_key", "SKILL TERPUBLIKASI", "TASK LIFECYCLE",
  "Jalankan", "Batalkan", "Pulihkan"
]) assert.ok(app.includes(contract), `missing Native runtime lifecycle contract: ${contract}`);
assert.ok(app.includes("loadRuntimeSessionTasks"));
assert.ok(app.includes("Eksekusi tetap membutuhkan policy runtime yang disetujui"));

for (const contract of [
  "/v1/content/mine", "/v1/content", "/media/resumable", "/complete", "/preview", "/publish", "/retry",
  "createNativeContentDraft", "createNativeStory", "submitNativeContent", "retryNativeContent", "previewNativeContent",
  "uploadNativeFileWithTus", "allpha:content:tus", "allpha:story:tus",
  "Draft konten tersimpan melalui FastAPI", "Konten dikirim untuk moderasi"
]) assert.ok(app.includes(contract), `missing ENG-P13 Native content pipeline contract: ${contract}`);

const nativeResumableMedia = readFileSync(new URL("../components/AiCinemaCreatorWorkspace.tsx", import.meta.url), "utf8");
for (const contract of ["Tus-Resumable", "Upload-Offset", "upload_token", "upload_metadata", "allpha:cinema:tus"]) {
  assert.ok(nativeResumableMedia.includes(contract), `missing Native TUS media contract: ${contract}`);
}

for (const contract of [
  "/v1/feed?", "/v1/feed/preferences", "/reaction", "/save", "/comments", "/report", "/share",
  "loadNativeFeed", "saveNativeFeedPreferences", "nativeFeedAction", "submitNativeFeedComment", "toggleNativeComments", "chooseNativeReportReason", "shareNativeContent", "Share.share",
  "Personalisasi: aktif", "Laporkan", "misinformation"
]) assert.ok(app.includes(contract), `missing ENG-P14 Native feed contract: ${contract}`);

for (const contract of [
  '"/v1/reels?"', "loadNativeReels", "ENG-P15 · REELS", "audio/mpeg", "audio/ogg",
  "Putar audio", "Putar video", "media_type.startsWith(\"audio/\")", 'contentFile.mimeType?.startsWith("audio/") ? "audio"'
]) assert.ok(app.includes(contract), `missing ENG-P15 Native Reels contract: ${contract}`);


{
  const values = new Map();
  let failNextChunkWrite = false;
  const store = {
    async getItemAsync(key) { return values.has(key) ? values.get(key) : null; },
    async setItemAsync(key, value) {
      if (failNextChunkWrite && key.includes(":v1:") && !key.endsWith(":manifest")) {
        failNextChunkWrite = false;
        throw new Error("simulated secure-store write failure");
      }
      values.set(key, value);
    },
    async deleteItemAsync(key) { values.delete(key); }
  };
  const storage = createSecureSessionStorage(store);
  const previousSession = "old-session-token".repeat(500);
  await storage.setItem("sb-auth-token", previousSession);
  assert.equal(await storage.getItem("sb-auth-token"), previousSession, "versioned chunks must round-trip a large session");

  failNextChunkWrite = true;
  await assert.rejects(storage.setItem("sb-auth-token", "new-session-token".repeat(500)), /simulated secure-store write failure/);
  assert.equal(await storage.getItem("sb-auth-token"), previousSession, "an interrupted write must preserve the previous committed session");

  const legacyStore = new Map([
    ["legacy:count", "2"], ["legacy:0", "legacy-"], ["legacy:1", "session"]
  ]);
  const legacyStorage = createSecureSessionStorage({
    async getItemAsync(key) { return legacyStore.has(key) ? legacyStore.get(key) : null; },
    async setItemAsync(key, value) { legacyStore.set(key, value); },
    async deleteItemAsync(key) { legacyStore.delete(key); }
  });
  assert.equal(await legacyStorage.getItem("legacy"), "legacy-session", "existing chunked sessions must remain readable during migration");
  await legacyStorage.setItem("legacy", "migrated-session");
  assert.equal(await legacyStorage.getItem("legacy"), "migrated-session", "the next write must migrate legacy sessions to the versioned format");

  // A reader holding the old manifest must finish before a writer can
  // commit a new generation and clean up the old chunks.
  const raceValues = new Map();
  let releaseChunkRead, chunkReadStartedResolve;
  const chunkStarted = new Promise(resolve => { chunkReadStartedResolve = resolve; });
  const chunkGate = new Promise(resolve => { releaseChunkRead = resolve; });
  let pauseOldChunk = false;
  const raceStore = {
    async getItemAsync(key) {
      if (pauseOldChunk && key.includes(":v1:") && key.endsWith(":0")) {
        pauseOldChunk = false; chunkReadStartedResolve(); await chunkGate;
      }
      return raceValues.has(key) ? raceValues.get(key) : null;
    },
    async setItemAsync(key, value) { raceValues.set(key, value); },
    async deleteItemAsync(key) { raceValues.delete(key); },
  };
  const raceStorage = createSecureSessionStorage(raceStore);
  await raceStorage.setItem("race-session", "previous-session");
  pauseOldChunk = true;
  const pendingRead = raceStorage.getItem("race-session");
  await chunkStarted;
  const pendingWrite = raceStorage.setItem("race-session", "replacement-session");
  releaseChunkRead();
  assert.equal(await pendingRead, "previous-session", "concurrent read must finish against its committed generation");
  await pendingWrite;
  assert.equal(await raceStorage.getItem("race-session"), "replacement-session", "writer must commit after serialized read");

  await storage.removeItem("sb-auth-token");
  assert.equal(await storage.getItem("sb-auth-token"), null, "logout must tombstone the session before chunk cleanup");
}

console.log("ENG-P01 source, ENG-P10 task lifecycle, ENG-P12 Skill Challenge, ENG-P13 content pipeline, and ENG-P14 feed and ENG-P15 Reels smoke tests passed.");

const nativeWorldRenderer = readFileSync(new URL("../components/spatial/CanonicalNativeWorldRenderer.tsx", import.meta.url), "utf8");
assert.ok(nativeWorldRenderer.includes("onSelect={setSelectedEntityId}"), "Native renderer must wire scene object selection");
assert.ok(nativeWorldRenderer.includes("Interaksi ruang"), "Native renderer must expose spatial interaction details");
assert.ok(nativeWorldRenderer.includes("accessibilityState={{ selected: object.entity_id === selectedEntityId }}"), "Native object list must expose accessible selection state");
assert.ok(nativeWorldRenderer.includes('m.coordinate_system !== "right-handed-y-up"'), "Native renderer must validate scene coordinate system");
assert.ok(nativeWorldRenderer.includes("Number.isSafeInteger(m.scene_version)"), "Native renderer must validate scene version");
assert.ok(nativeWorldRenderer.includes("!object.asset_id.trim()"), "Native renderer must reject missing asset identity");
assert.ok(nativeWorldRenderer.includes("object.asset_version < 1"), "Native renderer must reject invalid asset versions");
assert.ok(nativeWorldRenderer.includes("useLoader.clear(GLTFLoader, object.asset_url)"), "Native renderer retry must clear cached GLTFLoader failures");
assert.ok(nativeWorldRenderer.includes("Fallback aktif: daftar objek scene tetap tersedia di bawah."), "Native renderer must preserve scene object fallback after a render error");

const meshoptHelper = readFileSync(new URL("../lib/spatial/configureAllphaGLTFLoader.ts", import.meta.url), "utf8");
assert.ok(meshoptHelper.includes("MeshoptDecoder"), "Native GLTF loader must import MeshoptDecoder");
assert.ok(meshoptHelper.includes("loader.setMeshoptDecoder(MeshoptDecoder)"), "Native GLTF loader must register MeshoptDecoder");
await MeshoptDecoder.ready;
assert.equal(typeof MeshoptDecoder.decodeGltfBuffer, "function", "Meshopt decoder must initialize before GLB parsing");
for (const [file, loadCall] of [
  ["../components/spatial/CanonicalNativeGlbPreview.tsx", "useLoader(GLTFLoader, url, configureAllphaGLTFLoader)"],
  ["../components/spatial/CanonicalNativeWorldRenderer.tsx", "useLoader(GLTFLoader, object.asset_url, configureAllphaGLTFLoader)"]
]) {
  const source = readFileSync(new URL(file, import.meta.url), "utf8");
  assert.ok(source.includes("configureAllphaGLTFLoader"), `missing Meshopt loader configuration in ${file}`);
  assert.ok(source.includes(loadCall), `GLTFLoader call is not configured for Meshopt in ${file}`);
  assert.ok(source.includes("useLoader.clear(GLTFLoader"), `retry path must clear failed GLTFLoader cache in ${file}`);
}


const nativeThemeCatalog = readFileSync(new URL("../components/spatial/SpatialThemeCatalogScreen.tsx", import.meta.url), "utf8");
assert.ok(app.includes("SpatialThemeCatalogScreen"), "Native app must retain the route for the Spatial development notice");
assert.ok(app.includes("ENG-P22 · THEME BUILDER / GLB MANIFEST"), "Native app must retain the Spatial entry point while locked");
assert.ok(nativeThemeCatalog.includes("Sedang dalam tahap pengembangan"), "Native Theme route must show the development lock notice");
assert.ok(nativeThemeCatalog.includes("sementara tidak dapat diakses oleh siapa pun"), "Native Theme route must clearly deny all access while locked");
assert.ok(!nativeThemeCatalog.includes("/v1/spatial/themes"), "Native Theme route must not request the locked Spatial API");
assert.ok(!nativeThemeCatalog.includes("CanonicalNativeWorldRenderer"), "Native Theme route must not render locked Spatial assets");
console.log("ENG-P22 Native Theme route global development lock smoke tests passed.");

const challengeContracts = [
  "/v1/skill-challenges/catalog?agent_id=", "/v1/skill-challenges/runs", "challengeNonce",
  "/execute", "/comparison", "/release-decision", "Catat keputusan release", "Model Router", "evidence_digest"
];
for (const contract of challengeContracts) assert.ok(app.includes(contract), `missing ENG-P12 Native Skill Challenge contract: ${contract}`);

for (const contract of [
  "/v1/skill-catalog?limit=100&offset=", "allpha_skill_key", "allpha_skill_catalog_version",
  "character_profile", "PILIH BIDANG & SKILL AI AGENT", "Pilih satu Skill dari katalog Allpha"
]) assert.ok(app.includes(contract), `missing Native Agent Identity Skill catalog contract: ${contract}`);


const validMeshoptFallback = {
  extensionsRequired: ["EXT_meshopt_compression"],
  buffers: [
    { byteLength: 8 },
    { byteLength: 16, extensions: { EXT_meshopt_compression: { fallback: true } } }
  ],
  bufferViews: [{
    buffer: 1,
    byteLength: 16,
    extensions: { EXT_meshopt_compression: {
      buffer: 0, byteOffset: 0, byteLength: 8, byteStride: 4, count: 4, mode: "ATTRIBUTES"
    } }
  }]
};
assert.deepEqual(findInvalidMeshoptFallbackBuffers(validMeshoptFallback), [],
  "spec-conformant URI-less Meshopt fallback buffer must not be misclassified as malformed");
const invalidMeshoptFallback = structuredClone(validMeshoptFallback);
delete invalidMeshoptFallback.buffers[1].extensions.EXT_meshopt_compression.fallback;
assert.deepEqual(findInvalidMeshoptFallbackBuffers(invalidMeshoptFallback), [
  { index: 1, reasons: ["fallback_flag_missing"] }
], "URI-less nonzero buffer without fallback marker must be rejected");


assert.match(app,/linking=\{\{ prefixes: \["allpha:\/\/"\]/);
assert.match(app,/AppState\.addEventListener\("change", syncAuthRefresh\)/, "Native auth refresh must follow foreground/background lifecycle");
assert.ok(app.includes("supabase.auth.startAutoRefresh()") && app.includes("supabase.auth.stopAutoRefresh()"), "Native auth refresh must start in foreground and stop in background/unmount");
assert.ok(app.includes('Welcome: "", Auth: "auth", AuthCallback: "auth/callback", Recovery: "auth/recovery", Profile: "profile"'), "Native auth callback and recovery routes must be registered");
assert.ok(app.includes('Stories: { story?: string } | undefined') && app.includes('initialStoryId={route.params?.story}'), "Native Story deep links must preserve the selected Story ID");
assert.ok(app.includes("selectedStoryId") && app.includes("Story tidak tersedia, tidak dapat diakses, atau sudah kedaluwarsa."), "Native Story deep links must show selected Story or a truthful unavailable state");
assert.ok(app.includes('Feed: { content?: string } | undefined') && app.includes('initialContentId={route.params?.content}'), "Native Feed deep links must preserve the selected content ID");
assert.ok(app.includes('apiRequest("/v1/feed/item/" + encodeURIComponent(selectedFeedContentId))') && app.includes("selectedFeedContentId"), "Native Feed deep links must resolve the selected content through the canonical API");
assert.ok(app.includes('<Stack.Screen name="Feed">{({ route }) => <Welcome initialContentId={route.params?.content}/>}</Stack.Screen>') && app.includes('<Stack.Screen name="Stories">{({ route }) => <Welcome initialStoryId={route.params?.story}/>}</Stack.Screen>'), "Native public Feed and Story deep links must resolve while signed out");
assert.ok(app.includes('encodeURIComponent(selectedPublicFeedId)') && app.includes('payload.item.id !== selectedPublicFeedId') && app.includes('if (active) setSelectedPublicFeedError'), "Guest Feed deep links must safely encode IDs and reject unavailable or mismatched content");
assert.ok(app.includes('encodeURIComponent(selectedFeedContentId)') && app.includes('payload.item.id !== selectedFeedContentId') && app.includes('setSelectedFeedError'), "Authenticated Feed deep links must reject unavailable or mismatched content");
assert.ok(app.includes('initialStoryId && !selectedStory && !guestLoading') && app.includes('initialStoryId && <View style={s.socialRow}>'), "Guest and authenticated Story deep links must render truthful unavailable states");
assert.ok(app.includes('if (!active) return;') && app.includes('setSelectedFeedItem(payload.item)') && app.includes('return () => { active = false; };'), "Feed deep-link requests must ignore stale results after route changes or unmount");
assert.ok(app.includes('updateInterestPreference') && app.includes('"not_interested"'), "Native Social Graph must persist both interested and not-interested preferences");
assert.ok(app.includes('/v1/social/recommendations?node_type=human&limit=12') && app.includes('/v1/social/recommendations?node_type=agent&limit=12') && app.includes("followSocialRecommendation") && app.includes("mutual_followers_count"), "Native Social Graph must load privacy-aware Human and Agent recommendations and follow via the canonical relationship API");
assert.ok(app.includes('result.outcome === "follow_active"') && app.includes('result.outcome === "follow_request_created"'), "Native Social Graph must show the server-derived follow outcome");
for (const contract of ["/v1/social/relationships", "/v1/social/actor-agents", "/v1/social/discover-agents?q=", "/v1/social/activity?limit=", "actor_agent_id", "target_type: targetType", "socialTargetType", "socialActorAgentId", "target_node_type"]) {
  assert.ok(app.includes(contract), "Native Social Graph must use the typed Human-Agent relationship contract: " + contract);
}
const guestWelcome = app.slice(app.indexOf("function Welcome"), app.indexOf("function Auth"));
for (const contract of [
  "/v1/feed?mode=recent&limit=10", "/v1/stories?limit=20", "/v1/reels?mode=recent&limit=10",
  "requestLogin(\"Menyukai postingan\")", "requestLogin(\"Mengomentari postingan\")",
  "requestLogin(\"Mengikuti kreator\")", "Share.share", "Linking.openURL"
]) assert.ok(guestWelcome.includes(contract), `missing Native guest social contract: ${contract}`);



for (const contract of [
  'emailRedirectTo: nativeAuthRedirect',
  'options: { emailRedirectTo: nativeAuthRedirect }',
  'supabase.auth.getUser(data.session.access_token)',
  'email_confirmed_at',
  'supabase.auth.resend({ type: "signup"',
  'resetPasswordForEmail',
  'redirectTo: nativeRecoveryRedirect',
  'auth/v1/user',
  '"/v1/me"',
  'account_status',
  'scope: "local"',
  '"/v1/auth/revoke"',
  'scope: "local"'
]) assert.ok(app.includes(contract), `missing Native auth/session lifecycle contract: ${contract}`);
assert.ok(app.includes("[^" + String.fromCharCode(92) + "s@]") && app.includes(".test(normalizedEmail)"), "Native auth email validation must use whitespace-aware email syntax");


for (const contract of [
  'AuthCallback: "auth/callback"', 'Recovery: "auth/recovery"',
  'exchangeCodeForSession(code)', 'setSession({ access_token: accessToken, refresh_token: refreshToken })',
  'EXPO_PUBLIC_NATIVE_AUTH_REDIRECT_URL', 'EXPO_PUBLIC_NATIVE_RECOVERY_REDIRECT_URL',
  'recoveryFlowRef.current', 'supabase.auth.updateUser({ password })',
  'apiBase + "/v1/auth/revoke"', 'function PasswordRecovery()',
]) assert.ok(app.includes(contract), `missing Native PKCE deep-link and recovery contract: ${contract}`);
assert.ok(app.includes('const callbackPath = (parsed.hostname + parsed.pathname).toLowerCase()'), 'Native auth callback must normalize custom-scheme routes');
assert.ok(app.includes('processedAuthUrls.current.delete(rawUrl)'), 'Native auth callback must release failed URL deduplication so transient exchange errors can be retried');

assert.ok(app.includes("const [passwordUpdated, setPasswordUpdated] = useState(false)"), "Native password recovery must retain the password-updated state so revocation can be retried without resubmitting the password");
assert.ok(app.includes("if (!passwordUpdated) {") && app.includes('passwordUpdated ? "Cabut sesi dan selesaikan"'), "Native recovery must retry server session revocation independently after password update");
assert.ok(app.includes("authLinkSubscription.remove()"), "Native auth deep-link listener must be removed on every navigator cleanup path");
assert.ok(app.includes("const [sessionVerificationError, setSessionVerificationError] = useState<string | null>(null)"), "Native session verification must expose a recoverable unavailable state");
assert.ok(app.includes("retrySessionVerificationRef.current = () =>"), "Native session verification must provide an explicit retry path");
assert.ok(app.includes("authResponse.status === 401 || authResponse.status === 403"), "Definitive Supabase rejection must clear the invalid local session");
assert.ok(app.includes("meResponse.status === 401 || meResponse.status === 403"), "Definitive FastAPI rejection must clear the invalid local session");
assert.ok(app.includes("Sesi lokal tetap disimpan; coba lagi."), "Transient Auth/API failures must preserve the recoverable local session");
assert.ok(app.includes("Konten akun tetap terkunci sampai verifikasi berhasil."), "Protected Native content must remain hidden while session verification is unavailable");
assert.ok(app.includes("retrySessionVerificationRef.current?.()"), "Native unavailable screen must invoke the session verification retry");

assert.ok(app.includes('function AuthCallback({ status, canContinue }'), "Native callback screen must expose truthful success/error states");
assert.ok(app.includes('const ready = status === "success" && canContinue'), "Native callback must wait for FastAPI identity bootstrap before continuing");
assert.ok(app.includes('setAuthCallbackStatus("success")') && app.includes('setAuthCallbackStatus("error")'), "Native callback must distinguish successful and failed code exchanges");
