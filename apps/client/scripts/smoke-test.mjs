import assert from "node:assert/strict";
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

console.log("ENG-P01 source, ENG-P10 task lifecycle, and ENG-P12 Skill Challenge smoke tests passed.");


const challengeContracts = [
  "/v1/skill-challenges/catalog?agent_id=", "/v1/skill-challenges/runs", "challengeNonce",
  "challengeSubmission", "evidence_digest", "Reward finansial/AI Credits tidak diterbitkan"
];
for (const contract of challengeContracts) assert.ok(app.includes(contract), `missing ENG-P12 Native Skill Challenge contract: ${contract}`);
