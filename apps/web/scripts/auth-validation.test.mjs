import test from "node:test";
import assert from "node:assert/strict";
import { isValidEmail } from "../lib/auth-validation.mjs";

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
