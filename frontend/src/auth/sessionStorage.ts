const ACCESS_TOKEN_STORAGE_KEY = "mascot.access_token";

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readAccessToken(): string | null {
  const token = storage()?.getItem(ACCESS_TOKEN_STORAGE_KEY)?.trim();
  return token || null;
}

export function persistAccessToken(token: string | null): void {
  const session = storage();
  if (!session) return;
  if (token) session.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
  else session.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

export { ACCESS_TOKEN_STORAGE_KEY };
