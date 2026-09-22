import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  createAIConversation,
  deleteAIConversation,
  getAIConversation,
  listAIConversations,
  postAIChat,
} from "../src/api/client.ts";


test("conversation API supports create, list, load, and delete", async () => {
  const requests: Array<{ url: string; method: string }> = [];
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      requests.push({ url, method });
      if (method === "DELETE") return new Response(null, { status: 204 });
      if (url.endsWith("/ai/conversations/conversation-1")) {
        return Response.json({
          id: "conversation-1",
          title: "Hello",
          created_at: "2026-09-08T00:00:00Z",
          updated_at: "2026-09-08T00:00:00Z",
          messages: [{
            id: "message-1",
            role: "user",
            content: "Hello",
            created_at: "2026-09-08T00:00:00Z",
          }],
        });
      }
      if (method === "POST") {
        return Response.json({
          id: "conversation-1",
          title: "New conversation",
          created_at: "2026-09-08T00:00:00Z",
          updated_at: "2026-09-08T00:00:00Z",
        }, { status: 201 });
      }
      return Response.json([]);
    },
  });

  await listAIConversations();
  await createAIConversation();
  const detail = await getAIConversation("conversation-1");
  await deleteAIConversation("conversation-1");

  assert.equal(detail.messages[0]?.content, "Hello");
  assert.deepEqual(requests.map(({ method }) => method), ["GET", "POST", "GET", "DELETE"]);
  assert.ok(requests.every(({ url }) => url.includes("/api/v1/ai/conversations")));
});


test("chat sends one new message with the active server conversation id", async () => {
  let body: Record<string, unknown> = {};
  Object.assign(globalThis, {
    fetch: async (_input: RequestInfo | URL, init?: RequestInit) => {
      body = JSON.parse(String(init?.body));
      return Response.json({
        conversation_id: "conversation-1",
        message: { role: "assistant", content: "Hello" },
        confirmation_required: null,
      });
    },
  });

  await postAIChat("What does resilient mean?", "english-track", "conversation-1");

  assert.deepEqual(body, {
    message: "What does resilient mean?",
    conversation_id: "conversation-1",
    learning_track_id: "english-track",
  });
  assert.equal("messages" in body, false);
});


test("drawer restores, creates, and switches server conversations", async () => {
  const source = await readFile(
    new URL("../src/components/AIChatDrawer.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /listAIConversations\(\)/);
  assert.match(source, /getAIConversation\(selected\.id\)/);
  assert.match(source, /createAIConversation\(\)/);
  assert.match(source, /handleSelectConversation\(conversation\.id\)/);
  assert.match(source, /New Chat/);
  assert.match(source, /localStorage\.setItem/);
  assert.match(source, /setMessages\(detail\.messages\)/);
});


test("restored messages remain plain visible history and confirmation UI is preserved", async () => {
  const source = await readFile(
    new URL("../src/components/AIChatDrawer.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /confirmation: response\.confirmation_required/);
  assert.match(source, /handleConfirm\(msg\.confirmation!/);
  assert.match(source, /handleCancel\(msg\.confirmation!/);
  assert.match(source, /key=\{msg\.id \?\? index\}/);
});
