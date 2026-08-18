import { type FormEvent, useEffect, useState } from "react";
import { ArrowRight, Compass, Search } from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  listVocabularySets,
  type CefrLevel,
  type VocabularySetListResponse,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";
import { LearningIllustration } from "../components/LearningIllustration";
import { PageHeader } from "../components/PageHeader";
import { PenguinMark } from "../components/PenguinMark";
import { getTopicAccent, getTopicIcon } from "../features/learn/topicPresentation";

const LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];
const LEVEL_LABELS: Record<CefrLevel, string> = {
  A1: "Cơ bản", A2: "Sơ cấp", B1: "Trung cấp", B2: "Trên trung cấp", C1: "Nâng cao", C2: "Thành thạo",
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể tải thư viện từ vựng.";
}

export function LearnPage() {
  const [level, setLevel] = useState<CefrLevel>("A1");
  const [topicDraft, setTopicDraft] = useState("");
  const [topic, setTopic] = useState("");
  const [result, setResult] = useState<VocabularySetListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError("");
    listVocabularySets({ level, topic })
      .then((response) => {
        if (active) setResult(response);
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
  }, [level, topic]);

  function applyTopic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTopic(topicDraft.trim());
  }

  return (
    <section className="learn-page" aria-labelledby="learn-heading">
      <div className="learn-hero">
        <PageHeader
          className="learn-page-header"
          icon={Compass}
          eyebrow="Thư viện từ vựng Mascot"
          title={<>Khám phá tiếng Anh <em>theo cách của bạn.</em></>}
          description="Chọn trình độ, khám phá chủ đề phù hợp và bắt đầu xây dựng vốn từ của riêng bạn."
          titleId="learn-heading"
          aside={<div className="learn-hero-aside"><LearningIllustration variant="library" /><dl className="track-card">
            <div><dt>Ngôn ngữ</dt><dd>Tiếng Anh</dd></div>
            <div><dt>Lộ trình học</dt><dd>Tiếng Anh tổng quát</dd></div>
            <div><dt>Khung trình độ</dt><dd>CEFR</dd></div>
          </dl></div>}
        />
      </div>

      <section className="level-section" aria-labelledby="level-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Bước 1</p>
            <h2 id="level-heading">Chọn trình độ CEFR</h2>
          </div>
        </div>
        <div className="level-tabs" role="tablist" aria-label="Trình độ CEFR">
          {LEVELS.map((item) => (
            <button
              key={item}
              className={item === level ? "level-tab active" : "level-tab"}
              type="button"
              role="tab"
              aria-selected={item === level}
              onClick={() => {
                setLevel(item);
                setTopic("");
                setTopicDraft("");
              }}
            >
              <strong>{item}</strong><small>{LEVEL_LABELS[item]}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="sets-section" aria-labelledby="sets-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Bước 2</p>
            <h2 id="sets-heading">Chọn bộ từ / chủ đề</h2>
          </div>
          <form className="topic-search" onSubmit={applyTopic}>
            <Search size={17} aria-hidden="true" />
            <input
              value={topicDraft}
              onChange={(event) => setTopicDraft(event.target.value)}
              placeholder="Lọc theo chủ đề"
              aria-label="Lọc theo chủ đề"
            />
            <button className="secondary-button" type="submit">Lọc</button>
          </form>
        </div>

        {error && <div className="form-error" role="alert">{error}</div>}
        {isLoading ? (
          <PageSkeleton cards={3} />
        ) : result?.items.length ? (
          <div className="set-grid">
            {result.items.map((set) => {
              const TopicIcon = getTopicIcon(set.topic);
              const accent = getTopicAccent(set.topic);
              const progress = set.entry_count ? Math.round((set.added_count / set.entry_count) * 100) : 0;
              return <article className={`set-card topic-accent-${accent}`} key={set.id}>
                <div className="set-card-topline">
                  <span className="topic-visual" aria-hidden="true"><TopicIcon size={22} /></span>
                  <span className="level-badge">{set.level_code}</span>
                  {set.import_status !== "none" && (
                    <span className={`library-status ${set.import_status}`}>
                      {set.import_status === "all" ? "Đã thêm toàn bộ" : "Đã thêm một phần"}
                    </span>
                  )}
                </div>
                <h3>{set.name}</h3>
                <p>{set.description}</p>
                <div className="set-progress">
                  <span>{set.entry_count} từ</span>
                  <span>{set.added_count}/{set.entry_count} đã thêm</span>
                </div>
                <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
                <Link className="primary-link" to={`/app/learn/sets/${set.id}`}>
                  {set.import_status === "none" ? "Bắt đầu học" : "Tiếp tục"} <ArrowRight size={16} />
                </Link>
              </article>;
            })}
          </div>
        ) : (
          <div className="list-state">
            <PenguinMark size={68} />
            <h2>Chưa có bộ demo cho {level}</h2>
            <p>Dữ liệu seed hiện chỉ mang tính đại diện và sẽ được mở rộng bằng nội dung được biên tập.</p>
          </div>
        )}
      </section>
    </section>
  );
}
