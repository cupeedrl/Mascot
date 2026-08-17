import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_QUESTION_COUNT,
  generationCount,
  isQuestionCountDraft,
  parseQuestionCount,
  questionCountError,
} from "../src/features/exercises/practiceSetup.ts";

test("question count defaults to five", () => {
  assert.equal(DEFAULT_QUESTION_COUNT, 5);
});

test("question count accepts the 1 to 15 boundaries", () => {
  assert.equal(parseQuestionCount("1"), 1);
  assert.equal(parseQuestionCount("15"), 15);
});

test("question count rejects values outside 1 to 15", () => {
  assert.equal(parseQuestionCount("0"), null);
  assert.equal(parseQuestionCount("16"), null);
  assert.match(questionCountError("0") ?? "", /1.*15/);
  assert.match(questionCountError("16") ?? "", /1.*15/);
});

test("question count draft can be temporarily blank", () => {
  assert.equal(isQuestionCountDraft(""), true);
  assert.equal(parseQuestionCount(""), null);
  assert.equal(isQuestionCountDraft("10"), true);
  assert.equal(isQuestionCountDraft("1.5"), false);
});

test("fill in the blank normalizes count to one passage", () => {
  assert.equal(generationCount("fill_in_blank", 15), 1);
  assert.equal(generationCount("multiple_choice", 15), 15);
});
