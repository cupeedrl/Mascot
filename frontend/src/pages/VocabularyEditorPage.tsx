import { type FormEvent, useEffect, useState } from "react";
import { ArrowLeft, Save, ShieldCheck, Sparkles, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  createVocabulary,
  generateAIVocabulary,
  getLearningTracks,
  getVocabulary,
  updateVocabulary,
  type LearningStatus,
  type LearningTrack,
  type Vocabulary,
  type VocabularyInput,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";
import { TopicCombobox } from "../components/TopicCombobox";
import {
  getExistingVocabularyId,
  getVocabularyEditRoute,
} from "../features/vocabulary/duplicateConflict";
import { PARTS_OF_SPEECH } from "../features/vocabulary/partsOfSpeech";
import { pronunciationLabel, useActiveLearningTrack } from "../learning/ActiveLearningTrackContext";


const STATUSES: Array<{ value: LearningStatus; label: string }> = [
  { value: "new", label: "Mới" },
  { value: "learning", label: "Đang học" },
  { value: "review", label: "Cần ôn" },
  { value: "mastered", label: "Đã thuộc" },
];

interface FormState {
  learningTrackId: string;
  word: string;
  ipa: string;
  partOfSpeech: string;
  meaning: string;
  translation: string;
  example: string;
  level: string;
  topic: string;
  status: LearningStatus;
}

function emptyForm(): FormState {
  return {
    learningTrackId: "",
    word: "",
    ipa: "",
    partOfSpeech: "noun",
    meaning: "",
    translation: "",
    example: "",
    level: "A1",
    topic: "",
    status: "new",
  };
}

function fromVocabulary(item: Vocabulary): FormState {
  return {
    learningTrackId: item.learning_track_id,
    word: item.word,
    ipa: item.ipa ?? "",
    partOfSpeech: item.part_of_speech || "noun",
    meaning: item.meaning,
    translation: item.translation,
    example: item.example_sentences[0] ?? "",
    level: item.level_code,
    topic: item.topic ?? "",
    status: item.learning_status,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Đã có lỗi xảy ra. Vui lòng thử lại.";
}

export function VocabularyEditorPage() {
  const { activeTrack } = useActiveLearningTrack();
  const { vocabularyId } = useParams();
  const navigate = useNavigate();
  const isEditing = Boolean(vocabularyId);
  const [tracks, setTracks] = useState<LearningTrack[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasAIPreview, setHasAIPreview] = useState(false);
  const [aiError, setAIError] = useState("");
  const [error, setError] = useState("");
  const [duplicateVocabularyId, setDuplicateVocabularyId] = useState<string | null>(null);

  useEffect(() => {
    if (!activeTrack) return;
    let active = true;
    setIsLoading(true);
    setError("");
    setDuplicateVocabularyId(null);
    const itemRequest = vocabularyId
      ? getVocabulary(vocabularyId)
      : Promise.resolve(null);
    Promise.all([getLearningTracks(), itemRequest])
      .then(([catalog, item]) => {
        if (!active) return;
        setTracks(catalog);
        const initialTrack = item
          ? catalog.find((track) => track.id === item.learning_track_id)
          : catalog.find((track) => track.id === activeTrack?.id) ?? catalog[0];
        setForm(item
          ? fromVocabulary(item)
          : {
              ...emptyForm(),
              learningTrackId: initialTrack?.id ?? "",
              level: initialTrack?.level_codes[0] ?? "",
            });
      })
      .catch((caughtError: unknown) => {
        if (active) setError(errorMessage(caughtError));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activeTrack?.id, vocabularyId]);

  const selectedTrack = tracks.find((track) => track.id === form.learningTrackId)
    ?? activeTrack;

  async function handleAIGeneration() {
    setAIError("");
    const word = form.word.trim();
    const pos = form.partOfSpeech.trim();
    const translation = form.translation.trim();

    if (!word) {
      setAIError(`Vui lòng nhập từ ${selectedTrack?.language.name ?? "cần học"} trước khi hoàn thiện với AI.`);
      return;
    }
    if (!pos) {
      setAIError("Vui lòng chọn Từ loại trước khi hoàn thiện với AI.");
      return;
    }
    if (!translation) {
      setAIError("Vui lòng nhập Nghĩa tiếng Việt (nét nghĩa mong muốn) trước khi hoàn thiện với AI.");
      return;
    }

    setIsGenerating(true);
    try {
      const candidate = await generateAIVocabulary({
        word,
        part_of_speech: pos,
        translation,
        learning_track_id: form.learningTrackId,
      });
      setForm((current) => ({
        ...current,
        ipa: candidate.ipa || current.ipa,
        meaning: candidate.definition,
        example: candidate.examples[0] ?? "",
        level: candidate.cefr_level,
        topic: current.topic.trim() ? current.topic : (candidate.topic || "Khác"),
        status: "new",
      }));
      setHasAIPreview(true);
    } catch (caughtError) {
      setAIError(errorMessage(caughtError));
    } finally {
      setIsGenerating(false);
    }
  }

  function discardAIPreview() {
    const firstLevel = selectedTrack?.level_codes[0] ?? "";
    setForm((current) => ({
      ...emptyForm(),
      learningTrackId: current.learningTrackId,
      level: firstLevel,
      word: current.word,
      partOfSpeech: current.partOfSpeech,
      translation: current.translation,
    }));
    setHasAIPreview(false);
    setAIError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setDuplicateVocabularyId(null);
    if (!form.learningTrackId) {
      setError("Không tìm thấy learning track đang hoạt động.");
      return;
    }
    const payload: VocabularyInput = {
      learning_track_id: form.learningTrackId,
      word: form.word.trim(),
      ipa: form.ipa.trim() || null,
      part_of_speech: form.partOfSpeech.trim(),
      meaning: form.meaning.trim(),
      translation: form.translation.trim(),
      translation_language_code: "vi",
      example_sentences: form.example.trim() ? [form.example.trim()] : [],
      level_code: form.level,
      topic: form.topic.trim() || "Khác",
      learning_status: form.status,
    };
    setIsSaving(true);
    try {
      if (vocabularyId) {
        await updateVocabulary(vocabularyId, payload);
      } else {
        await createVocabulary(payload);
      }
      navigate("/app/vocabulary", {
        replace: true,
        state: { message: isEditing ? "Đã cập nhật từ vựng." : "Đã thêm từ vựng mới." },
      });
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 409) {
        setDuplicateVocabularyId(getExistingVocabularyId(caughtError.detail));
      }
      setError(errorMessage(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <PageSkeleton cards={2} />;

  return (
    <section className="vocabulary-page editor-page" aria-labelledby="editor-heading">
      <Link className="back-link" to="/app/vocabulary"><ArrowLeft size={17} /> Quay lại Từ vựng của tôi</Link>
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">{isEditing ? "Chỉnh sửa" : "Thêm thủ công hoặc dùng AI"}</p>
          <h1 id="editor-heading">{isEditing ? "Cập nhật từ vựng" : "Tạo từ vựng mới"}</h1>
          <p>{isEditing
            ? "Cập nhật nội dung từ vựng đang học."
            : "Nhập từ, từ loại và nghĩa tiếng Việt rồi chọn Hoàn thiện với AI để điền tự động các trường còn lại."}</p>
        </div>
      </div>

      <section className="vocabulary-form-card">
        <form className="vocabulary-form" onSubmit={handleSubmit}>
          <label>
            Lộ trình học
            <select
              value={form.learningTrackId}
              onChange={(event) => {
                const track = tracks.find((item) => item.id === event.target.value);
                setForm({
                  ...form,
                  learningTrackId: event.target.value,
                  level: track?.level_codes[0] ?? "",
                });
              }}
              required
            >
              {tracks.map((track) => (
                <option key={track.id} value={track.id}>{track.name} · {track.language.name}</option>
              ))}
            </select>
          </label>
          <label>
            Từ {selectedTrack?.language.name ?? "cần học"} <span className="field-required">*</span>
            <input
              value={form.word}
              onChange={(event) => setForm({ ...form, word: event.target.value })}
              required
              maxLength={255}
              placeholder={selectedTrack?.language.code === "zh" ? "学习" : "solely"}
            />
          </label>
          <label>
            Từ loại (Part of speech) <span className="field-required">*</span>
            <select
              value={form.partOfSpeech}
              onChange={(event) => setForm({ ...form, partOfSpeech: event.target.value })}
              required
            >
              {PARTS_OF_SPEECH.map((pos) => (
                <option key={pos.value} value={pos.value}>{pos.label}</option>
              ))}
            </select>
          </label>
          <label className="wide-field">
            Nghĩa tiếng Việt (Nét nghĩa cần học) <span className="field-required">*</span>
            <textarea
              value={form.translation}
              onChange={(event) => setForm({ ...form, translation: event.target.value })}
              required
              maxLength={2000}
              rows={2}
              placeholder="duy nhất, chỉ..."
            />
          </label>
          {!isEditing && (
            <div className="ai-generate-control">
              <span className="ai-badge"><Sparkles size={15} /> Mascot AI</span>
              <button
                className="ai-button"
                type="button"
                disabled={isGenerating || isSaving}
                onClick={() => void handleAIGeneration()}
              >
                <Sparkles size={17} /> {isGenerating ? "Đang hoàn thiện…" : "Hoàn thiện với Mascot AI"}
              </button>
              <small>AI dùng dữ liệu bạn nhập để gợi ý {pronunciationLabel(selectedTrack)}, định nghĩa, ví dụ và mức {selectedTrack?.level_framework}.</small>
            </div>
          )}
          {aiError && <div className="form-error wide-field" role="alert">{aiError}</div>}
          {hasAIPreview && !isEditing && (
            <div className="ai-preview-notice wide-field" role="status">
              <div>
                <strong><ShieldCheck size={17} /> Bản nháp do AI hoàn thiện</strong>
                <span>Nét nghĩa của bạn được giữ nguyên. Hãy đọc và chỉnh sửa thêm nếu muốn trước khi lưu.</span>
              </div>
              <button className="text-button" type="button" onClick={discardAIPreview}>
                <X size={15} /> Bỏ gợi ý
              </button>
            </div>
          )}
          <label>
            {pronunciationLabel(selectedTrack)}
            <input
              value={form.ipa}
              onChange={(event) => setForm({ ...form, ipa: event.target.value })}
              maxLength={100}
              placeholder={selectedTrack?.language.code === "zh" ? "xuéxí" : "/ˈsəʊl.li/"}
            />
          </label>
          <label>
            Trình độ {selectedTrack?.level_framework}
            <select value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value })}>
              {selectedTrack?.level_codes.map((level) => <option key={level}>{level}</option>)}
            </select>
          </label>
          <label className="wide-field">
            Định nghĩa / ghi chú
            <textarea
              value={form.meaning}
              onChange={(event) => setForm({ ...form, meaning: event.target.value })}
              required
              maxLength={4000}
              rows={3}
              placeholder={selectedTrack?.language.code === "zh" ? "学习知识或技能。" : "Not involving anyone or anything else; only."}
            />
          </label>
          <label className="wide-field">
            Câu ví dụ
            <textarea
              value={form.example}
              onChange={(event) => setForm({ ...form, example: event.target.value })}
              rows={2}
              maxLength={500}
              placeholder={selectedTrack?.language.code === "zh" ? "我每天学习中文。" : "The decision was based solely on cost."}
            />
          </label>
          <TopicCombobox
            label="Chủ đề"
            value={form.topic}
            onChange={(topic) => setForm((current) => ({ ...current, topic }))}
            placeholder="Khác"
            learningTrackId={form.learningTrackId}
          />
          <label>
            Trạng thái học
            <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as LearningStatus })}>
              {STATUSES.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
            </select>
          </label>
          {error && (
            <div className="form-error duplicate-warning wide-field" role="alert">
              <span>{error}</span>
              {duplicateVocabularyId && (
                <button
                  className="duplicate-edit-action"
                  type="button"
                  onClick={() => navigate(getVocabularyEditRoute(duplicateVocabularyId))}
                >
                  Chỉnh sửa từ hiện có
                </button>
              )}
            </div>
          )}
          <div className="form-actions wide-field">
            <Link className="secondary-link" to="/app/vocabulary">Hủy</Link>
            {hasAIPreview && !isEditing && (
              <span className="ai-save-reminder">Chỉ lưu khi bạn bấm “Thêm từ vựng”.</span>
            )}
            <button className="primary-button compact-button" type="submit" disabled={isSaving}>
              <Save size={17} /> {isSaving ? "Đang lưu…" : isEditing ? "Lưu thay đổi" : "Thêm từ vựng"}
            </button>
          </div>
        </form>
      </section>
    </section>
  );
}
