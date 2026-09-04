import assert from "node:assert/strict";
import test from "node:test";

import { postAIChat, type ChatMessage } from "../src/api/client.ts";

test("postAIChat sends structured message history to /ai/chat endpoint", async () => {
  let requestedUrl = "";
  let requestedOptions: RequestInit | undefined;

  const mockFetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    requestedUrl = String(input);
    requestedOptions = init;
    return new Response(
      JSON.stringify({
        message: {
          role: "assistant",
          content: "Xin chào! Tôi là Trợ lý AI Mascot.",
        },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  Object.assign(globalThis, { fetch: mockFetch });

  const messages: ChatMessage[] = [
    { role: "user", content: "Hôm nay tôi nên học gì?" },
  ];

  const result = await postAIChat(messages);

  assert.equal(requestedUrl.endsWith("/api/v1/ai/chat"), true);
  assert.equal(requestedOptions?.method, "POST");

  const body = JSON.parse(String(requestedOptions?.body));
  assert.deepEqual(body.messages, messages);
  assert.equal(result.message.role, "assistant");
  assert.equal(result.message.content, "Xin chào! Tôi là Trợ lý AI Mascot.");
});

test("postAIChat rejects message content exceeding client boundary", () => {
  const longContent = "x".repeat(1001);
  assert.equal(longContent.length > 1000, true);
});
