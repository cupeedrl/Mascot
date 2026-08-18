import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Dumbbell,
  Flame,
  Plus,
  RefreshCw,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";

import { ApiError, DashboardResponse, getDashboard } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { PageSkeleton } from "../components/PageSkeleton";
import { PenguinMark } from "../components/PenguinMark";

const statusLabels = {
  new: "Mới",
  learning: "Đang học",
  review: "Ôn tập",
  mastered: "Đã thành thạo",
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể tải trang chủ. Vui lòng thử lại.";
}

function accuracyLabel(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

function vietnamTodayUtc(): Date {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return new Date(Date.UTC(Number(value("year")), Number(value("month")) - 1, Number(value("day"))));
}

function activityWeek(activeDates: string[]) {
  const today = vietnamTodayUtc();
  const active = new Set(activeDates);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setUTCDate(today.getUTCDate() - (6 - index));
    const isoDate = date.toISOString().slice(0, 10);
    return {
      isoDate,
      label: ["CN", "T2", "T3", "T4", "T5", "T6", "T7"][date.getUTCDay()],
      isActive: active.has(isoDate),
    };
  });
}

function vietnamDateParts() {
  const now = new Date();
  const weekday = new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    weekday: "long",
  }).format(now);
  const dayAndMonth = new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "numeric",
    month: "long",
  }).format(now);
  return {
    weekday: weekday.charAt(0).toUpperCase() + weekday.slice(1),
    dayAndMonth,
  };
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
        <p>{error ?? "Không thể tải trang chủ."}</p>
        <button className="primary-button compact-button" type="button" onClick={() => void loadDashboard()}>
          Thử lại
        </button>
      </section>
    );
  }

  const weeklyActivity = activityWeek(dashboard.recent_active_dates);
  const today = vietnamDateParts();

  return (
    <section className="dashboard-page">
      <section className="dashboard-top-region">
        <PageHeader
          eyebrow="Chào mừng trở lại"
          title="Hôm nay mình học gì?"
          description="Mascot đã sắp xếp những bước quan trọng nhất để bạn tiếp tục tiến bộ."
        />
        <aside className="dashboard-hero-meta" aria-label="Tổng quan hoạt động hôm nay">
          <div className="dashboard-date-card">
            <span>Hôm nay</span>
            <strong>{today.weekday}</strong>
            <time>{today.dayAndMonth}</time>
          </div>
          <section className="learning-streak-card" aria-label="Chuỗi ngày học tập">
            <div className="streak-summary">
              <span className="streak-icon"><Flame size={18} /></span>
              <div>
                <strong>{dashboard.current_streak} ngày liên tiếp</strong>
                <span>Kỷ lục: {dashboard.longest_streak} ngày</span>
              </div>
            </div>
            <div className="streak-calendar" aria-label="Hoạt động 7 ngày gần nhất">
              {weeklyActivity.map((day) => (
                <div className={day.isActive ? "streak-day active" : "streak-day"} key={day.isoDate}>
                  <span>{day.label}</span>
                  <i aria-label={day.isActive ? "Có hoạt động học" : "Chưa có hoạt động học"} />
                </div>
              ))}
            </div>
          </section>
        </aside>
      </section>

      <section className="journey-hero" aria-labelledby="journey-heading">
        <div className="journey-copy">
          <div className="journey-label"><BookOpen size={17} /> Hành trình hiện tại</div>
          <p className="eyebrow">TIẾNG ANH TỔNG QUÁT · CEFR</p>
          <h2 id="journey-heading">Học từ đúng lộ trình.</h2>
          <p>
            Chọn chủ đề phù hợp, thêm từ vào thư viện cá nhân và luyện lại theo tiến độ thực tế.
          </p>
          <div className="journey-actions">
            <Link className="primary-link" to="/app/learn">
              Tiếp tục học <ArrowRight size={17} />
            </Link>
            <Link className="hero-text-link" to="/app/vocabulary">Xem từ vựng của tôi</Link>
          </div>
        </div>
        <div className="journey-visual" aria-label="Linh vật chim cánh cụt Mascot">
          <div className="penguin-hero-stage" aria-hidden="true">
            <span className="hero-sparkle hero-sparkle-one">✦</span>
            <span className="hero-sparkle hero-sparkle-two">✦</span>
            <PenguinMark size={168} />
          </div>
        </div>
      </section>

      <section className="next-actions" aria-labelledby="next-actions-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">BƯỚC TIẾP THEO</p>
            <h2 id="next-actions-heading">Một bước nhỏ cho hôm nay</h2>
          </div>
        </div>
        <div className="next-action-grid">
          <Link className="next-action-card review-action" to="/app/review">
            <span className="action-icon"><RefreshCw size={21} /></span>
            <div><strong>Ôn từ đến hạn</strong><p>Ôn lại đúng lúc để ghi nhớ lâu hơn.</p></div>
            <b>{dashboard.words_due_for_review}</b>
            <ArrowRight size={18} />
          </Link>
          <Link className="next-action-card practice-action" to="/app/practice">
            <span className="action-icon"><Dumbbell size={21} /></span>
            <div><strong>Luyện tập với AI</strong><p>Luyện câu hỏi từ chính vốn từ của bạn.</p></div>
            <b>{accuracyLabel(dashboard.exercise_accuracy)}</b>
            <ArrowRight size={18} />
          </Link>
          <Link className="next-action-card add-action" to="/app/vocabulary/new">
            <span className="action-icon"><Plus size={21} /></span>
            <div><strong>Thêm từ vựng</strong><p>Thêm thủ công hoặc tạo bản nháp cùng Mascot AI.</p></div>
            <b>Mới</b>
            <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      <section className="progress-summary" aria-labelledby="progress-summary-heading">
        <div className="section-heading-row">
          <div><p className="eyebrow">TIẾN ĐỘ CỦA BẠN</p><h2 id="progress-summary-heading">Nhìn nhanh hành trình</h2></div>
        </div>
        <div className="dashboard-metrics" aria-label="Tổng quan tiến độ">
          <article className="dashboard-metric">
            <span className="metric-icon"><Target size={19} /></span>
            <div><span>Tổng từ vựng</span><strong>{dashboard.total_vocabulary}</strong></div>
          </article>
          <article className="dashboard-metric">
            <span className="metric-icon"><RefreshCw size={19} /></span>
            <div><span>Từ đến hạn ôn</span><strong>{dashboard.words_due_for_review}</strong></div>
          </article>
          <article className="dashboard-metric">
            <span className="metric-icon"><CheckCircle2 size={19} /></span>
            <div><span>Độ chính xác bài tập</span><strong>{accuracyLabel(dashboard.exercise_accuracy)}</strong></div>
          </article>
        </div>
      </section>

      <section className="dashboard-panel dashboard-recent" aria-labelledby="recent-heading">
        <div className="dashboard-panel-heading">
          <div><p className="eyebrow">TỪ VỰNG MỚI THÊM</p><h2 id="recent-heading">Mới trong thư viện của bạn</h2></div>
          <Link to="/app/vocabulary/new">Thêm từ vựng <ArrowRight size={15} /></Link>
        </div>

        {dashboard.recently_added_vocabulary.length === 0 ? (
          <div className="dashboard-empty">
            <PenguinMark size={76} />
            <h3>Thư viện đang chờ bạn</h3>
            <p>Khám phá một chủ đề và thêm những từ đầu tiên.</p>
            <Link className="primary-link" to="/app/learn">Khám phá chủ đề</Link>
          </div>
        ) : (
          <div className="dashboard-recent-list">
            {dashboard.recently_added_vocabulary.map((item) => (
              <Link to={`/app/vocabulary/${item.id}/edit`} key={item.id}>
                <div><strong>{item.word}</strong><p>{item.meaning}</p></div>
                <div className="dashboard-recent-meta">
                  <span>{item.level_code}</span>
                  <span>{statusLabels[item.learning_status]}</span>
                  <time dateTime={item.created_at}>
                    {new Intl.DateTimeFormat("vi-VN", { dateStyle: "short" }).format(new Date(item.created_at))}
                  </time>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
