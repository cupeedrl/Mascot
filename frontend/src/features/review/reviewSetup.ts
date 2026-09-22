import type { CefrLevel, Vocabulary } from "../../api/client";

export type ReviewSourceMode = "due" | "recent" | "topic" | "custom";

export const RECENT_REVIEW_LIMIT = 20;

export function filterEligibleVocabularies(
  vocabularies: Vocabulary[],
  filters: {
    search?: string;
    level?: string;
    topic?: string;
  },
): Vocabulary[] {
  let result = vocabularies;

  if (filters.search && filters.search.trim()) {
    const term = filters.search.trim().toLowerCase();
    result = result.filter(
      (item) =>
        item.word.toLowerCase().includes(term) ||
        item.translation.toLowerCase().includes(term) ||
        item.meaning.toLowerCase().includes(term),
    );
  }

  if (filters.level) {
    result = result.filter((item) => item.level_code === filters.level);
  }

  if (filters.topic && filters.topic.trim()) {
    const cleanTopic = filters.topic.trim().toLowerCase();
    result = result.filter(
      (item) => (item.topic || "Khác").toLowerCase() === cleanTopic,
    );
  }

  return result;
}
