import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Dumbbell,
  LayoutDashboard,
  RotateCcw,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  Exercise,
  ExerciseAttemptResult,
  ExerciseType,
  Vocabulary,
  generateAIExercises,
  listExercises,
  listVocabularies,
  submitExerciseAttempt,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể hoàn thành yêu cầu. Vui lòng thử lại.";
}

export function PracticePage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [vocabularies, setVocabularies] = useState<Vocabulary[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [generationType, setGenerationType] =
    useState<ExerciseType>("multiple_choice");
  const [generationCount, setGenerationCount] = useState(1);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generationSuccess, setGenerationSuccess] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<ExerciseAttemptResult | null>(null);
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
    setResult(null);
    setCorrectCount(0);
    setCompletedCount(0);
    try {
      const [exerciseResponse, vocabularyResponse] = await Promise.all([
        listExercises(),
        listVocabularies({ page: 1, pageSize: 100 }),
      ]);
      setExercises(exerciseResponse.items);
      setVocabularies(vocabularyResponse.items);
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
  const availableVocabularies = useMemo(
    () => vocabularies.filter((item) => item.learning_status !== "mastered"),
    [vocabularies],
  );
  const selectedVocabularies = useMemo(
    () => availableVocabularies.filter((item) => selectedIds.includes(item.id)),
    [availableVocabularies, selectedIds],
  );
  const distinctSelectedWords = new Set(
    selectedVocabularies.map((item) => item.normalized_word),
  ).size;
  const selectionIsValid =
    selectedIds.length > 0 &&
    generationCount >= 1 &&
    generationCount <= 10 &&
    generationCount <= selectedIds.length &&
    (generationType !== "multiple_choice" || distinctSelectedWords >= 4);

  function resetPracticeSession(items: Exercise[]) {
    setExercises(items);
    setCurrentIndex(0);
    setAnswer("");
    setResult(null);
    setCorrectCount(0);
    setCompletedCount(0);
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

  async function handleGenerate() {
    if (!selectionIsValid || isGenerating) return;
    setIsGenerating(true);
    setGenerationError(null);
    setGenerationSuccess(null);
    try {
      const generated = await generateAIExercises(
        selectedIds,
        generationType,
        generationCount,
      );
      resetPracticeSession(generated.items);
      setGenerationSuccess(
        `Đã tạo ${generated.created_count} bài tập. Bạn có thể luyện ngay bên dưới.`,
      );
    } catch (generateError) {
      setGenerationError(errorMessage(generateError));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!currentExercise || !answer.trim() || isSubmitting || result) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const graded = await submitExerciseAttempt(currentExercise.id, answer);
      setResult(graded);
      setCompletedCount((value) => value + 1);
      if (graded.is_correct) setCorrectCount((value) => value + 1);
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
      <header className="practice-heading">
        <div className="hero-icon"><Dumbbell size={22} /></div>
        <p className="eyebrow">FOCUSED PRACTICE</p>
        <h1>Practice with purpose.</h1>
        <p>Chọn từ trong My Vocabulary, để Mascot AI soạn câu hỏi và backend chấm đáp án rõ ràng.</p>
      </header>

      <section className="ai-exercise-generator" aria-labelledby="ai-generator-title">
        <div className="generator-heading">
          <div>
            <span className="ai-badge"><Sparkles size={15} /> Mascot AI</span>
            <h2 id="ai-generator-title">Generate Exercise</h2>
          </div>
          <span>{selectedIds.length} từ đã chọn</span>
        </div>

        {availableVocabularies.length === 0 ? (
          <div className="empty-state generator-empty">
            <h3>Chưa có từ vựng</h3>
            <p>Hãy thêm từ vào My Vocabulary trước khi tạo bài tập.</p>
          </div>
        ) : (
          <>
            <div className="generator-toolbar">
              <label>
                <span>Loại bài</span>
                <select
                  value={generationType}
                  disabled={isGenerating}
                  onChange={(event) => {
                    setGenerationType(event.target.value as ExerciseType);
                    setGenerationError(null);
                  }}
                >
                  <option value="multiple_choice">Multiple choice</option>
                  <option value="fill_in_blank">Fill in the blank</option>
                </select>
              </label>
              <label>
                <span>Số câu (1–10)</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={generationCount}
                  disabled={isGenerating}
                  onChange={(event) => setGenerationCount(Number(event.target.value))}
                />
              </label>
              <div className="generator-selection-actions">
                <button
                  type="button"
                  disabled={isGenerating}
                  onClick={() => setSelectedIds(availableVocabularies.map((item) => item.id))}
                >
                  Chọn tất cả
                </button>
                <button
                  type="button"
                  disabled={isGenerating || selectedIds.length === 0}
                  onClick={() => setSelectedIds([])}
                >
                  Bỏ chọn
                </button>
              </div>
            </div>

            <div className="generator-vocabulary-list">
              {availableVocabularies.map((vocabulary) => (
                <label
                  className={`generator-vocabulary${selectedIds.includes(vocabulary.id) ? " selected" : ""}`}
                  key={vocabulary.id}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(vocabulary.id)}
                    disabled={isGenerating}
                    onChange={() => toggleVocabulary(vocabulary.id)}
                  />
                  <span>
                    <strong>{vocabulary.word}</strong>
                    <small>{vocabulary.part_of_speech} · {vocabulary.level_code}</small>
                  </span>
                </label>
              ))}
            </div>

            {generationType === "multiple_choice" && distinctSelectedWords < 4 && (
              <p className="generator-hint">Multiple choice cần chọn ít nhất 4 từ khác nhau.</p>
            )}
            {generationCount > selectedIds.length && selectedIds.length > 0 && (
              <p className="generator-hint">Số câu không được lớn hơn số từ đã chọn.</p>
            )}
            {generationError && <div className="inline-error">{generationError}</div>}
            {generationSuccess && <div className="inline-success">{generationSuccess}</div>}

            <button
              className="primary-button generator-submit"
              type="button"
              disabled={!selectionIsValid || isGenerating}
              onClick={() => void handleGenerate()}
            >
              <Sparkles size={18} /> {isGenerating ? "AI đang tạo bài tập…" : "Generate with AI"}
            </button>
          </>
        )}
      </section>

      {exercises.length === 0 ? (
        <div className="empty-state practice-empty">
          <h2>Chưa có bài tập</h2>
          <p>Chọn từ vựng ở trên để tạo phiên luyện tập đầu tiên.</p>
        </div>
      ) : isComplete ? (
        <PracticeSummary
          completedCount={completedCount}
          correctCount={correctCount}
          onRestart={() => resetPracticeSession(exercises)}
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
              <span>{currentExercise.exercise_type === "multiple_choice" ? "Multiple choice" : "Fill in the blank"}</span>
              <span>•</span>
              <span>Nguồn: {currentExercise.source === "manual" ? "Demo" : "AI"}</span>
            </div>
            <h2>{currentExercise.prompt}</h2>

            {currentExercise.exercise_type === "multiple_choice" ? (
              <div className="practice-options">
                {currentExercise.options?.map((option) => (
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
            ) : (
              <label className="practice-fill-answer">
                <span>Câu trả lời</span>
                <input
                  value={answer}
                  maxLength={1000}
                  disabled={isSubmitting || result !== null}
                  onChange={(event) => setAnswer(event.target.value)}
                  placeholder="Nhập từ còn thiếu"
                  autoComplete="off"
                />
              </label>
            )}

            {error && <div className="inline-error">{error}</div>}

            {result ? (
              <div className={`practice-feedback ${result.is_correct ? "correct" : "incorrect"}`}>
                <strong>{result.is_correct ? <><CheckCircle2 size={19} /> Chính xác!</> : <><XCircle size={19} /> Chưa đúng</>}</strong>
                <p>Đáp án đúng: <b>{result.correct_answer}</b></p>
                {result.explanation && <p>{result.explanation}</p>}
              </div>
            ) : (
              <button
                className="primary-button practice-submit"
                type="submit"
                disabled={!answer.trim() || isSubmitting}
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
  onRestart,
}: {
  completedCount: number;
  correctCount: number;
  onRestart: () => void;
}) {
  const accuracy = completedCount
    ? Math.round((correctCount / completedCount) * 100)
    : 0;
  return (
    <div className="practice-complete">
      <p className="eyebrow">HOÀN THÀNH</p>
      <h2>Kết quả luyện tập</h2>
      <div className="practice-summary">
        <div><strong>{completedCount}</strong><span>Đã làm</span></div>
        <div className="correct"><strong>{correctCount}</strong><span>Đúng</span></div>
        <div><strong>{accuracy}%</strong><span>Độ chính xác</span></div>
      </div>
      <div className="practice-complete-actions">
        <button className="primary-button" type="button" onClick={onRestart}>
          <RotateCcw size={17} /> Practice Again
        </button>
        <Link className="secondary-link" to="/app"><LayoutDashboard size={17} /> Back to Dashboard</Link>
      </div>
    </div>
  );
}
