import assert from "node:assert/strict";
import test from "node:test";

import {
  getExistingVocabularyId,
  getVocabularyEditRoute,
} from "../src/features/vocabulary/duplicateConflict.ts";

const EXISTING_ID = "16b7e9e1-3c9f-4fc7-a9b1-4d8a9b741704";

test("duplicate conflict stores a valid existing vocabulary ID", () => {
  assert.equal(
    getExistingVocabularyId({ existing_vocabulary_id: EXISTING_ID }),
    EXISTING_ID,
  );
});

test("duplicate action uses the existing vocabulary edit route", () => {
  assert.equal(
    getVocabularyEditRoute(EXISTING_ID),
    `/app/vocabulary/${EXISTING_ID}/edit`,
  );
});

test("duplicate action is unavailable when the ID is missing or invalid", () => {
  assert.equal(getExistingVocabularyId(undefined), null);
  assert.equal(getExistingVocabularyId({}), null);
  assert.equal(
    getExistingVocabularyId({ existing_vocabulary_id: "not-a-valid-id" }),
    null,
  );
});
