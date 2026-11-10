import { type FormEvent, useEffect, useState } from "react";
import { ArrowLeft, BookmarkCheck, BookmarkPlus, Search } from "lucide-react";
import { Link } from "react-router-dom";

import {
  ApiError,
  getHskEntry,
  getHskLevels,
  listHskEntries,
  saveHskSense,
  type HskEntryDetail,
  type HskEntryListResponse,
  type HskLevelsResponse,
} from "../api/client";
import { PageSkeleton } from "../components/PageSkeleton";
import {
  formatRawPos,
  formatSensePos,
  formatSourceLevels,
  HSK_BROWSE_LEVELS,
  levelLabel,
  releaseNotice,
  reviewStatusLabel,
} from "../features/hsk/hskPresentation";
import { useActiveLearningTrack } from "../learning/ActiveLearningTrackContext";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể tải danh mục HSK.";
}

export function HskCatalogPage() {
  const { activeTrack } = useActiveLearningTrack();
  const trackId = activeTrack?.level_framework === "HSK" ? activeTrack.id : null;
  const [levels, setLevels] = useState<HskLevelsResponse | null>(null);
  const [level, setLevel] = useState<string>("HSK1");
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [entries, setEntries] = useState<HskEntryListResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<HskEntryDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [savingMapping, setSavingMapping] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!trackId) return;
    getHskLevels(trackId).then(setLevels).catch((caught: unknown) => setError(errorMessage(caught)));
  }, [trackId]);

  useEffect(() => {
    if (!trackId) return;
    let active = true;
    setIsLoading(true);
    listHskEntries(trackId, { level: query ? undefined : level, q: query, page })
      .then((response) => active && setEntries(response))
      .catch((caught: unknown) => active && setError(errorMessage(caught)))
      .finally(() => active && setIsLoading(false));
    return () => {
      active = false;
    };
  }, [trackId, level, query, page]);

  async function loadDetail(entryId: string) {
    if (!trackId) return;
    setSelectedId(entryId);
    setNotice("");
    try {
      setDetail(await getHskEntry(trackId, entryId));
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  async function saveSense(mappingId: string) {
    if (!trackId || !detail) return;
    setSavingMapping(mappingId);
    setError("");
    try {
      const result = await saveHskSense(trackId, detail.source.id, mappingId);
      setNotice(
        result.created
          ? "Đã lưu nghĩa này vào Từ vựng của tôi."
          : result.reason === "overlapping_personal_word"
            ? "Bạn đã có một từ trùng nghĩa trong Từ vựng của tôi."
            : "Nghĩa này đã có trong Từ vựng của tôi.",
      );
      await loadDetail(detail.source.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSavingMapping(null);
    }
  }

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setQuery(queryDraft.trim());
  }

  if (!trackId) {
    return (
      <section className="learn-page">
        <Link className="back-link" to="/app/learn"><ArrowLeft size={17} /> Quay lại Học từ vựng</Link>
        <div className="list-state"><h2>Hãy chọn lộ trình tiếng Trung (HSK) để xem danh mục HSK 1–6.</h2></div>
      </section>
    );
  }

  const releaseWarning = releaseNotice(levels?.release ?? null);
  const levelCounts = new Map(levels?.levels.map((item) => [item.level_code, item]) ?? []);

  return (
    <section className="learn-page hsk-catalog-page" aria-labelledby="hsk-heading">
      <Link className="back-link" to="/app/learn"><ArrowLeft size={17} /> Quay lại Học từ vựng</Link>
      <div className="set-detail-heading">
        <div>
          <p className="eyebrow">{activeTrack?.name} · {levels?.release?.title ?? "Chưa có bản phát hành"}</p>
          <h1 id="hsk-heading">Danh mục từ vựng HSK 1–6</h1>
          {releaseWarning && <p className="hsk-release-warning" role="note">{releaseWarning}</p>}
        </div>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {notice && <div className="success-banner" role="status">{notice}</div>}

      <div className="level-tabs" role="tablist" aria-label="Cấp độ HSK">
        {HSK_BROWSE_LEVELS.map((code) => (
          <button
            key={code}
            type="button"
            role="tab"
            aria-selected={!query && code === level}
            className={`level-tab${!query && code === level ? " active" : ""}`}
            onClick={() => {
              setLevel(code);
              setQuery("");
              setQueryDraft("");
              setPage(1);
            }}
          >
            <strong>{levelLabel(code)}</strong>
            <small>{levelCounts.get(code)?.entry_count ?? 0} từ</small>
          </button>
        ))}
      </div>

      <form className="topic-search" onSubmit={applySearch}>
        <Search size={17} aria-hidden="true" />
        <input
          value={queryDraft}
          onChange={(event) => setQueryDraft(event.target.value)}
          placeholder="Tìm chữ Hán, pinyin (không dấu) hoặc nghĩa"
          aria-label="Tìm trong danh mục HSK"
        />
        <button className="secondary-button" type="submit">Tìm</button>
      </form>

      <div className="hsk-layout">
        <div className="entry-list hsk-entry-list">
          {isLoading && !entries ? (
            <PageSkeleton cards={3} />
          ) : entries?.items.length ? (
            entries.items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`entry-row hsk-entry-row${item.id === selectedId ? " selected" : ""}`}
                onClick={() => void loadDetail(item.id)}
              >
                <div className="entry-word">
                  <strong>{item.raw_word}</strong>
                  <small className="entry-ipa">Pinyin: {item.raw_pinyin}</small>
                  <span>{formatRawPos(item.raw_pos)}</span>
                </div>
                <div className="entry-definition">
                  <small>{levelLabel(item.level_code)} · {reviewStatusLabel(item.review_status)}</small>
                  <small>{item.sense_count} nghĩa đã biên tập{item.saved_count ? ` · đã lưu ${item.saved_count}` : ""}</small>
                </div>
              </button>
            ))
          ) : (
            <div className="list-state"><p>{levels?.release ? "Không có từ phù hợp." : releaseWarning}</p></div>
          )}
          {entries && entries.total_pages > 1 && (
            <div className="selection-toolbar">
              <button className="secondary-button" type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trước</button>
              <span>Trang {entries.page}/{entries.total_pages}</span>
              <button className="secondary-button" type="button" disabled={page >= entries.total_pages} onClick={() => setPage(page + 1)}>Sau</button>
            </div>
          )}
        </div>

        <aside className="hsk-detail" aria-live="polite">
          {detail ? (
            <>
              <h2 className="hsk-headword">{detail.source.raw_word}</h2>
              <dl className="hsk-source-fields">
                <div><dt>Pinyin (nguồn)</dt><dd>{detail.source.raw_pinyin}</dd></div>
                <div><dt>Từ loại (nguồn)</dt><dd>{formatRawPos(detail.source.raw_pos)}</dd></div>
                <div><dt>Cấp độ</dt><dd>{formatSourceLevels(detail.source.levels)}</dd></div>
                <div><dt>Mã bản ghi / số thứ tự</dt><dd>{detail.source.record_id} / {detail.source.official_serial ?? "không có"}</dd></div>
                <div><dt>Trạng thái</dt><dd>{reviewStatusLabel(detail.source.review_status)}</dd></div>
              </dl>
              {!detail.interpretations.length && (
                <p className="hsk-awaiting">Mục này đang chờ biên tập: chưa có cách đọc/nghĩa được duyệt.</p>
              )}
              {detail.interpretations.map((interpretation) => (
                <section className="hsk-interpretation" key={interpretation.lexical_entry_id}>
                  <h3>
                    {interpretation.headword}
                    {interpretation.pronunciations.length > 0 && <small> · {interpretation.pronunciations.join(" / ")}</small>}
                  </h3>
                  {interpretation.variants.length > 0 && (
                    <p className="hsk-variants">
                      Biến thể: {interpretation.variants.map((variant) => `${variant.form} (${variant.type === "traditional" ? "phồn thể" : variant.type})`).join(", ")}
                    </p>
                  )}
                  {interpretation.awaiting_sense_review && !interpretation.senses.length && (
                    <p className="hsk-awaiting">Nghĩa đang chờ biên tập.</p>
                  )}
                  <ol className="hsk-senses">
                    {interpretation.senses.map((sense) => (
                      <li key={sense.mapping_id}>
                        <div className="hsk-sense-head">
                          {sense.pronunciations.length > 0 && <strong>{sense.pronunciations.join(" / ")}</strong>}
                          <span className={sense.pos_missing ? "hsk-pos missing" : "hsk-pos"}>{formatSensePos(sense.pos)}</span>
                        </div>
                        {sense.gloss_vi && <p>{sense.gloss_vi}</p>}
                        {sense.gloss_en && <p className="hsk-gloss-en">{sense.gloss_en}</p>}
                        {sense.examples.map((example) => (
                          <small key={example.text_zh}>{example.text_zh}{example.translation_vi ? ` — ${example.translation_vi}` : ""}</small>
                        ))}
                        {sense.saved_vocabulary_id ? (
                          <span className="library-status all"><BookmarkCheck size={15} /> Đã lưu</span>
                        ) : (
                          <button
                            className="primary-button compact-button"
                            type="button"
                            disabled={!sense.saveable || savingMapping === sense.mapping_id}
                            onClick={() => void saveSense(sense.mapping_id)}
                          >
                            <BookmarkPlus size={15} /> {sense.saveable ? "Lưu nghĩa này" : "Chưa thể lưu"}
                          </button>
                        )}
                      </li>
                    ))}
                  </ol>
                </section>
              ))}
            </>
          ) : (
            <p className="hsk-detail-empty">Chọn một từ để xem cách đọc, nghĩa và từ loại.</p>
          )}
        </aside>
      </div>
    </section>
  );
}
