import assert from "node:assert/strict";
import test from "node:test";

import {
  ACCESS_TOKEN_STORAGE_KEY,
  persistAccessToken,
  readAccessToken,
} from "../src/auth/sessionStorage.ts";

class MemorySessionStorage {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

test("access token is persisted only in sessionStorage and can be restored", () => {
  const sessionStorage = new MemorySessionStorage();
  Object.assign(globalThis, { window: { sessionStorage } });

  persistAccessToken("access-token");
  assert.equal(sessionStorage.getItem(ACCESS_TOKEN_STORAGE_KEY), "access-token");
  assert.equal(readAccessToken(), "access-token");
});

test("clearing the access token removes the persisted session", () => {
  const sessionStorage = new MemorySessionStorage();
  Object.assign(globalThis, { window: { sessionStorage } });

  persistAccessToken("access-token");
  persistAccessToken(null);
  assert.equal(sessionStorage.getItem(ACCESS_TOKEN_STORAGE_KEY), null);
  assert.equal(readAccessToken(), null);
});
