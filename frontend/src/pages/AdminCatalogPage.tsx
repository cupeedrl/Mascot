import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Edit2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";

import {
  AdminCatalogEntryItem,
  AdminCreateCatalogEntryPayload,
  ApiError,
  createAdminCatalogEntry,
  deleteAdminCatalogEntry,
  getAdminCatalog,
  updateAdminCatalogEntry,
} from "../api/client";

const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const PARTS_OF_SPEECH = [
  { value: "noun", label: "Noun (Danh từ)" },
  { value: "verb", label: "Verb (Động từ)" },
  { value: "adjective", label: "Adjective (Tính từ)" },
  { value: "adverb", label: "Adverb (Trạng từ)" },
  { value: "phrasal verb", label: "Phrasal Verb (Cụm động từ)" },
  { value: "phrase", label: "Phrase (Cụm từ)" },
  { value: "pronoun", label: "Pronoun (Đại từ)" },
  { value: "preposition", label: "Preposition (Giới từ)" },
  { value: "conjunction", label: "Conjunction (Liên từ)" },
  { value: "determiner", label: "Determiner (Từ hạn định)" },
  { value: "interjection", label: "Interjection (Thán từ)" },
  { value: "other", label: "Other (Khác)" },
];

export function AdminCatalogPage() {
  const [entries, setEntries] = useState<AdminCatalogEntryItem[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [topicFilter, setTopicFilter] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<AdminCatalogEntryItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form fields
  const [formWord, setFormWord] = useState("");
  const [formIpa, setFormIpa] = useState("");
  const [formPos, setFormPos] = useState("noun");
  const [formMeaning, setFormMeaning] = useState("");
  const [formTranslation, setFormTranslation] = useState("");
  const [formExample, setFormExample] = useState("");
  const [formLevel, setFormLevel] = useState("A1");
  const [formTopic, setFormTopic] = useState("General");

  // Delete modal
  const [deletingEntry, setDeletingEntry] = useState<AdminCatalogEntryItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const fetchCatalog = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminCatalog({
        page,
        pageSize,
        search: debouncedSearch || undefined,
        level: levelFilter || undefined,
        topic: topicFilter || undefined,
      });
      setEntries(res.items);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Không thể tải danh mục từ vựng.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, levelFilter, topicFilter]);

  useEffect(() => {
    fetchCatalog();
  }, [fetchCatalog]);

  function openCreateModal() {
    setEditingEntry(null);
    setFormWord("");
    setFormIpa("");
    setFormPos("noun");
    setFormMeaning("");
    setFormTranslation("");
    setFormExample("");
    setFormLevel("A1");
    setFormTopic("Daily Life");
    setFormError(null);
    setIsModalOpen(true);
  }

  function openEditModal(entry: AdminCatalogEntryItem) {
    setEditingEntry(entry);
    setFormWord(entry.word);
    setFormIpa(entry.ipa ?? "");
    setFormPos(entry.part_of_speech);
    setFormMeaning(entry.meaning);
    setFormTranslation(entry.translation);
    setFormExample(entry.example_sentences[0] ?? "");
    setFormLevel(entry.level_code);
    setFormTopic(entry.topic);
    setFormError(null);
    setIsModalOpen(true);
  }

  async function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const cleanWord = formWord.trim();
    const cleanMeaning = formMeaning.trim();
    const cleanTranslation = formTranslation.trim();
    const cleanExample = formExample.trim();
    const cleanTopic = formTopic.trim();

    if (!cleanWord || !cleanMeaning || !cleanTranslation || !cleanExample || !cleanTopic) {
      setFormError("Vui lòng điền đầy đủ tất cả các trường bắt buộc.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (editingEntry) {
        await updateAdminCatalogEntry(editingEntry.id, {
          word: cleanWord,
          ipa: formIpa.trim() || undefined,
          part_of_speech: formPos,
          meaning: cleanMeaning,
          translation: cleanTranslation,
          example_sentences: [cleanExample],
          level_code: formLevel,
          topic: cleanTopic,
        });
        setActionMessage(`Đã cập nhật từ vựng "${cleanWord}" thành công.`);
      } else {
        await createAdminCatalogEntry({
          word: cleanWord,
          ipa: formIpa.trim() || undefined,
          part_of_speech: formPos,
          meaning: cleanMeaning,
          translation: cleanTranslation,
          example_sentences: [cleanExample],
          level_code: formLevel,
          topic: cleanTopic,
        });
        setActionMessage(`Đã thêm từ vựng "${cleanWord}" vào thư viện.`);
      }
      setIsModalOpen(false);
      fetchCatalog();
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setFormError(caughtError.message);
      } else {
        setFormError("Đã có lỗi xảy ra khi lưu từ vựng.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deletingEntry) return;
    setIsDeleting(true);
    try {
      await deleteAdminCatalogEntry(deletingEntry.id);
      setActionMessage(`Đã xóa từ vựng "${deletingEntry.word}" khỏi thư viện.`);
      setDeletingEntry(null);
      fetchCatalog();
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        alert(caughtError.message);
      } else {
        alert("Không thể xóa từ vựng.");
      }
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="admin-page-container">
      <header className="admin-page-header">
        <div>
          <p className="admin-eyebrow">QUẢN TRỊ NỘI DUNG</p>
          <h1>Thư viện từ vựng dùng chung</h1>
          <p className="admin-subtext">
            Kho từ vựng chuẩn CEFR cho lộ trình học tập ({total} mục từ).
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className="secondary-button admin-refresh-btn"
            type="button"
            onClick={fetchCatalog}
            disabled={isLoading}
          >
            <RefreshCw size={15} className={isLoading ? "spin" : ""} /> Làm mới
          </button>
          <button className="primary-button" type="button" onClick={openCreateModal}>
            <Plus size={16} /> Thêm từ vựng
          </button>
        </div>
      </header>

      {actionMessage && (
        <div className="admin-success-box">
          <CheckCircle2 size={18} />
          <span>{actionMessage}</span>
        </div>
      )}

      {error && (
        <div className="admin-error-box" role="alert">
          <AlertCircle size={20} />
          <div>
            <strong>Lỗi tải danh mục</strong>
            <p>{error}</p>
          </div>
          <button className="primary-button" type="button" onClick={fetchCatalog}>
            Thử lại
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="admin-filter-bar">
        <div className="admin-search-input">
          <Search size={16} />
          <input
            type="search"
            placeholder="Tìm theo từ vựng..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="admin-select-group">
          <label htmlFor="level-select">Cấp độ:</label>
          <select
            id="level-select"
            value={levelFilter}
            onChange={(e) => {
              setLevelFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả cấp độ</option>
            {CEFR_LEVELS.map((lvl) => (
              <option key={lvl} value={lvl}>
                {lvl}
              </option>
            ))}
          </select>
        </div>

        <div className="admin-search-input" style={{ width: "200px" }}>
          <input
            type="search"
            placeholder="Lọc theo chủ đề..."
            value={topicFilter}
            onChange={(e) => {
              setTopicFilter(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="admin-table-container">
        <table className="admin-table" aria-label="Bảng thư viện từ vựng">
          <thead>
            <tr>
              <th>Từ vựng</th>
              <th>Loại từ</th>
              <th>Cấp độ</th>
              <th>Chủ đề</th>
              <th>Định nghĩa Tiếng Anh</th>
              <th>Nghĩa Tiếng Việt</th>
              <th style={{ textAlign: "center" }}>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "40px" }}>
                  <RefreshCw size={24} className="spin" style={{ margin: "0 auto 8px" }} />
                  <p style={{ color: "var(--muted)", margin: 0 }}>Đang tải thư viện từ...</p>
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "48px" }}>
                  <p style={{ color: "var(--muted)", fontSize: "14px", margin: 0 }}>
                    Không tìm thấy từ vựng nào phù hợp.
                  </p>
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <strong>{entry.word}</strong>
                    {entry.ipa && (
                      <span style={{ display: "block", color: "var(--muted)", fontSize: "11.5px" }}>
                        {entry.ipa}
                      </span>
                    )}
                  </td>
                  <td>
                    <span className="admin-pos-badge">{entry.part_of_speech}</span>
                  </td>
                  <td>
                    <span className={`admin-cefr-badge cefr-${entry.level_code.toLowerCase()}`}>
                      {entry.level_code}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontSize: "13px", fontWeight: 600, color: "#334155" }}>
                      {entry.topic}
                    </span>
                  </td>
                  <td style={{ maxWidth: "260px" }}>
                    <p className="admin-truncate-cell" title={entry.meaning}>
                      {entry.meaning}
                    </p>
                  </td>
                  <td style={{ maxWidth: "220px" }}>
                    <p className="admin-truncate-cell" title={entry.translation}>
                      {entry.translation}
                    </p>
                  </td>
                  <td>
                    <div className="admin-actions-cell">
                      <button
                        className="admin-mini-btn"
                        type="button"
                        onClick={() => openEditModal(entry)}
                        title="Chỉnh sửa từ vựng"
                      >
                        <Edit2 size={13} /> Sửa
                      </button>
                      <button
                        className="admin-mini-btn btn-danger"
                        type="button"
                        onClick={() => setDeletingEntry(entry)}
                        title="Xóa từ vựng"
                      >
                        <Trash2 size={13} /> Xóa
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <footer className="admin-pagination">
          <span>
            Trang <strong>{page}</strong> / {totalPages} (Tổng {total} từ vựng)
          </span>
          <div className="admin-pagination-btns">
            <button
              className="secondary-button"
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft size={16} /> Trước
            </button>
            <button
              className="secondary-button"
              type="button"
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Sau <ChevronRight size={16} />
            </button>
          </div>
        </footer>
      )}

      {/* Create / Edit Modal */}
      {isModalOpen && (
        <div className="admin-modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="admin-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h3>{editingEntry ? "Chỉnh sửa từ vựng" : "Thêm từ vựng vào thư viện"}</h3>
              <button
                className="icon-button"
                type="button"
                onClick={() => setIsModalOpen(false)}
                aria-label="Đóng modal"
              >
                <X size={18} />
              </button>
            </div>

            {formError && (
              <div className="admin-error-box" role="alert" style={{ margin: "0 24px 16px" }}>
                <AlertCircle size={18} />
                <p style={{ margin: 0 }}>{formError}</p>
              </div>
            )}

            <form onSubmit={handleFormSubmit} className="admin-modal-form">
              <div className="admin-form-group-title">1. Thông tin cơ bản</div>
              <div className="admin-form-grid-3">
                <div className="admin-form-field">
                  <label htmlFor="modal-word">Từ vựng (Word) *</label>
                  <input
                    id="modal-word"
                    type="text"
                    required
                    value={formWord}
                    onChange={(e) => setFormWord(e.target.value)}
                    placeholder="e.g. Resilient"
                  />
                </div>
                <div className="admin-form-field">
                  <label htmlFor="modal-pos">Loại từ (Part of Speech) *</label>
                  <select
                    id="modal-pos"
                    value={formPos}
                    onChange={(e) => setFormPos(e.target.value)}
                  >
                    {PARTS_OF_SPEECH.map((pos) => (
                      <option key={pos.value} value={pos.value}>
                        {pos.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="admin-form-field">
                  <label htmlFor="modal-ipa">Phiên âm IPA</label>
                  <input
                    id="modal-ipa"
                    type="text"
                    value={formIpa}
                    onChange={(e) => setFormIpa(e.target.value)}
                    placeholder="e.g. /rɪˈzɪl.jənt/"
                  />
                </div>
              </div>

              <div className="admin-form-group-title">2. Ngữ nghĩa & Bản dịch</div>
              <div className="admin-form-grid-2">
                <div className="admin-form-field">
                  <label htmlFor="modal-meaning">Định nghĩa Tiếng Anh *</label>
                  <textarea
                    id="modal-meaning"
                    required
                    rows={2}
                    value={formMeaning}
                    onChange={(e) => setFormMeaning(e.target.value)}
                    placeholder="English definition..."
                  />
                </div>
                <div className="admin-form-field">
                  <label htmlFor="modal-trans">Nghĩa Tiếng Việt *</label>
                  <textarea
                    id="modal-trans"
                    required
                    rows={2}
                    value={formTranslation}
                    onChange={(e) => setFormTranslation(e.target.value)}
                    placeholder="Vietnamese meaning..."
                  />
                </div>
              </div>

              <div className="admin-form-group-title">3. Phân loại học tập</div>
              <div className="admin-form-grid-2">
                <div className="admin-form-field">
                  <label htmlFor="modal-level">Cấp độ CEFR *</label>
                  <select
                    id="modal-level"
                    value={formLevel}
                    onChange={(e) => setFormLevel(e.target.value)}
                  >
                    {CEFR_LEVELS.map((lvl) => (
                      <option key={lvl} value={lvl}>
                        {lvl}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="admin-form-field">
                  <label htmlFor="modal-topic">Chủ đề (Topic) *</label>
                  <input
                    id="modal-topic"
                    type="text"
                    required
                    value={formTopic}
                    onChange={(e) => setFormTopic(e.target.value)}
                    placeholder="e.g. Personality"
                  />
                </div>
              </div>

              <div className="admin-form-field">
                <label htmlFor="modal-example">Câu ví dụ minh họa *</label>
                <input
                  id="modal-example"
                  type="text"
                  required
                  value={formExample}
                  onChange={(e) => setFormExample(e.target.value)}
                  placeholder="e.g. She is a remarkably resilient individual."
                />
              </div>

              <div className="admin-modal-footer">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isSubmitting}
                >
                  Hủy
                </button>
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Đang lưu..." : editingEntry ? "Lưu thay đổi" : "Tạo từ vựng"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingEntry && (
        <div className="admin-modal-backdrop" onClick={() => setDeletingEntry(null)}>
          <div
            className="admin-modal-card"
            style={{ maxWidth: "440px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="admin-modal-header">
              <h3>Xóa từ vựng khỏi thư viện</h3>
              <button
                className="icon-button"
                type="button"
                onClick={() => setDeletingEntry(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div style={{ padding: "0 24px 20px" }}>
              <p style={{ color: "var(--text)", fontSize: "14px", lineHeight: 1.6, margin: "0 0 12px" }}>
                Bạn có chắc muốn xóa từ <strong>"{deletingEntry.word}"</strong> khỏi kho từ vựng dùng chung?
              </p>
              <p style={{ color: "var(--muted)", fontSize: "12.5px", margin: 0 }}>
                💡 <em>Lưu ý:</em> Người học đã thêm từ này vào sổ tay cá nhân sẽ vẫn giữ nguyên từ vựng của mình (liên kết nguồn sẽ tự động tách an toàn).
              </p>
            </div>
            <div className="admin-modal-footer">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setDeletingEntry(null)}
                disabled={isDeleting}
              >
                Hủy
              </button>
              <button
                className="primary-button btn-danger"
                type="button"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
              >
                {isDeleting ? "Đang xóa..." : "Xác nhận xóa"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
