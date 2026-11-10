import { type FormEvent, useEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { Link } from "react-router-dom";

import { ApiError, getHskLevels, type HskLevelsResponse } from "../../api/client";
import { PageSkeleton } from "../../components/PageSkeleton";
import { PenguinMark } from "../../components/PenguinMark";
import { getTopicAccent, getTopicIcon } from "../learn/topicPresentation";
import { TopicName } from "./TopicName";
import { levelLabel, levelTabTone, partLabel, releaseNotice, topicHref } from "./hskPresentation";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể tải thư viện từ vựng.";
}

/** HSK steps 1–2 of the Learn page, with the same layout as the English library. */
export function HskLearnBrowser({ trackId }: { trackId: string }) {
  const [data, setData] = useState<HskLevelsResponse | null>(null);
  const [level, setLevel] = useState("HSK1");
  const [topicDraft, setTopicDraft] = useState("");
  const [topic, setTopic] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    getHskLevels(trackId)
      .then((response) => active && setData(response))
      .catch((caught: unknown) => active && setError(errorMessage(caught)));
    return () => {
      active = false;
    };
  }, [trackId]);

  function applyTopic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTopic(topicDraft.trim());
  }

  const current = data?.levels.find((item) => item.level_code === level) ?? data?.levels[0];
  const filter = topic.toLocaleLowerCase();
  const cards = (current?.topic_groups ?? [])
    .flatMap((group) => group.topics)
    // Like English sets, only topics that actually contain words are shown.
    .filter((card) => card.entry_count > 0)
    .filter((card) => !filter || `${card.name_vi ?? ""} ${card.name_zh}`.toLocaleLowerCase().includes(filter));
  const notice = data ? releaseNotice(data.release) : null;

  return (
    <>
      <section className="level-section" aria-labelledby="level-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Bước 1</p>
            <h2 id="level-heading">Chọn trình độ HSK</h2>
          </div>
        </div>
        <div className="level-tabs level-tabs-hsk" role="tablist" aria-label="Trình độ HSK">
          {(data?.levels ?? []).map((item) => (
            <button
              key={item.level_code}
              className={`level-tab level-tab-${levelTabTone(item.level_code)}${item.level_code === current?.level_code ? " active" : ""}`}
              type="button"
              role="tab"
              aria-selected={item.level_code === current?.level_code}
              onClick={() => {
                setLevel(item.level_code);
                setTopic("");
                setTopicDraft("");
              }}
            >
              <strong>{levelLabel(item.level_code)}</strong><small>{item.entry_count} từ</small>
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
        {!data && !error ? (
          <PageSkeleton cards={3} />
        ) : cards.length ? (
          <div className="set-grid">
            {cards.map((card) => {
              const TopicIcon = getTopicIcon(card.name_zh);
              const accent = getTopicAccent(card.name_zh);
              const progress = card.entry_count ? Math.round((card.saved_count / card.entry_count) * 100) : 0;
              const status = card.saved_count === 0 ? "none" : card.saved_count >= card.entry_count ? "all" : "partial";
              const part = partLabel(card.part, card.part_count);
              return <article className={`set-card topic-accent-${accent}`} key={`${card.id}-${card.part ?? 0}`}>
                <div className="set-card-topline">
                  <span className="topic-visual" aria-hidden="true"><TopicIcon size={22} /></span>
                  <span className="level-badge">{levelLabel(current?.level_code ?? level)}</span>
                  {status !== "none" && (
                    <span className={`library-status ${status}`}>
                      {status === "all" ? "Đã thêm toàn bộ" : "Đã thêm một phần"}
                    </span>
                  )}
                </div>
                <h3><TopicName topic={card} />{part && <span className="topic-part"> · {part}</span>}</h3>
                <p>{card.subtopics.join(" · ")}</p>
                <div className="set-progress">
                  <span>{card.entry_count} từ</span>
                  <span>{card.saved_count}/{card.entry_count} đã thêm</span>
                </div>
                <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
                <Link className="primary-link" to={topicHref(card.id, card.part)}>
                  {status === "none" ? "Bắt đầu học" : "Tiếp tục"} <ArrowRight size={16} />
                </Link>
              </article>;
            })}
          </div>
        ) : (
          <div className="list-state">
            <PenguinMark size={68} />
            <h2>Chưa có bộ từ cho {levelLabel(current?.level_code ?? level)}</h2>
            <p>{notice ?? "Cấp độ này chưa được nạp dữ liệu theo chủ đề."}</p>
          </div>
        )}
      </section>
    </>
  );
}
