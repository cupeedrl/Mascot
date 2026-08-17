import { useCallback, useEffect, useState } from "react";
import { Check, Dumbbell, Eye, LayoutDashboard, RefreshCw, X } from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  getDueVocabularies,
  submitVocabularyReview,
  type ReviewQueueResponse,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể hoàn thành lượt ôn. Vui lòng thử lại.";
}

export function ReviewPage() {
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [correctInSession, setCorrectInSession] = useState(0);
  const [incorrectInSession, setIncorrectInSession] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadQueue = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const response = await getDueVocabularies(100);
      setQueue(response);
      setCurrentIndex(0);
      setRevealed(false);
      setCorrectInSession(0);
      setIncorrectInSession(0);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const currentItem = queue?.items[currentIndex] ?? null;
  const completed = queue !== null && queue.items.length > 0 && !currentItem;
  const reviewedInSession = correctInSession + incorrectInSession;
  const sessionAccuracy = reviewedInSession
    ? Math.round((correctInSession / reviewedInSession) * 100)
    : 0;

  async function recordResult(isCorrect: boolean) {
    if (!currentItem || !revealed) return;
    setIsSubmitting(true);
    setError("");
    try {
      await submitVocabularyReview(currentItem.id, isCorrect);
      if (isCorrect) setCorrectInSession((count) => count + 1);
      else setIncorrectInSession((count) => count + 1);
      setCurrentIndex((index) => index + 1);
      setRevealed(false);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="review-page" aria-labelledby="review-heading">
      <div className="review-heading">
        <div>
          <p className="eyebrow">Vocabulary Review</p>
          <h1 id="review-heading">Ôn từ đến hạn.</h1>
          <p>Tự kiểm tra trí nhớ, mở đáp án rồi chọn kết quả đúng với lần ôn của bạn.</p>
        </div>
        {queue && queue.items.length > 0 && !completed && (
          <div className="review-progress" aria-label="Tiến độ phiên ôn">
            <strong>{currentIndex + 1}/{queue.items.length}</strong>
            <span>{queue.total} từ đến hạn</span>
            <div className="progress-track">
              <span style={{ width: `${(currentIndex / queue.items.length) * 100}%` }} />
            </div>
          </div>
        )}
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}

      {isLoading ? (
        <PageSkeleton cards={1} />
      ) : completed && queue ? (
        <div className="review-complete" role="status">
          <p className="eyebrow">Hoàn thành</p>
          <h2>Đã xong phiên ôn này.</h2>
          <div className="review-summary">
            <div><strong>{queue.items.length}</strong><span>Đã ôn</span></div>
            <div className="correct"><strong>{correctInSession}</strong><span>Đúng</span></div>
            <div className="incorrect"><strong>{incorrectInSession}</strong><span>Sai</span></div>
            <div><strong>{sessionAccuracy}%</strong><span>Accuracy</span></div>
          </div>
          {queue.total > queue.items.length && (
            <p>Còn {queue.total - queue.items.length} từ ngoài giới hạn phiên hiện tại.</p>
          )}
          <div className="review-complete-actions">
            <button className="primary-button" type="button" onClick={() => void loadQueue()}>
              <RefreshCw size={17} /> Kiểm tra lượt tiếp theo
            </button>
            <Link className="secondary-link" to="/app"><LayoutDashboard size={17} /> Dashboard</Link>
            <Link className="secondary-link" to="/app/practice"><Dumbbell size={17} /> Practice</Link>
          </div>
        </div>
      ) : !currentItem ? (
        <div className="list-state review-empty">
          <h2>Chưa có từ nào đến hạn.</h2>
          <p>Từ mới trong My Vocabulary sẽ xuất hiện ở đây ngay; từ đã ôn sẽ quay lại theo lịch.</p>
          <div className="review-complete-actions">
            <Link className="primary-link" to="/app/learn">Khám phá thư viện</Link>
            <Link className="secondary-link" to="/app/vocabulary">My Vocabulary</Link>
          </div>
        </div>
      ) : (
        <article className="review-card">
          <div className="review-card-meta">
            <span className="level-badge">{currentItem.level_code}</span>
            <span>{currentItem.learning_track.name}</span>
            {currentItem.topic && <span>#{currentItem.topic}</span>}
          </div>
          <div className="review-prompt">
            <h2>{currentItem.word}</h2>
            {currentItem.part_of_speech && <p>{currentItem.part_of_speech}</p>}
          </div>

          {!revealed ? (
            <button
              className="primary-button reveal-button"
              type="button"
              onClick={() => setRevealed(true)}
            >
              <Eye size={18} /> Reveal Meaning
            </button>
          ) : (
            <div className="review-answer" aria-live="polite">
              <p>{currentItem.meaning}</p>
              <strong>{currentItem.translation}</strong>
              {currentItem.example_sentences[0] && (
                <blockquote>{currentItem.example_sentences[0]}</blockquote>
              )}
              <p className="review-question">Bạn nhớ từ này đúng không?</p>
              <div className="review-actions">
                <button
                  className="review-result incorrect"
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => void recordResult(false)}
                >
                  <X size={18} /> Didn't Know
                  <small>Ôn lại sau 1 giờ</small>
                </button>
                <button
                  className="review-result correct"
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => void recordResult(true)}
                >
                  <Check size={18} /> Got It
                  <small>Tiến sang bước tiếp theo</small>
                </button>
              </div>
            </div>
          )}
        </article>
      )}

      <aside className="review-rule-note">
        <strong>Lịch V1</strong>
        <span>Đúng: new → 1 ngày → learning → 3 ngày → review → mastered.</span>
        <span>Sai: quay về learning và ôn lại sau 1 giờ.</span>
      </aside>
    </section>
  );
}
