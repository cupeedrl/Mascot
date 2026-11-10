import assert from "node:assert/strict";
import test from "node:test";

import {
  formatRawPos,
  formatSavedPos,
  formatSensePos,
  formatSourceLevels,
  HSK_BROWSE_LEVELS,
  levelLabel,
  levelTabTone,
  partLabel,
  topicHref,
  topicLabel,
  OFFICIAL_POS_MISSING_LABEL,
  POS_MISSING_LABEL,
  releaseNotice,
  reviewStatusLabel,
} from "../src/features/hsk/hskPresentation.ts";

test("browse levels cover HSK 1-6 and the combined 7-9 band", () => {
  assert.deepEqual([...HSK_BROWSE_LEVELS], ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7-9"]);
  assert.equal(levelLabel("HSK7-9"), "HSK 7–9");
  assert.equal(levelLabel("HSK3"), "HSK 3");
});

test("large topics show their part and link to it", () => {
  assert.equal(partLabel(3, 21), "Phần 3/21");
  assert.equal(partLabel(null, 1), "");
  assert.equal(topicHref("t1", 2), "/app/learn/hsk/topics/t1?part=2");
  assert.equal(topicHref("t1", null), "/app/learn/hsk/topics/t1");
});

test("HSK level tabs reuse the English colour ramp", () => {
  assert.deepEqual(HSK_BROWSE_LEVELS.map(levelTabTone), ["a1", "a2", "b1", "b2", "c1", "c2", "c2"]);
});

test("every official HSK topic has its own icon and colour", async () => {
  const { HSK_TOPIC_NAMES_WITH_VISUALS, getTopicAccent, getTopicVisual } = await import(
    "../src/features/learn/topicPresentation.ts"
  );
  assert.ok(HSK_TOPIC_NAMES_WITH_VISUALS.length >= 82);
  for (const name of HSK_TOPIC_NAMES_WITH_VISUALS) {
    assert.notEqual(getTopicVisual(name).key, "other", name);
    assert.notEqual(getTopicAccent(name), "neutral", name);
  }
  assert.equal(getTopicVisual("饮食").key, "food");
  assert.equal(getTopicVisual("交通出行").key, "travel");
});

test("topic labels show Vietnamese with the official Chinese name", () => {
  assert.equal(topicLabel({ name_zh: "饮食", name_vi: "Ăn uống" }), "Ăn uống (饮食)");
  assert.equal(topicLabel({ name_zh: "饮食", name_vi: null }), "饮食");
});

test("missing POS is labelled as missing, never guessed", () => {
  assert.equal(formatSensePos([]), POS_MISSING_LABEL);
  assert.equal(formatRawPos(null), OFFICIAL_POS_MISSING_LABEL);
  assert.equal(formatRawPos("  "), OFFICIAL_POS_MISSING_LABEL);
  assert.equal(formatSavedPos("unspecified"), POS_MISSING_LABEL);
});

test("multiple POS annotations keep their origin", () => {
  assert.equal(
    formatSensePos([
      { code: "verb", origin: "official_source", source_label: "动" },
      { code: "noun", origin: "editorial", source_label: null },
    ]),
    "Động từ · Danh từ (biên tập)",
  );
  assert.equal(formatRawPos("动、名"), "动、名");
  assert.equal(formatSavedPos("adjective, verb"), "Tính từ · Động từ");
});

test("source levels show primary and annotation levels", () => {
  assert.equal(
    formatSourceLevels([
      { level_code: "HSK2", role: "primary" },
      { level_code: "HSK4", role: "annotation" },
      { level_code: "HSK7-9", role: "annotation" },
    ]),
    "HSK 2 (ghi chú: HSK 4, HSK 7–9)",
  );
});

test("review state and release notices are explicit", () => {
  assert.equal(reviewStatusLabel("pending"), "Đang chờ biên tập");
  assert.equal(reviewStatusLabel("ambiguous"), "Cần xem xét (mơ hồ)");
  assert.match(releaseNotice(null) ?? "", /Chưa có bản phát hành/);
  assert.match(releaseNotice({ data_origin: "synthetic_fixture", status: "published" }) ?? "", /không phải/);
  assert.match(releaseNotice({ data_origin: "third_party", status: "draft" }) ?? "", /xem trước/);
  assert.equal(releaseNotice({ data_origin: "third_party", status: "published" }), null);
});

test("saved words without POS display a readable label", async () => {
  const { displayPartOfSpeech } = await import("../src/features/vocabulary/partsOfSpeech.ts");
  assert.equal(displayPartOfSpeech("unspecified"), "Chưa có từ loại");
  assert.equal(displayPartOfSpeech("noun"), "noun");
});
