import assert from "node:assert/strict";
import test from "node:test";
import { BookOpen, BriefcaseBusiness, Leaf, Plane, School, Users } from "lucide-react";

import { getTopicAccent, getTopicIcon, getTopicVisual } from "../src/features/learn/topicPresentation.ts";

test("topic presentation maps catalog topics to their matching Lucide icons", () => {
  assert.equal(getTopicIcon("Travel"), Plane);
  assert.equal(getTopicIcon("School"), School);
  assert.equal(getTopicIcon("Family"), Users);
  assert.equal(getTopicIcon("Work & Business"), BriefcaseBusiness);
  assert.equal(getTopicIcon("Unknown topic"), BookOpen);
});

test("topic presentation assigns deterministic semantic tones", () => {
  assert.equal(getTopicAccent("Family"), "teal");
  assert.equal(getTopicAccent("School"), "academic");
  assert.equal(getTopicAccent("Food & Drink"), "coral");
  assert.equal(getTopicAccent("Unknown topic"), "neutral");
});

test("multilingual aliases share one canonical topic visual", () => {
  for (const alias of ["Environment", "Môi trường", "环境"]) {
    assert.equal(getTopicVisual(alias).key, "environment");
    assert.equal(getTopicIcon(alias), Leaf);
    assert.equal(getTopicAccent(alias), "green");
  }
  assert.equal(getTopicVisual("Gia đình").key, getTopicVisual("家庭").key);
});

test("unknown topics use the neutral fallback visual", () => {
  const fallback = getTopicVisual("A future catalog topic");
  assert.equal(fallback.key, "other");
  assert.equal(fallback.icon, BookOpen);
  assert.equal(fallback.tone, "neutral");
});
