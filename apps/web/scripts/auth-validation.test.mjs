import test from "node:test";
import assert from "node:assert/strict";
import { isValidEmail, verifyBackendSession } from "../lib/auth-validation.mjs";

test("accepts a normal email address", () => {
  assert.equal(isValidEmail("farhan@example.com"), true);
});

test("trims surrounding whitespace", () => {
  assert.equal(isValidEmail("  farhan@example.co.id  "), true);
});

test("rejects missing or malformed email addresses", () => {
  for (const value of ["", "farhan", "farhan@", "@example.com", "farhan@example", "farhan @example.com"]) {
    assert.equal(isValidEmail(value), false, value);
  }
});

const session = { access_token: "access-token-fixture", user: { id: "user-123" } };
const jsonResponse = (status, body) => ({
  status,
  ok: status >= 200 && status < 300,
  json: async () => body,
});

test("backend session validation accepts the matching active identity", async () => {
  const result = await verifyBackendSession("https://api.example.test/", session, async (url, options) => {
    assert.equal(url, "https://api.example.test/v1/me");
    assert.equal(options.headers.Authorization, "Bearer access-token-fixture");
    assert.equal(options.cache, "no-store");
    return jsonResponse(200, { user: { id: "user-123" }, profile: { id: "user-123", account_status: "active" } });
  });
  assert.equal(result.status, "valid");
  assert.equal(result.identity.user.id, "user-123");
  assert.equal(result.identity.profile.account_status, "active");
});

test("backend session validation rejects explicitly revoked sessions", async () => {
  for (const status of [401, 403]) {
    const result = await verifyBackendSession("https://api.example.test", session, async () => jsonResponse(status, {}));
    assert.deepEqual(result, { status: "rejected" });
  }
});

test("backend session validation preserves local session on server and rate-limit failures", async () => {
  for (const status of [408, 429, 500, 502, 503]) {
    const result = await verifyBackendSession("https://api.example.test", session, async () => jsonResponse(status, {}));
    assert.deepEqual(result, { status: "unavailable" });
  }
});

test("backend session validation rejects mismatched identity and inactive account", async () => {
  const mismatch = await verifyBackendSession("https://api.example.test", session, async () =>
    jsonResponse(200, { user: { id: "other-user" }, profile: { id: "other-user", account_status: "active" } }));
  const inactive = await verifyBackendSession("https://api.example.test", session, async () =>
    jsonResponse(200, { user: { id: "user-123" }, profile: { id: "user-123", account_status: "deactivation_requested" } }));
  assert.deepEqual(mismatch, { status: "rejected" });
  assert.deepEqual(inactive, { status: "rejected" });
});

test("backend session validation preserves local session on network and malformed response failures", async () => {
  const network = await verifyBackendSession("https://api.example.test", session, async () => { throw new Error("offline"); });
  const malformed = await verifyBackendSession("https://api.example.test", session, async () => ({
    status: 200, ok: true, json: async () => { throw new Error("invalid json"); },
  }));
  assert.deepEqual(network, { status: "unavailable" });
  assert.deepEqual(malformed, { status: "unavailable" });
});
