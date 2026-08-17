import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Dumbbell,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";

import { ApiError, DashboardResponse, getDashboard } from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";

const statusLabels = {
  new: "Mới",
  learning: "Đang học",
  review: "Ôn tập",
  mastered: "Đã thành thạo",
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể tải dashboard. Vui lòng thử lại.";
}

function accuracyLabel(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

export function AppHomePage() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setDashboard(await getDashboard());
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (isLoading) return <PageSkeleton cards={3} />;

  if (error || !dashboard) {
    return (
      <section className="page-state error-state">
        <div className="state-icon"><RefreshCw size={24} /></div>
        <h2>Chưa thể tải hành trình của bạn</h2>
        <p>{error ?? "Không thể tải dashboard."}</p>
        <button className="primary-button compact-button" type="button" onClick={() => void loadDashboard()}>
          Thử lại
        </button>
      </section>
    );
  }

  const masteryProgress = dashboard.total_vocabulary
    ? Math.round((dashboard.mastered_words / dashboard.total_vocabulary) * 100)
    : 0;

  return (
    <section className="dashboard-page">
      <header className="dashboard-welcome">
        <div>
          <p className="eyebrow">YOUR LEARNING JOURNEY</p>
          <h1>Ready for your next word?</h1>
          <p>Tiếp tục General English, ôn đúng lúc và biến từ mới thành vốn từ của riêng bạn.</p>
        </div>
        <span className="welcome-date">
          {new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "numeric", month: "long" }).format(new Date())}
        </span>
      </header>

      <section className="journey-hero" aria-labelledby="journey-heading">
        <div className="journey-copy">
          <div className="journey-label"><BookOpen size={17} /> Current journey</div>
          <p className="eyebrow">GENERAL ENGLISH · CEFR</p>
          <h2 id="journey-heading">Build vocabulary that stays with you.</h2>
          <p>
            Chọn chủ đề phù hợp, thêm từ vào thư viện cá nhân và luyện lại theo tiến độ thực tế.
          </p>
          <div className="journey-actions">
            <Link className="primary-link" to="/app/learn">
              Continue learning <ArrowRight size={17} />
            </Link>
            <Link className="hero-text-link" to="/app/vocabulary">View My Vocabulary</Link>
          </div>
        </div>
        <div className="journey-progress-card">
          <div className="motif-orbit" aria-hidden="true"><Sparkles size={28} /></div>
          <span>Vocabulary mastery</span>
          <strong>{masteryProgress}%</strong>
          <div className="progress-track" aria-label={`${masteryProgress}% từ vựng đã thành thạo`}>
            <span style={{ width: `${masteryProgress}%` }} />
          </div>
          <small>{dashboard.mastered_words} / {dashboard.total_vocabulary} từ đã thành thạo</small>
        </div>
      </section>

      <section className="next-actions" aria-labelledby="next-actions-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">WHAT'S NEXT</p>
            <h2 id="next-actions-heading">Một bước nhỏ cho hôm nay</h2>
          </div>
        </div>
        <div className="next-action-grid">
          <Link className="next-action-card review-action" to="/app/review">
            <span className="action-icon"><RefreshCw size={21} /></span>
            <div><strong>Review due words</strong><p>Ôn lại đúng lúc để ghi nhớ lâu hơn.</p></div>
            <b>{dashboard.words_due_for_review}</b>
            <ArrowRight size={18} />
          </Link>
          <Link className="next-action-card practice-action" to="/app/practice">
            <span className="action-icon"><Dumbbell size={21} /></span>
            <div><strong>Practice with AI</strong><p>Luyện câu hỏi từ chính vốn từ của bạn.</p></div>
            <b>{accuracyLabel(dashboard.exercise_accuracy)}</b>
            <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      <div className="dashboard-metrics" aria-label="Tổng quan tiến độ">
        <article className="dashboard-metric">
          <span className="metric-icon"><Target size={19} /></span>
          <div><span>Vocabulary learned</span><strong>{dashboard.total_vocabulary}</strong></div>
        </article>
        <article className="dashboard-metric">
          <span className="metric-icon"><RefreshCw size={19} /></span>
          <div><span>Due for review</span><strong>{dashboard.words_due_for_review}</strong></div>
        </article>
        <article className="dashboard-metric">
          <span className="metric-icon"><CheckCircle2 size={19} /></span>
          <div><span>Exercise accuracy</span><strong>{accuracyLabel(dashboard.exercise_accuracy)}</strong></div>
        </article>
      </div>

      <div className="dashboard-detail-grid">
        <section className="dashboard-panel" aria-labelledby="status-heading">
          <div className="dashboard-panel-heading">
            <div><p className="eyebrow">MY VOCABULARY</p><h2 id="status-heading">Learning progress</h2></div>
            <Link to="/app/vocabulary">View all <ArrowRight size={15} /></Link>
          </div>
          <dl className="dashboard-status-list">
            <div><dt>Mới</dt><dd>{dashboard.new_words}</dd></div>
            <div><dt>Đang học</dt><dd>{dashboard.learning_words}</dd></div>
            <div><dt>Chờ ôn</dt><dd>{dashboard.review_words}</dd></div>
            <div><dt>Đã thuộc</dt><dd>{dashboard.mastered_words}</dd></div>
          </dl>
        </section>

        <section className="dashboard-panel" aria-labelledby="attempt-heading">
          <div className="dashboard-panel-heading">
            <div><p className="eyebrow">PRACTICE</p><h2 id="attempt-heading">Exercise results</h2></div>
            <Link to="/app/practice">Practice <ArrowRight size={15} /></Link>
          </div>
          <dl className="dashboard-status-list attempt-status">
            <div><dt>Đúng</dt><dd>{dashboard.correct_exercise_attempts}</dd></div>
            <div><dt>Cần luyện thêm</dt><dd>{dashboard.incorrect_exercise_attempts}</dd></div>
          </dl>
        </section>
      </div>

      <section className="dashboard-panel dashboard-recent" aria-labelledby="recent-heading">
        <div className="dashboard-panel-heading">
          <div><p className="eyebrow">RECENTLY ADDED</p><h2 id="recent-heading">Fresh in your library</h2></div>
          <Link to="/app/vocabulary/new">Add vocabulary <ArrowRight size={15} /></Link>
        </div>

        {dashboard.recently_added_vocabulary.length === 0 ? (
          <div className="dashboard-empty">
            <span className="state-icon"><Sparkles size={24} /></span>
            <h3>Your library is ready</h3>
            <p>Khám phá một chủ đề và thêm những từ đầu tiên.</p>
            <Link className="primary-link" to="/app/learn">Explore topics</Link>
          </div>
        ) : (
          <div className="dashboard-recent-list">
            {dashboard.recently_added_vocabulary.map((item) => (
              <article key={item.id}>
                <div><strong>{item.word}</strong><p>{item.meaning}</p></div>
                <div className="dashboard-recent-meta">
                  <span>{item.level_code}</span>
                  <span>{statusLabels[item.learning_status]}</span>
                  <time dateTime={item.created_at}>
                    {new Intl.DateTimeFormat("vi-VN", { dateStyle: "short" }).format(new Date(item.created_at))}
                  </time>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
