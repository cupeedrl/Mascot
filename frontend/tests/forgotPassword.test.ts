import assert from "node:assert/strict";
import test from "node:test";

test("password reset validation requires at least 12 characters", () => {
  const isLengthValid = (pwd: string) => pwd.length >= 12;
  assert.equal(isLengthValid("short"), false);
  assert.equal(isLengthValid("12345678901"), false);
  assert.equal(isLengthValid("123456789012"), true);
  assert.equal(isLengthValid("VeryStrongPassword2026!"), true);
});

test("password reset validation requires matching confirmation", () => {
  const isMatching = (pwd: string, confirm: string) => pwd === confirm;
  assert.equal(isMatching("Password123456", "Different123456"), false);
  assert.equal(isMatching("Password123456", "Password123456"), true);
});

test("token extraction handles query string parameters safely", () => {
  const urlWithToken = "https://mascot.app/reset-password?token=secure_random_token_12345";
  const url = new URL(urlWithToken);
  const token = url.searchParams.get("token")?.trim() ?? "";
  assert.equal(token, "secure_random_token_12345");

  const urlWithoutToken = "https://mascot.app/reset-password";
  const urlNoToken = new URL(urlWithoutToken);
  const emptyToken = urlNoToken.searchParams.get("token")?.trim() ?? "";
  assert.equal(emptyToken, "");
});

test("reset password token initial state determines loading vs immediate invalidation", () => {
  const getInitialState = (token: string) => (token.trim() ? "checking" : "invalid");

  assert.equal(getInitialState(""), "invalid");
  assert.equal(getInitialState("   "), "invalid");
  assert.equal(getInitialState("valid_token_string"), "checking");
});

test("reset password token state resolution handles valid and invalid outcomes", () => {
  type State = "checking" | "valid" | "invalid" | "success";

  const resolveValidation = (isValid: boolean): State => (isValid ? "valid" : "invalid");
  assert.equal(resolveValidation(true), "valid");
  assert.equal(resolveValidation(false), "invalid");
});
