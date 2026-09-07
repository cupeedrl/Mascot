import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  cancelAIAction,
  confirmAIAction,
  postAIChat,
} from "../src/api/client.ts";


test("chat response exposes a deterministic add vocabulary confirmation", async () => {
  const action = {
    type: "confirmation_required",
    action_id: "6e3b40b7-11d4-4283-a646-eb9e49eeaf2b",
    action_token: "opaque-signed-token",
    tool_name: "add_vocabulary",
    summary: 'Add "resilient" to My Vocabulary',
    expires_at: "2026-09-07T10:05:00Z",
    vocabulary: {
      word: "resilient",
      ipa: "/rɪˈzɪliənt/",
      part_of_speech: "adjective",
      meaning: "Able to recover quickly.",
      translation: "kiên cường",
      translation_language_code: "vi",
      example_sentences: ["She remained resilient."],
      level_code: "B2",
      topic: "Personal Growth",
    },
  };
  Object.assign(globalThis, {
    fetch: async () => new Response(
      JSON.stringify({
        message: { role: "assistant", content: "Review and confirm." },
        confirmation_required: action,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  });

  const response = await postAIChat([{ role: "user", content: "Add resilient" }]);

  assert.deepEqual(response.confirmation_required, action);
});


test("confirm and cancel use explicit action endpoints with only the opaque token", async () => {
  const requests: Array<{ url: string; body: unknown }> = [];
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: String(input), body: JSON.parse(String(init?.body)) });
      const isConfirm = String(input).endsWith("/ai/actions/confirm");
      return new Response(
        JSON.stringify(
          isConfirm
            ? {
                status: "executed",
                action_id: "6e3b40b7-11d4-4283-a646-eb9e49eeaf2b",
                message: "Added resilient.",
                vocabulary: {
                  id: "fc33534f-68fc-4676-9aa7-776d16bc8027",
                  word: "resilient",
                  meaning: "Able to recover quickly.",
                  translation: "kiên cường",
                  level_code: "B2",
                  topic: "Personal Growth",
                  learning_status: "new",
                },
              }
            : {
                status: "canceled",
                action_id: "6e3b40b7-11d4-4283-a646-eb9e49eeaf2b",
                message: "Canceled.",
              },
        ),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    },
  });

  await confirmAIAction("opaque-signed-token");
  await cancelAIAction("opaque-signed-token");

  assert.equal(requests[0]?.url.endsWith("/api/v1/ai/actions/confirm"), true);
  assert.equal(requests[1]?.url.endsWith("/api/v1/ai/actions/cancel"), true);
  assert.deepEqual(requests[0]?.body, { action_token: "opaque-signed-token" });
  assert.deepEqual(requests[1]?.body, { action_token: "opaque-signed-token" });
});


test("chat drawer renders explicit Confirm and Cancel controls", async () => {
  const source = await readFile(
    new URL("../src/components/AIChatDrawer.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /Confirm\s*<\/button>/);
  assert.match(source, /Cancel\s*<\/button>/);
  assert.match(source, /handleConfirm\(msg\.confirmation!/);
  assert.match(source, /handleCancel\(msg\.confirmation!/);
  assert.doesNotMatch(source, /content\s*===\s*["']yes["']/i);
});
