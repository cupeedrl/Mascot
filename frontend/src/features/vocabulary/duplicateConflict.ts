interface DuplicateConflictDetail {
  existing_vocabulary_id?: string;
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function getExistingVocabularyId(
  detail: DuplicateConflictDetail | undefined,
): string | null {
  const vocabularyId = detail?.existing_vocabulary_id;
  return typeof vocabularyId === "string" && UUID_PATTERN.test(vocabularyId)
    ? vocabularyId
    : null;
}

export function getVocabularyEditRoute(vocabularyId: string): string {
  return `/app/vocabulary/${vocabularyId}/edit`;
}
