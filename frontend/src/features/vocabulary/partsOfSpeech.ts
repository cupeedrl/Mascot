export interface PartOfSpeechOption {
  value: string;
  label: string;
}

/** Saved catalog words without an official POS store "unspecified". */
export function displayPartOfSpeech(value: string): string {
  return value === "unspecified" ? "Chưa có từ loại" : value;
}

export const PARTS_OF_SPEECH: PartOfSpeechOption[] = [
  { value: "noun", label: "Danh từ (noun)" },
  { value: "verb", label: "Động từ (verb)" },
  { value: "adjective", label: "Tính từ (adjective)" },
  { value: "adverb", label: "Trạng từ (adverb)" },
  { value: "pronoun", label: "Đại từ (pronoun)" },
  { value: "preposition", label: "Giới từ (preposition)" },
  { value: "conjunction", label: "Liên từ (conjunction)" },
  { value: "determiner", label: "Từ hạn định (determiner)" },
  { value: "interjection", label: "Thán từ (interjection)" },
  { value: "phrasal verb", label: "Cụm động từ (phrasal verb)" },
  { value: "phrase", label: "Cụm từ (phrase)" },
  { value: "other", label: "Khác (other)" },
];
