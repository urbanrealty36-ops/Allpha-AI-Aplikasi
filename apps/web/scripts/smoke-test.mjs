import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../app/agents/[agentId]/studio/page.tsx", import.meta.url), "utf8");

assert.match(page, /\/v1\/agents\/\$\{encodeURIComponent\(agentId\)\}\/knowledge\/retrieve/);
assert.match(page, /Authorization: "Bearer " \+ session\.access_token/);
assert.match(page, /method: "POST"/);
assert.match(page, /setRetrievalLoading\(true\)/);
assert.match(page, /API sedang mencari knowledge yang diizinkan/);
assert.match(page, /role="alert"/);
assert.match(page, /Coba lagi/);
assert.match(page, /API mengembalikan 0 hasil untuk query ini/);
assert.match(page, /Trace ID:/);
for (const field of ["source_id", "source_version", "chunk_id", "content_sha256", "source_location", "sensitivity", "retrieval_method", "score"]) {
  assert.ok(page.includes(field), `missing retrieval provenance field: ${field}`);
}
assert.match(page, /retrievalRequestSequence\.current/);
assert.match(page, /\}, \[agentId\]\);/);
assert.match(page, /requestSequence !== retrievalRequestSequence\.current/);
assert.match(page, /preview konteks retrieval, bukan respons generatif Agent/);
assert.doesNotMatch(page, /mockRetrievalResults|fakeKnowledgeResults|fixtureRetrieval/);

console.log("ENG-P08 Web retrieval contract smoke assertions passed.");
