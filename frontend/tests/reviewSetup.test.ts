import assert from "node:assert/strict";
import test from "node:test";

import {
  filterEligibleVocabularies,
  RECENT_REVIEW_LIMIT,
} from "../src/features/review/reviewSetup.ts";
import type { Vocabulary } from "../src/api/client.ts";

const mockVocabularies: Vocabulary[] = [
  {
    id: "1",
    user_id: "u1",
    learning_track_id: "t1",
    source_vocabulary_entry_id: null,
    word: "abundant",
    ipa: "/əˈbʌn.dənt/",
    part_of_speech: "adjective",
    meaning: "Existing or available in large quantities; plentiful.",
    translation: "dồi dào, phong phú",
    translation_language_code: "vi",
    example_sentences: ["There is abundant evidence to support this claim."],
    level_code: "B2",
    topic: "Nature",
    learning_status: "new",
    review_count: 0,
    correct_count: 0,
    incorrect_count: 0,
    last_reviewed_at: null,
    next_review_at: null,
    created_at: "2026-08-19T00:00:00Z",
    updated_at: "2026-08-19T00:00:00Z",
    learning_track: { id: "t1", code: "general-english", name: "General English" },
  },
  {
    id: "2",
    user_id: "u1",
    learning_track_id: "t1",
    source_vocabulary_entry_id: null,
    word: "diligent",
    ipa: "/ˈdɪl.ɪ.dʒənt/",
    part_of_speech: "adjective",
    meaning: "Having or showing care and conscientiousness in one's work.",
    translation: "chăm chỉ, cần cù",
    translation_language_code: "vi",
    example_sentences: ["She is a diligent student."],
    level_code: "C1",
    topic: "Work",
    learning_status: "learning",
    review_count: 2,
    correct_count: 2,
    incorrect_count: 0,
    last_reviewed_at: "2026-08-18T00:00:00Z",
    next_review_at: "2026-08-21T00:00:00Z",
    created_at: "2026-08-18T00:00:00Z",
    updated_at: "2026-08-18T00:00:00Z",
    learning_track: { id: "t1", code: "general-english", name: "General English" },
  },
  {
    id: "3",
    user_id: "u1",
    learning_track_id: "t1",
    source_vocabulary_entry_id: null,
    word: "wander",
    ipa: "/ˈwɒn.dər/",
    part_of_speech: "verb",
    meaning: "Walk or move in a leisurely, casual, or aimless way.",
    translation: "đi lang thang",
    translation_language_code: "vi",
    example_sentences: ["He loved to wander through the city streets."],
    level_code: "A2",
    topic: null,
    learning_status: "new",
    review_count: 0,
    correct_count: 0,
    incorrect_count: 0,
    last_reviewed_at: null,
    next_review_at: null,
    created_at: "2026-08-17T00:00:00Z",
    updated_at: "2026-08-17T00:00:00Z",
    learning_track: { id: "t1", code: "general-english", name: "General English" },
  },
];

test("recent review limit is 20", () => {
  assert.equal(RECENT_REVIEW_LIMIT, 20);
});

test("filterEligibleVocabularies filters by search term", () => {
  const filtered = filterEligibleVocabularies(mockVocabularies, { search: "chăm chỉ" });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].word, "diligent");
});

test("filterEligibleVocabularies filters by CEFR level", () => {
  const filtered = filterEligibleVocabularies(mockVocabularies, { level: "B2" });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].word, "abundant");
});

test("filterEligibleVocabularies filters by topic including Khác fallback", () => {
  const nature = filterEligibleVocabularies(mockVocabularies, { topic: "Nature" });
  assert.equal(nature.length, 1);
  assert.equal(nature[0].word, "abundant");

  const khac = filterEligibleVocabularies(mockVocabularies, { topic: "Khác" });
  assert.equal(khac.length, 1);
  assert.equal(khac[0].word, "wander");
});
