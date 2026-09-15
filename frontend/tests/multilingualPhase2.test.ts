import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  generateAIVocabulary,
  getDashboard,
  getDueVocabularies,
  listVocabularySets,
  listVocabularies,
  postAIChat,
  type LearningTrack,
} from "../src/api/client.ts";
import {
  pronunciationLabel,
  selectInitialTrack,
} from "../src/learning/trackMetadata.ts";

const english: LearningTrack = {
  id: "english-track",
  code: "general-english",
  name: "General English",
  description: null,
  level_framework: "CEFR",
  level_codes: ["A1", "A2", "B1", "B2", "C1", "C2"],
  language: { id: "en", code: "en", name: "English", native_name: "English" },
};
const chinese: LearningTrack = {
  id: "chinese-track",
  code: "general-chinese",
  name: "General Chinese",
  description: null,
  level_framework: "HSK",
  level_codes: Array.from({ length: 9 }, (_, index) => `HSK${index + 1}`),
  language: { id: "zh", code: "zh", name: "Chinese", native_name: "中文" },
};

test("active track prefers persisted selection and defaults to English", () => {
  assert.equal(selectInitialTrack([chinese, english], "chinese-track")?.id, "chinese-track");
  assert.equal(selectInitialTrack([chinese, english], "missing")?.id, "english-track");
});

test("level selectors and pronunciation labels are metadata driven", () => {
  assert.deepEqual(english.level_codes, ["A1", "A2", "B1", "B2", "C1", "C2"]);
  assert.deepEqual(chinese.level_codes, ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7", "HSK8", "HSK9"]);
  assert.equal(pronunciationLabel(english), "IPA");
  assert.equal(pronunciationLabel(chinese), "Pinyin");
});

test("learner API requests carry the active Chinese track", async () => {
  const requests: Array<{ url: string; body?: string }> = [];
  Object.assign(globalThis, {
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: String(input), body: init?.body ? String(init.body) : undefined });
      return new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0, limit: 20, recently_added_vocabulary: [], message: { role: "assistant", content: "ok" }, confirmation_required: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });

  await listVocabularies({ page: 1, pageSize: 10, learningTrackId: chinese.id });
  await getDueVocabularies(20, chinese.id);
  await getDashboard(chinese.id);
  await listVocabularySets({ language: "zh", learningTrack: chinese.id, level: "HSK1" });
  await generateAIVocabulary({ word: "学习", part_of_speech: "verb", translation: "học tập", learning_track_id: chinese.id });
  await postAIChat([{ role: "user", content: "Tôi cần ôn từ nào?" }], chinese.id);

  assert.ok(requests[0].url.includes("learning_track_id=chinese-track"));
  assert.ok(requests[1].url.includes("learning_track_id=chinese-track"));
  assert.ok(requests[2].url.includes("learning_track_id=chinese-track"));
  assert.ok(requests[3].url.includes("language=zh"));
  assert.ok(requests[3].url.includes("learning_track=chinese-track"));
  assert.equal(JSON.parse(requests[4].body ?? "{}").learning_track_id, chinese.id);
  assert.equal(JSON.parse(requests[5].body ?? "{}").learning_track_id, chinese.id);
});

test("active track preference is shared across routed learning pages", async () => {
  const [appSource, contextSource] = await Promise.all([
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/learning/ActiveLearningTrackContext.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(appSource, /<ActiveLearningTrackProvider>/);
  assert.match(contextSource, /localStorage\.getItem\(STORAGE_KEY\)/);
  assert.match(contextSource, /localStorage\.setItem\(STORAGE_KEY, trackId\)/);
});

test("learning and vocabulary views use track metadata and language-aware pronunciation", async () => {
  const [learnSource, vocabularySource, setSource] = await Promise.all([
    readFile(new URL("../src/pages/LearnPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/pages/VocabularyPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/pages/VocabularySetPage.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(learnSource, /activeTrack\?\.level_codes\.map/);
  assert.match(vocabularySource, /language\.code === "zh" \? "Pinyin" : "IPA"/);
  assert.match(setSource, /language\.code === "zh" \? "Pinyin" : "IPA"/);
});
