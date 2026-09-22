export type PracticeSourceMode = "recent" | "topic" | "custom";

export const DEFAULT_QUESTION_COUNT = 5;
export const MIN_QUESTION_COUNT = 1;
export const MAX_QUESTION_COUNT = 15;
export const RECENT_SOURCE_LIMIT = 20;

export function isQuestionCountDraft(value: string): boolean {
  return /^\d*$/.test(value);
}

export function parseQuestionCount(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) &&
    parsed >= MIN_QUESTION_COUNT &&
    parsed <= MAX_QUESTION_COUNT
    ? parsed
    : null;
}

export function questionCountError(value: string): string | null {
  if (!value.trim()) return "Hãy nhập số câu bạn muốn tạo.";
  return parseQuestionCount(value) === null
    ? `Số câu phải là số nguyên từ ${MIN_QUESTION_COUNT} đến ${MAX_QUESTION_COUNT}.`
    : null;
}

export function normalizedTopic(value: string): string {
  return value.normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

export function generationCount(
  exerciseType: "multiple_choice" | "fill_in_blank",
  multipleChoiceCount: number,
): number {
  return exerciseType === "fill_in_blank" ? 1 : multipleChoiceCount;
}
