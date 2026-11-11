import assert from "node:assert/strict";
import test from "node:test";

import {
  cleanCode,
  formatCountdown,
  isValidUsername,
  normalizeUsername,
  passwordStrength,
} from "../src/features/auth/authForm.ts";

test("password strength requires 12 characters and rewards variety", () => {
  assert.equal(passwordStrength("").score, 0);
  assert.equal(passwordStrength("Short1!").score, 1);
  assert.equal(passwordStrength("Short1!").meetsMinimum, false);
  assert.equal(passwordStrength("alllowercaseletters").score, 2);
  assert.equal(passwordStrength("Mixed-Case-Password-9").score, 4);
  assert.equal(passwordStrength("Mixed-Case-Password-9").label, "Mạnh");
});

test("usernames follow the backend rule", () => {
  assert.equal(normalizeUsername("  Lan.Nguyen "), "lan.nguyen");
  for (const ok of ["lan", "lan.nguyen", "dat_2026"]) assert.ok(isValidUsername(ok), ok);
  for (const bad of ["ab", "1lan", "lan..x", "lan_", "lan nguyen", "lân"]) assert.ok(!isValidUsername(bad), bad);
});

test("codes and countdowns are formatted for the verify step", () => {
  assert.equal(cleanCode(" 48 29-37 1"), "482937");
  assert.equal(formatCountdown(42), "0:42");
  assert.equal(formatCountdown(60), "1:00");
  assert.equal(formatCountdown(-3), "0:00");
});
