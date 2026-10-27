import assert from "node:assert/strict";
import { findInvalidMeshoptFallbackBuffers } from "../../../tools/3d-assets/meshopt-fallback-compat.mjs";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { readFileSync, existsSync } from "node:fs";
const app=readFileSync(new URL("../App.tsx",import.meta.url),"utf8");
const cfg=JSON.parse(readFileSync(new URL("../app.json",import.meta.url),"utf8"));
const pkg=JSON.parse(readFileSync(new URL("../package.json",import.meta.url),"utf8"));
assert.equal(cfg.expo.ios.bundleIdentifier,"com.allpha.universe");
assert.equal(cfg.expo.android.package,"com.allpha.universe");
assert.ok(pkg.dependencies.expo && pkg.dependencies["expo-secure-store"]);
assert.match(app,/signInWithPassword/); assert.match(app,/signUp\(/);
assert.match(app,/Authorization: "Bearer " \+ session.access_token/);
assert.match(app,/SecureStore\.setItemAsync/); assert.match(app,/https:\/\/api\.allpha\.web\.id/); assert.match(app,/\/healthz/);
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
  "/v1/content/mine", "/v1/content", "/media", "/preview", "/publish", "/retry",
  "createNativeContentDraft", "submitNativeContent", "retryNativeContent", "previewNativeContent",
  "Draft konten tersimpan melalui FastAPI", "Konten dikirim untuk moderasi"
]) assert.ok(app.includes(contract), `missing ENG-P13 Native content pipeline contract: ${contract}`);

for (const contract of [
  "/v1/feed?", "/v1/feed/preferences", "/reaction", "/save", "/comments", "/report", "/share",
  "loadNativeFeed", "saveNativeFeedPreferences", "nativeFeedAction", "submitNativeFeedComment", "toggleNativeComments", "chooseNativeReportReason", "shareNativeContent", "Share.share",
  "Personalisasi: aktif", "Laporkan", "misinformation"
]) assert.ok(app.includes(contract), `missing ENG-P14 Native feed contract: ${contract}`);

for (const contract of [
  '"/v1/reels?"', "loadNativeReels", "ENG-P15 · REELS", "audio/mpeg", "audio/ogg",
  "Putar audio", "Putar video", "media_type.startsWith(\"audio/\")", 'contentFile.mimeType?.startsWith("audio/") ? "audio"'
]) assert.ok(app.includes(contract), `missing ENG-P15 Native Reels contract: ${contract}`);

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
assert.ok(app.includes("SpatialThemeCatalogScreen"), "Native app must expose the canonical Theme catalog screen");
assert.ok(app.includes("ENG-P22 · THEME BUILDER / GLB MANIFEST"), "Native app must place the Theme catalog in the product surface");
assert.ok(nativeThemeCatalog.includes("/v1/spatial/themes?limit=100&offset=0"), "Native Theme catalog must use the public FastAPI catalog");
assert.ok(nativeThemeCatalog.includes("CanonicalNativeWorldRenderer"), "Native Theme catalog must use the canonical Native renderer");
assert.ok(nativeWorldRenderer.includes("/v1/spatial/themes/") && nativeWorldRenderer.includes("/manifest"), "Native renderer must resolve the canonical published Theme manifest");
assert.ok(nativeWorldRenderer.includes("publication_status") && nativeWorldRenderer.includes("fallback_mode"), "Native renderer must validate publication and fallback contract");
console.log("ENG-P22 Theme catalog and ENG-P23 Native renderer source smoke tests passed.");

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
assert.match(app,/Welcome: "", Auth: "auth", Profile: "profile"/);
assert.ok(app.includes('updateInterestPreference') && app.includes('"not_interested"'), "Native Social Graph must persist both interested and not-interested preferences");
assert.ok(app.includes('result.outcome === "follow_active"') && app.includes('result.outcome === "follow_request_created"'), "Native Social Graph must show the server-derived follow outcome");
const guestWelcome = app.slice(app.indexOf("function Welcome"), app.indexOf("function Auth"));
for (const contract of [
  "/v1/feed?mode=recent&limit=10", "/v1/stories?limit=20", "/v1/reels?mode=recent&limit=10",
  "requestLogin(\"Menyukai postingan\")", "requestLogin(\"Mengomentari postingan\")",
  "requestLogin(\"Mengikuti kreator\")", "Share.share", "Linking.openURL"
]) assert.ok(guestWelcome.includes(contract), `missing Native guest social contract: ${contract}`);

