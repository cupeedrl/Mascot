import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Clock3,
  Cloud,
  Dumbbell,
  GraduationCap,
  Heart,
  Music2,
  Plus,
  RefreshCw,
  Sparkles,
  Star,
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
import { useAuth } from "../auth/AuthContext";
import { PageSkeleton } from "../components/PageSkeleton";
import { PenguinMark } from "../components/PenguinMark";
import { StudyActivityCalendar } from "../components/StudyActivityCalendar";
import { DEFAULT_QUESTION_COUNT } from "../features/exercises/practiceSetup";
import {
  accuracyText,
  greetingName,
  longToday,
  relativeDay,
  todayIso,
  todayPlan,
} from "../features/home/homeSummary";
import { loadWordOfTheDay, type WordOfTheDay } from "../features/home/wordOfTheDay";
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

function currentMonthCursor() {
  const [year, month] = todayIso().split("-").map(Number);
  return { year, month };
}

// Decorative word stickers in the hero, in the language being learned.
function heroStickers(languageCode: string) {
  return languageCode === "zh"
    ? [{ emoji: "🍎", word: "苹果" }, { emoji: "🐼", word: "熊猫" }, { emoji: "📚", word: "书" }]
    : [{ emoji: "🍎", word: "apple" }, { emoji: "🐼", word: "panda" }, { emoji: "📚", word: "book" }];
}

const planIcons = {
  review: RefreshCw,
  practice: Dumbbell,
  start: BookOpen,
};

export function AppHomePage() {
  const { user } = useAuth();
  const { tracks, activeTrack, setActiveTrackId, isLoading: isTrackLoading } = useActiveLearningTrack();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [currentLevel, setCurrentLevel] = useState<string | null>(null);
  const [isLevelLoading, setIsLevelLoading] = useState(false);
  const [isLevelSaving, setIsLevelSaving] = useState(false);
  const [levelError, setLevelError] = useState<string | null>(null);
  const [calendarCursor, setCalendarCursor] = useState(currentMonthCursor);
  const [studyCalendar, setStudyCalendar] = useState<StudyCalendarResponse | null>(null);
  const [isCalendarLoading, setIsCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [word, setWord] = useState<WordOfTheDay | null>(null);
  const [wordSaving, setWordSaving] = useState(false);
  const [wordError, setWordError] = useState<string | null>(null);
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

  // One catalog word per day at the learner's level; hidden if none is available.
  useEffect(() => {
    let active = true;
    setWord(null);
    setWordError(null);
    if (!activeTrack || isLevelLoading) return () => { active = false; };
    loadWordOfTheDay(activeTrack, currentLevel, todayIso())
      .then((result) => {
        if (active) setWord(result);
      })
      .catch(() => {
        if (active) setWord(null);
      });
    return () => { active = false; };
  }, [activeTrack, currentLevel, isLevelLoading]);

  const saveWord = async () => {
    if (!word || word.saved) return;
    setWordSaving(true);
    setWordError(null);
    try {
      await word.save();
      setWord({ ...word, saved: true });
    } catch (saveError) {
      setWordError(errorMessage(saveError));
    } finally {
      setWordSaving(false);
    }
  };

  const moveCalendarMonth = (offset: number) => {
    setCalendarCursor((current) => {
      const next = new Date(Date.UTC(current.year, current.month - 1 + offset, 1));
      const year = next.getUTCFullYear();
      const month = next.getUTCMonth() + 1;
      const now = currentMonthCursor();
      if (year < 2000 || year > now.year || (year === now.year && month > now.month)) return current;
      return { year, month };
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

  const today = todayIso();
  const plan = todayPlan({
    wordsDue: dashboard.words_due_for_review,
    totalVocabulary: dashboard.total_vocabulary,
    practiceQuestions: DEFAULT_QUESTION_COUNT,
  });
  const PlanIcon = planIcons[plan.kind];
  const hasStudiedToday = dashboard.recent_active_dates.some((day) => day.slice(0, 10) === today);
  const firstName = greetingName(user?.display_name, user?.username);
  const accuracy = accuracyText(dashboard.exercise_accuracy, dashboard.exercises_completed);
  const currentLevelIndex = currentLevel ? activeTrack.level_codes.indexOf(currentLevel) : -1;
  const nextLevel = currentLevelIndex >= 0
    ? activeTrack.level_codes[currentLevelIndex + 1] ?? "Hoàn thành"
    : "Chưa xác định";

  return (
    <section className="dashboard-page">
      <section className="dashboard-top-grid">
        <section className="dashboard-learning-hero" aria-labelledby="journey-heading">
          <div className="dashboard-hero-copy">
            <p className="eyebrow">{firstName ? `Chào ${firstName}` : "Chào bạn"}</p>
            <h1 id="journey-heading">Hôm nay mình <em>học gì?</em></h1>
            <p className="dashboard-hero-description">Mỗi ngày vài phút là đủ. Mascot sẽ gợi ý việc nên làm và nhắc bạn ôn đúng lúc.</p>
            <div className="journey-actions">
              <Link className="secondary-link" to="/app/vocabulary">
                <BookOpen size={16} aria-hidden="true" /> Từ vựng của tôi · {dashboard.total_vocabulary} từ
              </Link>
            </div>
            <ul className="hero-stickers" aria-hidden="true">
              {heroStickers(activeTrack.language.code).map((sticker) => (
                <li key={sticker.word}><span>{sticker.emoji}</span><b lang={activeTrack.language.code}>{sticker.word}</b></li>
              ))}
            </ul>
          </div>
          <div className="hero-doodles" aria-hidden="true">
            <Cloud className="hero-doodle hero-doodle-cloud-a" size={46} />
            <Cloud className="hero-doodle hero-doodle-cloud-b" size={32} />
            <Star className="hero-doodle hero-doodle-star" size={20} />
            <Music2 className="hero-doodle hero-doodle-note" size={18} />
            <span className="hero-doodle hero-doodle-dots" />
          </div>
          <div className="journey-visual dashboard-mascot-visual" aria-label="Linh vật chim cánh cụt Mascot">
            <span className="hero-bubble hero-bubble-hello" aria-hidden="true" lang={activeTrack.language.code}>
              {activeTrack.language.code === "zh" ? "你好!" : "Hello!"}
            </span>
            <span className="hero-bubble hero-bubble-word" aria-hidden="true" lang={activeTrack.language.code}>
              {activeTrack.language.code === "zh" ? "加油" : "ABC"}
            </span>
            <Heart className="hero-doodle hero-doodle-heart" size={22} aria-hidden="true" />
            <div className="bee-hero-stage" aria-hidden="true">
              <span className="hero-sparkle hero-sparkle-one">✦</span>
              <span className="hero-sparkle hero-sparkle-two">✦</span>
              <PenguinMark size={224} variant="scholar" />
            </div>
          </div>
          <section className="dashboard-track-selector" aria-label="Chọn lộ trình học">
            <div className="track-summary-main">
              <span className="track-summary-bee"><PenguinMark size={42} /></span>
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
        </section>

        <aside className="dashboard-hero-meta" aria-label="Gợi ý từ Mascot">
          <section className="home-card home-mascot-card" aria-labelledby="mascot-tip-heading">
            <header className="home-mascot-head">
              <span className="home-mascot-avatar"><PenguinMark size={38} /></span>
              <div>
                <span className="home-mascot-eyebrow"><Sparkles size={13} aria-hidden="true" /> Gợi ý từ Mascot</span>
                <time dateTime={today}>{longToday()}</time>
              </div>
            </header>
            <p className="home-mascot-bubble">{plan.detail}</p>
            <div className="home-mascot-task">
              <strong id="mascot-tip-heading">{plan.title}</strong>
              <span className="home-mascot-chips">
                {plan.minutes ? <small><Clock3 size={12} aria-hidden="true" /> Khoảng {plan.minutes} phút</small> : null}
                <small><Target size={12} aria-hidden="true" /> {currentLevel ?? activeTrack.level_framework}</small>
                {hasStudiedToday && <small className="done"><CheckCircle2 size={12} aria-hidden="true" /> Đã học hôm nay</small>}
              </span>
            </div>
            <Link className="primary-link home-today-cta" to={plan.to}>
              <PlanIcon size={16} aria-hidden="true" /> {plan.cta} <ArrowRight size={16} />
            </Link>
          </section>

          <StudyActivityCalendar
            year={calendarCursor.year}
            month={calendarCursor.month}
            today={studyCalendar?.today ?? today}
            activeDates={studyCalendar?.active_dates ?? []}
            currentStreak={studyCalendar?.current_streak ?? dashboard.current_streak}
            longestStreak={studyCalendar?.longest_streak ?? dashboard.longest_streak}
            studiedToday={hasStudiedToday}
            isLoading={isCalendarLoading}
            error={calendarError}
            onPreviousMonth={() => moveCalendarMonth(-1)}
            onNextMonth={() => moveCalendarMonth(1)}
            onCurrentMonth={() => setCalendarCursor(currentMonthCursor())}
          />
          {word && (
            <section className="home-card home-word-card" aria-labelledby="word-heading">
              <header className="home-card-heading">
                <span id="word-heading"><Sparkles size={14} aria-hidden="true" /> Từ của hôm nay</span>
                <small className="home-word-level">{word.levelCode}</small>
              </header>
              <div className="home-word-row">
                <strong className="home-word-tile" lang={activeTrack.language.code}>{word.headword}</strong>
                <div className="home-word-text">
                  {word.pronunciation && <span className="home-word-pron">{word.pronunciation}</span>}
                  <p>{word.meaning}</p>
                  {word.partOfSpeech && <small>{word.partOfSpeech}</small>}
                </div>
                {word.saved ? (
                  <span className="home-word-action saved" title="Đã có trong từ vựng của bạn">
                    <Check size={15} aria-hidden="true" /> Đã lưu
                  </span>
                ) : (
                  <button
                    className="home-word-action"
                    type="button"
                    onClick={() => void saveWord()}
                    disabled={wordSaving}
                    title="Lưu vào từ vựng của tôi"
                  >
                    <Plus size={15} aria-hidden="true" /> {wordSaving ? "Đang lưu" : "Lưu"}
                  </button>
                )}
              </div>
              {wordError && <small className="home-word-error" role="alert">{wordError}</small>}
            </section>
          )}
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
            <span className="metric-icon"><GraduationCap size={19} /></span>
            <div><span>Đã thành thạo</span><strong>{dashboard.mastered_words}</strong></div>
          </article>
          <article className="dashboard-metric">
            <span className="metric-icon"><CheckCircle2 size={19} /></span>
            <div>
              <span>Độ chính xác bài tập</span>
              <strong>{accuracy}</strong>
              {dashboard.exercises_completed === 0 && <small>Chưa làm bài nào</small>}
            </div>
          </article>
        </div>
      </section>

      <section className="next-actions" aria-labelledby="next-actions-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">LÀM THÊM</p>
            <h2 id="next-actions-heading">Khi bạn còn thời gian</h2>
          </div>
        </div>
        <div className="next-action-grid">
          {plan.kind !== "review" && (
            <Link className="next-action-card review-action" to="/app/review">
              <span className="action-icon"><RefreshCw size={21} /></span>
              <div><strong>Ôn tập tự chọn</strong><p>Ôn lại từ mới lưu hoặc theo chủ đề.</p></div>
              <ArrowRight size={18} />
            </Link>
          )}
          {plan.kind !== "practice" && (
            <Link className="next-action-card practice-action" to="/app/practice">
              <span className="action-icon"><Dumbbell size={21} /></span>
              <div><strong>Luyện tập với AI</strong><p>Câu hỏi tạo từ chính vốn từ của bạn.</p></div>
              <ArrowRight size={18} />
            </Link>
          )}
          <Link className="next-action-card add-action" to="/app/vocabulary/new">
            <span className="action-icon"><Plus size={21} /></span>
            <div><strong>Thêm từ vựng</strong><p>Tự nhập hoặc nhờ Mascot AI soạn giúp.</p></div>
            <ArrowRight size={18} />
          </Link>
          {plan.kind !== "start" && (
            <Link className="next-action-card learn-action" to="/app/learn">
              <span className="action-icon"><BookOpen size={21} /></span>
              <div><strong>Khám phá chủ đề</strong><p>Tìm thêm từ theo {activeTrack.level_framework}.</p></div>
              <ArrowRight size={18} />
            </Link>
          )}
        </div>
      </section>

      <section className="dashboard-panel dashboard-recent" aria-labelledby="recent-heading">
        <div className="dashboard-panel-heading">
          <div><p className="eyebrow">TỪ VỰNG MỚI THÊM</p><h2 id="recent-heading">Gần đây</h2></div>
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
                  <time dateTime={item.created_at}>{relativeDay(item.created_at)}</time>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
