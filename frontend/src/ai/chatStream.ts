// Reader for POST /ai/chat/stream (Server-Sent Events).
//
// The backend sends:
//   delta   {"text"}            display-only draft text of the answer
//   discard {}                  drop the draft (retry, fallback, or tool calls)
//   done    AIChatResponse      the validated, persisted answer
//   error   {"status","detail"} what POST /ai/chat would have returned
//
// Only `done` is authoritative: the draft is replaced by its message.

export interface ChatStreamHandlers {
  onDelta?: (text: string) => void;
  onDiscard?: () => void;
}

export class ChatStreamError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ChatStreamError";
    this.status = status;
  }
}

export const STREAM_INTERRUPTED_MESSAGE =
  "Kết nối tới Trợ lý AI bị gián đoạn. Hãy mở lại cuộc trò chuyện để xem câu trả lời.";

const EVENT_BOUNDARY = /\r?\n\r?\n/;

// Incremental SSE parser: feed decoded text in any chunk sizes.
export function createSSEParser(onMessage: (event: string, data: string) => void): {
  push: (chunk: string) => void;
  flush: () => void;
} {
  let buffer = "";

  function dispatch(block: string): void {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (!line || line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }
    if (data.length > 0) onMessage(event, data.join("\n"));
  }

  return {
    push(chunk: string) {
      buffer += chunk;
      let match = EVENT_BOUNDARY.exec(buffer);
      while (match) {
        dispatch(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
        match = EVENT_BOUNDARY.exec(buffer);
      }
    },
    flush() {
      if (buffer.trim()) dispatch(buffer);
      buffer = "";
    },
  };
}

// Reads the whole stream and resolves with the `done` payload.
export async function readChatStream(
  body: ReadableStream<Uint8Array>,
  handlers: ChatStreamHandlers = {},
): Promise<unknown> {
  // Mutated from the parser callback, so kept in an object rather than in
  // `let` variables that TypeScript would narrow to their initial values.
  const outcome: { result?: unknown; hasResult: boolean; failure: ChatStreamError | null } = {
    hasResult: false,
    failure: null,
  };

  const parser = createSSEParser((event, data) => {
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(data) as Record<string, unknown>;
    } catch {
      return;
    }
    if (event === "delta" && typeof payload.text === "string") {
      handlers.onDelta?.(payload.text);
    } else if (event === "discard") {
      handlers.onDiscard?.();
    } else if (event === "done") {
      outcome.result = payload;
      outcome.hasResult = true;
    } else if (event === "error") {
      outcome.failure = new ChatStreamError(
        typeof payload.status === "number" ? payload.status : 500,
        typeof payload.detail === "string" ? payload.detail : "Không thể tạo phản hồi từ AI.",
      );
    }
  });

  const reader = body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.push(decoder.decode());
  parser.flush();

  if (outcome.failure) throw outcome.failure;
  if (!outcome.hasResult) throw new ChatStreamError(0, STREAM_INTERRUPTED_MESSAGE);
  return outcome.result;
}
