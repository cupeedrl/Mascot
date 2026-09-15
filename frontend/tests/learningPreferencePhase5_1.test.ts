import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  getLearningPreference,
  updateLearningPreference,
} from "../src/api/client.ts";


test("learning preference API reads and persists an authoritative track level", async () => {
  const requests: Array<{ url: string; method: string; body?: string }> = [];
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({
        url: String(input),
        method: init?.method ?? "GET",
        body: init?.body ? String(init.body) : undefined,
      });
      return Response.json({
        learning_track_id: "chinese-track",
        framework: "HSK",
        current_level_code: init?.method === "PUT" ? "HSK2" : null,
        level_codes: ["HSK1", "HSK2", "HSK3"],
      });
    },
  });

  await getLearningPreference("chinese-track");
  const saved = await updateLearningPreference("chinese-track", "HSK2");

  assert.equal(saved.current_level_code, "HSK2");
  assert.deepEqual(requests.map(({ method }) => method), ["GET", "PUT"]);
  assert.ok(requests.every(({ url }) => url.endsWith("/learning-preferences/chinese-track")));
  assert.deepEqual(JSON.parse(requests[1]?.body ?? "{}"), {
    current_level_code: "HSK2",
  });
});


test("dashboard selector is metadata-driven and reloads when the active track changes", async () => {
  const source = await readFile(
    new URL("../src/pages/AppHomePage.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /getLearningPreference\(activeTrack\.id\)/);
  assert.match(source, /\}, \[activeTrack\]\);/);
  assert.match(source, /activeTrack\.level_codes\.map/);
  assert.match(source, /Chọn trình độ/);
  assert.match(source, /updateLearningPreference\(activeTrack\.id, nextLevel\)/);
});


test("saved level is backend-backed rather than added to localStorage", async () => {
  const [homeSource, contextSource] = await Promise.all([
    readFile(new URL("../src/pages/AppHomePage.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../src/learning/ActiveLearningTrackContext.tsx", import.meta.url),
      "utf8",
    ),
  ]);

  assert.doesNotMatch(homeSource, /localStorage/);
  assert.match(contextSource, /mascot\.activeLearningTrackId/);
  assert.match(homeSource, /setCurrentLevel\(preference\.current_level_code\)/);
});
