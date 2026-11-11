// Pure helpers for the sign-in / sign-up forms (kept framework-free for tests).

export interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
  meetsMinimum: boolean;
}

/** Rough strength meter: length is required, variety adds points. */
export function passwordStrength(password: string): PasswordStrength {
  const meetsMinimum = password.length >= 12;
  if (!password) return { score: 0, label: "", meetsMinimum: false };
  let score = 0;
  if (meetsMinimum) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password) || password.length >= 16) score += 1;
  if (!meetsMinimum) score = Math.min(score, 1);
  const labels = ["Rất yếu", "Yếu", "Trung bình", "Khá", "Mạnh"];
  return { score: score as PasswordStrength["score"], label: labels[score], meetsMinimum };
}

export const USERNAME_RULE =
  "3–30 ký tự: chữ thường không dấu, số, dấu chấm hoặc gạch dưới, bắt đầu bằng chữ.";

/** Same rule as the backend; checked locally before asking the server. */
export function normalizeUsername(value: string): string {
  return value.trim().toLowerCase();
}

export function isValidUsername(value: string): boolean {
  const name = normalizeUsername(value);
  return /^[a-z][a-z0-9._]{2,29}$/.test(name) && !/[._]$/.test(name) && !name.includes("..");
}

/** "0:42" style countdown label. */
export function formatCountdown(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

/** Keep only digits, at most `length` of them (for pasting codes). */
export function cleanCode(value: string, length = 6): string {
  return value.replace(/\D/g, "").slice(0, length);
}
