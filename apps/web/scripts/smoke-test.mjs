import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../app/agents/[agentId]/studio/page.tsx", import.meta.url), "utf8");
const agents = readFileSync(new URL("../app/agents/page.tsx", import.meta.url), "utf8");

assert.ok(page.includes("/v1/agents/${encodeURIComponent(agentId)}/knowledge/retrieve"));
assert.ok(page.includes('Authorization: "Bearer " + session.access_token'));
assert.ok(page.includes('method: "POST"'));
assert.ok(page.includes("setRetrievalLoading(true)"));
assert.ok(page.includes("API sedang mencari knowledge yang diizinkan"));
assert.ok(page.includes('role="alert"'));
assert.ok(page.includes("Coba lagi"));
assert.ok(page.includes("API mengembalikan 0 hasil untuk query ini"));
assert.ok(page.includes("Trace ID:"));
for (const field of ["source_id", "source_version", "chunk_id", "content_sha256", "source_location", "sensitivity", "retrieval_method", "score"]) {
  assert.ok(page.includes(field), `missing retrieval provenance field: ${field}`);
}
assert.ok(page.includes("retrievalRequestSequence.current"));
assert.ok(page.includes("}, [agentId]);"));
assert.ok(page.includes("requestSequence !== retrievalRequestSequence.current"));
assert.ok(page.includes("preview konteks retrieval, bukan respons generatif Agent"));
assert.ok(page.includes('href="/skill-challenges"'), "Agent Studio must link to Skill Challenge");
assert.doesNotMatch(page, /mockRetrievalResults|fakeKnowledgeResults|fixtureRetrieval/);


for (const contract of [
  "/v1/agent-runtime/tasks", "createRuntimeTask", "runtimeTaskAction",
  "idempotency_key", "Pulihkan status", "Batalkan",
  "Jalankan", "Skill terpublikasi", "runtimeTasks"
]) assert.ok(agents.includes(contract), `missing Web runtime lifecycle contract: ${contract}`);
assert.ok(agents.includes('/v1/agent-runtime/sessions/'));
assert.ok(agents.includes('task.state !== "created"'));
assert.ok(agents.includes('execution outcome') || agents.includes("hasilnya tidak diketahui"));


const workflows = readFileSync(new URL("../app/workflows/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/workflows/definitions", "/v1/workflows/runs", "Authorization: \"Bearer \" + session.access_token",
  "createDefinition", "createRun", "inspectRun", "cancelRun", "selectedRun.steps",
  "selectedRun.events", "JSON.parse(definitionText)", "JSON.parse(inputText)",
  "worker yang dikonfigurasi secara terpisah", "role=\"alert\"", "Coba lagi"
]) assert.ok(workflows.includes(contract), `missing Workflow Engine Web contract: ${contract}`);
assert.doesNotMatch(workflows, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);

const challenges = readFileSync(new URL("../app/skill-challenges/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/skill-challenges/catalog?agent_id=", "/v1/skill-challenges/runs", "idempotency_key",
  "nonce", "evidence_digest", "evaluation_result", "Expected output tidak dikirim ke browser.",
  "reward finansial tidak diterbitkan", "Authorization: \"Bearer \" + session.access_token"
]) assert.ok(challenges.includes(contract), `missing Skill Challenge Web contract: ${contract}`);
assert.doesNotMatch(challenges, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);

for (const contract of [
  "/v1/skill-catalog?limit=100&offset=", "allpha_skill_key", "allpha_skill_catalog_version",
  "character_profile", "Pilih satu Skill", "catalogSkills", "asset GLB belum otomatis tersedia"
]) assert.ok(agents.includes(contract), `missing Agent Identity Skill catalog contract: ${contract}`);
const superAdmin = readFileSync(new URL("../../super-admin/app/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/admin/official-bots", "/v1/admin/official-bots/provision", "Siapkan kandidat", "Agency Agents · metadata-only", "catalog_source",
  "officialBotAction", "Aktifkan", "Stop", "Isolasi", "asset_validation_status"
]) assert.ok(superAdmin.includes(contract), `missing Super Admin Official Bot control contract: ${contract}`);
assert.doesNotMatch(superAdmin, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);

console.log("ENG-P08 retrieval, ENG-P10 task lifecycle, ENG-P11 workflow, ENG-P12 Skill Challenge, Agent Skill catalog, and Official Bot control smoke assertions passed.");
