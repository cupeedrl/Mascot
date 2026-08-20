import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Dumbbell,
  LayoutDashboard,
  ListChecks,
  Minus,
  Plus,
  RotateCcw,
  Sparkles,
  Tags,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  Exercise,
  ExerciseAttemptResult,
  ExerciseClozeBlank,
  ExerciseOption,
  ExerciseType,
  Vocabulary,
  generateAIExercises,
  getActiveAIExercises,
  listAllVocabularies,
  submitExerciseAttempt,
} from "../api/client";
import { LearningIllustration } from "../components/LearningIllustration";
import { PageHeader } from "../components/PageHeader";
import { PageSkeleton } from "../components/PageSkeleton";
import { PenguinMark } from "../components/PenguinMark";
import { TopicCombobox } from "../components/TopicCombobox";
import {
  DEFAULT_QUESTION_COUNT,
  generationCount,
  MAX_QUESTION_COUNT,
  MIN_QUESTION_COUNT,
  RECENT_SOURCE_LIMIT,
  isQuestionCountDraft,
  normalizedTopic,
  parseQuestionCount,
  questionCountError,
  type PracticeSourceMode,
} from "../features/exercises/practiceSetup";

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể hoàn thành yêu cầu. Vui lòng thử lại.";
}

function clozeBlanks(exercise: Exercise | undefined): ExerciseClozeBlank[] | null {
  if (
    exercise?.exercise_type !== "fill_in_blank" ||
    !Array.isArray(exercise.options) ||
    exercise.options.length !== 4 ||
    !exercise.options.every((item) => "number" in item && "options" in item)
  ) {
    return null;
  }
  return exercise.options as ExerciseClozeBlank[];
}

function multipleChoiceOptions(exercise: Exercise): ExerciseOption[] {
  if (!Array.isArray(exercise.options)) return [];
  return exercise.options.filter(
    (item): item is ExerciseOption => "id" in item && "text" in item,
  );
}

function passageParts(prompt: string): { title: string | null; passage: string } {
  const parts = prompt.split(/\n\s*\n/, 2);
  return parts.length === 2
    ? { title: parts[0].trim(), passage: parts[1].trim() }
    : { title: null, passage: prompt };
}

interface SessionReviewItem {
  exercise: Exercise;
  submittedAnswer: string | Record<string, string>;
  result: ExerciseAttemptResult;
}

function optionLabel(options: ExerciseOption[], optionId: string): string {
  const option = options.find((item) => item.id === optionId);
  return option ? `${option.id}. ${option.text}` : optionId;
}

export function PracticePage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [activeSessionExercises, setActiveSessionExercises] = useState<Exercise[]>([]);
  const [vocabularies, setVocabularies] = useState<Vocabulary[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sourceMode, setSourceMode] = useState<PracticeSourceMode>("recent");
  const [selectedTopic, setSelectedTopic] = useState("");
  const [generationType, setGenerationType] =
    useState<ExerciseType>("multiple_choice");
  const [questionCountInput, setQuestionCountInput] = useState(
    String(DEFAULT_QUESTION_COUNT),
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generationSuccess, setGenerationSuccess] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [clozeAnswers, setClozeAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ExerciseAttemptResult | null>(null);
  const [sessionReview, setSessionReview] = useState<SessionReviewItem[]>([]);
  const [correctCount, setCorrectCount] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setIsComplete(false);
    setCurrentIndex(0);
    setAnswer("");
    setClozeAnswers({});
    setResult(null);
    setCorrectCount(0);
    setCompletedCount(0);
    try {
      setExercises([]);
      const [vocabList, activeResp] = await Promise.all([
        listAllVocabularies(),
        getActiveAIExercises().catch(() => ({ items: [], created_count: 0, resumed: false })),
      ]);
      setVocabularies(vocabList);
      if (activeResp.items && activeResp.items.length > 0) {
        setActiveSessionExercises(activeResp.items);
      } else {
        setActiveSessionExercises([]);
      }
      setSessionReview([]);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const currentExercise = exercises[currentIndex];
  const currentClozeBlanks = clozeBlanks(currentExercise);
  const currentPassage = currentExercise
    ? passageParts(currentExercise.prompt)
    : { title: null, passage: "" };
  const allClozeAnswersSelected = currentClozeBlanks
    ? currentClozeBlanks.every((blank) => Boolean(clozeAnswers[String(blank.number)]))
    : false;
  const availableVocabularies = useMemo(
    () => vocabularies.filter((item) => item.learning_status !== "mastered"),
    [vocabularies],
  );
  const selectedVocabularies = useMemo(
    () => availableVocabularies.filter((item) => selectedIds.includes(item.id)),
    [availableVocabularies, selectedIds],
  );
  const recentVocabularies = useMemo(
    () => availableVocabularies.slice(0, RECENT_SOURCE_LIMIT),
    [availableVocabularies],
  );
  const topicVocabularies = useMemo(() => {
    const topic = normalizedTopic(selectedTopic);
    if (!topic) return [];
    return availableVocabularies.filter(
      (item) => item.topic && normalizedTopic(item.topic) === topic,
    );
  }, [availableVocabularies, selectedTopic]);
  const sourceVocabularies =
    sourceMode === "recent"
      ? recentVocabularies
      : sourceMode === "topic"
        ? topicVocabularies
        : selectedVocabularies;
  const distinctSourceWords = new Set(
    sourceVocabularies.map((item) => item.normalized_word),
  ).size;
  const parsedQuestionCount = parseQuestionCount(questionCountInput);

  function resetPracticeSession(items: Exercise[]) {
    setExercises(items);
    setCurrentIndex(0);
    setAnswer("");
    setClozeAnswers({});
    setResult(null);
    setCorrectCount(0);
    setCompletedCount(0);
    setSessionReview([]);
    setIsComplete(false);
    setError(null);
  }

  function toggleVocabulary(vocabularyId: string) {
    setSelectedIds((current) =>
      current.includes(vocabularyId)
        ? current.filter((item) => item !== vocabularyId)
        : [...current, vocabularyId],
    );
    setGenerationError(null);
    setGenerationSuccess(null);
  }

  function selectSourceMode(mode: PracticeSourceMode) {
    setSourceMode(mode);
    setGenerationError(null);
    setGenerationSuccess(null);
  }

  function adjustQuestionCount(delta: number) {
    const current = parsedQuestionCount ?? DEFAULT_QUESTION_COUNT;
    const next = Math.min(
      MAX_QUESTION_COUNT,
      Math.max(MIN_QUESTION_COUNT, current + delta),
    );
    setQuestionCountInput(String(next));
    setGenerationError(null);
  }

  function sourceValidationError(): string | null {
    if (sourceMode === "topic" && !selectedTopic.trim()) {
      return "Hãy chọn một chủ đề trong Từ vựng của tôi.";
    }
    if (sourceMode === "custom" && selectedIds.length === 0) {
      return "Hãy chọn ít nhất một từ để làm nguồn luyện tập.";
    }
    if (sourceVocabularies.length === 0) {
      return "Không có từ vựng phù hợp trong nguồn bạn đã chọn.";
    }
    if (generationType === "multiple_choice" && distinctSourceWords < 4) {
      return "Bạn cần ít nhất 4 từ khác nhau để tạo bài tập trắc nghiệm.";
    }
    return null;
  }

  async function handleGenerate() {
    if (isGenerating) return;
    const countError = generationType === "multiple_choice"
      ? questionCountError(questionCountInput)
      : null;
    const sourceError = sourceValidationError();
    if (
      countError ||
      sourceError ||
      (generationType === "multiple_choice" && parsedQuestionCount === null)
    ) {
      setGenerationError(countError ?? sourceError);
      return;
    }
    setIsGenerating(true);
    setGenerationError(null);
    setGenerationSuccess(null);
    try {
      const generated = await generateAIExercises({
        source_mode: sourceMode,
        ...(sourceMode === "topic" ? { topic: selectedTopic.trim() } : {}),
        ...(sourceMode === "custom" ? { vocabulary_ids: selectedIds } : {}),
        exercise_type: generationType,
        count: generationCount(
          generationType,
          parsedQuestionCount ?? DEFAULT_QUESTION_COUNT,
        ),
      });
      resetPracticeSession(generated.items);
      setActiveSessionExercises([]);
      if (generated.resumed) {
        setGenerationSuccess(
          `Tiếp tục bài tập đang làm (${generated.created_count} câu). Bạn có thể hoàn thành bên dưới.`,
        );
      } else {
        setGenerationSuccess(
          generationType === "fill_in_blank"
            ? "Đã tạo 1 đoạn văn với 4 chỗ trống. Bạn có thể luyện ngay bên dưới."
            : `Đã tạo ${generated.created_count} câu hỏi. Bạn có thể luyện ngay bên dưới.`,
        );
      }
    } catch (generateError) {
      setGenerationError(errorMessage(generateError));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const response = currentClozeBlanks ? clozeAnswers : answer;
    if (
      !currentExercise ||
      (currentClozeBlanks ? !allClozeAnswersSelected : !answer.trim()) ||
      isSubmitting ||
      result
    ) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const graded = await submitExerciseAttempt(currentExercise.id, response);
      setResult(graded);
      setSessionReview((items) => [...items, {
        exercise: currentExercise,
        submittedAnswer: response,
        result: graded,
      }]);
      setCompletedCount((value) => value + (graded.total ?? 1));
      setCorrectCount(
        (value) => value + (graded.correct_count ?? (graded.is_correct ? 1 : 0)),
      );
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleNext() {
    if (currentIndex + 1 >= exercises.length) {
      setIsComplete(true);
      return;
    }
    setCurrentIndex((value) => value + 1);
    setAnswer("");
    setClozeAnswers({});
    setResult(null);
    setError(null);
  }

  if (isLoading) {
    return <PageSkeleton cards={2} />;
  }

  if (error && exercises.length === 0 && vocabularies.length === 0) {
    return (
      <section className="page-state error-state">
        <p>{error}</p>
        <button className="primary-button" type="button" onClick={() => void loadSession()}>
          Thử lại
        </button>
      </section>
    );
  }

  return (
    <section className="practice-page">
      <PageHeader
        className="practice-heading"
        icon={Dumbbell}
        eyebrow="Luyện tập tập trung"
        title="Luyện tập có mục tiêu."
        description="Chọn từ trong Từ vựng của tôi để Mascot AI soạn câu hỏi; backend luôn chấm đáp án theo quy tắc xác định."
        aside={<LearningIllustration variant="practice" />}
      />

      <section className="ai-exercise-generator" aria-labelledby="ai-generator-title">
        <div className="generator-heading">
          <div>
            <span className="ai-badge"><Sparkles size={15} /> Mascot AI</span>
            <h2 id="ai-generator-title">Chuẩn bị phiên luyện tập</h2>
            <p>Chọn nội dung bạn muốn luyện; Mascot sẽ tạo số câu riêng từ nguồn đó.</p>
          </div>
        </div>

        {activeSessionExercises.length > 0 && exercises.length === 0 && (
          <div className="active-session-banner" role="region" aria-label="Bài tập đang dở">
            <div className="active-session-content">
              <span className="active-session-icon" aria-hidden="true">
                <Sparkles size={20} />
              </span>
              <div>
                <strong>Bạn có bài luyện tập chưa hoàn thành ({activeSessionExercises.length} câu)</strong>
                <p>Tiếp tục bài đang làm để củng cố từ vựng thay vì phải tạo bài mới.</p>
              </div>
            </div>
            <button
              className="primary-button active-session-resume-btn"
              type="button"
              onClick={() => {
                resetPracticeSession(activeSessionExercises);
                setActiveSessionExercises([]);
                setGenerationSuccess(
                  `Đã tải lại bài tập chưa hoàn thành (${activeSessionExercises.length} câu).`,
                );
              }}
            >
              Tiếp tục bài đang làm <ArrowRight size={16} />
            </button>
          </div>
        )}

        {availableVocabularies.length === 0 ? (
          <div className="empty-state generator-empty">
            <h3>Chưa có từ vựng</h3>
            <p>Hãy thêm từ vào Từ vựng của tôi trước khi tạo bài tập.</p>
          </div>
        ) : (
          <>
            <div className="practice-setup-step">
              <div className="setup-step-heading">
                <span>1</span>
                <div><strong>Nguồn từ vựng</strong><small>Bạn muốn luyện nhóm từ nào?</small></div>
              </div>
              <div className="source-mode-grid" role="radiogroup" aria-label="Nguồn từ vựng">
                <button className={sourceMode === "recent" ? "active" : ""} type="button" role="radio" aria-checked={sourceMode === "recent"} disabled={isGenerating} onClick={() => selectSourceMode("recent")}>
                  <Clock3 size={19} /><span><strong>Từ gần đây</strong><small>Từ mới thêm gần nhất</small></span>
                </button>
                <button className={sourceMode === "topic" ? "active" : ""} type="button" role="radio" aria-checked={sourceMode === "topic"} disabled={isGenerating} onClick={() => selectSourceMode("topic")}>
                  <Tags size={19} /><span><strong>Theo chủ đề</strong><small>Chọn một chủ đề cá nhân</small></span>
                </button>
                <button className={sourceMode === "custom" ? "active" : ""} type="button" role="radio" aria-checked={sourceMode === "custom"} disabled={isGenerating} onClick={() => selectSourceMode("custom")}>
                  <ListChecks size={19} /><span><strong>Tự chọn</strong><small>Chọn từng từ bạn muốn</small></span>
                </button>
              </div>

              {sourceMode === "topic" && (
                <div className="topic-source-control">
                  <TopicCombobox label="Chủ đề trong Từ vựng của tôi" value={selectedTopic} onChange={(topic) => { setSelectedTopic(topic); setGenerationError(null); }} allowCreate={false} disabled={isGenerating} placeholder="Ví dụ: Công việc" />
                </div>
              )}

              {sourceMode === "custom" && (
                <div className="custom-source-panel">
                  <div className="generator-selection-actions">
                    <strong>{selectedIds.length} từ đã chọn</strong>
                    <div>
                      <button type="button" disabled={isGenerating || selectedIds.length === availableVocabularies.length} onClick={() => { setSelectedIds(availableVocabularies.map((item) => item.id)); setGenerationError(null); }}>Chọn tất cả</button>
                      <button type="button" disabled={isGenerating || selectedIds.length === 0} onClick={() => { setSelectedIds([]); setGenerationError(null); }}>Bỏ chọn</button>
                    </div>
                  </div>
                  <div className="generator-vocabulary-list">
                    {availableVocabularies.map((vocabulary) => (
                      <label className={`generator-vocabulary${selectedIds.includes(vocabulary.id) ? " selected" : ""}`} key={vocabulary.id}>
                        <input type="checkbox" checked={selectedIds.includes(vocabulary.id)} disabled={isGenerating} onChange={() => toggleVocabulary(vocabulary.id)} />
                        <span><strong>{vocabulary.word}</strong><small>{vocabulary.part_of_speech} · {vocabulary.level_code}{vocabulary.topic ? ` · ${vocabulary.topic}` : ""}</small></span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="source-summary" role="status">
                <strong>{sourceVocabularies.length} từ trong nguồn luyện tập</strong>
                <span>{sourceMode === "recent" ? `Đang dùng tối đa ${RECENT_SOURCE_LIMIT} từ được thêm gần đây nhất.` : sourceMode === "topic" ? selectedTopic.trim() ? `${selectedTopic.trim()} · ${topicVocabularies.length} từ khả dụng` : "Chọn chủ đề để xem số từ khả dụng." : "Chọn tất cả chỉ mở rộng nguồn từ, không thay đổi số câu."}</span>
              </div>
            </div>

            <div className="practice-setup-grid">
              <div className="practice-setup-step compact-step">
                <div className="setup-step-heading"><span>2</span><div><strong>Loại bài tập</strong><small>Chọn cách bạn muốn luyện.</small></div></div>
                <label className="setup-field">
                  <span>Loại bài</span>
                  <select value={generationType} disabled={isGenerating} onChange={(event) => { setGenerationType(event.target.value as ExerciseType); setGenerationError(null); }}>
                    <option value="multiple_choice">Trắc nghiệm theo ngữ cảnh</option>
                    <option value="fill_in_blank">Điền từ vào đoạn văn</option>
                  </select>
                </label>
              </div>
              <div className="practice-setup-step compact-step">
                <div className="setup-step-heading"><span>3</span><div><strong>{generationType === "multiple_choice" ? "Số câu hỏi" : "Cấu trúc bài"}</strong><small>{generationType === "multiple_choice" ? "Đây là số câu được tạo, không phải số từ nguồn." : "Một đoạn văn được chấm theo bốn chỗ trống."}</small></div></div>
                {generationType === "multiple_choice" ? (
                  <>
                    <div className="question-count-control">
                      <button type="button" aria-label="Giảm số câu" disabled={isGenerating || parsedQuestionCount === MIN_QUESTION_COUNT} onClick={() => adjustQuestionCount(-1)}><Minus size={17} /></button>
                      <input aria-label="Số câu hỏi" inputMode="numeric" value={questionCountInput} disabled={isGenerating} onChange={(event) => { if (isQuestionCountDraft(event.target.value)) { setQuestionCountInput(event.target.value); setGenerationError(null); } }} onBlur={() => { const message = questionCountError(questionCountInput); if (message) setGenerationError(message); }} />
                      <button type="button" aria-label="Tăng số câu" disabled={isGenerating || parsedQuestionCount === MAX_QUESTION_COUNT} onClick={() => adjustQuestionCount(1)}><Plus size={17} /></button>
                    </div>
                    <small className="question-count-range">1–15 câu hỏi</small>
                  </>
                ) : (
                  <div className="cloze-count-summary"><strong>1 đoạn văn</strong><span>4 chỗ trống</span></div>
                )}
              </div>
            </div>

            <div className="generation-output-summary">
              <strong>{generationType === "fill_in_blank" ? "1 đoạn văn · 4 chỗ trống" : `${parsedQuestionCount ?? "—"} câu hỏi`}</strong>
              <span>sẽ được tạo từ nguồn gồm {sourceVocabularies.length} từ</span>
            </div>
            {generationError && <div className="inline-error">{generationError}</div>}
            {generationSuccess && <div className="inline-success">{generationSuccess}</div>}

            <div className="generate-step-label">
              <span>4</span>
              <div><strong>Tạo phiên luyện tập</strong><small>AI tạo câu hỏi; backend vẫn chấm đáp án theo quy tắc xác định.</small></div>
            </div>
            <button
              className="primary-button generator-submit"
              type="button"
              disabled={isGenerating}
              onClick={() => void handleGenerate()}
            >
              <Sparkles size={18} /> {isGenerating ? "AI đang tạo bài tập…" : "Tạo bài tập với AI"}
            </button>
          </>
        )}
      </section>

      {exercises.length === 0 ? (
        <div className="empty-state practice-empty">
          <PenguinMark size={68} />
          <h2>Chưa có bài tập</h2>
          <p>Chọn từ vựng ở trên để tạo phiên luyện tập đầu tiên.</p>
        </div>
      ) : isComplete ? (
        <PracticeSummary
          completedCount={completedCount}
          correctCount={correctCount}
          reviewItems={sessionReview}
          onRestart={() => resetPracticeSession(exercises)}
          onContinue={() => resetPracticeSession([])}
        />
      ) : (
        <>
          <header className="practice-heading-row session-heading">
            <div>
              <p className="eyebrow">PHIÊN HIỆN TẠI</p>
              <h2>Làm bài</h2>
            </div>
            <div className="practice-progress">
              <strong>{currentIndex + 1} / {exercises.length}</strong>
              <span>Tiến độ phiên</span>
              <div className="progress-track">
                <span style={{ width: `${((currentIndex + (result ? 1 : 0)) / exercises.length) * 100}%` }} />
              </div>
            </div>
          </header>

          <form className="practice-card" onSubmit={handleSubmit}>
            <div className="practice-card-meta">
              <span>{currentExercise.exercise_type === "multiple_choice" ? "Trắc nghiệm theo ngữ cảnh" : "Điền từ vào đoạn văn"}</span>
              <span>•</span>
              <span>Nguồn: {currentExercise.source === "manual" ? "Demo" : "AI"}</span>
            </div>
            {currentClozeBlanks ? (
              <div className="cloze-passage">
                {currentPassage.title && <p className="cloze-title">{currentPassage.title}</p>}
                <p>{currentPassage.passage}</p>
                <span>4 chỗ trống</span>
              </div>
            ) : (
              <h2>{currentExercise.prompt}</h2>
            )}

            {currentExercise.exercise_type === "multiple_choice" ? (
              <div className="practice-options">
                {multipleChoiceOptions(currentExercise).map((option) => (
                  <button
                    className={`practice-option${answer === option.id ? " selected" : ""}`}
                    type="button"
                    key={option.id}
                    disabled={isSubmitting || result !== null}
                    onClick={() => setAnswer(option.id)}
                  >
                    <strong>{option.id}</strong>
                    <span>{option.text}</span>
                  </button>
                ))}
              </div>
            ) : currentClozeBlanks ? (
              <div className="cloze-questions">
                {currentClozeBlanks.map((blank) => {
                  const blankResult = result?.results.find(
                    (item) => item.number === blank.number,
                  );
                  return (
                    <fieldset
                      className={`cloze-question${blankResult ? blankResult.is_correct ? " correct" : " incorrect" : ""}`}
                      key={blank.number}
                    >
                      <legend>Chỗ trống {blank.number}</legend>
                      <div className="practice-options cloze-options">
                        {blank.options.map((option) => (
                          <button
                            className={`practice-option${clozeAnswers[String(blank.number)] === option.id ? " selected" : ""}`}
                            type="button"
                            key={option.id}
                            disabled={isSubmitting || result !== null}
                            onClick={() => setClozeAnswers((current) => ({
                              ...current,
                              [String(blank.number)]: option.id,
                            }))}
                          >
                            <strong>{option.id}</strong>
                            <span>{option.text}</span>
                          </button>
                        ))}
                      </div>
                      {blankResult && (
                        <div className="cloze-result">
                          <strong>{blankResult.is_correct ? "Chính xác" : `Đáp án đúng: ${optionLabel(blank.options, blankResult.correct_answer)}`}</strong>
                          {blankResult.explanation && <p>{blankResult.explanation}</p>}
                        </div>
                      )}
                    </fieldset>
                  );
                })}
              </div>
            ) : (
              <div className="inline-error" role="alert">Bài tập này dùng định dạng cũ và không còn được hỗ trợ trong phiên V1. Hãy tạo một phiên mới.</div>
            )}

            {error && <div className="inline-error">{error}</div>}

            {result && currentClozeBlanks ? (
              <div className={`practice-feedback ${result.is_correct ? "correct" : "incorrect"}`}>
                <strong>{result.is_correct ? <><CheckCircle2 size={19} /> Hoàn toàn chính xác!</> : <><XCircle size={19} /> Kết quả: {result.correct_count}/{result.total}</>}</strong>
                <p>Điểm: <b>{result.score_percent}%</b></p>
              </div>
            ) : result ? (
              <div className={`practice-feedback ${result.is_correct ? "correct" : "incorrect"}`}>
                <strong>{result.is_correct ? <><CheckCircle2 size={19} /> Chính xác!</> : <><XCircle size={19} /> Chưa đúng</>}</strong>
                <p>Đáp án đúng: <b>{optionLabel(multipleChoiceOptions(currentExercise), result.correct_answer)}</b></p>
                {result.explanation && <p>{result.explanation}</p>}
              </div>
            ) : (
              <button
                className="primary-button practice-submit"
                type="submit"
                disabled={currentClozeBlanks ? !allClozeAnswersSelected || isSubmitting : !answer.trim() || isSubmitting}
              >
                {isSubmitting ? "Đang chấm…" : "Nộp đáp án"}
              </button>
            )}

            {result && (
              <button className="primary-button practice-submit" type="button" onClick={handleNext}>
                {currentIndex + 1 === exercises.length ? "Xem tổng kết" : "Câu tiếp theo"} <ArrowRight size={17} />
              </button>
            )}
          </form>
        </>
      )}
    </section>
  );
}

function PracticeSummary({
  completedCount,
  correctCount,
  reviewItems,
  onRestart,
  onContinue,
}: {
  completedCount: number;
  correctCount: number;
  reviewItems: SessionReviewItem[];
  onRestart: () => void;
  onContinue: () => void;
}) {
  const accuracy = completedCount
    ? Math.round((correctCount / completedCount) * 100)
    : 0;
  return (
    <div className="practice-complete">
      <div className="practice-result-hero">
        <div className="result-celebration"><PenguinMark size={82} /></div>
        <div><p className="eyebrow">HOÀN THÀNH PHIÊN</p><h2>Bạn đã hoàn thành phiên luyện tập!</h2><p>Mỗi câu trả lời là một bước giúp vốn từ của bạn vững hơn.</p></div>
        <div className="practice-summary">
          <div><strong>{correctCount}/{completedCount}</strong><span>Kết quả</span></div>
          <div className="correct"><strong>{accuracy}%</strong><span>Độ chính xác</span></div>
          <div><strong>{completedCount - correctCount}</strong><span>Chưa đúng</span></div>
        </div>
      </div>
      <section className="practice-review-list" aria-labelledby="practice-review-heading">
        <div className="section-heading-row"><div><p className="eyebrow">XEM LẠI CÂU HỎI</p><h3 id="practice-review-heading">Kết quả từng bài</h3></div></div>
        {reviewItems.map((item, index) => {
          const options = multipleChoiceOptions(item.exercise);
          const submitted = typeof item.submittedAnswer === "string"
            ? optionLabel(options, item.submittedAnswer)
            : `${item.result.correct_count}/${item.result.total} chỗ trống đúng`;
          const correct = item.exercise.exercise_type === "multiple_choice"
            ? optionLabel(options, item.result.correct_answer)
            : `${item.result.correct_count}/${item.result.total} chỗ trống đúng`;
          return (
            <article className={item.result.is_correct ? "result-review-row correct" : "result-review-row incorrect"} key={item.exercise.id}>
              <span className="result-review-number">{index + 1}</span>
              <div><small>{item.exercise.exercise_type === "multiple_choice" ? "Trắc nghiệm" : "Đoạn văn điền từ"}</small><strong>{item.exercise.prompt}</strong></div>
              <dl><div><dt>Đáp án của bạn</dt><dd>{submitted}</dd></div><div><dt>Kết quả</dt><dd>{correct}</dd></div></dl>
            </article>
          );
        })}
      </section>
      <div className="practice-complete-actions">
        <button className="primary-button" type="button" onClick={onRestart}>
          <RotateCcw size={17} /> Làm lại
        </button>
        <button className="secondary-button" type="button" onClick={onContinue}><Dumbbell size={17} /> Luyện tập tiếp</button>
        <Link className="secondary-link" to="/app"><LayoutDashboard size={17} /> Về trang chủ</Link>
      </div>
    </div>
  );
}
