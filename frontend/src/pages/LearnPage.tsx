import { type FormEvent, useEffect, useState } from "react";
import { ArrowRight, BookOpen, Compass, Search } from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  listVocabularySets,
  type CefrLevel,
  type VocabularySetListResponse,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";

const LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

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
        <div>
          <div className="hero-icon"><Compass size={22} /></div>
          <p className="eyebrow">MASCOT VOCABULARY LIBRARY</p>
          <h1 id="learn-heading">Explore English your way.</h1>
          <p>Chọn trình độ, khám phá chủ đề phù hợp và bắt đầu xây dựng vốn từ của riêng bạn.</p>
        </div>
        <dl className="track-card">
          <div><dt>Ngôn ngữ</dt><dd>English</dd></div>
          <div><dt>Learning track</dt><dd>General English</dd></div>
          <div><dt>Framework</dt><dd>CEFR</dd></div>
        </dl>
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
              {item}
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
            {result.items.map((set) => (
              <article className="set-card" key={set.id}>
                <div className="set-card-topline">
                  <span className="topic-visual" aria-hidden="true"><BookOpen size={21} /></span>
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
                <Link className="primary-link" to={`/app/learn/sets/${set.id}`}>
                  {set.import_status === "none" ? "Start topic" : "Continue"} <ArrowRight size={16} />
                </Link>
              </article>
            ))}
          </div>
        ) : (
          <div className="list-state">
            <h2>Chưa có bộ demo cho {level}</h2>
            <p>Dữ liệu seed hiện chỉ mang tính đại diện và sẽ được mở rộng bằng nội dung được biên tập.</p>
          </div>
        )}
      </section>
    </section>
  );
}
