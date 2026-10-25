import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  ChatStreamError,
  createSSEParser,
  readChatStream,
  STREAM_INTERRUPTED_MESSAGE,
} from "../src/ai/chatStream.ts";
import { ApiError, postAIChatStream } from "../src/api/client.ts";

const DONE = {
  message: { role: "assistant", content: "Xin chào!" },
  conversation_id: "conversation-1",
  confirmation_required: null,
};

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

// A body that delivers `text` in the given chunk sizes, to exercise splits
// in the middle of lines, fields and multi-byte characters.
function streamOf(text: string, chunkSize = 7): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({
    start(controller) {
      for (let offset = 0; offset < bytes.length; offset += chunkSize) {
        controller.enqueue(bytes.slice(offset, offset + chunkSize));
      }
      controller.close();
    },
  });
}

test("SSE parser handles split chunks, CRLF, comments and multi-line data", () => {
  const seen: Array<[string, string]> = [];
  const parser = createSSEParser((event, data) => seen.push([event, data]));

  parser.push("event: delta\r\nda");
  parser.push('ta: {"text":"a"}\r\n\r\n: keep-alive\n\n');
  parser.push("data: line one\ndata: line two\n\nevent: done\ndata: {}");
  parser.flush();

  assert.deepEqual(seen, [
    ["delta", '{"text":"a"}'],
    ["message", "line one\nline two"],
    ["done", "{}"],
  ]);
});

test("readChatStream forwards deltas and discards, then resolves with done", async () => {
  const events: string[] = [];
  const body =
    sse("delta", { text: "Để tôi " }) +
    sse("discard", {}) +
    sse("delta", { text: "Xin " }) +
    sse("delta", { text: "chào!" }) +
    sse("done", DONE);

  const result = await readChatStream(streamOf(body), {
    onDelta: (text) => events.push(`delta:${text}`),
    onDiscard: () => events.push("discard"),
  });

  assert.deepEqual(events, ["delta:Để tôi ", "discard", "delta:Xin ", "delta:chào!"]);
  assert.deepEqual(result, DONE);
});

test("readChatStream raises the backend status and detail from an error event", async () => {
  const body = sse("delta", { text: "draft" }) + sse("error", { status: 429, detail: "Hệ thống AI đang bận." });

  await assert.rejects(readChatStream(streamOf(body)), (error: unknown) => {
    assert.ok(error instanceof ChatStreamError);
    assert.equal(error.status, 429);
    assert.equal(error.message, "Hệ thống AI đang bận.");
    return true;
  });
});

test("readChatStream reports an interrupted stream that never sent done", async () => {
  await assert.rejects(readChatStream(streamOf(sse("delta", { text: "half" }))), (error: unknown) => {
    assert.ok(error instanceof ChatStreamError);
    assert.equal(error.status, 0);
    assert.equal(error.message, STREAM_INTERRUPTED_MESSAGE);
    return true;
  });
});

test("postAIChatStream posts to /ai/chat/stream and returns the done payload", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: String(input), init });
      return new Response(streamOf(sse("delta", { text: "Xin chào!" }) + sse("done", DONE)), {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    },
  });
  const deltas: string[] = [];

  const result = await postAIChatStream("Xin chào", "track-1", "conversation-1", {
    onDelta: (text) => deltas.push(text),
  });

  assert.equal(requests.length, 1);
  assert.ok(requests[0].url.endsWith("/api/v1/ai/chat/stream"));
  assert.equal(new Headers(requests[0].init?.headers).get("Accept"), "text/event-stream");
  assert.deepEqual(JSON.parse(String(requests[0].init?.body)), {
    message: "Xin chào",
    conversation_id: "conversation-1",
    learning_track_id: "track-1",
  });
  assert.deepEqual(deltas, ["Xin chào!"]);
  assert.deepEqual(result, DONE);
});

test("postAIChatStream maps stream errors to ApiError for the existing chat messages", async () => {
  Object.assign(globalThis, {
    fetch: async () =>
      new Response(streamOf(sse("error", { status: 502, detail: "AI learning data is temporarily unavailable." })), {
        status: 200,
      }),
  });

  await assert.rejects(postAIChatStream("Xin chào"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 502);
    assert.equal(error.message, "AI learning data is temporarily unavailable.");
    return true;
  });
});

test("postAIChatStream keeps HTTP rejections and falls back only when the route is missing", async () => {
  const urls: string[] = [];
  let streamStatus = 404;
  let streamDetail = "AI conversation not found.";
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL) => {
      urls.push(String(input));
      if (String(input).endsWith("/ai/chat/stream")) {
        return new Response(JSON.stringify({ detail: streamDetail }), { status: streamStatus });
      }
      return new Response(JSON.stringify(DONE), { status: 200 });
    },
  });

  await assert.rejects(postAIChatStream("hi"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.message, "AI conversation not found.");
    return true;
  });
  assert.equal(urls.length, 1);

  // An older backend without the stream route: use POST /ai/chat once.
  urls.length = 0;
  streamDetail = "Not Found";
  assert.deepEqual(await postAIChatStream("hi"), DONE);
  assert.equal(urls.length, 2);
  assert.ok(urls[1].endsWith("/api/v1/ai/chat"));

  urls.length = 0;
  streamStatus = 429;
  streamDetail = "Bạn gửi quá nhanh.";
  await assert.rejects(postAIChatStream("hi"), /Bạn gửi quá nhanh/);
  assert.equal(urls.length, 1);
});

test("chat drawer streams into a draft and keeps the final message authoritative", async () => {
  const source = await readFile(
    new URL("../src/components/AIChatDrawer.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /postAIChatStream\(/);
  assert.match(source, /onDelta: \(text\) => setDraft\(\(current\) => current \+ text\)/);
  assert.match(source, /onDiscard: \(\) => setDraft\(""\)/);
  assert.match(source, /confirmation: response\.confirmation_required/);
});
