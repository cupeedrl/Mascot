import { persistAccessToken, readAccessToken } from "../auth/sessionStorage.ts";
import {
  BackendWarmupTimeoutError,
  isTransientBackendUnavailable,
  runBackendWarmup,
  type BackendWarmupOptions,
  type BackendWarmupProgress,
} from "./backendWarmup.ts";


const configuredBaseUrl =
  typeof import.meta !== "undefined" && import.meta.env
    ? import.meta.env.VITE_API_BASE_URL ?? "/api/v1"
    : "/api/v1";

const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

let accessToken: string | null = readAccessToken();
let unauthorizedHandler: (() => void) | null = null;

export interface User {
  id: string;
  email: string;
  role: "user" | "admin";
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
  code?: string;
  existing_vocabulary_id?: string;
}

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }> | ApiErrorDetail;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail?: ApiErrorDetail;
  public readonly code?: string;
  public readonly reason: "http" | "network" | "timeout";

  constructor(
    status: number,
    message: string,
    detail?: ApiErrorDetail,
    reason: "http" | "network" | "timeout" = "http",
  ) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
    this.code = detail?.code;
    this.reason = reason;
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

interface RequestOptions {
  timeoutMs?: number;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const controller = new AbortController();
  let didTimeout = false;
  const timeout = options.timeoutMs
    ? globalThis.setTimeout(() => {
        didTimeout = true;
        controller.abort();
      }, options.timeoutMs)
    : null;
  const callerSignal = init.signal;
  const handleCallerAbort = () => controller.abort();
  callerSignal?.addEventListener("abort", handleCallerAbort, { once: true });
  if (callerSignal?.aborted) controller.abort();

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (callerSignal?.aborted) throw new DOMException("Operation cancelled", "AbortError");
    throw new ApiError(
      0,
      didTimeout
        ? "Yêu cầu tới máy chủ đã hết thời gian chờ."
        : "Không thể kết nối tới máy chủ.",
      undefined,
      didTimeout ? "timeout" : "network",
    );
  } finally {
    if (timeout !== null) globalThis.clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", handleCallerAbort);
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

const BACKEND_READY_CACHE_MS = 60_000;
const HEALTH_REQUEST_TIMEOUT_MS = 5_000;
const AUTH_REQUEST_TIMEOUT_MS = 12_000;

interface SharedWarmup {
  controller: AbortController;
  consumers: number;
  listeners: Set<(progress: BackendWarmupProgress) => void>;
  promise: Promise<void>;
  startedAt: number;
}

let backendReadyAt = 0;
let sharedWarmup: SharedWarmup | null = null;

function recordWarmup(event: string, fields: Record<string, number>): void {
  console.info("Mascot backend warm-up", { event, ...fields });
}

function createSharedWarmup(): SharedWarmup {
  const flow: SharedWarmup = {
    controller: new AbortController(),
    consumers: 0,
    listeners: new Set(),
    promise: Promise.resolve(),
    startedAt: Date.now(),
  };
  recordWarmup("backend_warmup_started", { retry_count: 0, total_warmup_ms: 0 });
  flow.promise = runBackendWarmup(
    async (signal) => {
      await request(
        "/health/database",
        { method: "GET", signal },
        { timeoutMs: HEALTH_REQUEST_TIMEOUT_MS },
      );
    },
    {
      signal: flow.controller.signal,
      onProgress: (progress) => {
        for (const listener of flow.listeners) listener(progress);
      },
    },
  )
    .then((result) => {
      backendReadyAt = Date.now();
      if (result.retryCount > 0) {
        recordWarmup("backend_warmup_success", {
          retry_count: result.retryCount,
          total_warmup_ms: result.totalWarmupMs,
        });
      }
    })
    .catch((error) => {
      if (error instanceof BackendWarmupTimeoutError) {
        recordWarmup("backend_warmup_timeout", {
          retry_count: 4,
          total_warmup_ms: Date.now() - flow.startedAt,
        });
      }
      throw error;
    })
    .finally(() => {
      if (sharedWarmup === flow) sharedWarmup = null;
    });
  return flow;
}

export function invalidateBackendReadiness(): void {
  backendReadyAt = 0;
}

export function waitForBackendReady(
  options: BackendWarmupOptions = {},
): Promise<void> {
  if (Date.now() - backendReadyAt < BACKEND_READY_CACHE_MS) {
    return Promise.resolve();
  }
  const flow = sharedWarmup ?? createSharedWarmup();
  sharedWarmup = flow;
  flow.consumers += 1;
  if (options.onProgress) flow.listeners.add(options.onProgress);

  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      if (settled) return;
      settled = true;
      flow.consumers -= 1;
      if (options.onProgress) flow.listeners.delete(options.onProgress);
      options.signal?.removeEventListener("abort", handleAbort);
      if (flow.consumers === 0 && sharedWarmup === flow) {
        // Detach before aborting so the next caller (e.g. a StrictMode remount)
        // starts a fresh probe instead of joining this cancelled one.
        sharedWarmup = null;
        flow.controller.abort();
      }
    };
    const handleAbort = () => {
      cleanup();
      reject(new DOMException("Operation cancelled", "AbortError"));
    };
    options.signal?.addEventListener("abort", handleAbort, { once: true });
    if (options.signal?.aborted) {
      handleAbort();
      return;
    }
    flow.promise.then(
      () => {
        cleanup();
        resolve();
      },
      (error) => {
        cleanup();
        reject(error);
      },
    );
  });
}

async function requestAfterBackendWarmup<T>(
  path: string,
  init: RequestInit,
  warmupOptions: BackendWarmupOptions,
  retryTransient: boolean,
): Promise<T> {
  await waitForBackendReady(warmupOptions);
  try {
    return await request<T>(path, { ...init, signal: warmupOptions.signal }, {
      timeoutMs: AUTH_REQUEST_TIMEOUT_MS,
    });
  } catch (error) {
    if (!retryTransient || !isTransientBackendUnavailable(error)) throw error;
    invalidateBackendReadiness();
    await waitForBackendReady(warmupOptions);
    return request<T>(path, { ...init, signal: warmupOptions.signal }, {
      timeoutMs: AUTH_REQUEST_TIMEOUT_MS,
    });
  }
}

export function register(
  email: string,
  password: string,
  warmupOptions: BackendWarmupOptions = {},
): Promise<User> {
  return requestAfterBackendWarmup<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  }, warmupOptions, false);
}

export function login(
  email: string,
  password: string,
  warmupOptions: BackendWarmupOptions = {},
): Promise<TokenResponse> {
  return requestAfterBackendWarmup<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  }, warmupOptions, true);
}

export function getCurrentUser(
  warmupOptions: BackendWarmupOptions = {},
): Promise<User> {
  return requestAfterBackendWarmup<User>(
    "/auth/me",
    { method: "GET", signal: warmupOptions.signal },
    warmupOptions,
    true,
  );
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

export function validateResetToken(token: string): Promise<{ valid: boolean }> {
  const query = new URLSearchParams({ token }).toString();
  return request<{ valid: boolean }>(`/auth/reset-password/validate?${query}`);
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
  cefr_level: string;
  examples: string[];
  topic?: string | null;
}

export function generateAIVocabulary(params: {
  word: string;
  part_of_speech: string;
  translation: string;
  learning_track_id?: string;
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
  level_codes: string[];
  language: Language;
}

export interface LearningPreference {
  learning_track_id: string;
  framework: string;
  current_level_code: string | null;
  level_codes: string[];
}

export function getLearningPreference(
  learningTrackId: string,
): Promise<LearningPreference> {
  return request<LearningPreference>(
    `/learning-preferences/${encodeURIComponent(learningTrackId)}`,
  );
}

export function updateLearningPreference(
  learningTrackId: string,
  currentLevelCode: string | null,
): Promise<LearningPreference> {
  return request<LearningPreference>(
    `/learning-preferences/${encodeURIComponent(learningTrackId)}`,
    {
      method: "PUT",
      body: JSON.stringify({ current_level_code: currentLevelCode }),
    },
  );
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
  level_code: string;
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
  level?: string;
  topic?: string;
  learningTrackId?: string;
}

export function getLearningTracks(languageCode?: string): Promise<LearningTrack[]> {
  const query = languageCode ? `?language_code=${encodeURIComponent(languageCode)}` : "";
  return request<LearningTrack[]>(`/catalog/learning-tracks${query}`);
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
  if (params.learningTrackId) query.set("learning_track_id", params.learningTrackId);
  return request<VocabularyListResponse>(`/vocabularies?${query.toString()}`);
}

export async function listAllVocabularies(learningTrackId?: string): Promise<Vocabulary[]> {
  const firstPage = await listVocabularies({ page: 1, pageSize: 100, learningTrackId });
  if (firstPage.total_pages <= 1) return firstPage.items;
  const remainingPages = await Promise.all(
    Array.from({ length: firstPage.total_pages - 1 }, (_, index) =>
      listVocabularies({ page: index + 2, pageSize: 100, learningTrackId }),
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
  learningTrackId?: string,
): Promise<TopicSuggestionListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query.trim()) params.set("q", query.trim());
  if (learningTrackId) params.set("learning_track_id", learningTrackId);
  return request<TopicSuggestionListResponse>(`/vocabularies/topics?${params.toString()}`);
}

export function renamePersonalTopic(
  oldTopic: string,
  newTopic: string,
  learningTrackId?: string,
): Promise<TopicMutationResponse> {
  return request<TopicMutationResponse>("/vocabularies/topics", {
    method: "PATCH",
    body: JSON.stringify({ old_topic: oldTopic, new_topic: newTopic, learning_track_id: learningTrackId }),
  });
}

export function removePersonalTopic(topic: string, learningTrackId?: string): Promise<TopicMutationResponse> {
  return request<TopicMutationResponse>("/vocabularies/topics", {
    method: "DELETE",
    body: JSON.stringify({ topic, learning_track_id: learningTrackId }),
  });
}

export interface ReviewQueueResponse {
  items: Vocabulary[];
  total: number;
  limit: number;
}

export function getDueVocabularies(limit = 50, learningTrackId?: string): Promise<ReviewQueueResponse> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (learningTrackId) query.set("learning_track_id", learningTrackId);
  return request<ReviewQueueResponse>(`/vocabularies/due-for-review?${query.toString()}`);
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

export function getDashboard(learningTrackId?: string): Promise<DashboardResponse> {
  const query = learningTrackId ? `?learning_track_id=${encodeURIComponent(learningTrackId)}` : "";
  return request<DashboardResponse>(`/dashboard${query}`);
}

export interface StudyCalendarResponse {
  year: number;
  month: number;
  today: string;
  active_dates: string[];
  current_streak: number;
  longest_streak: number;
  learning_track_id: string | null;
}

export function getStudyCalendar(
  learningTrackId: string,
  year: number,
  month: number,
): Promise<StudyCalendarResponse> {
  const query = new URLSearchParams({
    learning_track_id: learningTrackId,
    year: String(year),
    month: String(month),
  });
  return request<StudyCalendarResponse>(`/dashboard/study-calendar?${query.toString()}`);
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
  learning_track_id?: string;
}

export function listExercises(pageSize = 100, learningTrackId?: string): Promise<ExerciseListResponse> {
  const query = new URLSearchParams({ page: "1", page_size: String(pageSize) });
  if (learningTrackId) query.set("learning_track_id", learningTrackId);
  return request<ExerciseListResponse>(`/exercises?${query.toString()}`);
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

export function getActiveAIExercises(learningTrackId?: string): Promise<AIExerciseGenerationResponse> {
  const query = learningTrackId ? `?learning_track_id=${encodeURIComponent(learningTrackId)}` : "";
  return request<AIExerciseGenerationResponse>(`/ai/exercises/active${query}`);
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
  level_code: string;
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
  language?: string;
  learningTrack?: string;
  level?: string;
  topic?: string;
  page?: number;
  pageSize?: number;
}): Promise<VocabularySetListResponse> {
  const query = new URLSearchParams({
    ...(params.language ? { language: params.language } : {}),
    ...(params.learningTrack ? { learning_track: params.learningTrack } : {}),
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.level) query.set("level", params.level);
  if (params.topic?.trim()) query.set("topic", params.topic.trim());
  return request<VocabularySetListResponse>(`/vocabulary-sets?${query.toString()}`);
}

export function getVocabularySet(setId: string, learningTrackId?: string): Promise<VocabularySetDetail> {
  const query = learningTrackId ? `?learning_track_id=${encodeURIComponent(learningTrackId)}` : "";
  return request<VocabularySetDetail>(`/vocabulary-sets/${setId}${query}`);
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

export interface AdminOverviewResponse {
  total_users: number;
  total_catalog_entries: number;
  total_personal_vocabulary: number;
  total_practice_sessions: number;
}

export function getAdminOverview(): Promise<AdminOverviewResponse> {
  return request<AdminOverviewResponse>("/admin/overview");
}

export interface AdminUserListItem {
  id: string;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
  last_active_at: string | null;
  personal_vocabulary_count: number;
  practice_session_count: number;
}

export interface AdminUserListResponse {
  items: AdminUserListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface AdminUserRecentActivityItem {
  id: string;
  exercise_id: string;
  is_correct: boolean;
  user_answer: string;
  correct_answer: string;
  completed_at: string;
}

export interface AdminUserDetailResponse {
  id: string;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
  last_active_at: string | null;
  total_vocabulary: number;
  learning_words: number;
  mastered_words: number;
  exercises_completed: number;
  exercise_accuracy: number;
  current_streak: number;
  longest_streak: number;
  recent_activity: AdminUserRecentActivityItem[];
}

export function getAdminUsers(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  role?: "user" | "admin";
  status?: "active" | "disabled";
} = {}): Promise<AdminUserListResponse> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.search?.trim()) query.set("search", params.search.trim());
  if (params.role) query.set("role", params.role);
  if (params.status) query.set("status", params.status);

  return request<AdminUserListResponse>(`/admin/users?${query.toString()}`);
}

export function getAdminUserDetail(userId: string): Promise<AdminUserDetailResponse> {
  return request<AdminUserDetailResponse>(`/admin/users/${userId}`);
}

export function updateAdminUserRole(
  userId: string,
  role: "user" | "admin",
): Promise<AdminUserListItem> {
  return request<AdminUserListItem>(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function updateAdminUserStatus(
  userId: string,
  isActive: boolean,
): Promise<AdminUserListItem> {
  return request<AdminUserListItem>(`/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export interface AdminCatalogEntryItem {
  id: string;
  vocabulary_set_id: string;
  word: string;
  ipa: string | null;
  part_of_speech: string;
  meaning: string;
  translation: string;
  example_sentences: string[];
  level_code: string;
  topic: string;
  set_name: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface AdminCatalogListResponse {
  items: AdminCatalogEntryItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface AdminCreateCatalogEntryPayload {
  word: string;
  ipa?: string;
  part_of_speech: string;
  meaning: string;
  translation: string;
  example_sentences: string[];
  level_code: string;
  topic: string;
}

export interface AdminUpdateCatalogEntryPayload {
  word?: string;
  ipa?: string;
  part_of_speech?: string;
  meaning?: string;
  translation?: string;
  example_sentences?: string[];
  level_code?: string;
  topic?: string;
}

export function getAdminCatalog(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  level?: string;
  topic?: string;
  sortBy?: "word" | "level" | "created_at";
  sortOrder?: "asc" | "desc";
} = {}): Promise<AdminCatalogListResponse> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.search?.trim()) query.set("search", params.search.trim());
  if (params.level) query.set("level", params.level);
  if (params.topic?.trim()) query.set("topic", params.topic.trim());
  if (params.sortBy) query.set("sort_by", params.sortBy);
  if (params.sortOrder) query.set("sort_order", params.sortOrder);

  return request<AdminCatalogListResponse>(`/admin/catalog?${query.toString()}`);
}

export function getAdminCatalogEntry(entryId: string): Promise<AdminCatalogEntryItem> {
  return request<AdminCatalogEntryItem>(`/admin/catalog/${entryId}`);
}

export function createAdminCatalogEntry(
  payload: AdminCreateCatalogEntryPayload,
): Promise<AdminCatalogEntryItem> {
  return request<AdminCatalogEntryItem>("/admin/catalog", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAdminCatalogEntry(
  entryId: string,
  payload: AdminUpdateCatalogEntryPayload,
): Promise<AdminCatalogEntryItem> {
  return request<AdminCatalogEntryItem>(`/admin/catalog/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteAdminCatalogEntry(entryId: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(`/admin/catalog/${entryId}`, {
    method: "DELETE",
  });
}

export interface AdminAIUsageItem {
  id: string;
  user_id: string | null;
  user_email: string | null;
  feature: string;
  provider: string;
  model: string;
  status: string;
  status_code: number | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  error_type: string | null;
  created_at: string;
}

export interface AdminAIUsageSummary {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  rate_limited_requests: number;
  average_latency_ms: number;
  total_tokens: number;
}

export interface AdminAIUsageListResponse {
  items: AdminAIUsageItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  summary: AdminAIUsageSummary;
}

export function getAdminAIUsage(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  feature?: string;
  status?: string;
  period?: "24h" | "7d" | "30d" | "all";
  provider?: string;
} = {}): Promise<AdminAIUsageListResponse> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.search?.trim()) query.set("search", params.search.trim());
  if (params.feature) query.set("feature", params.feature);
  if (params.status) query.set("status", params.status);
  if (params.period) query.set("period", params.period);
  if (params.provider) query.set("provider", params.provider);

  return request<AdminAIUsageListResponse>(`/admin/ai-usage?${query.toString()}`);
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AIChatRequest {
  message?: string;
  messages?: ChatMessage[];
  conversation_id?: string;
  learning_track_id?: string;
}

export interface AIChatResponse {
  message: ChatMessage;
  conversation_id: string;
  confirmation_required: AIActionConfirmation | null;
}

export interface AIActionVocabularyDetails {
  word: string;
  ipa: string | null;
  part_of_speech: string;
  meaning: string;
  translation: string;
  translation_language_code: string;
  example_sentences: string[];
  level_code: string;
  topic: string | null;
}

export interface AIActionConfirmation {
  type: "confirmation_required";
  action_id: string;
  action_token: string;
  tool_name: "add_vocabulary";
  summary: string;
  expires_at: string;
  vocabulary: AIActionVocabularyDetails;
}

export interface AIActionExecutionResponse {
  status: "executed";
  action_id: string;
  message: string;
  vocabulary: {
    id: string;
    word: string;
    meaning: string;
    translation: string;
    level_code: string;
    topic: string | null;
    learning_status: string;
  };
}

export interface AIActionCancellationResponse {
  status: "canceled";
  action_id: string;
  message: string;
}

export interface AIConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AIConversationMessage extends ChatMessage {
  id: string;
  created_at: string;
}

export interface AIConversationDetail extends AIConversationSummary {
  messages: AIConversationMessage[];
}

export function listAIConversations(): Promise<AIConversationSummary[]> {
  return request<AIConversationSummary[]>("/ai/conversations");
}

export function createAIConversation(): Promise<AIConversationSummary> {
  return request<AIConversationSummary>("/ai/conversations", { method: "POST" });
}

export function getAIConversation(conversationId: string): Promise<AIConversationDetail> {
  return request<AIConversationDetail>(`/ai/conversations/${conversationId}`);
}

export function deleteAIConversation(conversationId: string): Promise<void> {
  return request<void>(`/ai/conversations/${conversationId}`, { method: "DELETE" });
}

export function postAIChat(
  messageOrMessages: string | ChatMessage[],
  learningTrackId?: string,
  conversationId?: string,
): Promise<AIChatResponse> {
  const payload: AIChatRequest = Array.isArray(messageOrMessages)
    ? { messages: messageOrMessages, learning_track_id: learningTrackId }
    : {
        message: messageOrMessages,
        conversation_id: conversationId,
        learning_track_id: learningTrackId,
      };
  return request<AIChatResponse>("/ai/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function confirmAIAction(
  actionToken: string,
  conversationId?: string,
): Promise<AIActionExecutionResponse> {
  return request<AIActionExecutionResponse>("/ai/actions/confirm", {
    method: "POST",
    body: JSON.stringify({ action_token: actionToken, conversation_id: conversationId }),
  });
}

export function cancelAIAction(
  actionToken: string,
  conversationId?: string,
): Promise<AIActionCancellationResponse> {
  return request<AIActionCancellationResponse>("/ai/actions/cancel", {
    method: "POST",
    body: JSON.stringify({ action_token: actionToken, conversation_id: conversationId }),
  });
}




