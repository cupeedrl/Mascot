import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Dumbbell,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  DashboardResponse,
  getDashboard,
  getLearningPreference,
  getStudyCalendar,
  StudyCalendarResponse,
  updateLearningPreference,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";
import { BeeMark } from "../components/BeeMark";
import { StudyActivityCalendar } from "../components/StudyActivityCalendar";
import { useActiveLearningTrack } from "../learning/ActiveLearningTrackContext";

const statusLabels = {
  new: "Mới",
  learning: "Đang học",
  review: "Ôn tập",
  mastered: "Đã thành thạo",
};

const languageFlags: Record<string, string> = {
  en: "/flags/gb.svg",
  zh: "/flags/cn.svg",
};

function languageFlag(languageCode: string): string {
  return languageFlags[languageCode.toLowerCase()] ?? "";
}

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
  const { tracks, activeTrack, setActiveTrackId, isLoading: isTrackLoading } = useActiveLearningTrack();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [currentLevel, setCurrentLevel] = useState<string | null>(null);
  const [isLevelLoading, setIsLevelLoading] = useState(false);
  const [isLevelSaving, setIsLevelSaving] = useState(false);
  const [levelError, setLevelError] = useState<string | null>(null);
  const [calendarCursor, setCalendarCursor] = useState(() => {
    const today = vietnamTodayUtc();
    return { year: today.getUTCFullYear(), month: today.getUTCMonth() + 1 };
  });
  const [studyCalendar, setStudyCalendar] = useState<StudyCalendarResponse | null>(null);
  const [isCalendarLoading, setIsCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (!activeTrack) return;
      setDashboard(await getDashboard(activeTrack.id));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [activeTrack]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    let active = true;
    setCurrentLevel(null);
    setLevelError(null);
    if (!activeTrack) return () => { active = false; };

    setIsLevelLoading(true);
    getLearningPreference(activeTrack.id)
      .then((preference) => {
        if (active) setCurrentLevel(preference.current_level_code);
      })
      .catch((loadError: unknown) => {
        if (active) setLevelError(errorMessage(loadError));
      })
      .finally(() => {
        if (active) setIsLevelLoading(false);
      });
    return () => { active = false; };
  }, [activeTrack]);

  useEffect(() => {
    let active = true;
    if (!activeTrack) return () => { active = false; };

    setIsCalendarLoading(true);
    setCalendarError(null);
    getStudyCalendar(activeTrack.id, calendarCursor.year, calendarCursor.month)
      .then((calendar) => {
        if (active) setStudyCalendar(calendar);
      })
      .catch(() => {
        if (active) setCalendarError("Chưa thể tải hoạt động tháng này.");
      })
      .finally(() => {
        if (active) setIsCalendarLoading(false);
      });
    return () => { active = false; };
  }, [activeTrack, calendarCursor]);

  const moveCalendarMonth = (offset: number) => {
    setCalendarCursor((current) => {
      const next = new Date(Date.UTC(current.year, current.month - 1 + offset, 1));
      const year = next.getUTCFullYear();
      if (year < 2000 || year > 2100) return current;
      return { year, month: next.getUTCMonth() + 1 };
    });
  };

  const handleLevelChange = async (levelCode: string) => {
    if (!activeTrack) return;
    const previousLevel = currentLevel;
    const nextLevel = levelCode || null;
    setCurrentLevel(nextLevel);
    setIsLevelSaving(true);
    setLevelError(null);
    try {
      const preference = await updateLearningPreference(activeTrack.id, nextLevel);
      setCurrentLevel(preference.current_level_code);
    } catch (saveError) {
      setCurrentLevel(previousLevel);
      setLevelError(errorMessage(saveError));
    } finally {
      setIsLevelSaving(false);
    }
  };

  if (isLoading || isTrackLoading) return <PageSkeleton cards={3} />;

  if (error || !dashboard || !activeTrack) {
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

  const today = vietnamDateParts();
  const todayIsoDate = vietnamTodayUtc().toISOString().slice(0, 10);
  const todayFocus = dashboard.words_due_for_review > 0
    ? "Ôn lại từ đến hạn"
    : dashboard.total_vocabulary > 0
      ? "Luyện tập để củng cố"
      : "Bắt đầu từ đầu tiên";
  const hasStudiedToday = studyCalendar?.active_dates.includes(studyCalendar.today) ?? false;
  const currentLevelIndex = currentLevel ? activeTrack.level_codes.indexOf(currentLevel) : -1;
  const nextLevel = currentLevelIndex >= 0
    ? activeTrack.level_codes[currentLevelIndex + 1] ?? "Hoàn thành"
    : "Chưa xác định";

  return (
    <section className="dashboard-page">
      <section className="dashboard-top-grid">
        <section className="dashboard-learning-hero" aria-labelledby="journey-heading">
          <div className="dashboard-hero-copy">
            <p className="eyebrow">CHÀO MỪNG TRỞ LẠI</p>
            <h1 id="journey-heading">Hôm nay mình học gì?</h1>
            <p className="dashboard-hero-description">
              Mascot đã sắp xếp những bước quan trọng nhất để bạn tiếp tục tiến bộ.
            </p>
            <div className="hero-journey-badge">
              <BookOpen size={16} />
              <span>{activeTrack.language.name.toUpperCase()} · {activeTrack.level_framework}</span>
            </div>
            <div className="journey-actions">
              <Link className="primary-link" to="/app/learn">
                Tiếp tục học <ArrowRight size={17} />
              </Link>
              <Link className="hero-text-link" to="/app/vocabulary">Xem từ vựng của tôi</Link>
            </div>
          </div>
          <div className="journey-visual dashboard-mascot-visual" aria-label="Linh vật ong Mascot">
            <span className="hero-microcopy" aria-hidden="true">
              Học đều mỗi ngày.<br />Tiến bộ thật!
            </span>
            <div className="bee-hero-stage" aria-hidden="true">
              <span className="hero-sparkle hero-sparkle-one">✦</span>
              <span className="hero-sparkle hero-sparkle-two">✦</span>
              <BeeMark size={224} variant="hero" />
            </div>
          </div>
          <section className="dashboard-track-selector" aria-label="Chọn lộ trình học">
            <div className="track-summary-main">
              <span className="track-summary-bee"><BeeMark size={42} /></span>
              <div>
                <span className="track-summary-eyebrow">Lộ trình đang học</span>
                <strong>{activeTrack.name}</strong>
                <small>{activeTrack.language.name} · {activeTrack.level_framework}</small>
              </div>
            </div>
            <div className="track-summary-stats" aria-label="Tóm tắt lộ trình">
              <span><b>{currentLevel ?? "Chưa chọn"}</b><small>Trình độ hiện tại</small></span>
              <span><b>{activeTrack.name}</b><small>Lộ trình</small></span>
              <span><b>{nextLevel}</b><small>Mốc tiếp theo</small></span>
            </div>
            <div className="dashboard-track-controls">
              <div className="dashboard-track-options">
                {tracks.map((track) => (
                  <button
                    type="button"
                    key={track.id}
                    className={track.id === activeTrack.id ? "active" : ""}
                    aria-pressed={track.id === activeTrack.id}
                    disabled={isLevelSaving}
                    onClick={() => setActiveTrackId(track.id)}
                  >
                    {languageFlag(track.language.code) ? (
                      <img
                        className="track-language-flag"
                        src={languageFlag(track.language.code)}
                        alt=""
                        width={30}
                        height={20}
                        aria-hidden="true"
                      />
                    ) : (
                      <span className="track-language-flag track-language-flag-fallback" aria-hidden="true">🌐</span>
                    )}
                    <span className="track-language-copy">
                      <strong>{track.language.name}</strong>
                      <small>{track.level_framework} · {track.level_codes[0]}–{track.level_codes.at(-1)}</small>
                    </span>
                    <ArrowRight className="track-language-arrow" size={16} aria-hidden="true" />
                  </button>
                ))}
              </div>
              <label className="dashboard-level-selector">
                <span>Trình độ của bạn</span>
                <select
                  aria-label={`Trình độ ${activeTrack.level_framework}`}
                  value={currentLevel ?? ""}
                  disabled={isLevelLoading || isLevelSaving}
                  onChange={(event) => void handleLevelChange(event.target.value)}
                >
                  <option value="">Chọn trình độ</option>
                  {activeTrack.level_codes.map((levelCode) => (
                    <option key={levelCode} value={levelCode}>{levelCode}</option>
                  ))}
                </select>
                {levelError ? <small role="alert">{levelError}</small> : null}
              </label>
            </div>
          </section>
          <ul className="hero-learning-benefits" aria-label="Lợi ích học tập cùng Mascot">
            <li>
              <BookOpen size={18} />
              <span><strong>Học đúng trọng tâm</strong><small>Theo lộ trình {activeTrack.level_framework}</small></span>
            </li>
            <li>
              <RefreshCw size={18} />
              <span><strong>Ghi nhớ hiệu quả</strong><small>Ôn tập đúng thời điểm</small></span>
            </li>
            <li>
              <Target size={18} />
              <span><strong>Tiến bộ mỗi ngày</strong><small>Theo dõi hành trình rõ ràng</small></span>
            </li>
          </ul>
        </section>
        <aside className="dashboard-hero-meta" aria-label="Tổng quan hoạt động hôm nay">
          <div className="dashboard-date-card">
            <div className="date-card-heading">
              <span className="date-icon"><CalendarDays size={19} /></span>
              <div className="today-date-copy">
                <span>Hôm nay</span>
                <strong>{today.weekday}</strong>
                <time>· {today.dayAndMonth}</time>
              </div>
              <span className={`today-state-pill ${hasStudiedToday ? "complete" : "pending"}`}>
                {hasStudiedToday ? "Đã học" : "Sẵn sàng"}
              </span>
            </div>
            <div className="today-focus">
              <span>Trọng tâm hôm nay</span>
              <strong>{todayFocus}</strong>
              <div className="today-action-row">
                <span><RefreshCw size={13} /><b>{dashboard.words_due_for_review}</b> từ cần ôn</span>
                <span><Target size={13} /><b>10</b> phút</span>
                <Link to={dashboard.words_due_for_review > 0 ? "/app/review" : "/app/learn"}>
                  {dashboard.words_due_for_review > 0 ? "Ôn ngay" : "Học ngay"} <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          </div>
          <StudyActivityCalendar
            year={calendarCursor.year}
            month={calendarCursor.month}
            today={studyCalendar?.today ?? todayIsoDate}
            activeDates={studyCalendar?.active_dates ?? []}
            currentStreak={studyCalendar?.current_streak ?? dashboard.current_streak}
            longestStreak={studyCalendar?.longest_streak ?? dashboard.longest_streak}
            isLoading={isCalendarLoading}
            error={calendarError}
            onPreviousMonth={() => moveCalendarMonth(-1)}
            onNextMonth={() => moveCalendarMonth(1)}
          />
          <section className="dashboard-motivation-card" aria-label="Gợi ý từ Mascot">
            <BeeMark size={44} className="motivation-bee" />
            <div className="motivation-eyebrow">
              <Sparkles size={14} />
              <span>GỢI Ý TỪ MASCOT</span>
            </div>
            <strong className="motivation-title">
              {dashboard.words_due_for_review > 0
                ? `Bạn còn ${dashboard.words_due_for_review} từ đến hạn.`
                : "Duy trì nhịp học hôm nay."}
            </strong>
            <p className="motivation-body">
              {dashboard.words_due_for_review > 0
                ? "Ôn khoảng 10 phút hôm nay để giữ vững tiến độ."
                : "Dành chút ít thời gian để tiếp tục duy trì nhịp học nhé!"}
            </p>
            <Link to="/app/review" className="motivation-cta">
              Ôn tập ngay <ArrowRight size={13} />
            </Link>
          </section>
        </aside>
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
            <div><strong>Ôn từ đến hạn</strong><p>Ôn tập để ghi nhớ lâu hơn.</p></div>
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

      <section className="dashboard-panel dashboard-recent" aria-labelledby="recent-heading">
        <div className="dashboard-panel-heading">
          <div><p className="eyebrow">TỪ VỰNG MỚI THÊM</p><h2 id="recent-heading">Gần đây</h2></div>
          <Link to="/app/vocabulary/new">THÊM TỪ VỰNG <ArrowRight size={15} /></Link>
        </div>

        {dashboard.recently_added_vocabulary.length === 0 ? (
          <div className="dashboard-empty">
            <BeeMark size={76} />
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
