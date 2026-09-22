import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  BookOpenCheck,
  Check,
  Clock3,
  Dumbbell,
  Eye,
  Filter,
  GraduationCap,
  Layers,
  LayoutDashboard,
  ListChecks,
  RefreshCw,
  Search,
  Sparkles,
  Tags,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  getDueVocabularies,
  listAllVocabularies,
  listTopicSuggestions,
  submitVocabularyReview,
  type TopicSuggestion,
  type Vocabulary,
} from "../api/client";
import { LearningIllustration } from "../components/LearningIllustration";
import { PageHeader } from "../components/PageHeader";
import { PageSkeleton } from "../components/PageSkeleton";
import { PenguinMark } from "../components/PenguinMark";
import {
  filterEligibleVocabularies,
  RECENT_REVIEW_LIMIT,
  type ReviewSourceMode,
} from "../features/review/reviewSetup";
import { useActiveLearningTrack } from "../learning/ActiveLearningTrackContext";


function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể hoàn thành lượt ôn. Vui lòng thử lại.";
}

export function ReviewPage() {
  const { activeTrack } = useActiveLearningTrack();
  // Source setup state
  const [sourceMode, setSourceMode] = useState<ReviewSourceMode>("due");
  const [dueItems, setDueItems] = useState<Vocabulary[]>([]);
  const [dueTotal, setDueTotal] = useState(0);
  const [allVocabularies, setAllVocabularies] = useState<Vocabulary[]>([]);
  const [topics, setTopics] = useState<TopicSuggestion[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<string>("");

  // Custom filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [topicFilter, setTopicFilter] = useState("");
  const [selectedCustomIds, setSelectedCustomIds] = useState<Set<string>>(new Set());

  // Active review session state
  const [isReviewing, setIsReviewing] = useState(false);
  const [activeQueue, setActiveQueue] = useState<Vocabulary[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [correctInSession, setCorrectInSession] = useState(0);
  const [incorrectInSession, setIncorrectInSession] = useState(0);

  // Loading and error states
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    if (!activeTrack) return;
    setIsLoading(true);
    setError("");
    try {
      const [dueRes, vocabRes, topicRes] = await Promise.all([
        getDueVocabularies(100, activeTrack?.id),
        listAllVocabularies(activeTrack?.id),
        listTopicSuggestions("", 100, activeTrack?.id),
      ]);
      setDueItems(dueRes.items);
      setDueTotal(dueRes.total);
      setAllVocabularies(vocabRes);
      setTopics(topicRes.items);
      if (
        topicRes.items.length > 0
        && !topicRes.items.some((item) => item.name === selectedTopic)
      ) {
        setSelectedTopic(topicRes.items[0].name);
      }
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, [activeTrack?.id, selectedTopic]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    setSelectedCustomIds(new Set());
    setLevelFilter("");
    setTopicFilter("");
    setIsReviewing(false);
  }, [activeTrack?.id]);

  // Derived lists for each source mode
  const recentItems = useMemo(() => {
    return allVocabularies.slice(0, RECENT_REVIEW_LIMIT);
  }, [allVocabularies]);

  const topicItems = useMemo(() => {
    if (!selectedTopic) return [];
    const normalized = selectedTopic.trim().toLowerCase();
    return allVocabularies.filter(
      (item) => (item.topic || "Khác").toLowerCase() === normalized,
    );
  }, [allVocabularies, selectedTopic]);

  const eligibleCustomItems = useMemo(() => {
    return filterEligibleVocabularies(allVocabularies, {
      search: searchQuery,
      level: levelFilter,
      topic: topicFilter,
    });
  }, [allVocabularies, searchQuery, levelFilter, topicFilter]);

  const customSelectedItems = useMemo(() => {
    return allVocabularies.filter((item) => selectedCustomIds.has(item.id));
  }, [allVocabularies, selectedCustomIds]);

  // Start review session with selected source mode
  function startReview(items: Vocabulary[]) {
    if (items.length === 0) return;
    setActiveQueue(items);
    setCurrentIndex(0);
    setRevealed(false);
    setCorrectInSession(0);
    setIncorrectInSession(0);
    setIsReviewing(true);
    setError("");
  }

  function handleStartDue() {
    startReview(dueItems);
  }

  function handleStartRecent() {
    startReview(recentItems);
  }

  function handleStartTopic() {
    startReview(topicItems);
  }

  function handleStartCustom() {
    startReview(customSelectedItems);
  }

  // Custom selection helpers
  function toggleCustomItem(id: string) {
    setSelectedCustomIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function selectAllEligible() {
    setSelectedCustomIds((prev) => {
      const next = new Set(prev);
      for (const item of eligibleCustomItems) {
        next.add(item.id);
      }
      return next;
    });
  }

  function clearCustomSelection() {
    setSelectedCustomIds(new Set());
  }

  // Active review flow
  const currentItem = activeQueue[currentIndex] ?? null;
  const isComplete = isReviewing && activeQueue.length > 0 && !currentItem;
  const reviewedInSession = correctInSession + incorrectInSession;
  const sessionAccuracy = reviewedInSession
    ? Math.round((correctInSession / reviewedInSession) * 100)
    : 0;

  async function recordResult(isCorrect: boolean) {
    if (!currentItem || !revealed || isSubmitting) return;
    setIsSubmitting(true);
    setError("");
    try {
      await submitVocabularyReview(currentItem.id, isCorrect, true);
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

  function exitReviewSession() {
    setIsReviewing(false);
    setActiveQueue([]);
    void loadData();
  }

  if (isLoading && !isReviewing) {
    return <PageSkeleton cards={2} />;
  }

  return (
    <section className="review-page" aria-labelledby="review-heading">
      {!isReviewing ? (
        <>
          <PageHeader
            className="review-heading"
            icon={RefreshCw}
            eyebrow="Ôn tập từ vựng"
            title="Chọn nguồn từ để ôn tập."
            description="Ôn từ đến hạn theo lịch ngắt quãng hoặc chủ động chọn nhóm từ cá nhân bạn muốn củng cố."
            titleId="review-heading"
            aside={<LearningIllustration variant="review" />}
          />

          {error && <div className="form-error" role="alert">{error}</div>}

          {/* Mode Selector */}
          <div className="source-mode-grid" role="radiogroup" aria-label="Chế độ ôn tập">
            <button
              className={sourceMode === "due" ? "active" : ""}
              type="button"
              role="radio"
              aria-checked={sourceMode === "due"}
              onClick={() => setSourceMode("due")}
            >
              <Clock3 size={20} className="source-mode-icon source-icon-review" aria-hidden="true" />
              <span>
                <strong>Từ đến hạn</strong>
                <small>{dueTotal} từ cần ôn theo lịch</small>
              </span>
            </button>

            <button
              className={sourceMode === "recent" ? "active" : ""}
              type="button"
              role="radio"
              aria-checked={sourceMode === "recent"}
              onClick={() => setSourceMode("recent")}
            >
              <Sparkles size={20} className="source-mode-icon source-icon-recent" aria-hidden="true" />
              <span>
                <strong>Từ gần đây</strong>
                <small>Tối đa {RECENT_REVIEW_LIMIT} từ thêm mới nhất</small>
              </span>
            </button>

            <button
              className={sourceMode === "topic" ? "active" : ""}
              type="button"
              role="radio"
              aria-checked={sourceMode === "topic"}
              onClick={() => setSourceMode("topic")}
            >
              <Tags size={20} className="source-mode-icon source-icon-topic" aria-hidden="true" />
              <span>
                <strong>Theo chủ đề</strong>
                <small>{topics.length} chủ đề có sẵn</small>
              </span>
            </button>

            <button
              className={sourceMode === "custom" ? "active" : ""}
              type="button"
              role="radio"
              aria-checked={sourceMode === "custom"}
              onClick={() => setSourceMode("custom")}
            >
              <ListChecks size={20} className="source-mode-icon source-icon-custom" aria-hidden="true" />
              <span>
                <strong>Tự chọn</strong>
                <small>Chọn từng từ bạn muốn</small>
              </span>
            </button>
          </div>

          {/* Mode 1: Due Words */}
          {sourceMode === "due" && (
            <div className="review-setup-panel">
              <div className="review-setup-info">
                <h3>Từ vựng đến hạn ôn tập</h3>
                <p>
                  Mascot tự động tính toán thời điểm ôn tập tối ưu cho từng từ vựng dựa trên lịch ngắt quãng.
                </p>
                <div className="review-mode-stat">
                  <span className="stat-number">{dueTotal}</span>
                  <span className="stat-label">từ đang chờ bạn ôn tập</span>
                </div>
              </div>

              {dueItems.length > 0 ? (
                <div className="review-start-actions">
                  <button className="primary-button" type="button" onClick={handleStartDue}>
                    <GraduationCap size={18} /> Bắt đầu ôn {dueItems.length} từ đến hạn
                  </button>
                </div>
              ) : (
                <div className="review-setup-empty">
                  <PenguinMark size={56} variant="scholar" />
                  <p>Tuyệt vời! Hiện tại bạn không có từ nào đến hạn ôn.</p>
                  <p className="empty-subtext">
                    Bạn có thể chọn <strong>Từ gần đây</strong>, <strong>Theo chủ đề</strong>, hoặc <strong>Tự chọn</strong> để ôn tập ngay bất kỳ lúc nào.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Mode 2: Recent Words */}
          {sourceMode === "recent" && (
            <div className="review-setup-panel">
              <div className="review-setup-info">
                <h3>Từ vựng thêm gần đây</h3>
                <p>
                  Ôn lại nhanh tối đa {RECENT_REVIEW_LIMIT} từ vựng bạn vừa thêm hoặc vừa nhập vào Từ vựng của tôi.
                </p>
                <div className="review-mode-stat">
                  <span className="stat-number">{recentItems.length}</span>
                  <span className="stat-label">từ trong danh sách gần đây</span>
                </div>
              </div>

              {recentItems.length > 0 ? (
                <div className="review-start-actions">
                  <button className="primary-button" type="button" onClick={handleStartRecent}>
                    <Sparkles size={18} /> Bắt đầu ôn {recentItems.length} từ gần đây
                  </button>
                </div>
              ) : (
                <div className="review-setup-empty">
                  <p>Chưa có từ vựng nào trong danh sách cá nhân.</p>
                  <Link className="primary-link" to="/app/vocabulary/new">Thêm từ mới</Link>
                </div>
              )}
            </div>
          )}

          {/* Mode 3: By Topic */}
          {sourceMode === "topic" && (
            <div className="review-setup-panel">
              <div className="review-setup-info">
                <h3>Chọn chủ đề ôn tập</h3>
                <p>Chọn một chủ đề để củng cố toàn bộ từ vựng thuộc nhóm chủ đề đó.</p>
              </div>

              {topics.length > 0 ? (
                <div className="review-topic-grid">
                  {topics.map((t) => {
                    const isSelected = selectedTopic.toLowerCase() === t.name.toLowerCase();
                    return (
                      <button
                        key={t.name}
                        type="button"
                        className={`review-topic-card ${isSelected ? "selected" : ""}`}
                        onClick={() => setSelectedTopic(t.name)}
                      >
                        <span className="topic-name">{t.name}</span>
                        <span className="topic-count">{t.vocabulary_count} từ</span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="review-empty-text">Chưa có chủ đề nào.</p>
              )}

              {selectedTopic && topicItems.length > 0 && (
                <div className="review-start-actions">
                  <button className="primary-button" type="button" onClick={handleStartTopic}>
                    <Tags size={18} /> Bắt đầu ôn {topicItems.length} từ chủ đề “{selectedTopic}”
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Mode 4: Custom Selection */}
          {sourceMode === "custom" && (
            <div className="review-setup-panel">
              <div className="review-setup-info">
                <h3>Tự chọn danh sách từ vựng</h3>
                <p>Tìm kiếm, lọc theo trình độ hoặc chủ đề rồi tích chọn các từ bạn muốn ôn.</p>
              </div>

              {/* Filters */}
              <div className="custom-filters-bar">
                <label className="filter-input-wrap search-wrap">
                  <Search size={15} />
                  <input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Tìm theo từ, định nghĩa, tiếng Việt…"
                  />
                </label>

                <label className="filter-input-wrap">
                  <select
                    value={levelFilter}
                    onChange={(e) => setLevelFilter(e.target.value)}
                  >
                    <option value="">Tất cả {activeTrack?.level_framework}</option>
                    {activeTrack?.level_codes.map((lvl) => (
                      <option key={lvl} value={lvl}>{lvl}</option>
                    ))}
                  </select>
                </label>

                <label className="filter-input-wrap">
                  <select
                    value={topicFilter}
                    onChange={(e) => setTopicFilter(e.target.value)}
                  >
                    <option value="">Tất cả chủ đề</option>
                    {topics.map((t) => (
                      <option key={t.name} value={t.name}>{t.name} ({t.vocabulary_count})</option>
                    ))}
                  </select>
                </label>
              </div>

              {/* Selection Toolbar */}
              <div className="custom-selection-toolbar">
                <div className="selection-counts">
                  <strong>Đã chọn {selectedCustomIds.size} từ</strong>
                  <span>({eligibleCustomItems.length} từ phù hợp bộ lọc)</span>
                </div>
                <div className="selection-actions">
                  <button
                    className="secondary-button compact-button"
                    type="button"
                    onClick={selectAllEligible}
                    disabled={eligibleCustomItems.length === 0}
                  >
                    Chọn tất cả {eligibleCustomItems.length} từ này
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    onClick={clearCustomSelection}
                    disabled={selectedCustomIds.size === 0}
                  >
                    Bỏ chọn
                  </button>
                </div>
              </div>

              {/* Vocabulary Select List */}
              <div className="generator-vocabulary-list review-custom-list">
                {eligibleCustomItems.length > 0 ? (
                  eligibleCustomItems.map((item) => {
                    const isChecked = selectedCustomIds.has(item.id);
                    return (
                      <label
                        key={item.id}
                        className={`generator-vocabulary ${isChecked ? "selected" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleCustomItem(item.id)}
                        />
                        <div className="custom-item-content">
                          <div className="custom-item-head">
                            <strong>{item.word}</strong>
                            {item.ipa && <span className="custom-item-ipa">{item.learning_track.language.code === "zh" ? "Pinyin" : "IPA"}: {item.ipa}</span>}
                            <span className="level-badge">{item.level_code}</span>
                            <span className="pos-badge">{item.part_of_speech}</span>
                            {item.topic && <span className="topic-tag">#{item.topic}</span>}
                          </div>
                          <p className="custom-item-trans">{item.translation} — <small>{item.meaning}</small></p>
                        </div>
                      </label>
                    );
                  })
                ) : (
                  <p className="review-empty-text">Không tìm thấy từ nào phù hợp với bộ lọc.</p>
                )}
              </div>

              <div className="review-start-actions">
                <button
                  className="primary-button"
                  type="button"
                  onClick={handleStartCustom}
                  disabled={selectedCustomIds.size === 0}
                >
                  <ListChecks size={18} /> Bắt đầu ôn {selectedCustomIds.size} từ đã chọn
                </button>
              </div>
            </div>
          )}

          <aside className="review-rule-note">
            <strong>Lưu ý về lịch ôn tập</strong>
            <span>Kết quả của phiên ôn này sẽ được dùng để cập nhật lịch ôn tập của bạn.</span>
            <span>Đúng: Mới → 1 ngày → Đang học → 3 ngày → Cần ôn → Đã thuộc.</span>
            <span>Sai: quay về Đang học và ôn lại sau 1 giờ.</span>
          </aside>
        </>
      ) : isComplete ? (
        /* Complete Screen */
        <div className="review-complete" role="status">
          <PenguinMark size={76} variant="scholar" />
          <p className="eyebrow">Hoàn thành phiên ôn</p>
          <h2>Đã xong phiên ôn này!</h2>
          <div className="review-summary">
            <div><strong>{activeQueue.length}</strong><span>Đã ôn</span></div>
            <div className="correct"><strong>{correctInSession}</strong><span>Đúng</span></div>
            <div className="incorrect"><strong>{incorrectInSession}</strong><span>Sai</span></div>
            <div><strong>{sessionAccuracy}%</strong><span>Độ chính xác</span></div>
          </div>
          <div className="review-complete-actions">
            <button className="primary-button" type="button" onClick={exitReviewSession}>
              <RefreshCw size={17} /> Chọn phiên ôn khác
            </button>
            <Link className="secondary-link" to="/app"><LayoutDashboard size={17} /> Trang chủ</Link>
            <Link className="secondary-link" to="/app/practice"><Dumbbell size={17} /> Luyện tập</Link>
          </div>
        </div>
      ) : currentItem ? (
        /* Active Flashcard */
        <>
          <PageHeader
            className="review-heading"
            eyebrow={
              sourceMode === "due"
                ? "Ôn tập · Từ đến hạn"
                : sourceMode === "recent"
                ? "Ôn tập · Từ gần đây"
                : sourceMode === "topic"
                ? `Ôn tập · Chủ đề: ${selectedTopic}`
                : "Ôn tập · Tự chọn"
            }
            title="Ôn tập tương tác."
            description="Tự kiểm tra trí nhớ, mở đáp án rồi chọn kết quả đúng với lần ôn của bạn."
            titleId="review-heading"
            aside={
              <div className="review-progress" aria-label="Tiến độ phiên ôn">
                <div className="review-progress-top">
                  <div className="review-progress-icon" aria-hidden="true">
                    <BookOpenCheck size={18} />
                  </div>
                  <div className="review-progress-text">
                    <span className="review-progress-caption">Đang ôn từ</span>
                    <strong className="review-progress-count">
                      {currentIndex + 1} <small>/ {activeQueue.length}</small>
                    </strong>
                  </div>
                </div>
                <div
                  className="progress-track"
                  role="progressbar"
                  aria-valuenow={currentIndex + 1}
                  aria-valuemin={1}
                  aria-valuemax={activeQueue.length}
                >
                  <span style={{ width: `${((currentIndex + 1) / activeQueue.length) * 100}%` }} />
                </div>
                <div className="review-progress-meta">
                  <span>{activeQueue.length} từ trong phiên</span>
                  <span>{Math.round(((currentIndex + 1) / activeQueue.length) * 100)}%</span>
                </div>
              </div>
            }
          />

          <div className="review-session-toolbar">
            <span className="review-schedule-reminder">
              Kết quả của phiên ôn này sẽ được dùng để cập nhật lịch ôn tập của bạn.
            </span>
            <button className="text-button" type="button" onClick={exitReviewSession}>
              <X size={15} /> Dừng phiên ôn
            </button>
          </div>

          {error && <div className="form-error" role="alert">{error}</div>}

          <article className="review-card">
            <div className="review-card-meta">
              <span className="level-badge">{currentItem.level_code}</span>
              <span>{currentItem.learning_track.name}</span>
              {currentItem.topic && <span>#{currentItem.topic}</span>}
            </div>
            <div className="review-prompt">
              <h2>{currentItem.word}</h2>
              {currentItem.ipa && <p className="review-ipa">{currentItem.learning_track.language.code === "zh" ? "Pinyin" : "IPA"}: {currentItem.ipa}</p>}
              {currentItem.part_of_speech && <p className="review-pos">{currentItem.part_of_speech}</p>}
            </div>

            {!revealed ? (
              <button
                className="primary-button reveal-button"
                type="button"
                onClick={() => setRevealed(true)}
              >
                <Eye size={18} /> Xem nghĩa
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
                    <X size={18} /> Chưa nhớ
                    <small>Ôn lại sau 1 giờ</small>
                  </button>
                  <button
                    className="review-result correct"
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => void recordResult(true)}
                  >
                    <Check size={18} /> Đã nhớ
                    <small>Tiến sang bước tiếp theo</small>
                  </button>
                </div>
              </div>
            )}
          </article>

          <aside className="review-rule-note">
            <strong>Lịch V1</strong>
            <span>Đúng: Mới → 1 ngày → Đang học → 3 ngày → Cần ôn → Đã thuộc.</span>
            <span>Sai: quay về Đang học và ôn lại sau 1 giờ.</span>
          </aside>
        </>
      ) : null}
    </section>
  );
}
