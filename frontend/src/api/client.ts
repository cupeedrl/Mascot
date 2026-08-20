import { persistAccessToken, readAccessToken } from "../auth/sessionStorage";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

let accessToken: string | null = readAccessToken();
let unauthorizedHandler: (() => void) | null = null;

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

interface ApiErrorDetail {
  message?: string;
  existing_vocabulary_id?: string;
}

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }> | ApiErrorDetail;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: ApiErrorDetail,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  persistAccessToken(token);
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Không thể kết nối tới máy chủ.");
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Keep the generic fallback when the response is not JSON.
    }

    if (response.status === 401 && accessToken) {
      unauthorizedHandler?.();
    }

    const detail = body.detail;
    const structuredDetail =
      detail && typeof detail === "object" && !Array.isArray(detail)
        ? detail
        : undefined;
    const message = Array.isArray(detail)
      ? detail[0]?.msg ?? "Dữ liệu không hợp lệ."
      : typeof detail === "string"
        ? detail
        : structuredDetail?.message ?? "Yêu cầu không thành công.";
    throw new ApiError(response.status, message, structuredDetail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function register(email: string, password: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getCurrentUser(): Promise<User> {
  return request<User>("/auth/me");
}

export function logout(): Promise<{ status: "ok" }> {
  return request<{ status: "ok" }>("/auth/logout", { method: "POST" });
}

export function forgotPassword(email: string): Promise<{ message: string }> {
  return request<{ message: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(
  token: string,
  new_password: string,
  confirm_password: string,
): Promise<{ message: string }> {
  return request<{ message: string }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password, confirm_password }),
  });
}

export type LearningStatus = "new" | "learning" | "review" | "mastered";
export type CefrLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface AIVocabularyCandidate {
  word: string;
  part_of_speech: string;
  translation: string;
  ipa: string;
  definition: string;
  cefr_level: CefrLevel;
  examples: string[];
  topic?: string | null;
}

export function generateAIVocabulary(params: {
  word: string;
  part_of_speech: string;
  translation: string;
}): Promise<AIVocabularyCandidate> {
  return request<AIVocabularyCandidate>("/ai/vocabulary", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface Language {
  id: string;
  code: string;
  name: string;
  native_name: string | null;
}

export interface LearningTrack {
  id: string;
  code: string;
  name: string;
  description: string | null;
  level_framework: string;
  language: Language;
}

export interface Vocabulary {
  id: string;
  learning_track_id: string;
  learning_track: LearningTrack;
  source_vocabulary_entry_id: string | null;
  source_vocabulary_entry: {
    id: string;
    vocabulary_set: {
      id: string;
      name: string;
      level_code: string;
      topic: string;
    };
  } | null;
  word: string;
  normalized_word: string;
  ipa: string | null;
  part_of_speech: string;
  meaning: string;
  translation: string;
  translation_language_code: string;
  example_sentences: string[];
  level_code: string;
  topic: string | null;
  learning_status: LearningStatus;
  review_count: number;
  correct_count: number;
  incorrect_count: number;
  last_reviewed_at: string | null;
  next_review_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VocabularyInput {
  learning_track_id: string;
  word: string;
  ipa?: string | null;
  part_of_speech: string;
  meaning: string;
  translation: string;
  translation_language_code: string;
  example_sentences: string[];
  level_code: CefrLevel;
  topic: string | null;
  learning_status: LearningStatus;
}

export interface VocabularyListResponse {
  items: Vocabulary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface VocabularyListParams {
  page: number;
  pageSize: number;
  search?: string;
  learningStatus?: LearningStatus | "";
  level?: CefrLevel | "";
  topic?: string;
}

export function getLearningTracks(): Promise<LearningTrack[]> {
  return request<LearningTrack[]>("/catalog/learning-tracks?language_code=en");
}

export function listVocabularies(
  params: VocabularyListParams,
): Promise<VocabularyListResponse> {
  const query = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  });
  if (params.search?.trim()) query.set("q", params.search.trim());
  if (params.learningStatus) query.set("learning_status", params.learningStatus);
  if (params.level) query.set("level", params.level);
  if (params.topic?.trim()) query.set("topic", params.topic.trim());
  return request<VocabularyListResponse>(`/vocabularies?${query.toString()}`);
}

export async function listAllVocabularies(): Promise<Vocabulary[]> {
  const firstPage = await listVocabularies({ page: 1, pageSize: 100 });
  if (firstPage.total_pages <= 1) return firstPage.items;
  const remainingPages = await Promise.all(
    Array.from({ length: firstPage.total_pages - 1 }, (_, index) =>
      listVocabularies({ page: index + 2, pageSize: 100 }),
    ),
  );
  return [
    ...firstPage.items,
    ...remainingPages.flatMap((page) => page.items),
  ];
}

export function createVocabulary(payload: VocabularyInput): Promise<Vocabulary> {
  return request<Vocabulary>("/vocabularies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getVocabulary(vocabularyId: string): Promise<Vocabulary> {
  return request<Vocabulary>(`/vocabularies/${vocabularyId}`);
}

export function updateVocabulary(
  vocabularyId: string,
  payload: VocabularyInput,
): Promise<Vocabulary> {
  return request<Vocabulary>(`/vocabularies/${vocabularyId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteVocabulary(vocabularyId: string): Promise<void> {
  return request<void>(`/vocabularies/${vocabularyId}`, { method: "DELETE" });
}

export interface TopicSuggestion {
  name: string;
  vocabulary_count: number;
}

export interface TopicSuggestionListResponse {
  items: TopicSuggestion[];
}

export interface TopicMutationResponse {
  updated_count: number;
}

export function listTopicSuggestions(
  query = "",
  limit = 20,
): Promise<TopicSuggestionListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query.trim()) params.set("q", query.trim());
  return request<TopicSuggestionListResponse>(`/vocabularies/topics?${params.toString()}`);
}

export function renamePersonalTopic(
  oldTopic: string,
  newTopic: string,
): Promise<TopicMutationResponse> {
  return request<TopicMutationResponse>("/vocabularies/topics", {
    method: "PATCH",
    body: JSON.stringify({ old_topic: oldTopic, new_topic: newTopic }),
  });
}

export function removePersonalTopic(topic: string): Promise<TopicMutationResponse> {
  return request<TopicMutationResponse>("/vocabularies/topics", {
    method: "DELETE",
    body: JSON.stringify({ topic }),
  });
}

export interface ReviewQueueResponse {
  items: Vocabulary[];
  total: number;
  limit: number;
}

export function getDueVocabularies(limit = 50): Promise<ReviewQueueResponse> {
  return request<ReviewQueueResponse>(`/vocabularies/due-for-review?limit=${limit}`);
}

export function submitVocabularyReview(
  vocabularyId: string,
  isCorrect: boolean,
  force = true,
): Promise<Vocabulary> {
  return request<Vocabulary>(`/vocabularies/${vocabularyId}/reviews`, {
    method: "POST",
    body: JSON.stringify({ is_correct: isCorrect, force }),
  });
}

export interface DashboardRecentVocabulary {
  id: string;
  word: string;
  meaning: string;
  level_code: string;
  learning_status: LearningStatus;
  created_at: string;
}

export interface DashboardResponse {
  total_vocabulary: number;
  new_words: number;
  learning_words: number;
  review_words: number;
  mastered_words: number;
  words_due_for_review: number;
  exercises_completed: number;
  correct_exercise_attempts: number;
  incorrect_exercise_attempts: number;
  exercise_accuracy: number;
  current_streak: number;
  longest_streak: number;
  recent_active_dates: string[];
  recently_added_vocabulary: DashboardRecentVocabulary[];
}

export function getDashboard(): Promise<DashboardResponse> {
  return request<DashboardResponse>("/dashboard");
}

export type ExerciseType = "multiple_choice" | "fill_in_blank";

export interface ExerciseOption {
  id: string;
  text: string;
}

export interface ExerciseClozeBlank {
  number: number;
  options: ExerciseOption[];
}

export interface Exercise {
  id: string;
  learning_track_id: string;
  exercise_type: ExerciseType;
  prompt: string;
  options: ExerciseOption[] | ExerciseClozeBlank[] | null;
  source: "manual" | "ai";
  created_at: string;
}

export interface ExerciseListResponse {
  items: Exercise[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ExerciseAttemptResult {
  id: string;
  exercise_id: string;
  user_answer: string;
  is_correct: boolean;
  correct_answer: string;
  explanation: string | null;
  completed_at: string;
  correct_count: number | null;
  total: number | null;
  score_percent: number | null;
  results: ExerciseBlankResult[];
}

export interface ExerciseBlankResult {
  number: number;
  is_correct: boolean;
  correct_answer: string;
  explanation: string | null;
}

export interface AIExerciseGenerationResponse {
  items: Exercise[];
  created_count: number;
  resumed?: boolean;
}

export type ExerciseSourceMode = "recent" | "topic" | "custom";

export interface AIExerciseGenerationInput {
  source_mode: ExerciseSourceMode;
  topic?: string;
  vocabulary_ids?: string[];
  exercise_type: ExerciseType;
  count: number;
}

export function listExercises(pageSize = 100): Promise<ExerciseListResponse> {
  return request<ExerciseListResponse>(`/exercises?page=1&page_size=${pageSize}`);
}

export function submitExerciseAttempt(
  exerciseId: string,
  response: string | Record<string, string>,
): Promise<ExerciseAttemptResult> {
  return request<ExerciseAttemptResult>(`/exercises/${exerciseId}/attempts`, {
    method: "POST",
    body: JSON.stringify(
      typeof response === "string" ? { answer: response } : { answers: response },
    ),
  });
}

export function getActiveAIExercises(): Promise<AIExerciseGenerationResponse> {
  return request<AIExerciseGenerationResponse>("/ai/exercises/active");
}

export function generateAIExercises(
  input: AIExerciseGenerationInput,
): Promise<AIExerciseGenerationResponse> {
  return request<AIExerciseGenerationResponse>("/ai/exercises/generate", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export type ImportStatus = "none" | "partial" | "all";

export interface VocabularySetListItem {
  id: string;
  name: string;
  description: string | null;
  level_code: CefrLevel;
  topic: string;
  order_index: number;
  learning_track: LearningTrack;
  entry_count: number;
  added_count: number;
  import_status: ImportStatus;
}

export interface VocabularySetListResponse {
  items: VocabularySetListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface VocabularyLibraryEntry {
  id: string;
  word: string;
  normalized_word: string;
  ipa: string | null;
  part_of_speech: string;
  meaning: string;
  translation: string;
  translation_language_code: string;
  example_sentences: string[];
  order_index: number;
  is_added: boolean;
}

export interface VocabularySetDetail extends VocabularySetListItem {
  entries: VocabularyLibraryEntry[];
}

export interface VocabularyImportResponse {
  created_count: number;
  skipped_count: number;
  imported_entry_ids: string[];
}

export function listVocabularySets(params: {
  level?: CefrLevel | "";
  topic?: string;
  page?: number;
  pageSize?: number;
}): Promise<VocabularySetListResponse> {
  const query = new URLSearchParams({
    language: "en",
    learning_track: "general-english",
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.level) query.set("level", params.level);
  if (params.topic?.trim()) query.set("topic", params.topic.trim());
  return request<VocabularySetListResponse>(`/vocabulary-sets?${query.toString()}`);
}

export function getVocabularySet(setId: string): Promise<VocabularySetDetail> {
  return request<VocabularySetDetail>(`/vocabulary-sets/${setId}`);
}

export function importVocabularyEntries(
  entryIds: string[],
): Promise<VocabularyImportResponse> {
  return request<VocabularyImportResponse>("/vocabulary-entries/import", {
    method: "POST",
    body: JSON.stringify({ entry_ids: entryIds }),
  });
}

export function startLearningVocabularySet(
  setId: string,
): Promise<VocabularyImportResponse> {
  return request<VocabularyImportResponse>(
    `/vocabulary-sets/${setId}/start-learning`,
    { method: "POST" },
  );
}
