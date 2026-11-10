// Display helpers for the normalized HSK catalog. They never invent values:
// missing POS, unreviewed meanings and draft releases are labelled as such.

export const HSK_BROWSE_LEVELS = ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"] as const;

const POS_LABELS: Record<string, string> = {
  noun: "Danh từ",
  verb: "Động từ",
  adjective: "Tính từ",
  adverb: "Phó từ",
  pronoun: "Đại từ",
  numeral: "Số từ",
  measure_word: "Lượng từ",
  numeral_measure: "Số lượng từ",
  preposition: "Giới từ",
  conjunction: "Liên từ",
  particle: "Trợ từ",
  interjection: "Thán từ",
  onomatopoeia: "Từ tượng thanh",
  prefix: "Tiền tố",
  suffix: "Hậu tố",
  phrase: "Cụm từ",
  idiom: "Thành ngữ",
};

export const POS_MISSING_LABEL = "Chưa có từ loại";
export const OFFICIAL_POS_MISSING_LABEL = "Nguồn không ghi từ loại";

export interface PosAnnotation {
  code: string;
  origin: string;
  source_label: string | null;
}

export function posLabel(code: string): string {
  return POS_LABELS[code] ?? code;
}

/** Sense-level POS, or an explicit "missing" label — never a guessed value. */
export function formatSensePos(pos: PosAnnotation[]): string {
  if (!pos.length) return POS_MISSING_LABEL;
  return pos
    .map((item) => `${posLabel(item.code)}${item.origin === "editorial" ? " (biên tập)" : ""}`)
    .join(" · ");
}

/** Official raw POS from the source record, shown verbatim. */
export function formatRawPos(rawPos: string | null): string {
  return rawPos && rawPos.trim() ? rawPos : OFFICIAL_POS_MISSING_LABEL;
}

/** Personal vocabulary stores "unspecified" when the catalog had no POS. */
export function formatSavedPos(partOfSpeech: string): string {
  if (partOfSpeech === "unspecified") return POS_MISSING_LABEL;
  return partOfSpeech
    .split(",")
    .map((code) => posLabel(code.trim()))
    .join(" · ");
}

export function levelLabel(levelCode: string): string {
  return levelCode === "HSK7-9" ? "HSK 7–9" : levelCode.replace(/^HSK/, "HSK ");
}

export interface SourceLevel {
  level_code: string;
  role: "primary" | "annotation";
}

export function formatSourceLevels(levels: SourceLevel[]): string {
  const primary = levels.find((level) => level.role === "primary");
  const annotations = levels.filter((level) => level.role === "annotation");
  const head = primary ? levelLabel(primary.level_code) : "Không rõ cấp";
  return annotations.length
    ? `${head} (ghi chú: ${annotations.map((level) => levelLabel(level.level_code)).join(", ")})`
    : head;
}

export function reviewStatusLabel(status: string): string {
  switch (status) {
    case "accepted":
      return "Đã biên tập";
    case "ambiguous":
      return "Cần xem xét (mơ hồ)";
    case "retired":
      return "Đã ngừng sử dụng";
    default:
      return "Đang chờ biên tập";
  }
}

export function releaseNotice(release: { data_origin: string; status: string } | null): string | null {
  if (!release) return "Chưa có bản phát hành HSK nào được công bố.";
  if (release.status !== "published") return "Bản xem trước nội bộ — chưa công bố.";
  if (release.data_origin === "synthetic_fixture") {
    return "Dữ liệu thử nghiệm tổng hợp — không phải danh mục HSK chính thức.";
  }
  return null;
}
