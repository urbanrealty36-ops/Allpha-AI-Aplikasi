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
assert.doesNotMatch(page, /mockRetrievalResults|fakeKnowledgeResults|fixtureRetrieval/);


for (const contract of [
  "/v1/agent-runtime/tasks", "createRuntimeTask", "runtimeTaskAction",
  "idempotency_key", "IDEMPOTENCY", "Pulihkan status", "Batalkan",
  "Jalankan", "Skill terpublikasi", "runtimeTasks"
]) assert.ok(agents.includes(contract), `missing Web runtime lifecycle contract: ${contract}`);
assert.ok(agents.includes('/v1/agent-runtime/sessions/'));
assert.ok(agents.includes('task.state !== "created"'));
assert.ok(agents.includes('execution outcome') || agents.includes("hasilnya tidak diketahui"));

console.log("ENG-P08 retrieval and ENG-P10 task lifecycle smoke assertions passed.");
