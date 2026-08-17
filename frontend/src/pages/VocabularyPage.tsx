import { type FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Pencil, Plus, Search, Settings2, Trash2 } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import {
  ApiError,
  deleteVocabulary,
  listVocabularies,
  type CefrLevel,
  type LearningStatus,
  type Vocabulary,
  type VocabularyListResponse,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";
import { ManageTopicsModal } from "../components/ManageTopicsModal";
import { TopicCombobox } from "../components/TopicCombobox";

const CEFR_LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];
const STATUSES: Array<{ value: LearningStatus; label: string }> = [
  { value: "new", label: "Mới" },
  { value: "learning", label: "Đang học" },
  { value: "review", label: "Cần ôn" },
  { value: "mastered", label: "Đã thuộc" },
];

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Đã có lỗi xảy ra. Vui lòng thử lại.";
}

export function VocabularyPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [result, setResult] = useState<VocabularyListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [draftSearch, setDraftSearch] = useState("");
  const [draftTopic, setDraftTopic] = useState("");
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const [statusFilter, setStatusFilter] = useState<LearningStatus | "">("");
  const [levelFilter, setLevelFilter] = useState<CefrLevel | "">("");
  const [isLoading, setIsLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [success, setSuccess] = useState(
    (location.state as { message?: string } | null)?.message ?? "",
  );
  const [refreshKey, setRefreshKey] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isManagingTopics, setIsManagingTopics] = useState(false);

  useEffect(() => {
    if ((location.state as { message?: string } | null)?.message) {
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setPageError("");
    listVocabularies({
      page,
      pageSize: 10,
      search,
      topic,
      learningStatus: statusFilter,
      level: levelFilter,
    })
      .then((response) => {
        if (active) setResult(response);
      })
      .catch((error: unknown) => {
        if (active) setPageError(errorMessage(error));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [levelFilter, page, refreshKey, search, statusFilter, topic]);

  const hasFilters = useMemo(
    () => Boolean(search || topic || statusFilter || levelFilter),
    [levelFilter, search, statusFilter, topic],
  );

  async function handleDelete(item: Vocabulary) {
    if (!window.confirm(`Xóa “${item.word}” khỏi kho từ vựng?`)) return;
    setDeletingId(item.id);
    setPageError("");
    setSuccess("");
    try {
      await deleteVocabulary(item.id);
      setSuccess(`Đã xóa “${item.word}”.`);
      if (result?.items.length === 1 && page > 1) {
        setPage((value) => value - 1);
      } else {
        setRefreshKey((value) => value + 1);
      }
    } catch (error) {
      setPageError(errorMessage(error));
    } finally {
      setDeletingId(null);
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(draftSearch.trim());
    setTopic(draftTopic.trim());
  }

  function clearFilters() {
    setDraftSearch("");
    setDraftTopic("");
    setSearch("");
    setTopic("");
    setStatusFilter("");
    setLevelFilter("");
    setPage(1);
  }

  return (
    <section className="vocabulary-page" aria-labelledby="vocabulary-heading">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">General English</p>
          <h1 id="vocabulary-heading">My Vocabulary</h1>
          <p>Từ bạn tự thêm và từ đang học từ thư viện Mascot.</p>
        </div>
        <Link className="primary-link compact-button" to="/app/vocabulary/new">
          <Plus size={17} /> Add Vocabulary
        </Link>
      </div>

      {success && <div className="success-banner" role="status">{success}</div>}
      {pageError && <div className="form-error" role="alert">{pageError}</div>}

      <form className="filter-bar" onSubmit={applyFilters}>
        <label className="search-field">
          Tìm kiếm
          <span className="input-with-icon">
            <Search size={17} aria-hidden="true" />
            <input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Từ, định nghĩa hoặc bản dịch"
            />
          </span>
        </label>
        <label>
          Trạng thái
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value as LearningStatus | "");
              setPage(1);
            }}
          >
            <option value="">Tất cả</option>
            {STATUSES.map((status) => (
              <option key={status.value} value={status.value}>{status.label}</option>
            ))}
          </select>
        </label>
        <label>
          CEFR
          <select
            value={levelFilter}
            onChange={(event) => {
              setLevelFilter(event.target.value as CefrLevel | "");
              setPage(1);
            }}
          >
            <option value="">Tất cả</option>
            {CEFR_LEVELS.map((level) => <option key={level}>{level}</option>)}
          </select>
        </label>
        <TopicCombobox
          label="Chủ đề"
          value={draftTopic}
          onChange={setDraftTopic}
          placeholder="Work"
          allowCreate={false}
        />
        <div className="filter-actions">
          <button className="primary-button compact-button" type="submit">Áp dụng</button>
          {hasFilters && <button className="text-button" type="button" onClick={clearFilters}>Xóa lọc</button>}
          <button className="text-button" type="button" onClick={() => setIsManagingTopics(true)}>
            <Settings2 size={16} /> Manage topics
          </button>
        </div>
      </form>

      <div className="list-summary">
        <strong>{result?.total ?? 0} từ vựng</strong>
        {result && result.total > 0 && <span>Trang {result.page}/{result.total_pages}</span>}
      </div>

      {isLoading ? (
        <PageSkeleton cards={4} />
      ) : result?.items.length ? (
        <div className="vocabulary-grid">
          {result.items.map((item) => (
            <article className="vocabulary-card" key={item.id}>
              <div className="vocabulary-card-heading">
                <div>
                  <div className="vocabulary-word-line">
                    <h2>{item.word}</h2>
                    <span className="level-badge">{item.level_code}</span>
                  </div>
                  <p className="part-of-speech">{item.part_of_speech}</p>
                </div>
                <span className={`status-badge status-${item.learning_status}`}>
                  {STATUSES.find((status) => status.value === item.learning_status)?.label}
                </span>
              </div>
              <p className="meaning">{item.meaning}</p>
              <p className="translation">{item.translation}</p>
              {item.example_sentences[0] && <blockquote>{item.example_sentences[0]}</blockquote>}
              <div className="vocabulary-meta">
                <span>{item.learning_track.name}</span>
                {item.topic && <span>#{item.topic}</span>}
                {item.source_vocabulary_entry && (
                  <span className="source-note">
                    Từ thư viện: {item.source_vocabulary_entry.vocabulary_set.level_code} · {item.source_vocabulary_entry.vocabulary_set.name}
                  </span>
                )}
              </div>
              <div className="card-actions">
                <Link className="text-button" to={`/app/vocabulary/${item.id}/edit`}>
                  <Pencil size={15} /> Chỉnh sửa
                </Link>
                <button
                  className="danger-button"
                  type="button"
                  onClick={() => handleDelete(item)}
                  disabled={deletingId === item.id}
                >
                  <Trash2 size={15} /> {deletingId === item.id ? "Đang xóa…" : "Xóa"}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="list-state">
          <h2>{hasFilters ? "Không tìm thấy kết quả" : "Kho từ vựng đang trống"}</h2>
          <p>
            {hasFilters
              ? "Hãy thử thay đổi từ khóa hoặc bộ lọc."
              : "Thêm thủ công hoặc chọn một bộ từ trong trang Learn."}
          </p>
          {!hasFilters && <Link className="primary-link" to="/app/learn">Khám phá thư viện</Link>}
        </div>
      )}

      {result && result.total_pages > 1 && (
        <nav className="pagination" aria-label="Phân trang từ vựng">
          <button
            className="secondary-button"
            type="button"
            disabled={page <= 1 || isLoading}
            onClick={() => setPage((value) => value - 1)}
          >
            <ArrowLeft size={16} /> Trang trước
          </button>
          <span>{page} / {result.total_pages}</span>
          <button
            className="secondary-button"
            type="button"
            disabled={page >= result.total_pages || isLoading}
            onClick={() => setPage((value) => value + 1)}
          >
            Trang sau <ArrowRight size={16} />
          </button>
        </nav>
      )}
      <ManageTopicsModal
        isOpen={isManagingTopics}
        onClose={() => setIsManagingTopics(false)}
        onTopicsChanged={() => {
          setDraftTopic("");
          setTopic("");
          setPage(1);
          setRefreshKey((value) => value + 1);
        }}
      />
    </section>
  );
}
