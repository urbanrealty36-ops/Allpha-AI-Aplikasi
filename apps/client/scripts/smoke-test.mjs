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
}



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
