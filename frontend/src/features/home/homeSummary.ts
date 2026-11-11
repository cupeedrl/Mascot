// Plain-language summary for the home page: what to do today, how long it
// takes, the streak sentence and friendly dates. Pure functions, no React.

export const USER_TIME_ZONE = "Asia/Ho_Chi_Minh";

/** Rough time a learner spends per item, used for "khoảng N phút". */
export const SECONDS_PER_REVIEW_WORD = 20;
export const SECONDS_PER_PRACTICE_QUESTION = 40;
/** Above this many due words we suggest a first batch instead of everything. */
export const REVIEW_BATCH = 30;

export interface TodayPlanInput {
  wordsDue: number;
  totalVocabulary: number;
  practiceQuestions: number;
}

export interface TodayPlan {
  kind: "review" | "practice" | "start";
  title: string;
  /** What Mascot says about the task, in first person. */
  detail: string;
  minutes: number | null;
  to: string;
  cta: string;
}

export function estimateMinutes(items: number, secondsPerItem: number): number {
  if (items <= 0) return 0;
  return Math.max(1, Math.ceil((items * secondsPerItem) / 60));
}

export function todayPlan({ wordsDue, totalVocabulary, practiceQuestions }: TodayPlanInput): TodayPlan {
  if (wordsDue > 0) {
    const batch = Math.min(wordsDue, REVIEW_BATCH);
    const left = wordsDue - batch;
    return {
      kind: "review",
      title: left > 0 ? `Ôn ${batch} từ trước` : `Ôn ${wordsDue} từ đang chờ`,
      detail: left > 0
        ? `Bạn có ${wordsDue} từ đến hạn, nhiều quá thì mình chia nhỏ nhé: ôn ${batch} từ bây giờ, ${left} từ còn lại để lúc khác.`
        : `Có ${wordsDue} từ sắp bị quên rồi đó! Ôn một lượt là nhớ lại ngay.`,
      minutes: estimateMinutes(batch, SECONDS_PER_REVIEW_WORD),
      to: "/app/review",
      cta: "Bắt đầu ôn",
    };
  }
  if (totalVocabulary > 0) {
    return {
      kind: "practice",
      title: `Làm ${practiceQuestions} câu luyện tập`,
      detail: "Hôm nay không có từ nào đến hạn. Mình làm vài câu với từ bạn đã lưu cho nhớ chắc nhé!",
      minutes: estimateMinutes(practiceQuestions, SECONDS_PER_PRACTICE_QUESTION),
      to: "/app/practice",
      cta: "Luyện tập",
    };
  }
  return {
    kind: "start",
    title: "Mở sổ từ đầu tiên",
    detail: "Sổ từ của bạn còn trống. Chọn một chủ đề bạn thích, lưu vài từ, mình sẽ nhắc bạn ôn đúng lúc!",
    minutes: null,
    to: "/app/learn",
    cta: "Chọn chủ đề",
  };
}

// ---------------------------------------------------------------- dates

/** Today's date in the learner's time zone, as YYYY-MM-DD. */
export function todayIso(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: USER_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function isoToUtc(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function streakSentence(currentStreak: number, studiedToday: boolean): string {
  if (studiedToday) {
    return currentStreak > 1 ? `Bạn đã học hôm nay, chuỗi ${currentStreak} ngày liên tiếp.` : "Bạn đã học hôm nay.";
  }
  if (currentStreak > 0) return `Học hôm nay để giữ chuỗi ${currentStreak} ngày.`;
  return "Học hôm nay để bắt đầu một chuỗi mới.";
}

/** "Thứ Tư, 11 tháng 11" for the learner's today. */
export function longToday(now: Date = new Date()): string {
  const text = new Intl.DateTimeFormat("vi-VN", {
    timeZone: USER_TIME_ZONE,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(now);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "Hôm nay", "Hôm qua", "3 ngày trước", otherwise "05/11" (or "05/11/2025" in another year). */
export function relativeDay(timestamp: string, now: Date = new Date()): string {
  const today = todayIso(now);
  const day = todayIso(new Date(timestamp));
  const diff = Math.round((isoToUtc(today).getTime() - isoToUtc(day).getTime()) / 86_400_000);
  if (diff === 0) return "Hôm nay";
  if (diff === 1) return "Hôm qua";
  if (diff > 1 && diff < 7) return `${diff} ngày trước`;
  const [year, month, date] = day.split("-");
  return year === today.slice(0, 4) ? `${date}/${month}` : `${date}/${month}/${year}`;
}

export function accuracyText(accuracy: number, exercisesCompleted: number): string {
  if (exercisesCompleted <= 0) return "—";
  return `${Number.isInteger(accuracy) ? accuracy : accuracy.toFixed(1)}%`;
}

/** Vietnamese names put the given name last: "Trần Minh Thư" -> "Thư". */
export function greetingName(displayName?: string | null, username?: string | null): string | null {
  const name = displayName?.trim();
  if (name) return name.split(/\s+/).at(-1) ?? name;
  return username?.trim() || null;
}

/** Stable pick in [0, total) for a given day; FNV-1a over "date:salt". */
export function dailyIndex(dateIso: string, salt: string, total: number): number {
  if (total <= 0) return 0;
  let hash = 0x811c9dc5;
  for (const char of `${dateIso}:${salt}`) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash % total;
}
