export type BackendWarmupStatus =
  | "connecting"
  | "starting"
  | "almost_ready";

export interface BackendWarmupProgress {
  status: BackendWarmupStatus;
  retryCount: number;
  elapsedMs: number;
}

export interface BackendWarmupOptions {
  signal?: AbortSignal;
  onProgress?: (progress: BackendWarmupProgress) => void;
}

interface RunBackendWarmupOptions extends BackendWarmupOptions {
  delaysMs?: readonly number[];
  sleep?: (delayMs: number, signal?: AbortSignal) => Promise<void>;
  now?: () => number;
}

export class BackendWarmupTimeoutError extends Error {
  public readonly code = "BACKEND_WARMUP_TIMEOUT";

  constructor() {
    super("Máy chủ mất nhiều thời gian hơn dự kiến. Vui lòng thử lại.");
    this.name = "BackendWarmupTimeoutError";
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function isTransientBackendUnavailable(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { status?: unknown; reason?: unknown };
  return (
    candidate.status === 0 ||
    candidate.reason === "network" ||
    candidate.reason === "timeout" ||
    candidate.status === 502 ||
    candidate.status === 503 ||
    candidate.status === 504
  );
}

export function shouldClearAuthenticationOnRestoreFailure(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const status = (error as { status?: unknown }).status;
  return status === 401 || status === 403;
}

function abortError(): DOMException {
  return new DOMException("Operation cancelled", "AbortError");
}

function defaultSleep(delayMs: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(abortError());
  return new Promise((resolve, reject) => {
    const timer = globalThis.setTimeout(resolve, delayMs);
    signal?.addEventListener(
      "abort",
      () => {
        globalThis.clearTimeout(timer);
        reject(abortError());
      },
      { once: true },
    );
  });
}

function statusForAttempt(attempt: number): BackendWarmupStatus {
  if (attempt === 0) return "connecting";
  if (attempt < 3) return "starting";
  return "almost_ready";
}

export async function runBackendWarmup(
  probe: (signal?: AbortSignal) => Promise<void>,
  options: RunBackendWarmupOptions = {},
): Promise<{ retryCount: number; totalWarmupMs: number }> {
  const delaysMs = options.delaysMs ?? [0, 2_000, 4_000, 6_000, 8_000];
  const sleep = options.sleep ?? defaultSleep;
  const now = options.now ?? Date.now;
  const startedAt = now();

  for (let attempt = 0; attempt < delaysMs.length; attempt += 1) {
    if (options.signal?.aborted) throw abortError();
    options.onProgress?.({
      status: statusForAttempt(attempt),
      retryCount: attempt,
      elapsedMs: now() - startedAt,
    });
    if (delaysMs[attempt] > 0) {
      await sleep(delaysMs[attempt], options.signal);
    }
    try {
      await probe(options.signal);
      return { retryCount: attempt, totalWarmupMs: now() - startedAt };
    } catch (error) {
      if (options.signal?.aborted || isAbortError(error)) throw abortError();
      if (!isTransientBackendUnavailable(error)) throw error;
      if (attempt === delaysMs.length - 1) throw new BackendWarmupTimeoutError();
    }
  }

  throw new BackendWarmupTimeoutError();
}

export function warmupStatusMessage(status: BackendWarmupStatus): string {
  if (status === "connecting") return "Đang kết nối tới máy chủ…";
  if (status === "starting") {
    return "Máy chủ đang khởi động. Quá trình này có thể mất vài giây.";
  }
  return "Máy chủ sắp sẵn sàng…";
}
