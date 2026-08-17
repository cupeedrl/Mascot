import { type FormEvent, useEffect, useState } from "react";
import { Check, LoaderCircle, Pencil, Tag, Trash2, X } from "lucide-react";

import {
  ApiError,
  listTopicSuggestions,
  removePersonalTopic,
  renamePersonalTopic,
  type TopicSuggestion,
} from "../api/client";

interface ManageTopicsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTopicsChanged: () => void;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể cập nhật chủ đề. Vui lòng thử lại.";
}

export function ManageTopicsModal({
  isOpen,
  onClose,
  onTopicsChanged,
}: ManageTopicsModalProps) {
  const [topics, setTopics] = useState<TopicSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [editingTopic, setEditingTopic] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [removingTopic, setRemovingTopic] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  function loadTopics() {
    setIsLoading(true);
    setError("");
    listTopicSuggestions("", 100)
      .then((response) => setTopics(response.items))
      .catch((caughtError) => setError(errorMessage(caughtError)))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    if (!isOpen) return;
    loadTopics();
    setEditingTopic(null);
    setRemovingTopic(null);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape" && !isMutating) onClose();
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isMutating, isOpen, onClose]);

  if (!isOpen) return null;

  async function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingTopic || !renameValue.trim()) return;
    setIsMutating(true);
    setError("");
    try {
      await renamePersonalTopic(editingTopic, renameValue);
      setEditingTopic(null);
      onTopicsChanged();
      loadTopics();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsMutating(false);
    }
  }

  async function handleRemove(topic: string) {
    setIsMutating(true);
    setError("");
    try {
      await removePersonalTopic(topic);
      setRemovingTopic(null);
      onTopicsChanged();
      loadTopics();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsMutating(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !isMutating) onClose();
    }}>
      <section className="manage-topics-modal" role="dialog" aria-modal="true" aria-labelledby="manage-topics-heading">
        <header>
          <div>
            <span className="modal-icon"><Tag size={20} /></span>
            <div>
              <p className="eyebrow">TỪ VỰNG CỦA TÔI</p>
              <h2 id="manage-topics-heading">Quản lý chủ đề</h2>
            </div>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={isMutating} aria-label="Đóng">
            <X size={19} />
          </button>
        </header>
        <p className="modal-description">
          Đổi tên hoặc gỡ chủ đề khỏi từ vựng cá nhân. Chủ đề trong thư viện Mascot không bị thay đổi.
        </p>

        {error && <div className="form-error" role="alert">{error}</div>}
        {isLoading ? (
          <div className="topics-loading"><LoaderCircle size={20} /> Đang tải chủ đề…</div>
        ) : topics.length ? (
          <div className="personal-topic-list">
            {topics.map((topic) => (
              <article className="personal-topic-row" key={topic.name.toLocaleLowerCase()}>
                {editingTopic === topic.name ? (
                  <form onSubmit={handleRename}>
                    <label>
                      Tên chủ đề mới
                      <input
                        value={renameValue}
                        onChange={(event) => setRenameValue(event.target.value)}
                        maxLength={120}
                        autoFocus
                      />
                    </label>
                    <div className="topic-row-actions">
                      <button className="text-button" type="button" onClick={() => setEditingTopic(null)}>Hủy</button>
                      <button className="primary-button compact-button" type="submit" disabled={isMutating || !renameValue.trim()}>
                        <Check size={15} /> Lưu
                      </button>
                    </div>
                  </form>
                ) : removingTopic === topic.name ? (
                  <div className="topic-remove-confirmation">
                    <div>
                      <strong>Gỡ “{topic.name}”?</strong>
                      <small>{topic.vocabulary_count} từ vẫn được giữ, chỉ trường chủ đề được xóa.</small>
                    </div>
                    <div className="topic-row-actions">
                      <button className="text-button" type="button" onClick={() => setRemovingTopic(null)}>Hủy</button>
                      <button className="danger-button" type="button" onClick={() => void handleRemove(topic.name)} disabled={isMutating}>
                        <Trash2 size={15} /> Gỡ chủ đề
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div>
                      <strong>{topic.name}</strong>
                      <small>{topic.vocabulary_count} từ vựng</small>
                    </div>
                    <div className="topic-row-actions">
                      <button className="text-button" type="button" onClick={() => {
                        setEditingTopic(topic.name);
                        setRenameValue(topic.name);
                        setRemovingTopic(null);
                      }}>
                        <Pencil size={15} /> Đổi tên
                      </button>
                      <button className="danger-button" type="button" onClick={() => {
                        setRemovingTopic(topic.name);
                        setEditingTopic(null);
                      }}>
                        <Trash2 size={15} /> Gỡ
                      </button>
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="topic-modal-empty">
            <Tag size={24} />
            <strong>Chưa có chủ đề cá nhân</strong>
            <span>Chủ đề sẽ xuất hiện khi bạn thêm chúng vào từ vựng.</span>
          </div>
        )}
      </section>
    </div>
  );
}
