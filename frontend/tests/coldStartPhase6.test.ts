import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  ApiError,
  createVocabulary,
  invalidateBackendReadiness,
  login,
  register,
  setAccessToken,
  waitForBackendReady,
} from "../src/api/client.ts";
import {
  BackendWarmupTimeoutError,
  isTransientBackendUnavailable,
  runBackendWarmup,
  shouldClearAuthenticationOnRestoreFailure,
} from "../src/api/backendWarmup.ts";

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, { status });
}

test("healthy backend allows the normal login request immediately", async () => {
  invalidateBackendReadiness();
  setAccessToken(null);
  const requests: Array<{ url: string; method: string }> = [];
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      requests.push({ url, method: init?.method ?? "GET" });
      if (url.endsWith("/health/database")) {
        return jsonResponse({ status: "ok", database: "reachable" });
      }
      return jsonResponse({ access_token: "safe-test-token", token_type: "bearer", expires_in: 1800 });
    },
  });

  const token = await login("learner@example.com", "StrongPassword123!");

  assert.equal(token.access_token, "safe-test-token");
  assert.deepEqual(requests.map(({ method }) => method), ["GET", "POST"]);
  assert.ok(requests[0]?.url.endsWith("/health/database"));
  assert.ok(requests[1]?.url.endsWith("/auth/login"));
});

test("initial outage reports warm-up states and continues when readiness recovers", async () => {
  const states: string[] = [];
  let attempts = 0;
  const result = await runBackendWarmup(
    async () => {
      attempts += 1;
      if (attempts < 3) throw new ApiError(503, "Unavailable");
    },
    {
      delaysMs: [0, 2, 4],
      sleep: async () => undefined,
      onProgress: ({ status }) => states.push(status),
    },
  );

  assert.equal(attempts, 3);
  assert.equal(result.retryCount, 2);
  assert.deepEqual(states, ["connecting", "starting", "starting"]);
});

test("bounded warm-up ends with a friendly timeout", async () => {
  let attempts = 0;
  await assert.rejects(
    runBackendWarmup(
      async () => {
        attempts += 1;
        throw new ApiError(504, "Gateway timeout");
      },
      { delaysMs: [0, 1, 1], sleep: async () => undefined },
    ),
    (error: unknown) =>
      error instanceof BackendWarmupTimeoutError &&
      /mất nhiều thời gian hơn dự kiến/.test(error.message),
  );
  assert.equal(attempts, 3);
});

test("transient classification includes network, timeout, and gateway startup failures", () => {
  assert.equal(isTransientBackendUnavailable(new ApiError(0, "Network", undefined, "network")), true);
  assert.equal(isTransientBackendUnavailable(new ApiError(0, "Timeout", undefined, "timeout")), true);
  assert.equal(isTransientBackendUnavailable(new ApiError(502, "Bad gateway")), true);
  assert.equal(isTransientBackendUnavailable(new ApiError(503, "Unavailable")), true);
  assert.equal(isTransientBackendUnavailable(new ApiError(504, "Gateway timeout")), true);
  assert.equal(isTransientBackendUnavailable(new ApiError(500, "Application error")), false);
});

test("invalid credentials are not retried as a cold start", async () => {
  invalidateBackendReadiness();
  setAccessToken(null);
  let calls = 0;
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL) => {
      calls += 1;
      if (String(input).endsWith("/health/database")) {
        return jsonResponse({ status: "ok", database: "reachable" });
      }
      return jsonResponse({ detail: "Invalid email or password" }, 401);
    },
  });

  await assert.rejects(login("learner@example.com", "wrong"), (error: unknown) => {
    return error instanceof ApiError && error.status === 401;
  });
  assert.equal(calls, 2);
});

test("validation failures are not retried", async () => {
  invalidateBackendReadiness();
  setAccessToken(null);
  let calls = 0;
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL) => {
      calls += 1;
      if (String(input).endsWith("/health/database")) {
        return jsonResponse({ status: "ok", database: "reachable" });
      }
      return jsonResponse({ detail: [{ msg: "Invalid input" }] }, 422);
    },
  });

  await assert.rejects(register("invalid", "short"), (error: unknown) => {
    return error instanceof ApiError && error.status === 422;
  });
  assert.equal(calls, 2);
});

test("concurrent callers share one backend readiness probe", async () => {
  invalidateBackendReadiness();
  let resolveHealth: ((response: Response) => void) | undefined;
  let calls = 0;
  Object.assign(globalThis, {
    fetch: async () => {
      calls += 1;
      return new Promise<Response>((resolve) => { resolveHealth = resolve; });
    },
  });

  const first = waitForBackendReady();
  const second = waitForBackendReady();
  await Promise.resolve();
  assert.equal(calls, 1);
  resolveHealth?.(jsonResponse({ status: "ok", database: "reachable" }));
  await Promise.all([first, second]);
});

test("aborting the final consumer cancels pending warm-up work", async () => {
  invalidateBackendReadiness();
  const controller = new AbortController();
  Object.assign(globalThis, {
    fetch: async (_input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Cancelled", "AbortError")),
          { once: true },
        );
      }),
  });

  const pending = waitForBackendReady({ signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, (error: unknown) => {
    return error instanceof DOMException && error.name === "AbortError";
  });
});

test("transient auth restore errors preserve the token but explicit auth failures clear it", () => {
  assert.equal(
    shouldClearAuthenticationOnRestoreFailure(
      new ApiError(0, "Network", undefined, "network"),
    ),
    false,
  );
  assert.equal(shouldClearAuthenticationOnRestoreFailure(new ApiError(503, "Unavailable")), false);
  assert.equal(shouldClearAuthenticationOnRestoreFailure(new ApiError(401, "Expired")), true);
  assert.equal(shouldClearAuthenticationOnRestoreFailure(new ApiError(403, "Disabled")), true);
});

test("write operations outside the auth allowlist are never startup-retried", async () => {
  invalidateBackendReadiness();
  setAccessToken(null);
  let calls = 0;
  Object.assign(globalThis, {
    fetch: async () => {
      calls += 1;
      throw new TypeError("network down");
    },
  });

  await assert.rejects(
    createVocabulary({
      learning_track_id: "track",
      word: "test",
      part_of_speech: "noun",
      meaning: "test",
      translation: "thử",
      translation_language_code: "vi",
      example_sentences: ["A test."],
      level_code: "A1",
      topic: null,
      learning_status: "new",
    }),
  );
  assert.equal(calls, 1);
});

test("auth UI exposes warm-up copy, duplicate-submit guard, and cleanup", async () => {
  const [authPage, authContext, protectedRoute, backendWarmup] = await Promise.all([
    readFile(new URL("../src/pages/AuthPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/auth/AuthContext.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/auth/ProtectedRoute.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/api/backendWarmup.ts", import.meta.url), "utf8"),
  ]);

  assert.match(authPage, /warmupStatusMessage/);
  assert.match(backendWarmup, /Máy chủ đang khởi động/);
  assert.match(authPage, /Máy chủ mất nhiều thời gian hơn dự kiến/);
  assert.match(authPage, /submissionInFlight\.current/);
  assert.match(authPage, /controller\.abort\(\)/);
  assert.match(authContext, /shouldClearAuthenticationOnRestoreFailure/);
  assert.match(authContext, /setRestoreUnavailable\(true\)/);
  assert.match(protectedRoute, /Phiên đăng nhập của bạn vẫn được giữ an toàn/);
});
