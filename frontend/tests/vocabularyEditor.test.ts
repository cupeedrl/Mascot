import assert from "node:assert/strict";
import test from "node:test";

import { PARTS_OF_SPEECH } from "../src/features/vocabulary/partsOfSpeech.ts";

test("parts of speech options include required grammatical categories", () => {
  const values = PARTS_OF_SPEECH.map((item) => item.value);
  assert.ok(values.includes("noun"));
  assert.ok(values.includes("verb"));
  assert.ok(values.includes("adjective"));
  assert.ok(values.includes("adverb"));
  assert.ok(values.includes("pronoun"));
  assert.ok(values.includes("preposition"));
  assert.ok(values.includes("conjunction"));
  assert.ok(values.includes("determiner"));
  assert.ok(values.includes("interjection"));
  assert.ok(values.includes("phrasal verb"));
  assert.ok(values.includes("phrase"));
  assert.ok(values.includes("other"));
});

test("parts of speech options display bilingual labels", () => {
  const noun = PARTS_OF_SPEECH.find((item) => item.value === "noun");
  assert.ok(noun?.label.includes("Danh từ"));
  assert.ok(noun?.label.includes("noun"));
});
