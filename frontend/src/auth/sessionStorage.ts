const ACCESS_TOKEN_STORAGE_KEY = "mascot.access_token";

// A normal sign-in lives in sessionStorage (gone when the browser closes).
// "Ghi nhớ đăng nhập" keeps the long-lived token in localStorage instead.
function store(kind: "sessionStorage" | "localStorage"): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window[kind] ?? null;
  } catch {
    return null;
  }
}

export function readAccessToken(): string | null {
  const token =
    store("sessionStorage")?.getItem(ACCESS_TOKEN_STORAGE_KEY)?.trim() ||
    store("localStorage")?.getItem(ACCESS_TOKEN_STORAGE_KEY)?.trim();
  return token || null;
}

export function persistAccessToken(token: string | null, remember = false): void {
  const session = store("sessionStorage");
  const local = store("localStorage");
  // Only one copy may exist, so signing out or switching mode clears the other.
  session?.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  local?.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  if (!token) return;
  (remember ? local ?? session : session)?.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
}

export { ACCESS_TOKEN_STORAGE_KEY };
