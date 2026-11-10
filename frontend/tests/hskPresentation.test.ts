import assert from "node:assert/strict";
import test from "node:test";

import {
  formatRawPos,
  formatSavedPos,
  formatSensePos,
  formatSourceLevels,
  HSK_BROWSE_LEVELS,
  OFFICIAL_POS_MISSING_LABEL,
  POS_MISSING_LABEL,
  releaseNotice,
  reviewStatusLabel,
} from "../src/features/hsk/hskPresentation.ts";

test("browse levels cover HSK 1 through 6", () => {
  assert.deepEqual([...HSK_BROWSE_LEVELS], ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"]);
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
