import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, CheckCircle2, Library, Plus } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  getVocabularySet,
  importVocabularyEntries,
  startLearningVocabularySet,
  type VocabularySetDetail,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể hoàn thành yêu cầu.";
}

export function VocabularySetPage() {
  const { setId } = useParams();
  const [detail, setDetail] = useState<VocabularySetDetail | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadDetail() {
    if (!setId) return;
    setIsLoading(true);
    setError("");
    try {
      const response = await getVocabularySet(setId);
      setDetail(response);
      setSelectedIds(new Set());
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDetail();
  }, [setId]);

  const availableIds = useMemo(
    () => detail?.entries.filter((entry) => !entry.is_added).map((entry) => entry.id) ?? [],
    [detail],
  );

  function toggleEntry(entryId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(entryId)) next.delete(entryId);
      else next.add(entryId);
      return next;
    });
  }

  async function importSelected() {
    if (!selectedIds.size) return;
    setIsImporting(true);
    setError("");
    setSuccess("");
    try {
      const response = await importVocabularyEntries([...selectedIds]);
      setSuccess(`Đã thêm ${response.created_count} từ vào Từ vựng của tôi${response.skipped_count ? `, bỏ qua ${response.skipped_count} từ đã có` : ""}.`);
      await loadDetail();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsImporting(false);
    }
  }

  async function importWholeSet() {
    if (!setId) return;
    setIsImporting(true);
    setError("");
    setSuccess("");
    try {
      const response = await startLearningVocabularySet(setId);
      setSuccess(`Bắt đầu học: thêm ${response.created_count} từ, bỏ qua ${response.skipped_count} từ đã có.`);
      await loadDetail();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsImporting(false);
    }
  }

  if (isLoading && !detail) return <PageSkeleton cards={4} />;

  return (
    <section className="learn-page set-detail-page" aria-labelledby="set-heading">
      <Link className="back-link" to="/app/learn"><ArrowLeft size={17} /> Quay lại Học từ vựng</Link>
      {error && <div className="form-error" role="alert">{error}</div>}
      {success && <div className="success-banner" role="status">{success}</div>}

      {detail && (
        <>
          <div className="set-detail-heading">
            <div>
              <p className="eyebrow">{detail.learning_track.name} · {detail.level_code}</p>
              <h1 id="set-heading">{detail.name}</h1>
              <p>{detail.description}</p>
              <div className="set-progress">
                <span>{detail.entry_count} từ</span>
                <span>{detail.added_count}/{detail.entry_count} đã có trong Từ vựng của tôi</span>
              </div>
              <div className="progress-track set-detail-progress" aria-label="Tiến độ bộ từ">
                <span style={{ width: `${detail.entry_count ? (detail.added_count / detail.entry_count) * 100 : 0}%` }} />
              </div>
            </div>
            <button
              className="primary-button compact-button"
              type="button"
              onClick={importWholeSet}
              disabled={isImporting || detail.import_status === "all"}
            >
              {detail.import_status === "all" ? <><CheckCircle2 size={17} /> Đã học toàn bộ</> : <><Library size={17} /> Bắt đầu học cả bộ</>}
            </button>
          </div>

          <div className="selection-toolbar">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setSelectedIds(new Set(availableIds))}
              disabled={!availableIds.length}
            >
              <Check size={16} /> Chọn tất cả từ chưa thêm
            </button>
            <button className="text-button" type="button" onClick={() => setSelectedIds(new Set())}>
              Bỏ chọn
            </button>
            <span>{selectedIds.size} từ được chọn</span>
            <button
              className="primary-button compact-button"
              type="button"
              onClick={importSelected}
              disabled={!selectedIds.size || isImporting}
            >
              {isImporting ? "Đang thêm…" : <><Plus size={17} /> Thêm từ đã chọn</>}
            </button>
          </div>

          <div className="entry-list">
            {detail.entries.map((entry) => (
              <label className={entry.is_added ? "entry-row added" : "entry-row"} key={entry.id}>
                <input
                  type="checkbox"
                  checked={entry.is_added || selectedIds.has(entry.id)}
                  disabled={entry.is_added}
                  onChange={() => toggleEntry(entry.id)}
                />
                <div className="entry-word">
                  <strong>{entry.word}</strong>
                  {entry.ipa && <small className="entry-ipa">{entry.ipa}</small>}
                  <span>{entry.part_of_speech}</span>
                </div>
                <div className="entry-definition">
                  <p>{entry.meaning}</p>
                  <strong>{entry.translation}</strong>
                  {entry.example_sentences[0] && <small>{entry.example_sentences[0]}</small>}
                </div>
                <span className="entry-state">{entry.is_added ? "Đã thêm" : "Chọn"}</span>
              </label>
            ))}
          </div>

          {detail.added_count > 0 && (
            <div className="detail-footer">
              <Link className="primary-link" to="/app/vocabulary">Xem Từ vựng của tôi</Link>
            </div>
          )}
        </>
      )}
    </section>
  );
}
